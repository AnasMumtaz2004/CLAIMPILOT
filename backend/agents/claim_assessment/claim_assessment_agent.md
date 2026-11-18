
# Claim Assessment Agent

## 1. Overview

The Claim Assessment Agent evaluates the financial and factual aspects of an insurance claim using the findings produced by the previous specialist agents.

It combines claim information, document-review findings, policy coverage results, and internal Claims Handling Guidelines to prepare a transparent claim assessment.

A major responsibility of this agent is to invoke the deterministic settlement calculation service rather than relying on an LLM to perform financial calculations.

The agent produces an assessment and settlement estimate for Claims Officer review. It does not authorize payment or make the final approval/rejection decision.

## 2. Primary Responsibilities

- Retrieve claim information.
- Review Intake Agent findings.
- Review Document Review Agent findings.
- Review Policy Coverage Agent findings.
- Retrieve relevant internal Claims Handling Guidelines.
- Identify applicable assessment rules.
- Examine admissible and inadmissible claim components.
- Identify applicable limits and sub-limits.
- Evaluate depreciation and salvage where applicable.
- Consider deductibles and co-payment requirements.
- Evaluate sum insured and remaining available limits.
- Invoke the deterministic calculation service.
- Produce a transparent settlement calculation breakdown.
- Identify assumptions, missing information, and assessment flags.
- Prepare structured findings for Approval Preparation.

## 3. Agent Configuration

| Property | Configuration |
|---|---|
| Agent Name | claim_assessment |
| Version | 1.0.0 |
| LLM Provider | Google Gemini |
| Model Configuration | gemini_strong_model |
| Temperature | 0 |
| Execution Type | LLM-assisted assessment with deterministic financial calculation |

The LLM interprets the claim evidence and relevant internal guidelines. Python calculation functions handle financial arithmetic.

## 4. Workflow

1. Receive the claim ID.
2. Receive Intake Agent findings.
3. Receive Document Review Agent findings.
4. Receive Policy Coverage Agent findings.
5. Retrieve the claim details and relevant documents.
6. Search internal Claims Handling Guidelines.
7. Identify applicable assessment rules.
8. Examine admissible claim items and supporting evidence.
9. Identify applicable limits, sub-limits, depreciation, and salvage.
10. Collect the required financial inputs.
11. Invoke the deterministic calculation service.
12. Receive the calculated settlement breakdown.
13. Validate that the calculation output is available and structured.
14. Prepare the assessment findings.
15. Return the result to the shared workflow state.

## 5. Tools

The Claim Assessment Agent has four directly registered tools.

### 5.1 get_claim_details

**Purpose:** Retrieves claim information required for assessment.

Returns claim facts and relevant financial information.

### 5.2 get_claim_documents

**Purpose:** Retrieves documents associated with the claim.

These documents provide evidence for the assessment, such as bills, estimates, invoices, and other supporting records.

### 5.3 search_claims_guidelines

**Purpose:** Retrieves relevant internal Claims Handling Guidelines through RAG.

The retrieved guidelines support the assessment process and help identify applicable internal handling rules.

The guidelines are internal operational references, not contractual policy wording.

### 5.4 calculate_claim_amount

**Purpose:** Invokes the deterministic settlement calculation service.

The calculation service performs financial operations using Python's `Decimal` rather than relying on LLM-generated arithmetic.

## 6. Inputs

The agent receives:

- `claim_id`
- `intake_result`
- `document_review_result`
- `policy_coverage_result`

These inputs provide the claim facts, evidence findings, and policy coverage context required for assessment.

## 7. Outputs

The Claim Assessment Agent produces structured assessment findings, which can include:

- `status`
- `flags`
- `assessment_summary`
- `admissible_items`
- `inadmissible_items`
- `calculation_inputs`
- `calculation_breakdown`
- `estimated_settlement_amount`
- `applicable_limits`
- `assumptions`
- `missing_information`
- `guideline_references`

The exact output fields are governed by the agent's structured state and result schema.

## 8. Deterministic Settlement Calculation

Financial calculations are handled by the backend calculation service.

The service uses Python's `Decimal` to avoid floating-point precision problems.

The calculation process considers applicable components such as:

- Claimed amount.
- Admissible expenses.
- Inadmissible expenses.
- Policy limits.
- Sub-limits.
- Depreciation.
- Salvage value.
- Sum insured.
- Value at risk.
- Co-payment.
- Deductible.
- Remaining sum insured.

The applicable calculation steps depend on the insurance line and claim circumstances.

### Why Deterministic Calculation Matters

LLMs can make arithmetic mistakes or produce inconsistent numerical results.

Therefore:

- The LLM identifies relevant assessment information.
- The backend calculation service performs financial arithmetic.
- The calculation output is used in the assessment.
- The Claims Officer reviews the calculation before making a decision.

## 9. Internal Guidelines vs Policy Wording

The Claim Assessment Agent uses internal Claims Handling Guidelines.

These guidelines help determine how the claim should be assessed operationally.

They must not be confused with policy wording:

- Policy Coverage Agent examines contractual coverage.
- Claim Assessment Agent applies internal assessment guidelines and calculates the settlement estimate.

The Claim Assessment Agent should use policy findings as context and should not independently invent contractual coverage terms.

## 10. Decision Boundaries

The Claim Assessment Agent must:

- Never approve or reject a claim.
- Never authorize payment.
- Never use LLM-generated arithmetic as the final calculation.
- Never invent internal guideline references.
- Never treat internal guidelines as policy wording.
- Clearly identify missing inputs and assumptions.
- Preserve the calculation breakdown for review.
- Avoid presenting an estimate as an authorized payment.

## 11. Workflow Integration

The Claim Assessment Agent runs after Policy Coverage.

It receives findings from:

- Intake Agent.
- Document Review Agent.
- Policy Coverage Agent.

Its output is passed to:

- Approval Preparation Agent.
- Orchestrator.

The assessment provides the financial and operational basis for the Claims Officer review package.

## 12. Implementation Files

```text
backend/agents/claim_assessment/
├── agent.yaml
├── config.py
├── graph.py
├── state.py
├── tools.py
└── nodes/
    └── pipeline.py

backend/agents/prompts/
└── claim_assessment.py

backend/services/
└── calculation_service.py

backend/rag/
├── ingest.py
└── search.py
```

| File | Responsibility |
|---|---|
| agent.yaml | Defines agent configuration, tools, inputs, outputs, and boundaries. |
| config.py | Loads agent-specific configuration. |
| graph.py | Builds and executes the Claim Assessment graph. |
| state.py | Defines structured assessment state. |
| tools.py | Provides claim retrieval, document retrieval, guideline search, and calculation tools. |
| nodes/pipeline.py | Implements assessment logic and result generation. |
| prompts/claim_assessment.py | Contains assessment prompts. |
| services/calculation_service.py | Performs deterministic settlement calculations. |
| rag/search.py | Retrieves relevant internal Claims Handling Guidelines. |

## 13. Important Design Principle

The Claim Assessment Agent separates reasoning from arithmetic.

The LLM interprets evidence and internal guidelines, while deterministic Python code calculates financial values.

This improves numerical consistency, transparency, and auditability while keeping the final decision with the Claims Officer.
