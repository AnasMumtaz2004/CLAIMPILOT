"""In-process MCP tool adapter used by the existing synchronous LangGraph nodes.

It dispatches through the exact handler registry exposed by server.py, avoiding
one subprocess/session per tool call. Agent YAML allowlists are enforced before
a handler is invoked. A separate external MCP client can spawn server.py over
stdio and discover the same tools using the MCP protocol.
"""
from pathlib import Path
import yaml
from mcp_server.runtime import call_tool as _call_shared_tool

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_AGENT_TOOL_ALIASES = {
    ("document_review", "run_document_ocr"): "run_ocr",
    ("document_review", "extract_document_text"): "get_document_text",
    ("approval_preparation", "get_approval_requirements"): "search_approval_requirements",
}


def call_tool(db, name: str, *, agent: str, **arguments):
    if agent not in {"intake", "document_review", "policy_coverage", "claim_assessment", "approval_preparation"}:
        raise ValueError("Unknown specialist agent.")
    config_path = _BACKEND_ROOT / "agents" / agent / "agent.yaml"
    with config_path.open("r", encoding="utf-8") as stream:
        allowed = set(yaml.safe_load(stream).get("allowed_tools", []))
    allowed_name = _AGENT_TOOL_ALIASES.get((agent, name), name)
    if allowed_name not in allowed:
        raise PermissionError(f"Agent '{agent}' is not allowed to call '{allowed_name}'.")
    return _call_shared_tool(db, name, **arguments)
