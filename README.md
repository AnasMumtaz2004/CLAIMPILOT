
# ClaimPilot — Agentic AI Insurance Claims Processing System

**ClaimPilot** is an AI-powered insurance claims processing platform that assists insurance teams with claim intake, document verification, policy coverage analysis, claim assessment and approval preparation. It uses a coordinated architecture of **6 specialized AI agents**, Retrieval-Augmented Generation (RAG), deterministic financial calculations and Human-in-the-Loop (HITL) review.

The platform supports four insurance lines: **Health, Private Vehicle, Commercial and Home**.

AI agents prepare findings and supporting evidence. They do not independently approve or reject claims or authorize payments. The final decision belongs to an authorized Claims Officer.

---

## Architecture

```mermaid
graph TD
    A([Customer Claim Submission]) --> B[React Frontend]
    B --> C[FastAPI Backend]
    C --> D[(PostgreSQL + pgvector)]

    C --> E[LangGraph Claim Workflow]

    E --> F["Agent 1 · Intake"]
    F --> G["Agent 2 · Document Review"]
    G --> H["Agent 3 · Policy Coverage"]
    H --> I["Agent 4 · Claim Assessment"]
    I --> J["Agent 5 · Approval Preparation"]
    J --> K["Agent 6 · Orchestrator"]

    G -.-> L[Tesseract OCR]
    H -.-> M["RAG · Customer Policy Wording"]
    I -.-> N["RAG · Internal Claims Guidelines"]
    J -.-> O["RAG · Internal Approval Policy"]

    I -.-> P[Deterministic Settlement Engine]

    K --> Q[Human Review Interrupt]
    Q --> R[Claims Officer Portal]
    R --> S{Officer Decision}

    S -->|Approve| T[Record Approval]
    S -->|Reject| U[Record Rejection]
    S -->|Request Information| V[Customer Information Request]
    S -->|Escalate| W[Specialist Review]

    T --> D
    U --> D
    V --> D
    W --> D

    D -.-> X[Audit Trail]
    D -.-> Y[SMTP Email Notifications]
```

---

## How It Works

ClaimPilot follows a coordinated claim-processing workflow.

1. **Claim Submission:** A customer creates a claim, selects an insurance policy, enters claim details and uploads supporting documents.
2. **Claim Intake:** The Intake Agent validates the submitted claim, identifies the event type and checks for missing information.
3. **Document Review:** The Document Review Agent uses OCR-extracted text to identify facts, check document consistency and highlight missing evidence.
4. **Policy Coverage:** The Policy Coverage Agent retrieves the customer's policy schedule and relevant policy wording to evaluate coverage conditions and exclusions.
5. **Claim Assessment:** The Claim Assessment Agent evaluates the claim using internal claims guidelines and invokes the deterministic settlement calculation service.
6. **Approval Preparation:** The Approval Preparation Agent checks required documents, approval requirements, specialist findings and outstanding items.
7. **Orchestration:** The Orchestrator consolidates specialist results and prepares the workflow for human review.
8. **Human Decision:** LangGraph pauses execution until an authorized Claims Officer reviews the evidence and records a decision.

**Workflow:** `claim submission → intake → document review → policy coverage → claim assessment → approval preparation → orchestration → human review`

---

## Agents

ClaimPilot uses six agents. Five perform specialized claim-processing tasks, while the Orchestrator coordinates the final workflow transition.

| Agent   | Name                 | Responsibility                                                              |
| :------ | :------------------- | :-------------------------------------------------------------------------- |
| Agent 1 | Intake               | Validates claim information, identifies event type and missing details      |
| Agent 2 | Document Review      | Extracts document facts, checks consistency and identifies missing evidence |
| Agent 3 | Policy Coverage      | Evaluates coverage using the customer's policy schedule and wording         |
| Agent 4 | Claim Assessment     | Applies internal claims guidelines and calculates settlement amounts        |
| Agent 5 | Approval Preparation | Prepares an evidence-backed review package for the Claims Officer           |
| Agent 6 | Orchestrator         | Consolidates agent findings and routes the workflow to human review         |

Detailed documentation for each agent is available in the [`backend/agents/`](backend/agents/) directory:

- [`intake_agent.md`](backend/agents/intake/intake_agent.md)
- [`document_review_agent.md`](backend/agents/document_review/document_review_agent.md)
- [`policy_coverage_agent.md`](backend/agents/policy_coverage/policy_coverage_agent.md)
- [`claim_assessment_agent.md`](backend/agents/claim_assessment/claim_assessment_agent.md)
- [`approval_preparation_agent.md`](backend/agents/approval_preparation/approval_preparation_agent.md)
- [`orchestrator_agent.md`](backend/agents/orchestrator/orchestrator_agent.md)

---

## Insurance Lines

The system supports four insurance domains:

| Insurance Line | Example Claim Information |
|---|---|
| Health | Hospitalization, medical expenses and treatment documents |
| Private Vehicle | Vehicle accidents, repairs and damage assessment |
| Commercial | Business property damage and commercial losses |
| Home | Building damage, household contents and property losses |

Claim fields and required document types depend on the selected insurance line.

---

## Retrieval-Augmented Generation (RAG)

ClaimPilot uses RAG to ground agent findings in relevant policy and internal reference documents.

The retrieval pipeline uses:

- **PyMuPDF:** Extracts text and page information from PDF documents.
- **Clause-level chunking:** Preserves document headings, sections and clause boundaries.
- **Sentence Transformers:** Generates embeddings using `BAAI/bge-small-en-v1.5`.
- **pgvector:** Stores embeddings and supports similarity-based retrieval.
- **Metadata filtering:** Restricts searches by document type, insurance line and policy number.
- **Citations:** Retains source document, clause, section and page information for agent findings.

### Reference Document Categories

| Document Type | Used By | Purpose |
|---|---|---|
| Customer Policy Schedule and Wording | Policy Coverage Agent | Establishes the customer's purchased coverage, limits, conditions and exclusions |
| Internal Claims Handling Guidelines | Claim Assessment Agent | Provides operational rules for evaluating and calculating claims |
| Internal Approval Policy | Approval Preparation Agent | Provides requirements for preparing claims for officer review |

**Important:** Customer policy documents and internal guidelines are separate sources of evidence. Internal guidelines must not be presented as contractual policy wording.

### Retrieval Flow

```text
Reference PDFs
     |
     v
PDF Text Extraction
     |
     v
Clause-Level Chunking
     |
     v
Metadata Assignment
     |
     v
Embedding Generation
     |
     v
PostgreSQL + pgvector
     |
     v
Metadata-Filtered Similarity Search
     |
     v
Relevant Clauses + Source References
     |
     v
Agent Analysis
     |
     v
Evidence-Backed Findings
```

The project has previously recorded an indexed dataset of **167 searchable chunks across 6 PDFs**. The actual indexed corpus can change when source documents are added or ingestion is repeated.

---

## Document Processing and OCR

Uploaded claim documents are stored and processed separately from reference policy documents.

The document-processing pipeline includes:

- Original document storage.
- Resized image storage where applicable.
- File and image hash generation.
- OCR processing using Tesseract.
- Orientation detection and handling of rotated pages.
- Extracted text and page-level confidence information.
- Document consistency checks against submitted claim information.

The Document Review Agent treats OCR output as a candidate reading, not verified truth. Extracted facts must be supported by document text and page references.

---

## Claim Assessment and Settlement Calculation

The Claim Assessment Agent evaluates the claim using:

- Claim and policy information.
- Document Review findings.
- Policy Coverage findings.
- Internal claims handling guidelines.
- Deterministic calculation tools.

Financial calculations are handled by Python code rather than relying on LLM-generated arithmetic.

### Settlement Engine

The calculation service follows a **nine-step settlement sequence** based on the internal claims guidelines.

Key implementation details:

- Python `Decimal` for monetary calculations.
- Two-decimal monetary rounding using `ROUND_HALF_UP`.
- Validation of negative amounts and invalid percentages.
- Non-admissible item deductions.
- Sub-limit application.
- Depreciation.
- Salvage deductions.
- Underinsurance and applicable policy adjustments.
- Co-payment, deductible and remaining sum-insured handling.

The calculation service produces a structured breakdown of the calculation steps and payable amount.

An illustrative project example is a claimed amount of ₹12,00,000 resulting in ₹5,75,000 payable after applying the configured settlement rules. The actual result depends on the claim inputs and applicable policy and guideline conditions.

---

## Human-in-the-Loop (HITL)

Human review is a required part of the ClaimPilot workflow.

After the specialist agents finish processing, the Orchestrator consolidates their results and routes the claim to the Claims Officer review stage.

LangGraph uses an interrupt to pause the workflow and preserve its state.

The Claims Officer can:

- Review claim information and uploaded documents.
- Inspect OCR-extracted facts and document issues.
- Examine policy coverage findings and citations.
- Review internal guideline findings.
- Inspect settlement calculations.
- Approve a claim.
- Reject a claim with a reason.
- Request additional information.
- Escalate the claim for further review.

After the officer records a decision, the workflow can resume using the saved workflow checkpoint.

**AI-generated findings are decision-support material. The authorized Claims Officer remains responsible for the final claim decision.**

---

## MCP Tool Integration

The project includes an MCP integration layer intended to provide agents with controlled access to shared backend operations.

The integrated design covers **10 shared MCP tool operations**, including:

- Claim detail retrieval.
- Customer policy retrieval.
- Policy wording search.
- Claim document retrieval.
- OCR operations.
- Claim completeness checks.
- Internal claims guideline retrieval.
- Settlement calculations.
- Approval requirement retrieval.
- Other claim-review operations.

MCP provides a standardized tool interface. It does not replace FastAPI, the service layer, PostgreSQL or LangGraph orchestration.

---

## Database

ClaimPilot uses PostgreSQL for application data and pgvector for document embeddings.

| Table | Purpose |
|---|---|
| `users` | Customer and staff accounts |
| `policies` | Customer insurance policies and policy schedules |
| `claims` | Claim details, insurance line and claim status |
| `claim_status_history` | Historical claim status changes |
| `claim_documents` | Uploaded document metadata, OCR data and file references |
| `audit_log` | Hash-chained audit events |
| `claim_messages` | Customer and staff claim messages |
| `claim_assignments` | Claims Officer assignments |
| `staff_reviews` | Private Claims Officer notes |
| `approval_decisions` | Recorded human decisions |
| `claim_tasks` | Open claim tasks and follow-up work |
| `agent_execution_logs` | Agent execution inputs, outputs, errors and run information |
| `document_chunks` | Indexed reference-document chunks and vector embeddings |

LangGraph workflow checkpoints are persisted separately from ordinary claim records.

---

## Audit and Execution Tracking

ClaimPilot maintains records of agent execution and human decisions.

**Agent execution logs:**
- Agent name and version.
- Model information.
- Claim identifier.
- Execution status.
- Input summary.
- Structured output.
- Error information.
- Execution duration.
- Run identifier.

**Audit trail:**
- Actor.
- Action.
- Claim identifier.
- Event payload.
- Timestamp.
- Previous hash.
- Current row hash.

The audit service uses SHA-256 hash chaining and includes a chain-verification function to identify integrity mismatches.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Vector Search | pgvector |
| ORM | SQLAlchemy |
| Database Migrations | Alembic |
| Agent Orchestration | LangGraph |
| LLM and Retrieval Integration | LangChain |
| LLM Providers | Google Gemini and Groq |
| Embeddings | Sentence Transformers |
| Embedding Model | `BAAI/bge-small-en-v1.5` |
| Reranker Configuration | `BAAI/bge-reranker-base` |
| PDF Processing | PyMuPDF |
| OCR | Tesseract |
| Financial Calculations | Python `Decimal` |
| Email | SMTP |
| Agent Tool Integration | MCP |
| Workflow Persistence | LangGraph Checkpointer |

---

## Key Design Decisions

### 1. LLM reasoning and deterministic calculations are separated

LLMs interpret claim information and explain evidence. Financial calculations are performed by deterministic Python services to maintain consistent monetary arithmetic.

### 2. Policy coverage and internal claims assessment use different reference sources

The Policy Coverage Agent retrieves the customer's policy wording and schedule. The Claim Assessment Agent retrieves internal claims handling guidelines. The Approval Preparation Agent retrieves internal approval requirements.

### 3. Citations must be supported by retrieved evidence

Agents must not invent policy clauses or cite clauses that were not retrieved. Findings supporting or limiting coverage require an exact quote and a source reference.

### 4. OCR output is not automatically trusted

OCR can contain incorrect readings. Extracted facts are checked against source text, page references and other claim information.

### 5. The Orchestrator does not make claim decisions

The Orchestrator consolidates specialist results and routes the workflow to human review. It does not approve, reject or authorize payment.

### 6. Workflow state and application data have different persistence responsibilities

PostgreSQL stores claims, documents, decisions and related application records. LangGraph checkpoints preserve workflow execution state for interruption and resumption.

### 7. Human review is mandatory

The workflow pauses for a Claims Officer to inspect the evidence and make the final decision.

---

## Project Structure

```text
CLAIMPILOT/
│
├── backend/
│   ├── agents/
│   │   ├── intake/                    # Agent 1 — Intake
│   │   ├── document_review/            # Agent 2 — Document Review
│   │   ├── policy_coverage/             # Agent 3 — Policy Coverage
│   │   ├── claim_assessment/            # Agent 4 — Claim Assessment
│   │   ├── approval_preparation/        # Agent 5 — Approval Preparation
│   │   ├── orchestrator/                # Agent 6 — Orchestrator
│   │   ├── prompts/                     # Agent system prompts
│   │   ├── llm.py                       # LLM configuration and creation
│   │   └── run_log.py                   # Agent execution logging
│   │
│   ├── api/                             # Reserved for API organization
│   │
│   ├── database/
│   │   ├── connection.py                # SQLAlchemy engine and sessions
│   │   ├── models.py                    # Database models
│   │   └── schemas.py                   # Request and response schemas
│   │
│   ├── migrations/                      # Alembic migrations
│   │
│   ├── rag/
│   │   ├── sources/
│   │   │   ├── customer_policies/
│   │   │   ├── internal_claims_guidelines/
│   │   │   └── internal_approval_policy/
│   │   ├── config.py                    # RAG configuration
│   │   ├── ingest.py                    # PDF ingestion and chunking
│   │   ├── models.py                    # Document chunk model
│   │   └── search.py                    # Vector retrieval and citations
│   │
│   ├── routes/
│   │   ├── auth.py                      # Authentication routes
│   │   ├── claims.py                    # Customer claim routes
│   │   ├── documents.py                 # Document upload and retrieval
│   │   ├── staff.py                     # Claims Officer routes
│   │   └── decisions.py                 # Human decision routes
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── claim_service.py
│   │   ├── document_service.py
│   │   ├── calculation_service.py
│   │   ├── workflow_service.py
│   │   ├── audit_service.py
│   │   └── email_service.py
│   │
│   ├── workflows/
│   │   ├── claim_state.py                # Shared workflow state
│   │   ├── claim_workflow.py             # Main LangGraph workflow
│   │   ├── persistence.py                # Workflow checkpointer
│   │   └── worker.py                     # Workflow worker
│   │
│   ├── scripts/
│   │   ├── create_staff.py
│   │   ├── seed_data.py
│   │   └── try_agent.py
│   │
│   ├── config.py
│   ├── main.py
│   ├── pyproject.toml
│   └── uv.lock
│
├── frontend/
│   └── src/
│       ├── components/
│       ├── context/
│       ├── pages/
│       │   ├── customer/
│       │   │   ├── CustomerLogin.jsx
│       │   │   ├── CustomerDashboard.jsx
│       │   │   └── CustomerClaims.jsx
│       │   └── staff/
│       │       ├── StaffLogin.jsx
│       │       ├── StaffDashboard.jsx
│       │       └── ClaimReview.jsx
│       ├── services/
│       ├── App.jsx
│       └── main.jsx
│
├── data/
│   └── claim_uploads/
│
├── docker-compose.yml
├── README.md
└── AGENTS.md
```

---

## Setup

### Prerequisites

- Python 3.14 or a compatible Python version supported by the backend dependencies.
- Node.js and npm.
- PostgreSQL with pgvector support.
- Google Gemini API key.
- Groq API key.
- Tesseract OCR installed locally.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd CLAIMPILOT
```

### 2. Start PostgreSQL

The included Docker Compose file starts PostgreSQL with the pgvector image.

```bash
docker compose up -d db
```

Default local database configuration:

| Setting | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `claims` |
| Username | `claims` |
| Password | `claims_dev_password` |

These are development defaults from `docker-compose.yml`. Change them before using the application in a non-development environment.

### 3. Configure Backend Environment

Create `backend/.env`:

```env
DATABASE_URL=postgresql://claims:claims_dev_password@localhost:5432/claims

JWT_SECRET=replace_with_a_secure_secret
APPROVAL_TOKEN_SECRET=replace_with_a_secure_secret

GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key

GROQ_SMALL_MODEL=llama-3.1-8b-instant
GROQ_FALLBACK_MODEL=openai/gpt-oss-120b
GEMINI_STRONG_MODEL=gemini-3.8-flash
GEMINI_VISION_MODEL=gemini-3.8-flash

EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-base

MCP_URL=

SMTP_HOST=localhost
SMTP_PORT=1025
EMAIL_FROM=claims@claimpilot.local

STORAGE_DIR=./storage
TESSERACT_CMD=

MAX_UPLOAD_MB=10
MAX_FILES_PER_CLAIM=15
APPROVAL_AMOUNT_LIMIT=50000
CLAIM_TOKEN_BUDGET=30000
```

The names above follow the backend settings configuration. Add any provider-specific credentials required by the installed integrations.

### 4. Install Backend Dependencies

```bash
cd backend
uv sync
```

Run database migrations:

```bash
uv run alembic upgrade head
```

### 5. Ingest Reference Documents

Run the RAG ingestion process:

```bash
uv run python -m rag.ingest
```

This processes the configured policy documents, internal claims guidelines and approval policy documents and stores searchable chunks and embeddings in PostgreSQL.

### 6. Create a Staff Account

Use the staff creation script:

```bash
uv run python -m scripts.create_staff
```

Follow the script's prompts to create a Claims Officer account.

### 7. Start the Backend

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend:

`http://localhost:8000`

Health check:

`http://localhost:8000/health`

### 8. Start the Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend:

`http://localhost:5173`

---

## Portals

| Portal | Route | Audience |
|---|---|---|
| Customer Login | `/customer/login` | Customer |
| Customer Dashboard | `/customer/dashboard` | Customer |
| Customer Claims | `/customer/claims` | Customer |
| Staff Login | `/staff/login` | Claims Officer |
| Staff Dashboard | `/staff/dashboard` | Claims Officer |
| Claim Review | `/staff/claims/:claimId` | Claims Officer |
| Backend Health | `/health` | Developer |

Frontend routes are handled by the React application. API routes are provided by FastAPI.

---

## API Reference

### Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Register a customer |
| POST | `/auth/login` | Customer login |
| POST | `/auth/staff/login` | Staff login |
| GET | `/auth/me` | Get current authenticated user |

### Customer Claims

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/customer/claim-config` | Get claim form configuration |
| GET | `/customer/policies` | List customer policies |
| GET | `/customer/claims` | List customer claims |
| POST | `/customer/claims` | Create a draft claim |
| GET | `/customer/claims/{claim_id}` | Get claim details |
| PATCH | `/customer/claims/{claim_id}` | Update a draft claim |
| POST | `/customer/claims/{claim_id}/submit` | Submit a claim |
| POST | `/customer/claims/{claim_id}/respond` | Respond to an information request |
| GET | `/customer/claims/{claim_id}/history` | Get claim status history |
| GET | `/customer/claims/{claim_id}/messages` | Get claim messages |
| POST | `/customer/claims/{claim_id}/messages` | Send a claim message |

### Documents

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/customer/claims/{claim_id}/documents` | List claim documents |
| POST | `/customer/claims/{claim_id}/documents` | Upload a claim document |
| GET | `/customer/claims/{claim_id}/documents/{document_id}/file` | Download original document |

### Claims Officer

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/staff/dashboard` | Get staff dashboard data |
| GET | `/staff/claims` | List and filter claims |
| GET | `/staff/claims/{claim_id}` | Get claim review details |
| GET | `/staff/claims/{claim_id}/documents/{document_id}/file` | Download a document |
| GET | `/staff/claims/{claim_id}/documents/{document_id}/ocr` | Get OCR text and confidence |
| POST | `/staff/claims/{claim_id}/assign` | Assign claim to logged-in officer |
| POST | `/staff/claims/{claim_id}/notes` | Add a private staff note |
| GET | `/staff/tasks` | List open tasks |

### Human Decisions

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/decisions/claims/{claim_id}/approve` | Record approval |
| POST | `/decisions/claims/{claim_id}/reject` | Record rejection |
| POST | `/decisions/claims/{claim_id}/request-info` | Request additional information |
| POST | `/decisions/claims/{claim_id}/escalate` | Escalate claim |
| GET | `/decisions/claims/{claim_id}/history` | Get decision history |

---

## Running Individual Agents

The repository includes a script for running individual agents against a claim.

```bash
cd backend
uv run python -m scripts.try_agent intake <claim_id>
uv run python -m scripts.try_agent document_review <claim_id>
uv run python -m scripts.try_agent policy_coverage <claim_id>
```

Other specialist agents can also be invoked through their respective graph entry points.

Individual agent execution requires the relevant API credentials and reference data where applicable.

---

## Workflow Persistence

ClaimPilot uses LangGraph checkpoint persistence to support human interruptions and workflow resumption.

- Workflow state is associated with the claim identifier.
- Specialist agent outputs are stored in the shared workflow state.
- The workflow pauses at the Claims Officer review gate.
- A recorded human decision is passed back to the workflow.
- The workflow resumes from its saved checkpoint.

Customer claim drafts and application records are stored in PostgreSQL through the claim services. Workflow checkpoints have a separate persistence responsibility.

---

## Documentation

| Document | Description |
| :--- | :--- |
| `README.md` | Project overview, architecture, setup and API reference |
| `backend/agents/intake/agent.yaml` | Intake Agent specification |
| `backend/agents/document_review/agent.yaml` | Document Review Agent specification |
| `backend/agents/policy_coverage/agent.yaml` | Policy Coverage Agent specification |
| `backend/agents/claim_assessment/agent.yaml` | Claim Assessment Agent specification |
| `backend/agents/approval_preparation/agent.yaml` | Approval Preparation Agent specification |
| `backend/agents/orchestrator/` | Orchestrator Agent workflow and routing implementation |
| `backend/workflows/claim_workflow.py` | Main LangGraph workflow implementation |
| `backend/rag/` | RAG ingestion, embedding and retrieval implementation |
| `backend/services/calculation_service.py` | Deterministic settlement calculation logic |
| `backend/services/audit_service.py` | Hash-chained audit implementation |
---



