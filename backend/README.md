
## MCP + specialist-agent integration

The ClaimPilot MCP implementation is in `mcp_server/`. All six agents (the Orchestrator and five specialists) retain at least two agent-specific tools and call shared backend capabilities through the allowlist-enforcing adapter in `mcp_server/client.py`. All shared handlers are implemented once in `mcp_server/runtime.py` and are exposed through the FastMCP stdio server in `mcp_server/server.py`. See `mcp_server/README.md` for setup and execution details.
