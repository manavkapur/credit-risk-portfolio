# Integrated AI stack

Runtime entry point is `src/ai_integrations.py`, imported by portfolio_qa.py.

- LiteLLM 1.109.1 routes the structured query-plan call. No proxy server, provider fallback or LiteLLM budget enforcement is deployed. Existing transactional local quotas remain authoritative.
- NeMo Guardrails 0.24.1 executes a deterministic input Colang rail. Its registered action invokes a Guardrails AI 0.11.0 custom validator for the existing input policy. No safety-model-based jailbreak detector or PII model is claimed.
- Guardrails AI also validates the generated plan against the Pydantic schema, without repair/reasks. Failed validation blocks SQL execution. Vendor metrics collection is disabled on these guards.
- Langfuse 5.2.0 records generation metadata and token usage when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are present. Configure LANGFUSE_BASE_URL for your project region. Current instrumentation excludes raw prompts, account records, answers and credentials. Trace delivery still needs verification with a configured Langfuse project.

The integrated live overall-default-rate request returned 16.10% (2,364/14,685). Tests also exercise deterministic query execution and adversarial input screening. Framework use does not prove general jailbreak immunity or semantic correctness. Exact cache hits bypass generation and therefore do not create generation traces.

Add Langfuse keys to the server environment (not Git). An OpenAI key is sufficient for normal questions when Langfuse is unconfigured. The app currently reads Langfuse configuration from environment variables, not Streamlit secrets. Hosted quotas/reviews still require durable storage. The submission PDFs predate these integrations and must be regenerated with updated architecture before publication.
