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
TIMEOUT_SECONDS = 60
MAX_RETRIES = 2

# Text with an OCR confidence below this needs a person to check it (guidelines, section 9)
OCR_REVIEW_THRESHOLD = 85.0

# Limits that keep one run small
MAX_DOCUMENTS = 10
MAX_TEXT_CHARS = 6000
MAX_QUOTE_CHARS = 200
MAX_FACTS = 25
MAX_LINE_ITEMS = 60
MAX_NOTES = 5

# How close two values must be to count as the same
AMOUNT_TOLERANCE = 1.0
DATE_TOLERANCE_DAYS = 1

# The fields to extract from each type of document, with a short description for the model
FIELDS_BY_DOC_TYPE = {
    "bill": [
        ("bill_number", "The bill number"),
        ("patient_name", "Name of the patient"),
        ("hospital_name", "Name of the hospital"),
        ("admission_date", "Date of admission"),
        ("discharge_date", "Date of discharge"),
        ("total_amount", "The final total or net amount of the bill"),
    ],
    "discharge_summary": [
        ("patient_name", "Name of the patient"),
        ("hospital_name", "Name of the hospital"),
        ("diagnosis", "Final diagnosis"),
        ("procedure", "Treatment or procedure done"),
        ("admission_date", "Date of admission"),
        ("discharge_date", "Date of discharge"),
    ],
    "prescription": [
        ("patient_name", "Name of the patient"),
        ("prescriber_name", "Name of the doctor"),
        ("document_date", "Date of the prescription"),
    ],
    "estimate": [
        ("vehicle_registration", "Vehicle registration number, if it is a vehicle estimate"),
        ("property_address", "Property address, if it is a property estimate"),
        ("owner_name", "Name of the owner"),
        ("document_date", "Date of the estimate"),
        ("total_amount", "The total of the estimate"),
    ],
    "police_report": [
        ("report_number", "FIR or report number"),
        ("incident_date", "Date of the incident"),
        ("incident_location", "Place of the incident"),
        ("complainant_name", "Name of the complainant"),
        ("vehicle_registration", "Vehicle registration number, if mentioned"),
    ],
    "incident_report": [
        ("business_or_owner_name", "Name of the business or owner"),
        ("incident_date", "Date of the incident"),
        ("incident_location", "Place of the incident"),
        ("cause", "Cause of the incident as reported"),
        ("estimated_loss_amount", "Estimated loss amount, if stated"),
    ],
    "invoice": [
        ("buyer_name", "Name of the buyer"),
        ("document_date", "Date of the invoice"),
        ("total_amount", "The invoice total"),
    ],
    "inventory_list": [
        ("owner_name", "Name of the owner"),
        ("total_amount", "Total value of the list, if stated"),
    ],
    "other": [
        ("document_title", "The title of the document"),
        ("document_date", "The date on the document"),
        ("total_amount", "A total amount, if one is stated"),
    ],
}

# Documents that list charged items with amounts
LINE_ITEM_DOC_TYPES = ["bill", "estimate", "invoice", "inventory_list"]

# Facts that hold the name of a person or a business
NAME_FIELDS = ["patient_name", "owner_name", "complainant_name", "buyer_name", "business_or_owner_name"]

# Facts that hold a date
DATE_FIELDS = ["admission_date", "discharge_date", "incident_date"]