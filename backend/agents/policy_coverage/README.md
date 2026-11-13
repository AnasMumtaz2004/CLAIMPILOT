# Policy coverage agent

The third specialist agent. It compares a claim with the schedule and the wording of the customer's own policy.

## What it does

- Loads the policy schedule (dates, sum insured, deductible, co-payment) and checks it with code:
  the policy exists, its line matches the claim, the date of loss is inside the policy period,
  the number of days from policy start to the loss, and the claimed amount against the sum insured.
- Searches the wording and schedule of THIS policy only: one search for the schedule and one for each topic.
- Asks the model for one finding for each topic: event coverage, waiting period, exclusions, sub-limits,
  conditions, deductible and co-payment. Each finding is `supports_coverage`, `limits_coverage` or
  `needs_more_information`.
- Checks every finding with code. A finding that supports or limits coverage must cite a clause that was
  really retrieved, and must contain an exact quote from a cited clause. Otherwise it becomes
  `needs_more_information`.
- Lists the add-ons named in the schedule (section 1) with their status. The general wording never proves
  that an add-on was bought.

It does **not** approve, reject, or estimate any payout.

## Inputs and outputs

- Input: `claim_id` of a submitted claim, and optionally the intake result (only its `event_type` is used).
- Output: `status` (`complete` or `needs_review`), `coverage_summary` (`no_limitations_found`,
  `limitations_found`, `uncertain` or `policy_conditions_not_met`), `flags`, `schedule`, `checks`,
  `findings`, `add_ons`, `clauses` and `unknowns`.
- The summary describes what was found. It is not a decision.
- Full clause text is kept only for clauses that a checked finding or add-on cites.
- Every run saves one row in `agent_execution_logs`, including failed runs.

## How it works

`load_inputs` -> `check_schedule` -> `retrieve_clauses` -> `analyze_coverage` (the only model call)
-> `verify_findings` -> `build_result`

The model has no tools. It only reads numbered clauses and fills in a form. Code does the searching,
the dates and amounts, and every check of the model's answer.

## Files

- `agent.yaml`: name, version, allowed tools. Read by `config.py`.
- `config.py`: model settings, topics, and the search question for each topic and insurance line.
- `state.py`: the graph state and the model's answer form (`CoverageReview`).
- `tools.py`: three tools. They call the services directly.
- `nodes/pipeline.py`: the graph steps.
- `graph.py`: builds the graph and has `run_policy_coverage_agent`.
- The prompts are in `agents/prompts/policy_coverage.py`.

## Try it

    python -m scripts.try_agent policy_coverage <claim_id>

This calls the real model, so `GOOGLE_API_KEY` must be set in `.env`, and `python -m rag.ingest` must have run.

## Limits

- The search questions are generic. If real runs often say `needs_more_information`, improve the questions
  in `config.py` first.
- Retrieval returns at most 3 clauses per question and 21 clauses in total.
- "Waiting period over" is judged by the model from the day count the system gives it. The day count is
  counted from the policy start date, not from any earlier continuous cover.
- A policy PDF that was not ingested gives `policy_wording_not_found` and every topic as unknown.