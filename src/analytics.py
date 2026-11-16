"""Portfolio summaries at explicit account and customer grains."""
from __future__ import annotations

import json
import pandas as pd
from src.build_data import ROOT


def add_bands(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    d['income_band'] = pd.cut(d.annual_income,[-float('inf'),30000,60000,100000,float('inf')],
                              labels=['Under $30k','$30k–$60k','$60k–$100k','$100k+'],right=False)
    d['age_band'] = pd.cut(d.age,[0,30,45,60,float('inf')],labels=['Under 30','30–44','45–59','60+'],right=False)
    return d


def summarize(d: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    result = d.groupby(dimensions,observed=True,dropna=False).agg(
        accounts=('account_id','size'), customers=('customer_id','nunique'),
        defaults=('target_default','sum'), original_loan_amount=('loan_amount','sum'),
        latest_recorded_balance=('latest_outstanding_balance','sum')).reset_index()
    result['default_rate'] = result.defaults / result.accounts
    result['original_amount_share'] = result.original_loan_amount / d.loan_amount.sum()
    return result


def build_analytics() -> dict:
    out = ROOT/'reports/analytics'
    out.mkdir(parents=True,exist_ok=True)
    d = add_bands(pd.read_parquet(ROOT/'data/processed/accounts.parquet'))
    customers = add_bands(pd.read_parquet(ROOT/'data/processed/customers.parquet'))
    dimensions = ['income_band','employment_type','region','age_band','loan_type']
    summaries = {}
    for dim in dimensions:
        summaries[dim] = summarize(d,[dim])
        summaries[dim].to_csv(out/f'by_{dim}.csv',index=False)
        if dim != 'loan_type':
            customers.groupby(dim,observed=True,dropna=False).size().rename('customers').reset_index().to_csv(
                out/f'customer_profile_{dim}.csv',index=False)
    cross = summarize(d,['income_band','employment_type'])
    cross.to_csv(out/'by_income_and_employment.csv',index=False)
    d['origination_year'] = d.origination_date.dt.year
    summarize(d,['origination_year']).to_csv(out/'by_origination_cohort.csv',index=False)
    monthly = pd.read_parquet(ROOT/'data/processed/repayments_monthly.parquet')
    monthly.groupby('payment_month').agg(accounts=('account_id','nunique'),mean_dpd=('days_past_due','mean'),
        emi_due=('emi_due','sum'),emi_paid=('emi_paid','sum')).assign(
            payment_ratio=lambda x:x.emi_paid/x.emi_due).reset_index().to_csv(out/'by_relative_payment_month.csv',index=False)
    insights = []
    actions = {
        'employment_type':'Prioritize manual review and investigate affordability within this segment; association does not establish causation.',
        'income_band':'Review affordability and payment burden in this income band, using count and exposure alongside the observed default rate.',
        'loan_type':'Focus product-level monitoring on this segment and compare its risk concentration with its share of original lending.',
        'region':'Investigate regional mix and underwriting differences before attributing the gap to location itself.',
    }
    for dim, action in actions.items():
        s = summaries[dim].loc[lambda x:x.accounts.ge(100)].sort_values('default_rate',ascending=False)
        high, low = s.iloc[0],s.iloc[-1]
        insights.append({'dimension':dim,'finding':f"{high[dim]} has the highest observed account default rate: {high.default_rate:.2%} "
            f"({int(high.defaults):,}/{int(high.accounts):,}), versus {low.default_rate:.2%} for {low[dim]} "
            f"({int(low.defaults):,}/{int(low.accounts):,}); gap {(high.default_rate-low.default_rate)*100:.2f} percentage points.",
            'so_what':action,'source':f'reports/analytics/by_{dim}.csv'})
    high = cross.loc[cross.accounts.ge(100)].sort_values('default_rate',ascending=False).iloc[0]
    insights.append({'dimension':'income_band × employment_type','finding':f"Among cross-segments with at least 100 accounts, "
        f"{high.income_band} / {high.employment_type} has the highest observed default rate: {high.default_rate:.2%} "
        f"({int(high.defaults):,}/{int(high.accounts):,}).",'so_what':'Use the combined segment to prioritize analyst review; validate on a later cohort before changing policy.',
        'source':'reports/analytics/by_income_and_employment.csv'})
    result = {'accounts':len(d),'customers':int(d.customer_id.nunique()),'defaults':int(d.target_default.sum()),
        'default_rate':float(d.target_default.mean()),'original_loan_amount':float(d.loan_amount.sum()),
        'latest_recorded_balance':float(d.latest_outstanding_balance.sum()),'insights':insights}
    (out/'portfolio_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    lines = ['# Portfolio insights','',f"{len(d):,} accounts; {d.customer_id.nunique():,} customers; observed default rate {d.target_default.mean():.2%}.",
        '', 'Rates use account counts, not customer counts. USD amounts use the source definition. Latest balances are not a common-date exposure snapshot.', '']
    for i,item in enumerate(insights,1):
        lines += [f"## {i}. {item['dimension']}",item['finding'],'',f"**So what:** {item['so_what']}",f"Source: `{item['source']}`",'']
    lines += ['## Interpretation','These are descriptive associations, not causal effects. Segment rankings are exploratory, with no multiple-comparison inference. '
        'Age profiles are included in the CSV tables. Origination-year rates describe historical cohorts with unspecified outcome windows, not default incidence over calendar time. '
        'Repayment trends use relative loan age. Customer profiles count each customer once; account-segment customer counts are not additive across loan types.']
    (ROOT/'reports/portfolio_insights.md').write_text('\n'.join(lines)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(build_analytics(),indent=2))
