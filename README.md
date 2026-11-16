# Credit Risk Portfolio

Data foundation for the credit-risk case study. Python **3.11** (tested with 3.11.14).
Data preparation, analytics, models, anomaly detection, the dashboard and the Ask the Portfolio workflow are implemented.

Launch the dashboard from this directory:

```bash
.venv/bin/streamlit run app/app.py
```

Open http://localhost:8501. Portfolio filters apply to all views. Account details shows model scores, baseline drivers and payment history. Anomaly review supports confirm/dismiss, notes, append-only local persistence and history export. Set `REVIEW_DB_PATH` to durable storage for hosting.

## Ask the Portfolio

## Local MCP integration

Run `.venv/bin/python -m src.mcp_server` from an MCP client to expose four read-only portfolio tools. See `docs/mcp.md` for the client configuration, protocol tests and access boundary. The dashboard continues to call its functions directly.

Rate limits, daily request/token reservation budgets, adversarial input screening and one-hour exact-result caching are implemented. See `docs/qa_guardrails.md` for configuration and limits. Set provider-side spending controls separately. Store QA_DB_PATH on durable storage to preserve quotas across restarts.

Set `OPENAI_API_KEY` in your environment or Streamlit secrets, or enter it in the masked session-only field in the Ask the Portfolio tab. Never commit a key. `.env.example` lists names; `.env` is not automatically loaded. Optional `OPENAI_MODEL` defaults to `gpt-4o-mini`; model access must be verified with your API account. Without a key the Ask button is disabled and other views work normally.

`src/portfolio_qa.py` uses LangGraph to interpret a question into a Pydantic plan, validate allowed dimensions/metrics/filter values, execute parameterized DuckDB SQL and render exact numerical answers. The LLM receives question text and category vocabulary only. No arbitrary model-generated SQL executes. Evidence, scope and plan are visible for human review. Unsupported questions are declined by the planner; interpretation can still be wrong, so inspect the plan. No conversation memory or semantic answer cache is used. API calls have a timeout and bounded retry. Reference-query and graph tests use an injected planner; live LLM quality requires an API key and separate verification.

## Setup and run

With Python 3.11 available, run these three commands from the project directory:

```bash
python -m pip install -r requirements.txt
python -m src.build_all
python -m streamlit run app/app.py
```

Run Step 2 after the data build:

```bash
.venv/bin/python -m src.train_models
```

Step 3 builds anomaly flags and explanations:

```bash
.venv/bin/python -m src.anomalies
```

See `docs/anomaly_detection.md` for triggers, false positives/negatives and review persistence. `src/reviews.py` saves append-only decisions in SQLite; durable hosted storage must be configured at deployment.

This generates five portfolio insights, dimension summaries, grouped train/validation/test splits, logistic regression and histogram gradient boosting models, evaluation metrics, importance tables, calibration/ROC data and account scores. Run tests after both builds. Models fit only on training rows; training scores are explicitly marked in-sample. No API key is needed.

For initial import from the supplied folder, use:

```bash
.venv/bin/python -m src.build_data --source '/Users/manavkapur/Downloads/Case 2/files (10)'
```

The raw files are copied without modification. A changed existing raw file is never overwritten automatically. No API keys or external services are needed for Step 1.

## Where to look

- `src/build_data.py`: ingestion, validation, aggregates, reconciliation and reporting.
- `docs/data_decisions.md`: join logic, missingness decisions, feature definitions and timing limitations.
- `reports/data_audit.md`: generated human-readable findings.
- `reports/feature_manifest.json`: feature types and exclusions.
- `data/processed/`: generated Parquet datasets.
- `tests/test_data.py`: invariant, failure-path and reproducibility checks.
- `src/analytics.py`: dimension profiles, cross-segment insights and relative-month/cohort summaries.
- `src/train_models.py`: grouped model training, selection, evaluation and explanations.
- `reports/portfolio_insights.md`: five findings and their business implications.
- `reports/model_evaluation.md`: held-out metrics and model limitations.
- `reports/models/`: detailed evaluation, split membership, importance, ROC and calibration files.
- `artifacts/`: locally saved models (regenerate with Step 2).
- `data/processed/account_scores.parquet`: model scores, split and in-sample flags.
- `data/processed/baseline_account_drivers.parquet`: baseline-only local coefficient contributions.
- `docs/model_monitoring.md`: future monitoring and deployment requirements.
- `docs/architecture.pdf` and `docs/solution_overview.pdf`: required one-page submission documents.
- `docs/demo_script.md`: four-minute recording outline.
- `docs/submission_checklist.md`: hosting, durable storage, links and acceptance checks.
- `Dockerfile`: optional container deployment; mount durable storage at /data.

Do not sum customer-level bureau balances repeated across loans. Latest recorded balances are not synchronized calendar-date exposure. The default label lacks timing, so downstream modelling must be described as retrospective.
