
# Policy Coverage Agent

## 1. Overview

The Policy Coverage Agent evaluates an insurance claim against the customer's actual insurance policy.

Its responsibility is to retrieve the relevant policy schedule and policy wording, examine the contractual terms, and identify whether the reported incident appears to satisfy the applicable coverage conditions.

It analyzes policy dates, coverage selections, exclusions, limits, deductibles, waiting periods, conditions, and applicable add-ons.

The agent must support its findings with retrieved policy clauses and source references. It does not make the final claim approval or rejection decision.

## 2. Primary Responsibilities

- Retrieve the customer's policy information.
- Identify the applicable insurance policy and insurance line.
- Retrieve the policy schedule and matching policy wording.
- Search for relevant clauses using the RAG retrieval system.
- Examine the policy period and relevant coverage dates.
- Identify the coverage selected by the customer.
- Analyze applicable exclusions and conditions.
- Identify policy limits and sub-limits.
- Examine deductibles and co-payment requirements.
- Check waiting periods where applicable.
- Verify whether optional add-ons are present in the customer's policy schedule.
- Compare the claim circumstances with the retrieved policy conditions.
- Produce evidence-backed coverage findings.
- Identify missing policy information or unresolved coverage questions.

## 3. Agent Configuration

| Property | Configuration |
|---|---|
| Agent Name | policy_coverage |
| Version | 1.0.0 |
| LLM Provider | Google Gemini |
| Model Configuration | gemini_strong_model |
| Temperature | 0 |
| Execution Type | LLM-assisted policy analysis with RAG retrieval |

The agent uses the configured Gemini model to interpret policy wording and compare retrieved contractual terms with the claim circumstances.

## 4. Workflow

1. Receive the claim ID and Intake Agent findings.
2. Retrieve the customer's claim and policy information.
3. Identify the customer's insurance line and policy.
4. Retrieve the relevant policy schedule.
5. Search the applicable policy wording through the RAG system.
6. Retrieve relevant clauses and their source metadata.
7. Examine the policy period and coverage conditions.
8. Analyze applicable exclusions, limits, deductibles, and waiting periods.
9. Verify optional coverage and add-ons against the policy schedule.
10. Compare the incident details with the retrieved policy conditions.
11. Identify confirmed coverage conditions and unresolved questions.
12. Attach supporting clause references and exact quotations.
13. Return structured policy coverage findings.

## 5. Tools

The Policy Coverage Agent has three directly registered tools.

### 5.1 get_claim_details

**Purpose:** Retrieves the claim details needed for policy analysis.

Provides relevant claim facts, including:

- Claim ID.
- Insurance line.
- Policy information.
- Loss date.
- Claim description.
- Claimed amount.

### 5.2 get_customer_policy

**Purpose:** Retrieves the customer's policy information.

The policy information is used to establish the customer's actual insurance product and policy-specific details.

Relevant information can include:

- Policy number.
- Policyholder.
- Insurance line.
- Policy start and end dates.
- Policy status.
- Insured values.
- Policy schedule details.
- Selected coverage and add-ons, where recorded.

### 5.3 search_policy_wording

**Purpose:** Searches the policy wording knowledge base for relevant clauses.

The RAG system retrieves relevant policy text and source metadata, such as:

- Document name.
- Policy or product information.
- Clause or section.
- Page number.
- Retrieved text.

## 6. Inputs

The agent receives:

- `claim_id`
- `intake_result`

The Intake Agent result provides initial claim classification and relevant claim context.

The remaining policy details and policy wording are retrieved through the agent's tools.

## 7. Outputs

The Policy Coverage Agent returns structured coverage findings.

These can include:

- `status`
- `flags`
- `coverage_findings`
- `applicable_clauses`
- `exclusions`
- `limits`
- `deductibles`
- `waiting_periods`
- `conditions`
- `add_on_findings`
- `missing_information`
- `uncertainties`

Each coverage finding should identify its supporting policy source.

## 8. RAG and Policy Evidence

The Policy Coverage Agent uses Retrieval-Augmented Generation (RAG) to retrieve relevant policy clauses.

The retrieval process involves:

1. Extracting policy document text.
2. Splitting text into meaningful chunks.
3. Preserving relevant headings and clause boundaries.
4. Generating embeddings using Sentence Transformers.
5. Storing embeddings in PostgreSQL with pgvector.
6. Retrieving relevant clauses using semantic search.
7. Applying document and policy filters.
8. Returning relevant source references for the agent's analysis.

### Policy Evidence Requirements

Every important coverage finding must be supported by:

- Retrieved policy document.
- Relevant clause or section.
- Page reference where available.
- Exact supporting quotation.

The agent must not create fictional clauses or citations.

## 9. Policy Schedule vs Policy Wording

These sources have different responsibilities.

### Policy Schedule

Establishes customer-specific policy details, such as:

- Purchased insurance product.
- Policy period.
- Sum insured.
- Deductible.
- Co-payment.
- Selected add-ons.
- Other policy-specific values.

### Policy Wording

Defines contractual terms, including:

- Coverage conditions.
- Exclusions.
- Definitions.
- Waiting periods.
- Limits and sub-limits.
- Claim conditions.

The agent must not assume that a customer has an optional add-on merely because it is mentioned in general policy wording.

## 10. Decision Boundaries

The Policy Coverage Agent must:

- Never approve or reject a claim.
- Never authorize a payment.
- Never invent policy clauses or citations.
- Never treat internal claims guidelines as contractual policy wording.
- Never assume an add-on is selected without schedule evidence.
- Clearly identify missing or uncertain policy information.
- Distinguish confirmed policy facts from interpretations.
- Use only retrieved evidence relevant to the customer's policy.

## 11. Workflow Integration

The Policy Coverage Agent runs after Document Review.

It receives the Intake Agent result and contributes policy findings to:

- Claim Assessment Agent.
- Approval Preparation Agent.
- Orchestrator.

Its findings help downstream processing understand the contractual coverage conditions applicable to the claim.

## 12. Implementation Files

```text
backend/agents/policy_coverage/
├── agent.yaml
├── config.py
├── graph.py
├── README.md
├── state.py
└── tools.py

backend/agents/policy_coverage/nodes/
└── pipeline.py

backend/agents/prompts/
└── policy_coverage.py

backend/rag/
├── config.py
├── ingest.py
├── models.py
└── search.py
```

| File | Responsibility |
|---|---|
| agent.yaml | Defines agent metadata, model configuration, tools, inputs, outputs, and boundaries. |
| config.py | Loads agent-specific configuration. |
| graph.py | Builds and executes the agent graph. |
| state.py | Defines structured policy coverage state. |
| tools.py | Implements claim retrieval, customer policy lookup, and policy wording search. |
| nodes/pipeline.py | Implements policy retrieval, clause analysis, and result generation. |
| prompts/policy_coverage.py | Contains policy-analysis prompts. |
| rag/ingest.py | Processes reference documents and prepares them for retrieval. |
| rag/search.py | Retrieves relevant policy wording and source references. |

## 13. Important Design Principle

The Policy Coverage Agent must be evidence-driven.

It evaluates the claim using the customer's actual policy schedule and applicable policy wording, rather than relying on general insurance knowledge or assumptions.

Its output is a coverage assessment for the Claims Officer, not a final claim decision.
