
from pathlib import Path

import yaml

from config import settings


# Load agent details from agent.yaml
_yaml_path = Path(__file__).resolve().parent / "agent.yaml"
_yaml_data = yaml.safe_load(_yaml_path.read_text(encoding="utf-8"))

AGENT_NAME = _yaml_data["name"]
AGENT_VERSION = _yaml_data["version"]
ALLOWED_TOOLS = _yaml_data["allowed_tools"]


# Model settings
MODEL_PROVIDER = "gemini"
MODEL_NAME = settings.gemini_strong_model
TEMPERATURE = 0.0
TIMEOUT_SECONDS = 90
MAX_RETRIES = 2


# Approval preparation limits
MAX_GUIDELINES = 15
MAX_GUIDELINE_CHARS = 1500
MAX_REQUIREMENTS = 20
MAX_EXPLANATION_CHARS = 400
MAX_QUOTE_CHARS = 200
MAX_DOCUMENTS = 15
MAX_HUMAN_REVIEW_POINTS = 8
MAX_OUTSTANDING_ITEMS = 15


# Search questions for each insurance line
APPROVAL_QUERY_BY_LINE = {
    "health": (
        "claim approval requirements, medical treatment authorization, "
        "hospitalization benefits, supporting documents and settlement conditions"
    ),
    "private_vehicle": (
        "motor insurance claim approval requirements, vehicle damage assessment, "
        "repair authorization, supporting documents and settlement conditions"
    ),
    "commercial": (
        "commercial insurance claim approval requirements, business loss assessment, "
        "property damage, supporting documents and settlement conditions"
    ),
    "home": (
        "home insurance claim approval requirements, building and contents damage, "
        "supporting documents and settlement conditions"
    ),
}

# Keep the shorter name available for other agent files
QUERIES = APPROVAL_QUERY_BY_LINE


# Requirement verification statuses
REQUIREMENT_STATUSES = [
    "satisfied",
    "not_satisfied",
    "needs_verification",
]


# Final preparation statuses
PREPARATION_STATUSES = [
    "ready_for_human_review",
    "incomplete",
    "needs_verification",
]
