# Data preparation decisions

## Grain and join contract

`accounts.parquet` contains exactly one row per loan. Loan accounts are the left-hand spine. Customers join many-to-one. Bureau lines aggregate by customer before joining many-to-one. Repayments and collections aggregate by account before one-to-one joins. Missing/duplicate keys, negative numerical values, invalid dates and orphan references fail the build. Original CSV bytes are preserved and SHA-256 hashes recorded.

Customer-level bureau totals repeat across a customer's loans. **Do not sum these repeated totals across accounts.** Use `bureau_lines.parquet` for total external borrowing and `customers.parquet` for customer profiles. Customer counts use distinct IDs. All currency amounts are USD according to the supplied dictionary.

## Cleaning and missingness

- Strip surrounding whitespace from text and standardize M/F to Male/Female. Gender remains for profiling but is excluded from the default-model candidate inputs.
- Parse date columns strictly. Preserve contradictory dates and count them in the audit; do not invent corrections.
- Keep missing customer attributes and interest rates as null, with missingness indicators. No global median imputation is performed.
- Missing bureau DPD remains unknown. Its mean/max use observed values; a missing-count feature records coverage. All-missing DPD remains null.
- An account/customer with no linked bureau or collections records has zero observed record counts/totals. This means no records in this extract, not proven absence of external borrowing or collection activity. Ratios, dates and DPD stay null when unavailable.
- Missing bureau closure date is retained; it may mean still open or unknown. No inferred closure date.
- Zero denominators produce null ratios. Payment/credit utilization ratios are not capped at one: overpayment and over-limit balances remain visible.
- Preserve the supplied payment status and DPD separately. Missed/late counts use status; DPD measures use numeric DPD. Contradictions are not silently reconciled.

## Aggregation definitions

- Bureau utilization = total outstanding / total sanctioned amount across available external credit lines.
- Repayment payment ratio = total EMI paid / total EMI due, not an unweighted mean of monthly ratios.
- Missed-payment rate = missed-status rows / observed repayment rows.
- Latest balance = balance at the highest observed payment-month index per account. Summing this is a latest-recorded balance total, **not a common-calendar-date exposure snapshot**.
- Recent window = last three relative payment-month indices; earlier window = all preceding observed months. Recent-change features compare their mean DPD and weighted payment ratios. Short histories can have null comparisons.
- Collections recovered total sums recorded event recovery amounts. No causal effectiveness claim is made.
- Monthly repayment data retains the supplied relative month index. No calendar payment date is fabricated. Cohort/origination trends and relative loan-age trends must be labelled separately.

## Prediction timing and leakage

The data has no default event date, label observation window, bureau snapshot date or reliable historical customer snapshots. Thus none of the proposed inputs is certified as available before default. A later model is a retrospective synthetic-data classification demonstration, not a validated prospective probability of default.

Repayment and current bureau features may encode distress/default already underway. Loan/bureau pairs opened after origination and collections before origination are explicitly audited. Full repayment history cannot be used for an origination-time claim. Collections features and has_collection_events are excluded from the primary default model. IDs and target are not predictors; gender is reserved for profiling/auditing.

Before fitting, split by customer ID so related loans cannot cross partitions. Fit imputation, encoding, scaling and any supervised feature selection only within training folds. Future bank deployment requires an explicit scoring date, point-in-time snapshots, default definition/date and a forward outcome horizon. Temporal validation needs these inputs.

## Outputs

- `data/processed/accounts.parquet`: account-level analysis and candidate features.
- `data/processed/repayments_monthly.parquet`: monthly behaviour and anomaly diagnostics.
- `data/processed/customers.parquet`: customer-grain profiles.
- `data/processed/bureau_lines.parquet`: cleaned external credit-line records.
- `data/processed/collections_events.parquet`: cleaned event-level records.
- `reports/data_audit.md` and `.json`: counts, source hashes, missingness and reconciliation.
- `reports/feature_manifest.json`: column types, modelling exclusions and timing cautions.

Source data stays unchanged in `data/raw`. Prepared data is regenerable and ignored by Git. Reports are deterministic for the same input bytes and dependency versions.
