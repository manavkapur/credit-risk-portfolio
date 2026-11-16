"""Explainable historical outlier screening; no default labels used."""
import json
import hashlib
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from src.build_data import ROOT

FEATURES = ['repayment_dpd_mean','repayment_missed_rate','repayment_payment_ratio',
            'dpd_recent_change','payment_ratio_recent_change','bureau_utilization','bureau_dpd_max']


def build():
    d = pd.read_parquet(ROOT/'data/processed/accounts.parquet')
    model = make_pipeline(SimpleImputer(strategy='median',add_indicator=True),
        IsolationForest(n_estimators=150,contamination=0.03,random_state=42,n_jobs=1))
    model.fit(d[FEATURES])
    scores = -model.score_samples(d[FEATURES])
    cutoff = float(np.quantile(scores,.97))
    # Customer bureau attributes repeat across loans: compute peers on unique customers.
    customers = d.drop_duplicates('customer_id').copy()
    peer = customers.groupby('employment_type').bureau_utilization.agg(['median','count'])
    customers['deviation'] = (customers.bureau_utilization-customers.employment_type.map(peer['median'])).abs()
    mad = customers.groupby('employment_type').deviation.median()
    reasons = []
    for i,row in d.iterrows():
        r = []
        if row.dpd_recent_change >= 15:
            r.append(f"Recent mean DPD {row.recent_3m_dpd_mean:.1f} versus earlier {row.earlier_dpd_mean:.1f}; increase at least 15 days")
        if row.payment_ratio_recent_change <= -.25:
            r.append(f"Recent paid/due {row.recent_3m_payment_ratio:.2f} versus earlier {row.earlier_payment_ratio:.2f}; drop at least 0.25")
        group = row.employment_type
        median, count = peer.loc[group,['median','count']]
        scale = mad.loc[group]
        if count >= 100 and scale > 0 and pd.notna(row.bureau_utilization):
            z = .67448975*(row.bureau_utilization-median)/scale
            if z > 3.5:
                r.append(f"Bureau utilization {row.bureau_utilization:.2f} versus employment-peer median {median:.2f}; robust z {z:.1f} exceeds 3.5")
        if scores[i] >= cutoff:
            r.append(f"Isolation Forest unusual feature combination: score {scores[i]:.4f}, threshold {cutoff:.4f} (top 3% in this extract)")
        reasons.append(r)
    version = hashlib.sha256((ROOT/'data/processed/accounts.parquet').read_bytes()).hexdigest()[:16]+'-anomaly-v1'
    result = d[['account_id','customer_id','loan_type','employment_type']].copy()
    result['anomaly_score'] = scores
    result['flagged'] = [bool(r) for r in reasons]
    result['reason_count'] = [len(r) for r in reasons]
    result['reasons_json'] = [json.dumps(r) for r in reasons]
    result['anomaly_version'] = version
    result.to_parquet(ROOT/'data/processed/anomalies.parquet',index=False)
    joblib.dump(model,ROOT/'artifacts/anomaly_model.joblib')
    report = {'version':version,'accounts':len(d),'flagged':int(result.flagged.sum()),
        'isolation_forest_threshold':cutoff,'features':FEATURES,'default_label_used':False,
        'limitations':'Historical outlier detection fitted to this extract. No labelled anomaly ground truth; false-negative rate unknown. Bureau peers use unique customers. Forest score is not a default probability.'}
    (ROOT/'reports/anomalies.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    build()
