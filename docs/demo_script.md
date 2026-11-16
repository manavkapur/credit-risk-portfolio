# Four-minute demonstration

0:00-0:40 - Explain the synthetic portfolio, account-grain joins, 14,685 accounts and observed 16.10% default rate. State the missing default-date limitation.

0:40-1:20 - Portfolio view: compare loan types, filter South, show repayment by relative loan age. Distinguish original lending from latest recorded balances.

1:20-2:00 - Account view: choose a loan, show score and baseline coefficient drivers, payment history and whether score is in-sample. Explain that scores prioritize review.

2:00-2:50 - Anomaly review: open a flagged loan, read its evidence, confirm/dismiss with a note, show review history. Explain false positives and missed anomalies; no anomaly ground-truth accuracy claim.

2:50-3:40 - Reset filters. Ask overall observed default rate, highest-default loan type and next year's default rate. Show SQL evidence and unsupported-question refusal. LLM interprets; SQL supplies all numbers.

3:40-4:00 - Mention grouped held-out AUC 0.6784, KS 0.2660, Gini 0.3568, baseline versus challenger, and where the two one-page PDFs and reproducible commands live.
