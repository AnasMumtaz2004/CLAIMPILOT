from pathlib import Path

import yaml

from config import settings


_yaml_path = Path(__file__).resolve().parent / "agent.yaml"
_yaml_data = yaml.safe_load(_yaml_path.read_text(encoding="utf-8"))

AGENT_NAME = _yaml_data["name"]
AGENT_VERSION = _yaml_data["version"]
ALLOWED_TOOLS = _yaml_data["allowed_tools"]

MODEL_PROVIDER = "gemini"
MODEL_NAME = settings.gemini_strong_model
TEMPERATURE = 0.0
TIMEOUT_SECONDS = 90
MAX_RETRIES = 2

GUIDELINE_RESULTS = 8
MAX_GUIDELINES = 12
MAX_GUIDELINE_CHARS = 1800
MAX_CLAIM_CHARS = 8000
MAX_DOCUMENTS = 30
MAX_FINDING_EXPLANATION = 500
MAX_EVIDENCE_QUOTE = 200

ASSESSMENT_STATUSES = [
    "compliant",
    "concern",
    "needs_more_information",
]

GUIDELINE_QUERY_BY_LINE = {
    "health": "health insurance claim assessment admissibility medical expenses hospitalization bills exclusions limits",
    "private_vehicle": "motor vehicle own damage claim assessment repair estimate depreciation admissibility survey",
    "commercial": "commercial property claim assessment loss valuation underinsurance admissibility evidence",
    "home": "home insurance claim assessment building contents loss valuation admissibility evidence",
}
