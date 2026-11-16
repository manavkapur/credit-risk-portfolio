# Portfolio insights

14,685 accounts; 10,000 customers; observed default rate 16.10%.

Rates use account counts, not customer counts. USD amounts use the source definition. Latest balances are not a common-date exposure snapshot.

## 1. employment_type
Unemployed has the highest observed account default rate: 34.96% (251/718), versus 13.56% for Business Owner (250/1,844); gap 21.40 percentage points.

**So what:** Prioritize manual review and investigate affordability within this segment; association does not establish causation.
Source: `reports/analytics/by_employment_type.csv`

## 2. income_band
Under $30k has the highest observed account default rate: 38.67% (174/450), versus 9.52% for $100k+ (295/3,098); gap 29.14 percentage points.

**So what:** Review affordability and payment burden in this income band, using count and exposure alongside the observed default rate.
Source: `reports/analytics/by_income_band.csv`

## 3. loan_type
Mortgage has the highest observed account default rate: 24.65% (353/1,432), versus 13.88% for Auto Loan (393/2,832); gap 10.77 percentage points.

**So what:** Focus product-level monitoring on this segment and compare its risk concentration with its share of original lending.
Source: `reports/analytics/by_loan_type.csv`

## 4. region
South has the highest observed account default rate: 16.86% (607/3,600), versus 15.00% for Central (347/2,314); gap 1.87 percentage points.

**So what:** Investigate regional mix and underwriting differences before attributing the gap to location itself.
Source: `reports/analytics/by_region.csv`

## 5. income_band × employment_type
Among cross-segments with at least 100 accounts, Under $30k / Unemployed has the highest observed default rate: 44.30% (101/228).

**So what:** Use the combined segment to prioritize analyst review; validate on a later cohort before changing policy.
Source: `reports/analytics/by_income_and_employment.csv`

## Interpretation
These are descriptive associations, not causal effects. Segment rankings are exploratory, with no multiple-comparison inference. Age profiles are included in the CSV tables. Origination-year rates describe historical cohorts with unspecified outcome windows, not default incidence over calendar time. Repayment trends use relative loan age. Customer profiles count each customer once; account-segment customer counts are not additive across loan types.
