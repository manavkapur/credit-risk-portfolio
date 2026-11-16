"""Run from repository root: streamlit run app/app.py."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import os
import pandas as pd
import plotly.express as px
import streamlit as st
from src.build_data import ROOT
from src.analytics import add_bands, summarize
from src.reviews import read_reviews, save_review

st.set_page_config(page_title='Credit Risk Portfolio',page_icon='📊',layout='wide')
for name in ['DATABASE_URL','OPENAI_API_KEY','LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY','LANGFUSE_BASE_URL']:
    if not os.getenv(name):
        try:
            if st.secrets.get(name):
                os.environ[name]=st.secrets[name]
        except Exception:
            pass


@st.cache_data
def load_data(version):
    accounts = pd.read_parquet(ROOT/'data/processed/accounts.parquet')
    scores = pd.read_parquet(ROOT/'data/processed/account_scores.parquet')
    anomalies = pd.read_parquet(ROOT/'data/processed/anomalies.parquet')
    d = accounts.merge(scores.drop(columns=['customer_id','target_default']),on='account_id',validate='one_to_one')
    d = d.merge(anomalies.drop(columns=['customer_id','loan_type','employment_type']),on='account_id',validate='one_to_one')
    return add_bands(d),pd.read_parquet(ROOT/'data/processed/repayments_monthly.parquet'),pd.read_parquet(ROOT/'data/processed/baseline_account_drivers.parquet')


required = ['accounts','account_scores','anomalies','repayments_monthly','baseline_account_drivers']
if any(not (ROOT/f'data/processed/{name}.parquet').exists() for name in required):
    import subprocess
    with st.spinner('Preparing portfolio data and models for the first launch…'):
        process = subprocess.run([sys.executable,'-m','src.build_all'],cwd=ROOT,capture_output=True,text=True)
    if process.returncode:
        st.error('Initial build failed. Run python -m src.build_all locally or inspect hosting logs.')
        st.stop()
version = tuple((ROOT/f'data/processed/{name}.parquet').stat().st_mtime_ns for name in required)
d,monthly,drivers = load_data(version)
st.title('Credit Risk Portfolio')
st.caption('Synthetic portfolio • USD • Historical analysis and analyst review')
st.info('Scores describe retrospective default patterns. Default dates and prediction horizons are unavailable; scores are not validated future probabilities of default.')
with st.sidebar:
    st.header('Portfolio filters')
    filtered = d.copy()
    for col,label in [('region','Region'),('loan_type','Loan type'),('employment_type','Employment')]:
        options = sorted(d[col].unique())
        chosen = st.multiselect(label,options,default=options)
        filtered = filtered.loc[filtered[col].isin(chosen)]
    st.caption(f'{len(filtered):,} of {len(d):,} accounts')
    st.caption('Filters apply to all three views.')
if filtered.empty:
    st.warning('No accounts match these filters. Select at least one value in each filter.')
    st.stop()
view = st.radio("View",['Portfolio','Account details','Anomaly review','Ask the Portfolio'],horizontal=True,key='active_view')
m = monthly.loc[monthly.account_id.isin(filtered.account_id)]
if view == 'Portfolio':
    cols = st.columns(4)
    for col,label,value in zip(cols,['Accounts','Customers','Observed default rate','Original lending'],
        [f'{len(filtered):,}',f'{filtered.customer_id.nunique():,}',f'{filtered.target_default.mean():.2%}',f'${filtered.loan_amount.sum():,.0f}']):
        col.metric(label,value)
    st.caption(f'Latest recorded balances: ${filtered.latest_outstanding_balance.sum():,.0f}. These balances are from different loan-age dates, not a synchronized exposure snapshot.')
    dimension = st.selectbox('Compare portfolio by',['loan_type','income_band','employment_type','region','age_band'])
    summary = summarize(filtered,[dimension])
    summary[dimension] = summary[dimension].astype(str)
    chart = px.bar(summary,x=dimension,y='default_rate',hover_data=['accounts','defaults','original_loan_amount'],
                   labels={'default_rate':'Observed default rate',dimension:dimension.replace('_',' ').title()})
    chart.update_yaxes(tickformat='.0%')
    st.plotly_chart(chart,use_container_width=True)
    st.dataframe(summary,use_container_width=True,hide_index=True)
    cross = summarize(filtered,['income_band','employment_type'])
    cross['income_band'] = cross.income_band.astype(str)
    st.subheader('Income and employment')
    st.dataframe(cross,use_container_width=True,hide_index=True)
    st.subheader('Repayment by loan age')
    m = monthly.loc[monthly.account_id.isin(filtered.account_id)]
    trend = m.groupby('payment_month').agg(mean_dpd=('days_past_due','mean'),accounts=('account_id','nunique')).reset_index()
    st.plotly_chart(px.line(trend,x='payment_month',y='mean_dpd',markers=True,hover_data=['accounts'],
        labels={'payment_month':'Month since origination','mean_dpd':'Mean days past due'}),use_container_width=True)
    st.caption('Relative loan-age trend, not calendar-time default incidence.')
    st.download_button('Download filtered portfolio',filtered.drop(columns=['reasons_json']).to_csv(index=False),'portfolio.csv','text/csv')
if view == 'Account details':
    selected = st.selectbox('Loan account',filtered.account_id.tolist())
    row = filtered.set_index('account_id').loc[selected]
    cols = st.columns(3)
    cols[0].metric('Model score',f'{row.risk_score:.3f}')
    cols[1].metric('Review priority',row.review_priority)
    cols[2].metric('Latest recorded balance',f'${row.latest_outstanding_balance:,.0f}')
    st.caption(f'Model: {row.selected_model}; partition: {row.split}; score scope: {row.score_scope}. Elevated means above an illustrative validation-based review threshold.')
    st.dataframe(pd.DataFrame({'Field':['Customer','Product','Region','Employment','Annual income','Observed default label'],
        'Value':[row.customer_id,row.loan_type,row.region,row.employment_type,f'${row.annual_income:,.0f}',str(row.target_default)]}),hide_index=True)
    st.subheader('Baseline model drivers')
    st.caption('Top absolute log-odds contributions to logistic regression; positive pushes the baseline score upward. Associations are not causal explanations.')
    st.dataframe(drivers.loc[drivers.account_id.eq(selected)].drop(columns='account_id'),hide_index=True,use_container_width=True)
    history = m.loc[m.account_id.eq(selected)]
    st.plotly_chart(px.line(history,x='payment_month',y='days_past_due',markers=True),use_container_width=True)
    st.dataframe(history[['payment_month','emi_due','emi_paid','days_past_due','payment_status']],hide_index=True)
if view == 'Anomaly review':
    st.subheader('Accounts requiring investigation')
    st.write('Triggered after each data refresh: worsening payments, unusual peer utilization, or an unusual combination detected by Isolation Forest.')
    st.caption('False positive: legitimate unusual behaviour is flagged. False negative: problematic unusual behaviour is missed. Analyst review is required; anomaly recall is unknown without labelled outcomes.')
    try:
        reviews = read_reviews()
    except Exception:
        st.error('Review storage is unavailable. Check REVIEW_DB_PATH and filesystem permissions.')
        st.stop()
    latest = reviews.drop_duplicates(['account_id','anomaly_version'])
    queue = filtered.loc[filtered.flagged].merge(latest[['account_id','anomaly_version','decision']],
        on=['account_id','anomaly_version'],how='left',validate='one_to_one')
    queue['decision'] = queue.decision.fillna('pending')
    status = st.selectbox('Review status',['All','pending','confirm','dismiss'])
    if status != 'All':
        queue = queue.loc[queue.decision.eq(status)]
    queue = queue.sort_values('anomaly_score',ascending=False)
    st.write(f'{len(queue):,} flagged accounts in this view')
    st.dataframe(queue[['account_id','loan_type','anomaly_score','reason_count','decision']],hide_index=True,use_container_width=True)
    if not queue.empty:
        review_id = st.selectbox('Account to review',queue.account_id.tolist())
        flagged = queue.set_index('account_id').loc[review_id]
        for reason in json.loads(flagged.reasons_json):
            st.write('• '+reason)
        st.caption('Inspect this account’s payment details in Account details before recording a decision.')
        with st.form('review_form'):
            reviewer = st.text_input('Reviewer name',value='Demo analyst')
            decision = st.radio('Decision',['confirm','dismiss'],horizontal=True)
            note = st.text_area('Review note')
            submitted = st.form_submit_button('Save review decision')
        if submitted:
            if not reviewer.strip():
                st.error('Enter a reviewer name.')
            else:
                try:
                    save_review(review_id,flagged.anomaly_version,decision,note,reviewer.strip())
                    st.success('Decision saved. Review history retains previous decisions.')
                    st.rerun()
                except Exception:
                    st.error('Decision could not be saved. Check review storage configuration.')
    st.caption(('Managed PostgreSQL storage configured.' if os.getenv('DATABASE_URL') else 'Local SQLite storage; hosted persistence needs DATABASE_URL.')+' Reviewer names are demo labels.')
    st.download_button('Download review history',reviews.to_csv(index=False),'review_history.csv','text/csv')
    with st.expander('Review history'):
        st.dataframe(reviews,hide_index=True,use_container_width=True)
if view == 'Ask the Portfolio':
    from src.portfolio_qa import ask
    from src.qa_controls import GuardrailError
    import uuid
    if 'qa_actor' not in st.session_state:
        st.session_state['qa_actor']=str(uuid.uuid4())
    st.subheader('Ask the Portfolio')
    for name in ['LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY','LANGFUSE_BASE_URL']:
        if not os.getenv(name):
            try:
                if st.secrets.get(name):
                    os.environ[name]=st.secrets[name]
            except Exception:
                pass
    tracing=bool(os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY'))
    st.caption('Langfuse: '+('configured at '+os.getenv('LANGFUSE_BASE_URL','https://cloud.langfuse.com') if tracing else 'disabled — project credentials are not available to this server process'))
    if tracing and st.button('Check Langfuse connection'):
        try:
            from langfuse import get_client
            if get_client().auth_check():
                st.success('Langfuse authentication succeeded. Submit a new question, then open Tracing in the same project.')
            else:
                st.error('Langfuse authentication failed. Check keys and project-region URL.')
        except Exception:
            st.error('Cannot reach Langfuse. Check keys, base URL and network access.')
    st.write('Ask about observed default rates, account/customer counts, original lending, latest recorded balances or average model scores. Current sidebar filters apply.')
    st.caption('Examples: Which loan type has the highest default rate? • How many customers are in the South? • Show original lending by region.')
    st.caption('Triggered when you submit a question. False positive: a question is misinterpreted into the wrong query. False negative: an answerable question is declined. Verify the interpreted plan, filters and evidence before using the answer.')
    try:
        configured_key = st.secrets.get('OPENAI_API_KEY','')
    except Exception:
        configured_key = ''
    configured_key = configured_key or os.getenv('OPENAI_API_KEY','')
    key = configured_key or st.text_input('OpenAI API key',type='password',help='Used in this session; never written to the repository.')
    if not key:
        st.warning('Set OPENAI_API_KEY in server secrets or enter a key above to enable LLM questions. Portfolio and review features remain available.')
    st.caption('The LLM receives your question and allowed category values. Account records and computed financial figures stay in the app; answers are rendered directly from SQL results.')
    with st.form('portfolio_question'):
        question = st.text_input('Question',max_chars=2000)
        submit = st.form_submit_button('Ask',disabled=not bool(key))
    if submit:
        try:
            with st.spinner('Interpreting question and checking portfolio data…'):
                result = ask(question,filtered,key,os.getenv('OPENAI_MODEL','gpt-4o-mini'),actor=st.session_state['qa_actor'])
            st.session_state['qa_result'] = result
            st.session_state['qa_question'] = question
        except GuardrailError as exc:
            st.session_state.pop('qa_result',None)
            st.warning(str(exc))
        except Exception:
            st.session_state.pop('qa_result',None)
            st.error('The question could not be answered. Check the API key/model and connection, or rephrase using a supported metric and dimension. No answer has been generated.')
    if 'qa_result' in st.session_state:
        result = st.session_state['qa_result']
        st.caption('Answer source: '+('cache — no new generation trace' if result.get('cache_hit') else 'new query execution'))
        st.write('Question: '+st.session_state['qa_question'])
        st.write(result['answer'])
        st.caption(f"Source: {result['source']}. Scope at query time: {result['scope_accounts']:,} accounts; fingerprint {result['scope_fingerprint']}. Re-submit after changing filters.")
        if result['rows']:
            st.dataframe(pd.DataFrame(result['rows']),hide_index=True)
        with st.expander('Verify interpretation and SQL evidence'):
            st.json(result['plan'])
            if result['sql']:
                st.code(result['sql'],language='sql')
                st.write('Bound parameters:',result.get('parameters',[]))
