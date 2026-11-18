
# Approval Preparation Agent

## 1. Overview

The Approval Preparation Agent is responsible for checking whether a claim file is sufficiently complete and organized for Claims Officer review.

It consolidates the outputs of the previous specialist agents, retrieves relevant internal approval requirements, identifies unresolved issues, and prepares a structured review package.

Its purpose is to ensure that the Claims Officer receives the necessary claim information, supporting evidence, policy findings, calculation results, and outstanding issues in one place.

The agent prepares a claim for human review. It does not approve or reject claims.

## 2. Primary Responsibilities

- Retrieve claim information.
- Review Intake Agent findings.
- Review Document Review Agent findings.
- Review Policy Coverage Agent findings.
- Review Claim Assessment Agent findings.
- Retrieve internal approval requirements.
- Check whether required documents and information are available.
- Identify unresolved verification requirements.
- Identify missing evidence and incomplete assessments.
- Check whether specialist findings are available.
- Identify issues that require Claims Officer attention.
- Prepare a consolidated review package.
- Determine whether the claim is ready for human review.
- Return structured preparation findings.

## 3. Agent Configuration

| Property | Configuration |
|---|---|
| Agent Name | approval_preparation |
| Version | 1.0.0 |
| LLM Provider | Google Gemini |
| Model Configuration | gemini_strong_model |
| Temperature | 0 |
| Execution Type | LLM-assisted review preparation with backend completeness checks |

The agent uses the configured Gemini model to interpret specialist findings and internal approval requirements.

## 4. Workflow

1. Receive the claim ID.
2. Receive Intake Agent findings.
3. Receive Document Review Agent findings.
4. Receive Policy Coverage Agent findings.
5. Receive Claim Assessment Agent findings.
6. Retrieve the claim details and supporting documents.
7. Check claim completeness using the backend service.
8. Retrieve relevant internal approval requirements.
9. Examine whether the required specialist findings are available.
10. Identify missing information and unresolved verification items.
11. Compare the claim file against the internal approval requirements.
12. Assign requirement-level statuses.
13. Determine the overall preparation status.
14. Prepare a consolidated Claims Officer review package.
15. Return structured findings to the shared workflow state.

## 5. Tools

The Approval Preparation Agent has five directly registered tools.

### 5.1 get_claim_details

**Purpose:** Retrieves claim information required to prepare the review package.

### 5.2 get_claim_documents

**Purpose:** Retrieves claim documents and document-related information.

It helps identify available and missing evidence.

### 5.3 search_approval_requirements

**Purpose:** Searches internal approval requirements using the RAG system.

The retrieved requirements help determine whether the claim file contains the information needed for Claims Officer review.

### 5.4 check_claim_completeness

**Purpose:** Checks whether required claim information and documents are available.

Returns completeness information, including missing fields and documents.

### 5.5 Shared Tool Access

The agent's registered tools are restricted to its configured allowlist. Any additional shared MCP operations must be exposed through the approved tool interface rather than unrestricted access.

## 6. Inputs

The agent receives:

- `claim_id`
- `intake_result`
- `document_review_result`
- `policy_coverage_result`
- `claim_assessment_result`

These inputs provide the specialist findings needed to prepare the review package.

## 7. Outputs

The Approval Preparation Agent returns structured preparation findings.

Important output fields include:

- `preparation_status`
- `flags`
- `requirements`
- `review_package`
- `missing_information`
- `unresolved_items`
- `specialist_findings`

### Preparation Status Values

| Status | Meaning |
|---|---|
| ready_for_human_review | The preparation checks indicate that the claim is ready for Claims Officer review. |
| incomplete | Required information or documents are missing. |
| needs_verification | One or more items require additional verification. |

### Requirement Status Values

| Status | Meaning |
|---|---|
| satisfied | The requirement has been met based on available evidence. |
| not_satisfied | The requirement has not been met. |
| needs_verification | The available information is insufficient to confirm the requirement. |

## 8. Claims Officer Review Package

The review package consolidates relevant information from the complete specialist workflow.

It can include:

- Claim summary.
- Customer and policy information.
- Insurance line and incident details.
- Intake Agent findings.
- Document-review findings.
- Extracted evidence and document references.
- Policy coverage findings and citations.
- Claim assessment summary.
- Settlement calculation breakdown.
- Missing information.
- Unresolved verification items.
- Review flags.
- Internal approval requirement findings.

The package is intended to help the Claims Officer understand the claim without independently collecting each agent's output.

## 9. Decision Boundaries

The Approval Preparation Agent must:

- Never approve a claim.
- Never reject a claim.
- Never authorize payment.
- Never release settlement funds.
- Never override specialist findings without evidence.
- Never mark an unverified requirement as satisfied.
- Clearly identify missing or unresolved information.
- Prepare findings for human review rather than making the final decision.

A status of `ready_for_human_review` means the preparation checks are complete enough for officer review. It does not mean the claim is approved.

## 10. Workflow Integration

The Approval Preparation Agent runs after Claim Assessment.

It receives outputs from all four previous specialist agents.

Its output is passed to the Orchestrator, which consolidates review flags and routes the claim to the human review stage.

## 11. Implementation Files

```text
backend/agents/approval_preparation/
├── agent.yaml
├── config.py
├── graph.py
├── state.py
├── tools.py
└── nodes/
    └── pipeline.py

backend/agents/prompts/
└── approval_preparation.py
```

| File | Responsibility |
|---|---|
| agent.yaml | Defines agent metadata, model configuration, tools, inputs, outputs, and boundaries. |
| config.py | Loads agent-specific configuration. |
| graph.py | Builds and executes the agent graph. |
| state.py | Defines structured preparation state. |
| tools.py | Implements claim retrieval, document retrieval, approval requirement search, and completeness checks. |
| nodes/pipeline.py | Implements requirement checks, specialist-result analysis, and review-package preparation. |
| prompts/approval_preparation.py | Contains the approval preparation prompts. |

## 12. Important Design Principle

The Approval Preparation Agent is a review-readiness component, not an approval authority.

Its responsibility is to make sure the Claims Officer has a structured, evidence-backed view of the claim and knows which items remain incomplete or require verification.

The final decision remains with an authorized Claims Officer.
