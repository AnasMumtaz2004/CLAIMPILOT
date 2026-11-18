from pathlib import Path
from config import settings

# The folder that holds the reference PDFs
SOURCES_DIR = Path(__file__).resolve().parent / "sources"
CUSTOMER_POLICIES_DIR = SOURCES_DIR / "customer_policies"
CLAIMS_GUIDELINES_DIR = SOURCES_DIR / "internal_claims_guidelines"
APPROVAL_POLICY_DIR = SOURCES_DIR / "internal_approval_policy"

# The folder names under customer_policies are also the insurance line names
INSURANCE_LINES = ["health", "private_vehicle", "commercial", "home"]

# Document types saved in the database
DOC_CUSTOMER_POLICY = "customer_policy"
DOC_CLAIMS_GUIDELINES = "internal_claims_guidelines"
DOC_APPROVAL_POLICY = "internal_approval_policy"

# Internal documents that apply to every insurance line use this domain
DOMAIN_ALL = "all"

# The embedding model name comes from the main settings, the size must match it
EMBEDDING_MODEL = settings.embedding_model
EMBEDDING_DIMENSIONS = 384
EMBEDDING_BATCH_SIZE = 32

# bge models work better when a search query starts with this sentence
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Chunk sizes in characters
MAX_CHUNK_CHARS = 1800
HARD_CHUNK_CHARS = 2600
MIN_BODY_CHARS = 40

# Search settings
DEFAULT_TOP_K = 5
MAX_TOP_K = 20