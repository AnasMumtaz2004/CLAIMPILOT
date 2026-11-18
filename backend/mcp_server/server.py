"""ClaimPilot MCP stdio server.

Run from backend with: python -m mcp_server.server
The default stdio transport is intended for a trusted local MCP client. Do not
expose this process over a network without adding authenticated identity and
claim-level authorization at the transport boundary.
"""
from mcp.server.fastmcp import FastMCP
from database.connection import SessionLocal
from mcp_server import runtime

mcp = FastMCP("ClaimPilot MCP Server")


def _invoke(name: str, **kwargs):
    db = SessionLocal()
    try:
        return runtime.call_tool(db, name, **kwargs)
    finally:
        db.close()


@mcp.tool()
def get_claim_details(claim_id: str) -> dict:
    """Return submitted claim facts and its linked policy schedule."""
    return _invoke("get_claim_details", claim_id=claim_id)


@mcp.tool()
def get_customer_policy(claim_id: str) -> dict:
    """Return the verified policy schedule linked to a submitted claim."""
    return _invoke("get_customer_policy", claim_id=claim_id)


@mcp.tool()
def search_policy_wording(claim_id: str, query: str, top_k: int = 6) -> list:
    """Search only the customer policy attached to this claim."""
    return _invoke("search_policy_wording", claim_id=claim_id, query=query, top_k=top_k)


@mcp.tool()
def get_claim_documents(claim_id: str) -> dict:
    """List documents attached to a submitted claim."""
    return _invoke("get_claim_documents", claim_id=claim_id)


@mcp.tool()
def run_document_ocr(claim_id: str, document_id: str) -> str:
    """Run OCR only for a document belonging to the supplied claim."""
    return _invoke("run_document_ocr", claim_id=claim_id, document_id=document_id)


@mcp.tool()
def extract_document_text(claim_id: str, document_id: str) -> dict:
    """Return OCR pages for a document belonging to the supplied claim."""
    return _invoke("extract_document_text", claim_id=claim_id, document_id=document_id)


@mcp.tool()
def check_claim_completeness(claim_id: str) -> dict:
    """Return deterministic missing-field and missing-document checks."""
    return _invoke("check_claim_completeness", claim_id=claim_id)


@mcp.tool()
def search_claims_guidelines(claim_id: str, query: str, top_k: int = 8) -> list:
    """Search internal claims-handling guidelines for this claim's domain."""
    return _invoke("search_claims_guidelines", claim_id=claim_id, query=query, top_k=top_k)


@mcp.tool()
def calculate_claim_amount(claim_id: str) -> dict:
    """Run the deterministic calculation service for the claim's submitted line items."""
    return _invoke("calculate_claim_amount", claim_id=claim_id)


@mcp.tool()
def get_approval_requirements(claim_id: str, query: str, top_k: int = 8) -> list:
    """Search internal approval requirements for this claim's domain."""
    return _invoke("get_approval_requirements", claim_id=claim_id, query=query, top_k=top_k)


if __name__ == "__main__":
    mcp.run(transport="stdio")
