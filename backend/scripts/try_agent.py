import json
import sys

from agents.document_review import run_document_review_agent
from agents.intake import run_intake_agent
from agents.policy_coverage import run_policy_coverage_agent
from database.connection import SessionLocal

# Every agent that can be tried from the terminal. More are added as they are built
AGENTS = {
    "intake": run_intake_agent,
    "document_review": run_document_review_agent,
    "policy_coverage": run_policy_coverage_agent,
}


def main():
    """Run one agent on one claim with the real model and print the result."""
    if len(sys.argv) != 3 or sys.argv[1] not in AGENTS:
        print("Usage: python -m scripts.try_agent <agent> <claim_id>")
        print("Agents: " + ", ".join(AGENTS))
        return

    agent_name = sys.argv[1]
    claim_id = sys.argv[2]

    db = SessionLocal()
    try:
        result = AGENTS[agent_name](db, claim_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()