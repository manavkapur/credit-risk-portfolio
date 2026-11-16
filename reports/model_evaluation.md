# Model evaluation

**Retrospective synthetic-data classification only.** Default dates and outcome windows are unavailable.

| Model | Validation AUC | Test AUC | Test KS | Test Gini | Test AP | Test Brier |
|---|---:|---:|---:|---:|---:|---:|
| logistic_regression | 0.6918 | 0.6784 | 0.2660 | 0.3568 | 0.3233 | 0.1217 |
| hist_gradient_boosting | 0.6732 | 0.6700 | 0.2644 | 0.3399 | 0.2793 | 0.1241 |

Selected on validation AUC: **logistic_regression**.
Account splits: {'train': 8826, 'test': 2968, 'validation': 2891}; customer splits: {'test': 2027, 'train': 5969, 'validation': 2004}.

## Method
Fixed seed; approximately 60/20/20 train/validation/test using nested StratifiedGroupKFold. Customer groups never cross partitions. All imputers, scalers and encoders fit on training only. Two fixed candidate specifications; no hyperparameter sweep. Histogram boosting early stopping is disabled to avoid an internal row-level split. No class balancing or oversampling. The selected model is not refitted, so saved models reproduce reported test scores.

## Metrics
AUC measures ranking; KS = max(TPR − FPR); Gini = 2 × AUC − 1. AP is average precision, not trapezoidal PR-AUC. Brier is mean squared probability error (lower is better). JSON includes precision/recall at 0.5 and selected-model review threshold; ROC and calibration bins are exported.

## Sensitivity to repayment features
Removing repayment features from the baseline gives test AUC 0.6661. This diagnostic does not prove leakage absence: current bureau and customer snapshots remain temporally unverified.

## Explanations
Validation permutation importance reports AUC drop after shuffling each raw feature, with 3 repetitions. Baseline coefficients use standardized numeric inputs and one-hot categories. Account drivers are the top 3 absolute baseline log-odds contributions relative to its intercept, not causal effects or explanations of the challenger. Full contributions plus intercept reconstruct baseline scores.

## Score interpretation
Illustrative review threshold: 0.2861, selected as validation score 90th percentile. Priority bands are review capacity markers, not credit decisions. All-account score exports explicitly label training scores as in-sample.

## Limitations
- Retrospective synthetic-data classification, not prospective default forecasting.
- No default date/outcome horizon; bureau, repayment and customer attributes lack point-in-time guarantees.
- Training rows have in-sample scores; test metrics only describe untouched held-out customers.
- Raw model probabilities are uncalibrated estimates, not validated bank PDs.
- Local coefficient explanations belong to the baseline only, not the challenger.
- Permutation importance uses validation AUC; correlated features may mask individual importance.
