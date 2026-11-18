
# Orchestrator

## 1. Overview

The Orchestrator is responsible for coordinating the final stage of the ClaimPilot specialist-agent workflow.

It receives the outputs of all five specialist agents, consolidates their review flags, checks the Approval Preparation Agent's readiness status, and determines the next workflow action.

In the current ClaimPilot implementation, the Orchestrator is a deterministic Python-based router integrated with LangGraph. It is not an LLM-powered agent.

Its primary responsibility is to ensure that specialist processing is completed and that the claim is routed to the Claims Officer review stage.

It does not make insurance decisions.

## 2. Primary Responsibilities

- Receive outputs from all five specialist agents.
- Examine the Intake Agent result.
- Examine the Document Review Agent result.
- Examine the Policy Coverage Agent result.
- Examine the Claim Assessment Agent result.
- Examine the Approval Preparation Agent result.
- Consolidate flags from specialist outputs.
- Identify whether approval preparation is ready.
- Add a review flag if approval preparation is not ready.
- Generate a structured orchestration result.
- Route the claim to the human review stage.
- Ensure the workflow reaches the LangGraph human-review interrupt.

## 3. Configuration

| Property | Configuration |
|---|---|
| Agent Name | orchestrator |
| Version | 1.0.0 |
| Execution Type | Deterministic Python router |
| Model | No LLM model |
| Framework | LangGraph |
| Decision Method | Rule-based state inspection |

The Orchestrator does not require an LLM to make its current routing decision.

Its behavior is implemented using Python logic and the shared workflow state.

## 4. Workflow

1. Receive the shared LangGraph workflow state.
2. Retrieve the outputs of the five specialist agents.
3. Collect flags from each specialist result.
4. Support both `flags` and `risk_flags` fields when consolidating findings.
5. Prefix each flag with its originating agent name.
6. Retrieve the Approval Preparation Agent's `preparation_status`.
7. Check whether the preparation status is `ready_for_human_review`.
8. If it is not ready, add the `approval_preparation_not_ready` flag.
9. Remove duplicate review flags.
10. Construct the orchestration result.
11. Set the next action to `pause_for_human_review`.
12. Return the result to the shared workflow state.

## 5. Inputs

The Orchestrator receives the shared workflow state containing:

- `claim_id`
- `intake_result`
- `document_review_result`
- `policy_coverage_result`
- `claim_assessment_result`
- `approval_preparation_result`

These results are produced by the five specialist agents.

## 6. Outputs

The Orchestrator produces an `orchestration` object containing:

- `agent`
- `agent_version`
- `claim_id`
- `next_action`
- `reason`
- `review_flags`
- `approval_preparation_status`
- `created_at`

### Next Action

The current implementation uses:

`pause_for_human_review`

The Orchestrator routes specialist-processed claims to Claims Officer review.

### Review Flags

Review flags are collected from specialist findings.

Examples include:

- `intake:missing_information`
- `document_review:document_issue`
- `policy_coverage:coverage_uncertainty`
- `claim_assessment:assessment_issue`
- `approval_preparation:verification_required`
- `approval_preparation_not_ready`

The actual flags depend on the specialist outputs.

## 7. Workflow Routing

The current LangGraph workflow follows this sequence:

```text
START
  |
  v
Intake Agent
  |
  v
Document Review Agent
  |
  v
Policy Coverage Agent
  |
  v
Claim Assessment Agent
  |
  v
Approval Preparation Agent
  |
  v
Orchestrator
  |
  v
Mark Claim for Review
  |
  v
Human Review Interrupt
  |
  v
END / WAIT
```

The Orchestrator is responsible for producing the orchestration result before the workflow updates the claim status and enters the human-review interrupt.

## 8. Human-in-the-Loop Integration

After orchestration, the workflow moves to the Claims Officer review stage.

LangGraph uses `interrupt()` to pause execution and expose the review information.

The interrupt payload includes:

- Review type.
- Claim ID.
- Orchestration result.
- Approval Preparation findings.

The Claims Officer can then examine the claim and make an authorized decision.

### Supported Human Decisions

- Approve.
- Reject.
- Request additional information.
- Escalate.

After the backend records the decision, the workflow can resume using:

`Command(resume=decision)`

The workflow uses the claim ID as its stable thread ID for checkpoint retrieval and resumption.

## 9. Tools and MCP Integration

The Orchestrator's current routing logic operates on the shared workflow state.

It does not need to retrieve claim documents, perform OCR, search policy wording, or calculate settlement amounts directly. Those responsibilities belong to the specialist agents.

Where shared MCP operations are available, they must remain restricted to the Orchestrator's explicitly permitted operations.

The Orchestrator must not gain unrestricted access to specialist tools simply because it coordinates the workflow.

## 10. Decision Boundaries

The Orchestrator must:

- Never approve a claim.
- Never reject a claim.
- Never authorize or release payment.
- Never calculate settlement amounts.
- Never invent missing specialist findings.
- Never declare fraud based only on a review flag.
- Never bypass the Claims Officer review stage.
- Never treat `ready_for_human_review` as an approval decision.
- Preserve specialist findings and review flags for human examination.

Its responsibility is workflow coordination and routing, not insurance judgment.

## 11. Error and Review Handling

The Orchestrator consolidates findings rather than silently removing specialist concerns.

If the Approval Preparation Agent does not return `ready_for_human_review`, the Orchestrator adds:

`approval_preparation_not_ready`

This allows the Claims Officer review stage to identify that the preparation checks were not completed successfully.

The presence of a review flag does not itself establish that a claim is invalid or fraudulent.

## 12. Execution Logging

The Orchestrator execution is recorded in the agent execution logs.

The recorded information includes:

- Run ID.
- Claim ID.
- Agent name and version.
- Model name (`deterministic-router`).
- Execution status.
- Specialist-result presence.
- Orchestration output.
- Error information.
- Execution duration.

This makes the routing operation traceable within the claim-processing workflow.

## 13. Implementation Files

```text
backend/agents/orchestrator/
├── graph.py
├── state.py
└── nodes/
    └── pipeline.py

backend/workflows/
├── claim_state.py
├── claim_workflow.py
├── persistence.py
└── worker.py
```

| File | Responsibility |
|---|---|
| graph.py | Builds and executes the Orchestrator graph. |
| state.py | Defines the Orchestrator state and specialist-result fields. |
| nodes/pipeline.py | Implements deterministic review-flag consolidation and routing output. |
| workflows/claim_state.py | Defines the shared workflow state. |
| workflows/claim_workflow.py | Connects all specialist agents, Orchestrator, claim-status update, and human-review interrupt. |
| workflows/persistence.py | Configures workflow checkpoint persistence. |
| workflows/worker.py | Handles workflow execution through the backend worker. |

## 14. Important Design Principle

The Orchestrator separates workflow control from insurance decision-making.

Specialist agents analyze claims, documents, policies, and settlement calculations. The Orchestrator consolidates their results and routes the claim to human review.

The Claims Officer remains the final decision-maker.
