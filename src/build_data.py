"""Reproducible, account-grain ingestion. Never imputes from the full dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEYS = {
    "customers": ["customer_id"], "loan_accounts": ["account_id"],
    "bureau_credit": ["bureau_id"], "repayment_history": ["account_id", "payment_month"],
    "collections_events": ["collection_event_id"],
}
DATES = {
    "customers": ["customer_since"], "loan_accounts": ["origination_date"],
    "bureau_credit": ["date_opened", "date_closed"], "collections_events": ["event_date"],
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.where(denominator > 0)


def validate_links(child: pd.DataFrame, parent: pd.DataFrame, key: str) -> None:
    require(child[key].isin(parent[key]).all(), f"Unmatched foreign key: {key}")


def build(raw: Path, output: Path, reports: Path) -> dict:
    tables, audit = {}, {"sources": {}, "checks": {}, "timing": {}}
    for name, keys in KEYS.items():
        path = raw / f"{name}.csv"
        frame = pd.read_csv(path)
        audit["sources"][name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": len(frame), "missing": frame.isna().sum().astype(int).to_dict(),
            "exact_duplicates": int(frame.duplicated().sum()),
        }
        require(not frame[keys].isna().any().any(), f"Missing key in {name}")
        require(not frame.duplicated(keys).any(), f"Duplicate key in {name}: {keys}")
        for col in frame.select_dtypes("object"):
            frame[col] = frame[col].str.strip()
        require(not frame.duplicated(keys).any(), f"Duplicate normalized key in {name}")
        for col in DATES.get(name, []):
            frame[col] = pd.to_datetime(frame[col], errors="raise")
        for col in frame.select_dtypes("number"):
            require(np.isfinite(frame[col].dropna()).all(), f"Nonfinite {name}.{col}")
            require(frame[col].dropna().ge(0).all(), f"Negative {name}.{col}")
        tables[name] = frame

    c, l, b, r, e = (tables[n] for n in KEYS)
    for child, parent, key in [(l,c,"customer_id"),(b,c,"customer_id"),
                               (r,l,"account_id"),(e,l,"account_id")]:
        validate_links(child, parent, key)
    require(l.target_default.isin([0,1]).all(), "Invalid target")
    require(l.collateral_flag.isin([0,1]).all(), "Invalid collateral flag")
    require(l.loan_amount.gt(0).all() and l.tenure_months.gt(0).all(), "Invalid loan size/tenure")
    require(c.age.between(18,110).all(), "Implausible customer age")
    require(r.payment_month.gt(0).all() and r.payment_month.mod(1).eq(0).all(), "Invalid month")
    audit["checks"]["gender_labels_normalized"] = int(c.gender.isin(["M","F"]).sum())
    c["gender"] = c.gender.replace({"M":"Male", "F":"Female"})
    for frame in [c, l]:
        for col in list(frame.columns):
            if frame[col].isna().any():
                frame[f"{col}_missing"] = frame[col].isna()

    b["is_active"] = b.account_status.eq("Active").astype(int)
    b["is_written_off"] = b.account_status.eq("Written-Off").astype(int)
    b["dpd_missing"] = b.days_past_due.isna().astype(int)
    bureau = b.groupby("customer_id").agg(
        bureau_line_count=("bureau_id","size"), bureau_active_count=("is_active","sum"),
        bureau_writeoff_count=("is_written_off","sum"),
        bureau_sanctioned_total=("sanctioned_amount","sum"),
        bureau_outstanding_total=("outstanding_amount","sum"),
        bureau_dpd_mean=("days_past_due","mean"), bureau_dpd_max=("days_past_due","max"),
        bureau_dpd_missing_count=("dpd_missing","sum"),
    )
    bureau["bureau_utilization"] = safe_ratio(bureau.bureau_outstanding_total, bureau.bureau_sanctioned_total)

    r = r.sort_values(["account_id","payment_month"]).copy()
    r["payment_ratio"] = safe_ratio(r.emi_paid, r.emi_due)
    r["missed"] = r.payment_status.eq("Missed").astype(int)
    r["late"] = r.payment_status.eq("Late").astype(int)
    repayment = r.groupby("account_id").agg(
        repayment_month_count=("payment_month","size"),
        repayment_last_month=("payment_month","max"),
        repayment_emi_due_total=("emi_due","sum"), repayment_emi_paid_total=("emi_paid","sum"),
        repayment_dpd_mean=("days_past_due","mean"), repayment_dpd_max=("days_past_due","max"),
        repayment_missed_count=("missed","sum"), repayment_late_count=("late","sum"),
    )
    repayment["repayment_payment_ratio"] = safe_ratio(repayment.repayment_emi_paid_total, repayment.repayment_emi_due_total)
    repayment["repayment_missed_rate"] = safe_ratio(repayment.repayment_missed_count, repayment.repayment_month_count)
    latest = r.groupby("account_id").tail(1).set_index("account_id")
    repayment["latest_outstanding_balance"] = latest.outstanding_balance
    repayment["latest_dpd"] = latest.days_past_due
    last_month = r.groupby("account_id").payment_month.transform("max")
    r["is_recent_3m"] = r.payment_month.gt(last_month - 3)
    for label, mask in [("recent_3m",r.is_recent_3m),("earlier",~r.is_recent_3m)]:
        summary = r.loc[mask].groupby("account_id").agg(
            dpd=("days_past_due","mean"), paid=("emi_paid","sum"), due=("emi_due","sum"))
        repayment[f"{label}_dpd_mean"] = summary.dpd
        repayment[f"{label}_payment_ratio"] = safe_ratio(summary.paid, summary.due)
    repayment["dpd_recent_change"] = repayment.recent_3m_dpd_mean - repayment.earlier_dpd_mean
    repayment["payment_ratio_recent_change"] = repayment.recent_3m_payment_ratio - repayment.earlier_payment_ratio

    collections = e.groupby("account_id").agg(
        collections_event_count=("collection_event_id","size"),
        collections_recovered_total=("amount_recovered","sum"),
        collections_last_event_date=("event_date","max"))
    accounts = l.merge(c,on="customer_id",how="left",validate="many_to_one")
    accounts = accounts.merge(bureau,on="customer_id",how="left",validate="many_to_one")
    accounts = accounts.merge(repayment,on="account_id",how="left",validate="one_to_one")
    accounts = accounts.merge(collections,on="account_id",how="left",validate="one_to_one")
    accounts["has_bureau_records"] = accounts.bureau_line_count.notna()
    accounts["has_repayment_records"] = accounts.repayment_month_count.notna()
    accounts["has_collection_events"] = accounts.collections_event_count.notna()
    # No linked record is a structural zero for counts/totals, not for DPD or ratios.
    zero_cols = [x for x in bureau if x.endswith(("count","total"))]
    zero_cols += ["collections_event_count","collections_recovered_total"]
    accounts[zero_cols] = accounts[zero_cols].fillna(0)
    require(len(accounts)==len(l) and accounts.account_id.is_unique, "Account grain changed")
    require(np.isclose(accounts.loan_amount.sum(),l.loan_amount.sum()), "Loan amount changed")
    require(accounts.target_default.sum()==l.target_default.sum(), "Target count changed")
    require(np.isclose(accounts.collections_recovered_total.sum(),e.amount_recovered.sum()), "Recovery reconciliation failed")
    require(np.isclose(accounts.repayment_emi_paid_total.sum(),r.emi_paid.sum()), "Payment reconciliation failed")

    event_check = e.merge(l[["account_id","origination_date"]],on="account_id",validate="many_to_one")
    bureau_check = l[["account_id","customer_id","origination_date"]].merge(
        b[["customer_id","date_opened"]],on="customer_id",how="inner")
    audit["timing"] = {
        "collections_before_origination": int((event_check.event_date < event_check.origination_date).sum()),
        "loan_bureau_pairs_opened_after_origination": int((bureau_check.date_opened > bureau_check.origination_date).sum()),
        "customer_relationship_after_loan": int((accounts.customer_since > accounts.origination_date).sum()),
        "bureau_closed_before_opened": int((b.date_closed < b.date_opened).sum()),
        "default_date_available": False, "outcome_horizon_available": False,
    }
    audit["checks"].update({
        "output_accounts":len(accounts), "distinct_customers":int(accounts.customer_id.nunique()),
        "original_loan_amount_total":float(l.loan_amount.sum()),
        "latest_recorded_balance_total":float(accounts.latest_outstanding_balance.sum()),
        "default_count":int(l.target_default.sum()), "default_rate":float(l.target_default.mean()),
        "accounts_without_bureau":int((~accounts.has_bureau_records).sum()),
        "accounts_without_repayments":int((~accounts.has_repayment_records).sum()),
        "zero_due_payment_rows":int(r.emi_due.eq(0).sum()),
        "on_time_rows_with_positive_dpd":int((r.payment_status.eq("On-Time") & r.days_past_due.gt(0)).sum()),
        "accounts_with_nonconsecutive_months":int(r.groupby("account_id").payment_month.apply(
            lambda s: not np.array_equal(s.to_numpy(),np.arange(1,int(s.max())+1))).sum()),
        "grain_and_financial_reconciliations":"PASS",
    })
    output.mkdir(parents=True,exist_ok=True)
    reports.mkdir(parents=True,exist_ok=True)
    accounts.to_parquet(output/"accounts.parquet",index=False)
    # Relative month index is authoritative; no fabricated calendar payment date.
    monthly = r.merge(l[["account_id","customer_id","loan_type","origination_date"]],
                      on="account_id",validate="many_to_one")
    monthly.to_parquet(output/"repayments_monthly.parquet",index=False)
    c.to_parquet(output/"customers.parquet",index=False)
    b.to_parquet(output/"bureau_lines.parquet",index=False)
    e.to_parquet(output/"collections_events.parquet",index=False)
    (reports/"data_audit.json").write_text(json.dumps(audit,indent=2)+"\n")
    manifest = {
        "grain":"one row per account_id", "target":"target_default",
        "prediction_status":"Retrospective demonstration only; no default date or outcome horizon supplied.",
        "exclude_from_default_model":[x for x in accounts if x.startswith("collections_")] +
            ["account_id","customer_id","target_default","has_collection_events","gender"],
        "timing_unverified_features":[x for x in accounts if x.startswith(("bureau_","repayment_","recent_","earlier_","latest_","dpd_","payment_ratio_"))],
        "preprocessing":"Split by customer first; fit imputers/encoders/scalers only on training folds.",
        "columns":{x:str(accounts[x].dtype) for x in accounts},
    }
    (reports/"feature_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    lines = ["# Data audit", "", "Generated by `python -m src.build_data`.", "", "## Source inventory", "",
             "| Table | Rows | Missing cells | Duplicate rows |", "|---|---:|---:|---:|"]
    for name, info in audit["sources"].items():
        lines.append(f"| {name} | {info['rows']:,} | {sum(info['missing'].values()):,} | {info['exact_duplicates']} |")
    for title, section in [("Checks",audit["checks"]),("Timing diagnostics",audit["timing"])]:
        lines += ["",f"## {title}",""] + [f"- **{k}**: {v}" for k,v in section.items()]
    lines += ["", "## Missing source values", ""]
    for name, info in audit["sources"].items():
        lines += [f"- {name}.{col}: {count:,}" for col,count in info["missing"].items() if count]
    lines += ["", "Interpret decisions and limitations using `docs/data_decisions.md`. Timing anomalies are retained and disclosed, not silently repaired."]
    (reports/"data_audit.md").write_text("\n".join(lines)+"\n")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,help="Optional source folder; copy original CSVs into data/raw")
    args = parser.parse_args()
    raw = ROOT/"data/raw"
    raw.mkdir(parents=True,exist_ok=True)
    if args.source:
        for name in [f"{n}.csv" for n in KEYS] + ["DATA_DICTIONARY.md"]:
            source, destination = args.source/name, raw/name
            if destination.exists():
                require(source.read_bytes()==destination.read_bytes(),f"Refusing to overwrite changed raw file: {name}")
            else:
                shutil.copy2(source,destination)
    audit = build(raw,ROOT/"data/processed",ROOT/"reports")
    print(json.dumps(audit["checks"],indent=2))


if __name__ == "__main__":
    main()
