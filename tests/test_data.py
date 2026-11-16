import hashlib
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.build_data import ROOT, build, safe_ratio, validate_links


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.accounts = pd.read_parquet(ROOT/'data/processed/accounts.parquet')
        cls.loans = pd.read_csv(ROOT/'data/raw/loan_accounts.csv')

    def test_preserves_accounts_and_targets(self):
        actual = self.accounts.set_index('account_id').sort_index()
        expected = self.loans.set_index('account_id').sort_index()
        self.assertTrue(actual.index.is_unique)
        pd.testing.assert_series_equal(actual.target_default,expected.target_default)
        pd.testing.assert_series_equal(actual.loan_amount,expected.loan_amount)

    def test_independent_payment_and_balance_reconciliation(self):
        raw = pd.read_csv(ROOT/'data/raw/repayment_history.csv')
        latest = raw.sort_values('payment_month').drop_duplicates('account_id',keep='last')
        self.assertAlmostEqual(self.accounts.latest_outstanding_balance.sum(),latest.outstanding_balance.sum(),places=5)
        self.assertAlmostEqual(self.accounts.repayment_emi_paid_total.sum(),raw.emi_paid.sum(),places=5)
        account = raw.account_id.iloc[0]
        subset = raw.loc[raw.account_id.eq(account)]
        row = self.accounts.set_index('account_id').loc[account]
        self.assertAlmostEqual(row.repayment_payment_ratio,subset.emi_paid.sum()/subset.emi_due.sum())

    def test_unknown_is_not_zero(self):
        raw = pd.read_csv(ROOT/'data/raw/loan_accounts.csv').set_index('account_id')
        clean = self.accounts.set_index('account_id')
        self.assertTrue(clean.loc[raw.interest_rate_pct.isna(),'interest_rate_pct'].isna().all())
        self.assertTrue(pd.isna(safe_ratio(pd.Series([2.]),pd.Series([0.])).iloc[0]))

    def test_orphan_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unmatched'):
            validate_links(pd.DataFrame({'id':['missing']}),pd.DataFrame({'id':['known']}),'id')

    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)/'raw'
            raw.mkdir()
            for source in (ROOT/'data/raw').glob('*.csv'):
                (raw/source.name).write_bytes(source.read_bytes())
            customers = pd.read_csv(raw/'customers.csv')
            pd.concat([customers,customers.iloc[:1]]).to_csv(raw/'customers.csv',index=False)
            with self.assertRaisesRegex(ValueError,'Duplicate key'):
                build(raw,Path(tmp)/'out',Path(tmp)/'reports')

    def test_reproducible_build_and_unchanged_raw(self):
        raw = ROOT/'data/raw'
        before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob('*.csv')}
        with tempfile.TemporaryDirectory() as tmp:
            out, reports = Path(tmp)/'out',Path(tmp)/'reports'
            build(raw,out,reports)
            pd.testing.assert_frame_equal(self.accounts,pd.read_parquet(out/'accounts.parquet'))
            self.assertEqual((ROOT/'reports/data_audit.json').read_text(),(reports/'data_audit.json').read_text())
        after = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob('*.csv')}
        self.assertEqual(before,after)


if __name__ == '__main__':
    unittest.main()
