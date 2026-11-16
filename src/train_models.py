"""Grouped holdout evaluation of retrospective default classifiers."""
from __future__ import annotations

import os
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')

import json
import hashlib
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import (roc_auc_score,roc_curve,average_precision_score,brier_score_loss,
                            precision_score,recall_score,confusion_matrix)
from sklearn.inspection import permutation_importance
from src.build_data import ROOT, require
from src.analytics import build_analytics

SEED = 42
NUMERIC = ['age','annual_income','years_employed','num_dependents','years_at_residence',
    'loan_amount','interest_rate_pct','tenure_months','collateral_flag',
    'bureau_line_count','bureau_active_count','bureau_writeoff_count','bureau_outstanding_total',
    'bureau_utilization','bureau_dpd_mean','bureau_dpd_max','bureau_dpd_missing_count',
    'repayment_dpd_mean','repayment_dpd_max','repayment_missed_rate','repayment_payment_ratio',
    'latest_dpd','dpd_recent_change','payment_ratio_recent_change']
CATEGORICAL = ['employment_type','region','loan_type','disbursal_channel','housing_type','city_tier']
FEATURES = NUMERIC + CATEGORICAL


def split_accounts(d: pd.DataFrame) -> pd.Series:
    outer = StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=SEED)
    dev,test = next(outer.split(d,d.target_default,d.customer_id))
    inner = StratifiedGroupKFold(n_splits=4,shuffle=True,random_state=SEED+1)
    tr,va = next(inner.split(d.iloc[dev],d.iloc[dev].target_default,d.iloc[dev].customer_id))
    split = pd.Series('train',index=d.index)
    split.iloc[test] = 'test'
    split.iloc[dev[va]] = 'validation'
    require(pd.DataFrame({'customer':d.customer_id,'split':split}).groupby('customer').split.nunique().max()==1,
            'Customer leakage across splits')
    return split


def make_model(kind: str, numeric=None, categorical=None) -> Pipeline:
    numeric = NUMERIC if numeric is None else numeric
    categorical = CATEGORICAL if categorical is None else categorical
    prep = ColumnTransformer([
        ('numeric',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]),numeric),
        ('categorical',Pipeline([('impute',SimpleImputer(strategy='most_frequent')),
                                 ('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))]),categorical)])
    classifier = (LogisticRegression(C=1.0,max_iter=2000,random_state=SEED)
        if kind=='logistic_regression' else HistGradientBoostingClassifier(
            max_iter=150,max_leaf_nodes=15,min_samples_leaf=40,l2_regularization=5.0,
            learning_rate=0.06,early_stopping=False,random_state=SEED))
    return Pipeline([('preprocess',prep),('classifier',classifier)])


def metrics(y, p, threshold=0.5) -> dict:
    fpr,tpr,_ = roc_curve(y,p)
    auc = roc_auc_score(y,p)
    labels = np.asarray(p)>=threshold
    return {'roc_auc':float(auc),'ks':float(np.max(tpr-fpr)),'gini':float(2*auc-1),
        'average_precision':float(average_precision_score(y,p)), 'brier_score':float(brier_score_loss(y,p)),
        'threshold':float(threshold),'precision':float(precision_score(y,labels,zero_division=0)),
        'recall':float(recall_score(y,labels,zero_division=0)),
        'confusion_matrix_tn_fp_fn_tp':confusion_matrix(y,labels,labels=[0,1]).ravel().astype(int).tolist(),
        'accounts':len(y),'default_rate':float(np.mean(y))}


def baseline_explanations(model, x: pd.DataFrame, ids: pd.Series) -> pd.DataFrame:
    prep = model.named_steps['preprocess']
    clf = model.named_steps['classifier']
    values = prep.transform(x)
    contributions = values * clf.coef_[0]
    logits = clf.intercept_[0]+contributions.sum(axis=1)
    require(np.allclose(expit(logits),model.predict_proba(x)[:,1]),'Coefficient contributions do not reconstruct baseline')
    names = prep.get_feature_names_out()
    order = np.argsort(np.abs(contributions),axis=1)[:,-3:][:,::-1]
    rows = []
    for i,account in enumerate(ids):
        for rank,j in enumerate(order[i],1):
            rows.append({'account_id':account,'rank':rank,'model':'logistic_regression',
                'feature':names[j],'log_odds_contribution':float(contributions[i,j]),
                'direction':'increases' if contributions[i,j]>0 else 'decreases'})
    return pd.DataFrame(rows)


def main() -> None:
    build_analytics()
    d = pd.read_parquet(ROOT/'data/processed/accounts.parquet')
    manifest = json.loads((ROOT/'reports/feature_manifest.json').read_text())
    require(not set(FEATURES)&set(manifest['exclude_from_default_model']),'Forbidden model input')
    split = split_accounts(d)
    train,valid,test = (split.eq(s) for s in ['train','validation','test'])
    x,y = d[FEATURES],d.target_default
    out, artifacts = ROOT/'reports/models',ROOT/'artifacts'
    out.mkdir(parents=True,exist_ok=True)
    artifacts.mkdir(parents=True,exist_ok=True)
    assignments = d[['account_id','customer_id']].assign(split=split)
    assignments.to_csv(out/'split_assignments.csv',index=False)
    models,results = {},{}
    for name in ['logistic_regression','hist_gradient_boosting']:
        print(f'Training {name}...',flush=True)
        model = make_model(name).fit(x.loc[train],y.loc[train])
        models[name] = model
        results[name] = {'validation':metrics(y.loc[valid],model.predict_proba(x.loc[valid])[:,1])}
    # Model selection and review threshold see validation only, never test.
    selected = max(results,key=lambda n:results[n]['validation']['roc_auc'])
    pv = models[selected].predict_proba(x.loc[valid])[:,1]
    threshold = float(np.quantile(pv,0.9))
    for name,model in models.items():
        results[name]['test'] = metrics(y.loc[test],model.predict_proba(x.loc[test])[:,1])
        joblib.dump(model,artifacts/f'{name}.joblib')
        print(f'Computing validation importance: {name}...',flush=True)
        importance = permutation_importance(model,x.loc[valid],y.loc[valid],scoring='roc_auc',
                                            n_repeats=3,random_state=SEED,n_jobs=1)
        pd.DataFrame({'feature':FEATURES,'auc_drop_mean':importance.importances_mean,
                      'auc_drop_std':importance.importances_std}).sort_values('auc_drop_mean',ascending=False).to_csv(
                          out/f'{name}_importance.csv',index=False)
        probs = model.predict_proba(x.loc[test])[:,1]
        fpr,tpr,thresholds = roc_curve(y.loc[test],probs)
        pd.DataFrame({'fpr':fpr,'tpr':tpr,'threshold':thresholds}).to_csv(out/f'{name}_roc.csv',index=False)
        cal = pd.DataFrame({'actual':y.loc[test].to_numpy(),'prediction':probs})
        cal['bin'] = pd.cut(cal.prediction,np.linspace(0,1,11),include_lowest=True)
        cal.groupby('bin',observed=True).agg(accounts=('actual','size'),mean_prediction=('prediction','mean'),
            observed_default_rate=('actual','mean')).reset_index().to_csv(out/f'{name}_calibration.csv',index=False)
    # Diagnostic sensitivity analysis; not another selection round.
    static_numeric = [f for f in NUMERIC if not f.startswith(('repayment_','latest_','dpd_recent','payment_ratio_recent'))]
    diagnostic = make_model('logistic_regression',numeric=static_numeric).fit(x.loc[train],y.loc[train])
    sensitivity = metrics(y.loc[test],diagnostic.predict_proba(x.loc[test])[:,1])
    scores = d[['account_id','customer_id','target_default']].assign(split=split)
    for name,model in models.items():
        scores[f'{name}_score'] = model.predict_proba(x)[:,1]
    scores['selected_model'] = selected
    scores['risk_score'] = scores[f'{selected}_score']
    scores['review_priority'] = np.where(scores.risk_score.ge(threshold),'Elevated','Standard')
    scores['score_scope'] = np.where(train,'in_sample','held_out')
    scores.to_parquet(ROOT/'data/processed/account_scores.parquet',index=False)
    baseline_explanations(models['logistic_regression'],x,d.account_id).to_parquet(
        ROOT/'data/processed/baseline_account_drivers.parquet',index=False)
    baseline = models['logistic_regression']
    pd.DataFrame({'feature':baseline.named_steps['preprocess'].get_feature_names_out(),
                  'coefficient':baseline.named_steps['classifier'].coef_[0]}).to_csv(out/'baseline_coefficients.csv',index=False)
    result = {'seed':SEED,'python':platform.python_version(),'sklearn':sklearn.__version__,
        'data_sha256':hashlib.sha256((ROOT/'data/processed/accounts.parquet').read_bytes()).hexdigest(),
        'features':FEATURES,'split_accounts':split.value_counts().to_dict(),
        'split_customers':assignments.groupby('split').customer_id.nunique().to_dict(),
        'selected_model':selected,'selection_rule':'Highest validation ROC-AUC; fixed hyperparameters; no test-set selection.',
        'review_threshold':threshold,'review_threshold_rule':'90th percentile of selected-model validation scores; illustrative capacity rule, not an approval threshold.',
        'selected_test_at_review_threshold':metrics(y.loc[test],models[selected].predict_proba(x.loc[test])[:,1],threshold),
        'models':results,'no_repayment_baseline_test':sensitivity,
        'limitations':['Retrospective synthetic-data classification, not prospective default forecasting.',
            'No default date/outcome horizon; bureau, repayment and customer attributes lack point-in-time guarantees.',
            'Training rows have in-sample scores; test metrics only describe untouched held-out customers.',
            'Raw model probabilities are uncalibrated estimates, not validated bank PDs.',
            'Local coefficient explanations belong to the baseline only, not the challenger.',
            'Permutation importance uses validation AUC; correlated features may mask individual importance.']}
    (out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
    lines = ['# Model evaluation','', '**Retrospective synthetic-data classification only.** Default dates and outcome windows are unavailable.',
        '', '| Model | Validation AUC | Test AUC | Test KS | Test Gini | Test AP | Test Brier |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,m in results.items():
        t=m['test']
        lines.append(f"| {name} | {m['validation']['roc_auc']:.4f} | {t['roc_auc']:.4f} | {t['ks']:.4f} | {t['gini']:.4f} | {t['average_precision']:.4f} | {t['brier_score']:.4f} |")
    lines += ['',f"Selected on validation AUC: **{selected}**.",f"Account splits: {result['split_accounts']}; customer splits: {result['split_customers']}.",
        '', '## Method','Fixed seed; approximately 60/20/20 train/validation/test using nested StratifiedGroupKFold. Customer groups never cross partitions. '
        'All imputers, scalers and encoders fit on training only. Two fixed candidate specifications; no hyperparameter sweep. '
        'Histogram boosting early stopping is disabled to avoid an internal row-level split. No class balancing or oversampling. '
        'The selected model is not refitted, so saved models reproduce reported test scores.',
        '', '## Metrics','AUC measures ranking; KS = max(TPR − FPR); Gini = 2 × AUC − 1. AP is average precision, not trapezoidal PR-AUC. '
        'Brier is mean squared probability error (lower is better). JSON includes precision/recall at 0.5 and selected-model review threshold; ROC and calibration bins are exported.',
        '', '## Sensitivity to repayment features',f"Removing repayment features from the baseline gives test AUC {sensitivity['roc_auc']:.4f}. "
        'This diagnostic does not prove leakage absence: current bureau and customer snapshots remain temporally unverified.',
        '', '## Explanations','Validation permutation importance reports AUC drop after shuffling each raw feature, with 3 repetitions. '
        'Baseline coefficients use standardized numeric inputs and one-hot categories. Account drivers are the top 3 absolute baseline log-odds contributions '
        'relative to its intercept, not causal effects or explanations of the challenger. Full contributions plus intercept reconstruct baseline scores.',
        '', '## Score interpretation',f"Illustrative review threshold: {threshold:.4f}, selected as validation score 90th percentile. "
        'Priority bands are review capacity markers, not credit decisions. All-account score exports explicitly label training scores as in-sample.',
        '', '## Limitations'] + ['- '+v for v in result['limitations']]
    (ROOT/'reports/model_evaluation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'selected_model':selected,'models':results},indent=2),flush=True)


if __name__=='__main__':
    main()
