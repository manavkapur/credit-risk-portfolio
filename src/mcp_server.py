"""Local read-only MCP interface. Run: python -m src.mcp_server."""
import json
import pandas as pd
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from src.build_data import ROOT
from src.analytics import add_bands
from src.portfolio_qa import QueryPlan, execute_plan

mcp=MCPServer('Credit Risk Portfolio')


def accounts():
    data=add_bands(pd.read_parquet(ROOT/'data/processed/accounts.parquet'))
    scores=pd.read_parquet(ROOT/'data/processed/account_scores.parquet')
    return data.merge(scores[['account_id','risk_score','score_scope']],on='account_id',validate='one_to_one')


@mcp.tool()
def query_portfolio(plan: QueryPlan) -> dict:
    """Compute an approved aggregate over the full synthetic portfolio. No dashboard filters are inherited. No arbitrary SQL or natural-language interpretation. Default rates are retrospective."""
    result=execute_plan(plan,accounts())
    result['source']='local account-level Parquet; full portfolio with explicit plan filters'
    return result


@mcp.tool()
def get_account_summary(account_id: str) -> dict:
    """Read one synthetic account score and repayment summary. Score is not a validated future PD."""
    d=accounts()
    row=d.loc[d.account_id.eq(account_id)]
    if row.empty:
        raise ToolError('Unknown account ID')
    fields=['account_id','loan_type','region','loan_amount','latest_outstanding_balance','risk_score',
            'score_scope','repayment_dpd_mean','repayment_missed_rate']
    return {'account':json.loads(row[fields].to_json(orient='records'))[0],
            'limitation':'Retrospective synthetic-data score; latest balances are not a synchronized snapshot.'}


@mcp.tool()
def list_anomalies(limit: int = 20) -> dict:
    """Return up to 100 flagged synthetic accounts with evidence, ranked by anomaly score. Read-only; cannot save decisions."""
    if not 1<=limit<=100:
        raise ToolError('Limit must be between 1 and 100')
    d=pd.read_parquet(ROOT/'data/processed/anomalies.parquet')
    flagged=d.loc[d.flagged].sort_values('anomaly_score',ascending=False).head(limit)
    rows=json.loads(flagged[['account_id','anomaly_score','reasons_json','anomaly_version']].to_json(orient='records'))
    for row in rows:
        row['reasons']=json.loads(row.pop('reasons_json'))
    return {'accounts':rows,'limitation':'Flags require analyst investigation; no measured anomaly recall.'}


@mcp.tool()
def get_model_metrics() -> dict:
    """Read saved held-out model metrics and limitations; no training or mutation."""
    result=json.loads((ROOT/'reports/models/evaluation.json').read_text())
    return {'selected_model':result['selected_model'],'models':result['models'],'limitations':result['limitations']}


if __name__=='__main__':
    mcp.run(transport='stdio')
