import tempfile
import unittest
from pathlib import Path
import pandas as pd
from src.build_data import ROOT
from src.reviews import save_review, read_reviews


class AnomalyTests(unittest.TestCase):
    def test_output(self):
        d = pd.read_parquet(ROOT/'data/processed/anomalies.parquet')
        self.assertTrue(d.account_id.is_unique)
        self.assertEqual(len(d),14685)
        self.assertTrue(d.loc[d.flagged,'reason_count'].gt(0).all())
        self.assertTrue(d.anomaly_score.notna().all())

    def test_persistence_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'reviews.db'
            save_review('account','v1','confirm',note="analyst's note",path=path)
            save_review('account','v1','dismiss',path=path)
            rows = read_reviews(path)
            self.assertEqual(rows.decision.tolist(),['dismiss','confirm'])
            self.assertEqual(rows.iloc[1].note,"analyst's note")
            with self.assertRaises(ValueError):
                save_review('account','v1','invalid',path=path)
