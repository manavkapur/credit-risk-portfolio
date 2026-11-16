import json
import unittest
import joblib
import numpy as np
import pandas as pd
from src.build_data import ROOT
from src.analytics import add_bands, summarize
from src.train_models import FEATURES, metrics, split_accounts


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = pd.read_parquet(ROOT/'data/processed/accounts.parquet')

    def test_customer_partitions_and_reproducibility(self):
        a,b = split_accounts(self.d),split_accounts(self.d)
        pd.testing.assert_series_equal(a,b)
        check = self.d.assign(split=a).groupby('customer_id').split.nunique()
        self.assertEqual(check.max(),1)
        self.assertEqual(set(a),{'train','validation','test'})

    def test_no_forbidden_inputs(self):
        manifest = json.loads((ROOT/'reports/feature_manifest.json').read_text())
        self.assertFalse(set(FEATURES)&set(manifest['exclude_from_default_model']))
        self.assertFalse(any('collections' in f for f in FEATURES))

    def test_metrics_known_cases(self):
        perfect = metrics(np.array([0,0,1,1]),np.array([.1,.2,.8,.9]))
        self.assertEqual((perfect['roc_auc'],perfect['ks'],perfect['gini']),(1.,1.,1.))
        tied = metrics(np.array([0,0,1,1]),np.array([.5,.5,.5,.5]))
        self.assertEqual((tied['roc_auc'],tied['ks'],tied['gini']),(.5,0.,0.))

    def test_segment_reconciliation(self):
        d = add_bands(self.d)
        for dims in [['loan_type'],['income_band'],['age_band'],['income_band','employment_type']]:
            summary = summarize(d,dims)
            self.assertEqual(summary.accounts.sum(),len(d))
            self.assertEqual(summary.defaults.sum(),d.target_default.sum())
            self.assertAlmostEqual(summary.original_loan_amount.sum(),d.loan_amount.sum(),places=4)

    def test_saved_scores_and_evaluation(self):
        scores = pd.read_parquet(ROOT/'data/processed/account_scores.parquet')
        result = json.loads((ROOT/'reports/models/evaluation.json').read_text())
        self.assertEqual(scores.account_id.tolist(),self.d.account_id.tolist())
        for name in result['models']:
            model = joblib.load(ROOT/f'artifacts/{name}.joblib')
            p = model.predict_proba(self.d[FEATURES])[:,1]
            np.testing.assert_allclose(p,scores[f'{name}_score'])
            mask = scores.split.eq('test')
            actual = metrics(self.d.loc[mask,'target_default'],p[mask])
            for key in ['roc_auc','ks','gini','brier_score']:
                self.assertAlmostEqual(actual[key],result['models'][name]['test'][key])
        self.assertTrue(scores.loc[scores.split.eq('train'),'score_scope'].eq('in_sample').all())

    def test_preprocessor_uses_training_medians(self):
        from src.train_models import NUMERIC
        scores = pd.read_parquet(ROOT/'data/processed/account_scores.parquet')
        model = joblib.load(ROOT/'artifacts/logistic_regression.joblib')
        imputer = model.named_steps['preprocess'].named_transformers_['numeric'].named_steps['impute']
        expected = self.d.loc[scores.split.eq('train'),NUMERIC].median().to_numpy()
        np.testing.assert_allclose(imputer.statistics_,expected)


if __name__=='__main__':
    unittest.main()
