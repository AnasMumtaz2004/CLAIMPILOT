from pathlib import Path

import yaml

from config import settings

# Name, version and tools come from agent.yaml, so they are written in one place only
_yaml_path = Path(__file__).resolve().parent / "agent.yaml"
_yaml_data = yaml.safe_load(_yaml_path.read_text(encoding="utf-8"))

AGENT_NAME = _yaml_data["name"]
AGENT_VERSION = _yaml_data["version"]
ALLOWED_TOOLS = _yaml_data["allowed_tools"]

# Model settings. The model name comes from the main settings
MODEL_PROVIDER = "gemini"
MODEL_NAME = settings.gemini_strong_model
TEMPERATURE = 0.0
TIMEOUT_SECONDS = 90
MAX_RETRIES = 2

# The topics the agent must give a finding for, with a short description for the model
TOPICS = [
    ("event_coverage", "Is the reported event or treatment covered by the policy?"),
    ("waiting_period", "Does any waiting period apply, and is it over on the date of loss?"),
    ("exclusions", "Does any exclusion apply to this event?"),
    ("sub_limits", "Does any sub-limit, cap or depreciation rule apply?"),
    ("conditions", "Are there claim conditions, such as time limits, reports or documents?"),
    ("deductible_and_copay", "Which deductible, excess or co-payment rules apply?"),
]

TOPIC_NAMES = []
for _topic, _description in TOPICS:
    TOPIC_NAMES.append(_topic)

ASSESSMENTS = ["supports_coverage", "limits_coverage", "needs_more_information"]
ADD_ON_STATUSES = ["selected", "not_selected", "not_shown"]

# One search question for each topic and insurance line. {event} is replaced by a short event text
SCHEDULE_QUERY = "policy schedule sum insured premium add-ons selected policy period"

QUERIES = {
    "health": {
        "event_coverage": "{event} covered hospitalization treatment benefits",
        "waiting_period": "waiting period for illness surgery and pre-existing disease",
        "exclusions": "permanent exclusions what is not covered",
        "sub_limits": "sub-limits room rent and procedure limits",
        "conditions": "claim conditions intimation documents time limit",
        "deductible_and_copay": "co-payment and deductible rules",
    },
    "private_vehicle": {
        "event_coverage": "{event} own damage cover accident",
        "waiting_period": "waiting period and policy commencement",
        "exclusions": "exclusions not covered drunk driving invalid licence wear and tear",
        "sub_limits": "limits depreciation on parts and sub-limits",
        "conditions": "claim conditions intimation police report survey",
        "deductible_and_copay": "compulsory deductible and voluntary deductible",
    },
    "commercial": {
        "event_coverage": "{event} fire and allied perils cover",
        "waiting_period": "waiting period and policy commencement",
        "exclusions": "exclusions not covered",
        "sub_limits": "sub-limits limits stock and condition of average",
        "conditions": "claim conditions intimation documents",
        "deductible_and_copay": "deductible and excess",
    },
    "home": {
        "event_coverage": "{event} building and contents cover",
        "waiting_period": "waiting period and policy commencement",
        "exclusions": "exclusions not covered",
        "sub_limits": "sub-limits limits valuables and contents",
        "conditions": "claim conditions intimation documents",
        "deductible_and_copay": "deductible and excess",
    },
}

# Search and size limits
RESULTS_PER_QUERY = 3
MAX_CLAUSES = 21
MAX_CLAUSE_CHARS_IN_PROMPT = 1500
MAX_EXPLANATION_CHARS = 400
MAX_QUOTE_CHARS = 200
MAX_EVENT_TEXT_CHARS = 60
MAX_ADD_ONS = 15