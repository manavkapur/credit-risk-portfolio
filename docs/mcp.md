# Local MCP server

The official MCP Python SDK exposes four read-only tools: query_portfolio, get_account_summary, list_anomalies and get_model_metrics. Query plans reuse approved metrics, validated dimensions and parameterized SQL. No LLM key is needed; the external client chooses tools. This interface does not inherit dashboard filters or trigger Langfuse model traces. No write/review tool is exposed.

Launch from the repository with `.venv/bin/python -m src.mcp_server`. It waits for MCP JSON-RPC on stdin; use a compatible client rather than typing natural-language questions in the terminal.

Example client configuration (adapt the client's configuration format):

```json
{
  "mcpServers": {
    "credit-risk": {
      "command": "/Users/manavkapur/Documents/ChatGPT/Interview Gen AI/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/Users/manavkapur/Documents/ChatGPT/Interview Gen AI"
    }
  }
}
```

Build datasets first with `python -m src.build_all`. Protocol verification: `python -m unittest tests/test_mcp.py -v`. Tests launch a real stdio subprocess, initialize the connection, discover tools, query the account count, reject an oversized anomaly list and retrieve model metrics.

Local clients launching this process are trusted to read the synthetic portfolio. There is no per-user row authorization or public HTTP endpoint. Do not expose real bank data or remote network transport without authentication, access controls and deployment-specific quotas. Existing LLM request budgets do not apply to these deterministic tools. Connecting a client is a separate installation step; this repository does not automatically register itself with Codex or ChatGPT.
