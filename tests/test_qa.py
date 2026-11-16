import unittest
import pandas as pd
from pydantic import ValidationError
from src.portfolio_qa import QueryPlan,execute_plan,ask
from src.analytics import add_bands
from src.build_data import ROOT


class QATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=add_bands(pd.read_parquet(ROOT/'data/processed/accounts.parquet'))
        cls.d['risk_score']=.2

    def plan(self,**kwargs):
        return dict(supported=True,reason='',metric='default_rate',group_by=None,filters=[],order='highest',limit=1,**kwargs)

    def test_reference_questions(self):
        cases=[('What is the overall observed default rate?','default_rate',None,[]),
               ('Which loan type has the highest default rate?','default_rate','loan_type',[]),
               ('How many customers are in the South?','customers',None,[{'column':'region','value':'South'}]),
               ('Show original lending by region','original_lending','region',[]),
               ('How many accounts?','accounts',None,[])]
        for question,metric,group,filters in cases:
            plan=self.plan();plan.update(metric=metric,group_by=group,filters=filters)
            result=ask(question,self.d,'',planner=lambda q:plan)
            subset=self.d
            for f in filters:
                subset=subset.loc[subset[f['column']].eq(f['value'])]
            if metric=='default_rate':
                expected=subset.groupby(group).target_default.mean().max() if group else subset.target_default.mean()
            elif metric=='customers': expected=subset.customer_id.nunique()
            elif metric=='original_lending': expected=subset.groupby(group).loan_amount.sum().max()
            else: expected=len(subset)
            self.assertAlmostEqual(result['rows'][0]['value'],expected,delta=max(1e-9,abs(expected)*1e-12))

    def test_abstention_and_validation(self):
        plan=self.plan();plan.update(supported=False,reason='Future default timing unavailable')
        self.assertIsNone(execute_plan(plan,self.d)['sql'])
        plan=self.plan();plan['filters']=[{'column':'region','value':"South'; DROP TABLE portfolio;--"}]
        with self.assertRaises(ValueError):execute_plan(plan,self.d)
        plan=self.plan();plan['metric']='arbitrary SQL'
        with self.assertRaises(ValidationError):QueryPlan.model_validate(plan)

    def test_scope_and_missing_key(self):
        subset=self.d.loc[self.d.region.eq('South')]
        result=execute_plan(self.plan(),subset)
        self.assertAlmostEqual(result['rows'][0]['value'],subset.target_default.mean())
        with self.assertRaises(ValueError):ask('How many accounts?',subset,'')
