# Monitoring plan and deployment requirements

This plan is documentation, not a deployed monitoring service.

## Before use at a bank

Obtain a default definition, default event dates, a scoring cutoff, forward outcome horizon and point-in-time snapshots. Rebuild features as of that cutoff, validate on later cohorts, calibrate probabilities and approve review thresholds against actual capacity/cost. Existing test metrics only assess retrospective classification on synthetic data. They do not establish future default performance or fairness.

## At every data refresh

Run existing key, referential-integrity, row-count, currency-total and range checks. Compare missingness, new categories, record coverage and freshness against training references. Stop scoring on schema/feature incompatibility or missing model artifacts. Log dataset hash, model version, input snapshot and run time. Keep the last successful run distinct from fresh results.

## Monthly, or at a cadence agreed with the bank

Compare numeric feature and score distributions with training/reference distributions using binned PSI and quantile shifts, and categorical frequencies/new-category rates. Track review volume, segment composition, score concentrations and unavailable scores. Proposed investigation triggers (such as a 5 percentage-point missingness increase or PSI above 0.2) must be calibrated to historical variation; they are not universal regulatory cutoffs. Drift alone does not prove accuracy degradation.

## Once outcome labels mature

Evaluate AUC, KS, Gini, average precision, Brier score and calibration plots on the same prediction horizon. Track precision/recall and alert workload at the deployed threshold, segmented by product, region and relevant customer groups. Include sample sizes and uncertainty; use customer-group bootstrap intervals where customers have multiple loans. Delayed labels require vintage tracking and exclude immature cohorts. Compare against a simple baseline and the last approved model.

## Explanations and review

Use validation permutation importance for aggregate model reliance, remembering that correlated variables can share importance. Baseline coefficient contributions explain only baseline predictions. Report observational associations rather than causal claims. Profile sensitive groups for disparate performance; excluding gender does not eliminate proxies or establish fairness. Human reviewers decide actions; scores do not automatically approve, deny or change loans.

## Change control

Investigate significant data/performance changes with the data owner. Recalibrate or retrain only after diagnosis and a separately held-out evaluation. Version features, preprocessing, training data, thresholds and models together. Require documented reviewer approval before replacing a deployed model, and maintain rollback artifacts. Never load untrusted joblib/pickle artifacts.
