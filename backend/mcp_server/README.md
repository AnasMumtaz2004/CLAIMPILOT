# ClaimPilot MCP integration

## How it is integrated

The existing LangGraph nodes are synchronous and already receive a request/workflow-scoped SQLAlchemy session. To avoid starting a new MCP subprocess for every tool call, specialist agent adapters use `mcp_server.client.call_tool()`. That adapter enforces the relevant agent's `agent.yaml` allowlist and dispatches to `mcp_server.runtime.HANDLERS` using the existing DB session. The standalone FastMCP server registers the *same* handlers and exposes them over MCP stdio for MCP-compatible clients.

This means the running claim workflow and the MCP server share one implementation of every backend operation. The agents do not duplicate SQL, OCR, RAG, or calculation service logic.

## Install

From the `backend` directory (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If the virtual environment is named `.venv`; if yours has another name, activate that environment instead.

## Run the application

Start PostgreSQL and the existing dependencies, then run FastAPI as usual:

```powershell
uvicorn main:app --reload
```

Agent workflows use the integrated in-process adapter automatically; no second server process is needed for normal application use.

## Run the MCP protocol server for an external MCP client

In another terminal, from `backend`:

```powershell
python -m mcp_server.server
```

This uses stdio transport. Configure the MCP client to launch that command with the backend directory as its working directory and the same environment variables as the application.

## Tools exposed

- `get_claim_details`
- `get_customer_policy`
- `search_policy_wording`
- `get_claim_documents`
- `run_document_ocr`
- `extract_document_text`
- `check_claim_completeness`
- `search_claims_guidelines`
- `calculate_claim_amount`
- `get_approval_requirements`

Every tool requires a submitted claim ID (and document ID/query where applicable). The handlers reject draft/missing claims, verify document-to-claim relationships, scope policy wording to the claim's own policy, validate search bounds, and reuse existing services.

## Specialist tools

Each of the five specialist agents has at least two local tools in its own `tools.py`; the Orchestrator also has two coordination tools in `agents/orchestrator/tools.py`. The complete tool registries are checked against each agent's `agent.yaml`; local specialist tools are called by the corresponding graph pipeline.

## Security boundary

The supplied MCP server is intentionally stdio-only and intended for a trusted local MCP client. Do not switch it to a network transport or expose it publicly until MCP client identity is authenticated and mapped to claim-level permissions. The current tool contract has no approve, reject, fraud-declaration, or payment-release operation. Final claim decisions remain with an authorized human Claims Officer through the existing FastAPI decision workflow.
