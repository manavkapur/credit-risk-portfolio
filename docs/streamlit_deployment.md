# Streamlit Community Cloud + PostgreSQL

1. Sign in at share.streamlit.io and connect the GitHub account. Create an app from manavkapur/credit-risk-portfolio, branch main, entry point app/app.py. Select Python 3.11 in advanced settings.
2. Create a managed PostgreSQL database in an account you control (for example Neon or Supabase). Copy its PostgreSQL connection string, including database/user/password and TLS parameters. Use a pooled connection endpoint if required by the provider. Never commit the connection string.
3. In Streamlit advanced settings / secrets, set DATABASE_URL, OPENAI_API_KEY and optionally LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL. Use top-level TOML string entries. DATABASE_URL enables PostgreSQL; tables are created automatically by the app's database role. Keep these secrets out of Git and chat.
4. Deploy. First launch builds the analytical data, models and anomalies from the included synthetic CSVs. This can take a few minutes. A build failure must be investigated using hosting logs.
5. Verify anonymous access, overall default rate 16.10%, a new live Q&A question and Langfuse delivery. Save an anomaly decision, reboot the Streamlit app, and verify history remains. Confirm the app displays managed PostgreSQL storage configured.

PostgreSQL keeps append-only reviews plus Q&A cache and quota rows. Quota admission uses a transaction-scoped advisory lock shared across app connections. SSL is required. PostgreSQL configuration errors fail rather than silently falling back to disposable local files. Tables use the database's default schema. Use a dedicated database/role for this app and keep the role credentials private. No existing SQLite review history is migrated automatically.

The local SQLite tests do not prove PostgreSQL connectivity or hosted persistence. Those checks remain pending until a real DATABASE_URL is configured. Free-tier sleep, storage limits and retention depend on the chosen provider; verify availability through the required 14-day review period.
