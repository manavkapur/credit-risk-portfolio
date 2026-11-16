# Submission handoff

## Publishing still required

1. Create a GitHub repository and push this project; no secrets. It must match the deployed app.
2. Deploy Streamlit using app/app.py and Python 3.11, or deploy the Dockerfile to Hugging Face Spaces. Set OPENAI_API_KEY in server secrets. First launch automatically builds missing datasets.
3. Configure genuinely durable review storage: a persistent volume with REVIEW_DB_PATH on Docker hosting, or external database integration. Streamlit Community Cloud's local filesystem alone does not guarantee persistence across redeployment. The current implementation uses SQLite and needs a durable filesystem.
4. Verify anonymous public access, working live LLM requests, filters and confirm/dismiss after restart. Keep app and API funding available for 14 days after submission.
5. Record a 3-5 minute video using docs/demo_script.md; upload and verify reviewer access.
6. Send one email with dashboard, GitHub repository and video links. No zip attachment. Both one-page PDFs are in docs/.

## Live smoke checks

All filters: 14,685 accounts; observed defaults 2,364 / 14,685 = 16.10%. Highest loan-type default rate: Mortgage, 353 / 1,432 = 24.65%. South filter: 3,600 accounts. Ask next-year forecast: decline. Confirm/dismiss an anomaly, restart the app, inspect retained history.

## Status

Local app and automated tests exist. One live overall-default-rate API call was verified. No hosted URL, remote repository or recorded video has yet been created. Do not present this checklist as proof of hosted acceptance.
