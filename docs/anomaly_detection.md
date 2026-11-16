# Anomaly detection and human review

Trigger: run the batch detector after each dataset build; the dashboard will display flagged accounts. Rules identify a recent mean DPD increase of at least 15 days, a recent paid/due decrease of at least 0.25, or unusually high bureau utilization relative to employment peers (robust z > 3.5, at least 100 observed peer customers). Own-history windows compare the final three loan-age months against earlier months. Missing comparisons do not trigger rules.

Isolation Forest independently flags the top 3% of unusual multivariate scores in the extract. This is an illustrative workload setting, not a measured prevalence. It uses no target_default or collections information. Forest explanations describe a multivariate outlier score, not a fabricated attribution to one variable. Rule explanations supply measured values and thresholds.

A false positive is legitimate unusual behaviour flagged for review. A false negative is genuinely problematic unusual behaviour the detector misses. No labelled anomaly outcomes exist, so accuracy/recall cannot be claimed. Review alert volume, confirmed fractions and samples of unflagged accounts; review confirmation is feedback, not automatic ground truth.

Human step: inspect payment and bureau evidence, confirm or dismiss, and record a note. Reviews are append-only with account ID, dataset/detector version, reviewer and UTC timestamp. The newest decision is the current one for that version; earlier decisions remain auditable. No automatic account action or retraining occurs.

`src/reviews.py` persists decisions in SQLite, surviving Python/app restarts on the same filesystem. Set REVIEW_DB_PATH to a durable mounted path on deployment. Ephemeral hosting can erase local files on redeploy; a persistent volume or external database is required before claiming durable hosted review storage. Reviewer names are demo labels, not authenticated identities.
