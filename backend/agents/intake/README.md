# Intake agent

The first specialist agent. It checks a submitted claim before any other step runs.

## What it does

- Confirms the description fits the insurance line (a car accident on a health claim is flagged).
- Names the type of event, from a fixed list for each insurance line.
- Writes a short, neutral summary of what happened.
- Lists contradictions inside the claim data.
- Lists missing required fields and documents (done by code, not by the model).
- Checks that the policy exists, belongs to the customer, and covers the loss date (done by code).

It does **not** decide coverage, approval or rejection.

## Inputs and outputs

- Input: `claim_id` of a submitted claim. Drafts are treated as not found.
- Output: one dictionary with `status` (`complete`, `incomplete` or `needs_review`), `flags`, `event_type`,
  `event_summary`, `policy_check`, `missing_fields`, `missing_documents` and a `checklist`.
- Every run saves one row in `agent_execution_logs`, including failed runs.

## How it works

`load_claim` -> `check_completeness` -> `classify_event` (the only model call) -> `build_result`

The model only fills in a structured form. It has no tools. Code calls the tools and checks the model's answer
(for example an event type that is not in the list becomes `unclear`).

## Files

- `agent.yaml`: name, version, allowed tools. Read by `config.py`.
- `config.py`: model settings, event type lists, text limits.
- `state.py`: the graph state and the model's answer form (`IntakeReview`).
- `tools.py`: the two tools. They call the services directly.
- `nodes/pipeline.py`: the graph steps.
- `graph.py`: builds the graph and has `run_intake_agent`.
- The prompts are in `agents/prompts/intake.py`.

## Try it

    python -m scripts.try_agent intake <claim_id>

This calls the real model, so `GROQ_API_KEY` must be set in `.env`.

## Limits

- The quality of the event type and the contradictions depends on the model. Check real runs before trusting them.
- The model sees the claim form and description only. It never sees contact details or documents.