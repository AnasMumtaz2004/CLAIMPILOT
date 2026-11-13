# Document review agent

The second specialist agent. It reads the documents on a claim and checks them against the claim form.

## What it does

- Reads the OCR text of every document that has text. A document that was never read is sent to OCR first.
- Asks the model to extract key facts (names, dates, totals, registration numbers) and charged line items.
- Checks every extracted value against the document text. A value is trusted only if its quote is found on a
  page and contains the value. Each fact keeps its document, page and OCR confidence.
- Compares the documents with the claim form and with each other: claimed amount, names, hospital,
  vehicle registration, property address, and dates. Line items must add up to the printed total.
- Flags text that was read with a confidence below 85%, documents that could not be read, and documents
  that do not look like the type they were uploaded as.
- Lists missing required documents.

OCR output is a candidate reading, never verified truth. The agent does **not** decide coverage,
approval or rejection.

## Inputs and outputs

- Input: `claim_id` of a submitted claim. Drafts are treated as not found.
- Output: `status` (`complete`, `incomplete` or `needs_review`), `flags`, `documents` (facts, line items,
  issues for each document), `issues`, `missing_documents`.
- Every run saves one row in `agent_execution_logs`, including failed runs.
- The result holds short quotes only. The full text stays in `claim_documents.extracted`.

## How it works

`load_claim` -> `read_documents` -> `extract_facts` (one model call per document) -> `verify_extractions`
-> `cross_check` -> `build_result`

The model only fills in a structured form for one document at a time. It has no tools. Code calls the tools,
checks the model's answers and does every comparison.

## Files

- `agent.yaml`: name, version, allowed tools. Read by `config.py`.
- `config.py`: model settings, thresholds, and the fields to extract for each document type.
- `state.py`: the graph state and the model's answer form (`DocumentExtraction`).
- `tools.py`: four tools. They call the services directly.
- `checks.py`: pure functions that compare names, amounts, dates, addresses and quotes.
- `nodes/pipeline.py`: the graph steps.
- `graph.py`: builds the graph and has `run_document_review_agent`.
- The prompts are in `agents/prompts/document_review.py`.

## Try it

    python -m scripts.try_agent document_review <claim_id>

This calls the real model, so `GOOGLE_API_KEY` must be set in `.env`.

## Limits

- Photos are skipped. They have no text, and no vision model is used yet.
- A value copied by the model in a different format from the document (for example a reformatted date)
  is marked unverified. This is on purpose.
- Only the first 10 readable documents, 20 pages each, and 6,000 characters per document are sent to the model.
- A name on a document counts as matching if its words are all found in a known name. A single word such as
  "Rao" therefore matches "Vikram Ananth Rao".
- The FIR registration date is not checked against the loss date, only the incident date.