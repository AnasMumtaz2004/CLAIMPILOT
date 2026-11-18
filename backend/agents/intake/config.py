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
MODEL_PROVIDER = "groq"
MODEL_NAME = settings.groq_small_model
TEMPERATURE = 0.0
TIMEOUT_SECONDS = 30
MAX_RETRIES = 2

# The event types the agent may choose from, for each insurance line
EVENT_TYPES = {
    "health": ["hospitalization", "day_care_procedure", "outpatient_treatment", "maternity", "accident_injury", "other", "unclear"],
    "private_vehicle": ["collision", "theft", "fire", "natural_calamity", "third_party_liability", "vandalism", "other", "unclear"],
    "commercial": ["fire", "burglary", "water_damage", "machinery_breakdown", "stock_loss", "other", "unclear"],
    "home": ["fire", "burglary", "water_damage", "storm", "structural_damage", "other", "unclear"],
}

# Limits for the text the model returns
MAX_SUMMARY_CHARS = 300
MAX_INCONSISTENCIES = 5
MAX_ITEM_CHARS = 200
