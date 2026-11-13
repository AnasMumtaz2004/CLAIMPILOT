from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from agents.document_review import checks
from agents.document_review import tools
from agents.document_review.config import AGENT_NAME
from agents.document_review.config import AGENT_VERSION
from agents.document_review.config import AMOUNT_TOLERANCE
from agents.document_review.config import DATE_FIELDS
from agents.document_review.config import DATE_TOLERANCE_DAYS
from agents.document_review.config import FIELDS_BY_DOC_TYPE
from agents.document_review.config import LINE_ITEM_DOC_TYPES
from agents.document_review.config import MAX_DOCUMENTS
from agents.document_review.config import MAX_FACTS
from agents.document_review.config import MAX_LINE_ITEMS
from agents.document_review.config import MAX_NOTES
from agents.document_review.config import MAX_QUOTE_CHARS
from agents.document_review.config import MAX_TEXT_CHARS
from agents.document_review.config import NAME_FIELDS
from agents.document_review.config import OCR_REVIEW_THRESHOLD
from agents.document_review.state import DocumentExtraction
from agents.prompts.document_review import SYSTEM_PROMPT
from agents.prompts.document_review import build_user_prompt


def short_text(text, limit):
    """Trim a text to a limit of characters."""
    clean = str(text).strip()
    if len(clean) > limit:
        return clean[: limit - 3] + "..."
    return clean


def make_issue(code, message, document_id=None):
    """Build one issue. The code is a short label, the message is for a person."""
    return {"code": code, "message": message, "document_id": document_id}


def format_amount(amount):
    """Write an amount with thousands separators and two decimals."""
    return f"{float(amount):,.2f}"


# ---------------------------------------------------------------------------
# Step 1 and 2: load the claim and read the documents
# ---------------------------------------------------------------------------


def load_claim(state, db):
    """Node: load the claim facts and the list of documents. Stops when the claim does not exist."""
    facts = tools.get_claim_details(db, state["claim_id"])
    if facts is None:
        return {"error": "claim_not_found"}

    listing = tools.get_claim_documents(db, state["claim_id"])
    return {"facts": facts, "listing": listing}


def route_after_load(state):
    """Choose the next step after the claim was loaded."""
    if state.get("error"):
        return "stop"
    return "continue"


def new_entry(item):
    """Create the working record of one document."""
    return {
        "document_id": item["id"],
        "doc_type": item["doc_type"],
        "doc_label": item["label"],
        "ocr_status": item["ocr_status"],
        "skipped": False,
        "skip_reason": "",
        "pages": [],
        "page_count": 0,
        "overall_confidence": None,
        "ocr_truncated": False,
        "error": None,
    }


def read_documents(state, db):
    """Node: read the OCR text of each document. A document that was never read is sent to OCR first."""
    claim_id = state["claim_id"]
    documents = []
    read_count = 0

    for item in state["listing"]["documents"]:
        entry = new_entry(item)

        # Photos have no text to read
        if item["doc_type"].startswith("photo"):
            entry["skipped"] = True
            entry["skip_reason"] = "photo"
            documents.append(entry)
            continue

        # One run only reads a limited number of documents
        if read_count >= MAX_DOCUMENTS:
            entry["skipped"] = True
            entry["skip_reason"] = "too_many_documents"
            documents.append(entry)
            continue
        read_count += 1

        if entry["ocr_status"] == "pending":
            entry["ocr_status"] = tools.run_ocr(db, item["id"])

        text_result = tools.get_document_text(db, claim_id, item["id"])
        if text_result is not None:
            entry["ocr_status"] = text_result["ocr_status"]
            entry["pages"] = text_result["pages"]
            entry["page_count"] = text_result["page_count"]
            entry["overall_confidence"] = text_result["overall_confidence"]
            entry["ocr_truncated"] = text_result["truncated"]
            entry["error"] = text_result["error"]

        documents.append(entry)

    return {"documents": documents}


# ---------------------------------------------------------------------------
# Step 3: ask the model to extract facts, one document at a time
# ---------------------------------------------------------------------------


def build_page_text(pages):
    """Join the pages of a document into one text with a marker before each page."""
    parts = []
    for page in pages:
        parts.append("[page " + str(page["page"]) + "]\n" + str(page["text"]))
    return "\n\n".join(parts)


def has_text(entry):
    """Return True if the document was read and has some text."""
    if entry["ocr_status"] in ["failed", "pending", "processing"]:
        return False

    for page in entry["pages"]:
        if str(page["text"]).strip() != "":
            return True
    return False


def extract_facts(state, llm):
    """Node: ask the model to extract facts from each readable document. Each document is a separate call."""
    model = llm.with_structured_output(DocumentExtraction)
    extractions = {}

    for entry in state["documents"]:
        if entry["skipped"] or not has_text(entry):
            continue

        field_descriptions = FIELDS_BY_DOC_TYPE.get(entry["doc_type"], FIELDS_BY_DOC_TYPE["other"])
        user_prompt = build_user_prompt(
            entry["doc_label"],
            field_descriptions,
            entry["doc_type"] in LINE_ITEM_DOC_TYPES,
            build_page_text(entry["pages"]),
            MAX_TEXT_CHARS,
        )
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]

        extraction = model.invoke(messages)
        extractions[entry["document_id"]] = extraction.model_dump()

    return {"extractions": extractions}


# ---------------------------------------------------------------------------
# Step 4: check every extracted value against the document text
# ---------------------------------------------------------------------------


def find_page(pages, quote, stated_page):
    """Return the page that contains the quote. The page the model named is tried first."""
    ordered = []
    for page in pages:
        if page["page"] == stated_page:
            ordered.append(page)
    for page in pages:
        if page["page"] != stated_page:
            ordered.append(page)

    for page in ordered:
        if checks.quote_in_text(quote, page["text"]):
            return page
    return None


def find_page_by_number(pages, number):
    """Return the page with this number, or None."""
    for page in pages:
        if page["page"] == number:
            return page
    return None


def page_details(page):
    """Return the page number, OCR confidence and method of a page, or empty values."""
    if page is None:
        return None, None, None
    return page["page"], page["confidence"], page["method"]


def is_low(confidence):
    """Return True if a confidence is under the review threshold."""
    return confidence is not None and confidence < OCR_REVIEW_THRESHOLD


def check_facts(entry, extraction, allowed_fields):
    """Check each extracted fact. A fact is verified only if its quote is on the page and holds the value."""
    facts = []
    seen_fields = []
    ignored = 0

    for fact in extraction["facts"][:MAX_FACTS]:
        field = str(fact["field"]).strip()

        # Unknown fields and repeated fields are dropped
        if field not in allowed_fields or field in seen_fields:
            ignored += 1
            continue
        seen_fields.append(field)

        quote = str(fact["evidence_quote"])
        found_page = find_page(entry["pages"], quote, fact["page"])
        verified = found_page is not None and checks.value_in_quote(fact["value"], quote)

        # A verified fact takes its page from where the quote was really found
        page_number, confidence, method = page_details(found_page)
        if found_page is None:
            page_number, confidence, method = page_details(find_page_by_number(entry["pages"], fact["page"]))

        facts.append({
            "field": field,
            "value": short_text(fact["value"], MAX_QUOTE_CHARS),
            "page": page_number,
            "confidence": confidence,
            "method": method,
            "low_confidence": is_low(confidence),
            "verified": verified,
            "evidence_quote": short_text(quote, MAX_QUOTE_CHARS),
        })

    return facts, ignored


def check_line_items(entry, extraction):
    """Check each line item. It is verified only if its quote is on the page and holds the amount."""
    items = []

    for item in extraction["line_items"][:MAX_LINE_ITEMS]:
        quote = str(item["evidence_quote"])
        found_page = find_page(entry["pages"], quote, item["page"])
        verified = found_page is not None and checks.number_in_text(item["amount"], quote)

        page_number, confidence, method = page_details(found_page)
        if found_page is None:
            page_number, confidence, method = page_details(find_page_by_number(entry["pages"], item["page"]))

        items.append({
            "description": short_text(item["description"], MAX_QUOTE_CHARS),
            "amount": float(item["amount"]),
            "page": page_number,
            "confidence": confidence,
            "low_confidence": is_low(confidence),
            "verified": verified,
            "evidence_quote": short_text(quote, MAX_QUOTE_CHARS),
        })

    return items


def new_checked_document(entry):
    """Create the checked result of one document, before any check was done."""
    return {
        "document_id": entry["document_id"],
        "doc_type": entry["doc_type"],
        "doc_label": entry["doc_label"],
        "ocr_status": entry["ocr_status"],
        "skipped": entry["skipped"],
        "skip_reason": entry["skip_reason"],
        "overall_confidence": entry["overall_confidence"],
        "pages_read": len(entry["pages"]),
        "page_count": entry["page_count"],
        "needs_human_check": False,
        "looks_like_expected_type": None,
        "notes": [],
        "facts": [],
        "line_items": [],
        "line_items_total": None,
        "issues": [],
    }


def check_reading(entry, checked):
    """Add issues about the OCR itself: not finished, unreadable, or low confidence."""
    label = entry["doc_label"]
    doc_id = entry["document_id"]

    if entry["ocr_status"] in ["pending", "processing"]:
        checked["needs_human_check"] = True
        checked["issues"].append(make_issue("ocr_not_finished", f"The text of the {label} has not been read yet.", doc_id))
        return False

    if not has_text(entry):
        checked["needs_human_check"] = True
        reason = entry["error"] or "No readable text was found."
        checked["issues"].append(make_issue("unreadable_document", f"The {label} could not be read. {reason}", doc_id))
        return False

    lowest = entry["overall_confidence"]
    for page in entry["pages"]:
        if lowest is None or page["confidence"] < lowest:
            lowest = page["confidence"]

    if is_low(lowest):
        checked["needs_human_check"] = True
        message = f"The text of the {label} was read with {lowest}% confidence on at least one page. A person should check the original."
        checked["issues"].append(make_issue("low_confidence_text", message, doc_id))

    return True


def verify_extractions(state):
    """Node: check every extracted value against the document text, and the OCR quality of each document."""
    checked_documents = []

    for entry in state["documents"]:
        checked = new_checked_document(entry)
        checked_documents.append(checked)
        label = entry["doc_label"]
        doc_id = entry["document_id"]

        if entry["skipped"]:
            if entry["skip_reason"] == "too_many_documents":
                message = f"The {label} was not read, because a claim can have at most {MAX_DOCUMENTS} readable documents."
                checked["issues"].append(make_issue("too_many_documents", message, doc_id))
            continue

        if not check_reading(entry, checked):
            continue

        extraction = state["extractions"].get(doc_id)
        if extraction is None:
            continue

        allowed_fields = []
        for field, description in FIELDS_BY_DOC_TYPE.get(entry["doc_type"], FIELDS_BY_DOC_TYPE["other"]):
            allowed_fields.append(field)

        facts, ignored = check_facts(entry, extraction, allowed_fields)
        checked["facts"] = facts
        checked["looks_like_expected_type"] = bool(extraction["looks_like_expected_type"])

        if entry["doc_type"] in LINE_ITEM_DOC_TYPES:
            items = check_line_items(entry, extraction)
            checked["line_items"] = items
            if len(items) > 0:
                total = 0.0
                for item in items:
                    total = total + item["amount"]
                checked["line_items_total"] = round(total, 2)

        for note in extraction["notes"][:MAX_NOTES]:
            if str(note).strip() != "":
                checked["notes"].append(short_text(note, MAX_QUOTE_CHARS))
        if ignored > 0:
            checked["notes"].append(f"{ignored} extracted value(s) were ignored because the field name was not allowed or was repeated.")

        if not checked["looks_like_expected_type"]:
            message = f"The text does not look like a {label}."
            checked["issues"].append(make_issue("wrong_document_type", message, doc_id))

        unverified = 0
        for fact in facts:
            if not fact["verified"]:
                unverified += 1
        for item in checked["line_items"]:
            if not item["verified"]:
                unverified += 1
        if unverified > 0:
            message = f"{unverified} value(s) from the {label} could not be found in its text and are not trusted."
            checked["issues"].append(make_issue("unverified_facts", message, doc_id))

        # The line items must add up to the total printed on the document
        total_fact = None
        for fact in facts:
            if fact["field"] == "total_amount" and fact["verified"]:
                total_fact = checks.parse_number(fact["value"])
        if total_fact is not None and checked["line_items_total"] is not None:
            if not checks.amounts_equal(total_fact, checked["line_items_total"], AMOUNT_TOLERANCE):
                message = (
                    f"The line items of the {label} add up to {format_amount(checked['line_items_total'])}, "
                    f"but the total on the document is {format_amount(total_fact)}."
                )
                checked["issues"].append(make_issue("line_items_total_mismatch", message, doc_id))

        text_was_cut = len(build_page_text(entry["pages"])) > MAX_TEXT_CHARS
        if entry["ocr_truncated"] or entry["page_count"] > len(entry["pages"]) or text_was_cut:
            message = f"Only part of the {label} was read, so some information may be missing."
            checked["issues"].append(make_issue("incomplete_reading", message, doc_id))

    return {"checked": checked_documents}


# ---------------------------------------------------------------------------
# Step 5: compare the documents with the claim form and with each other
# ---------------------------------------------------------------------------


def verified_facts(checked_documents, field):
    """Return (document, fact) pairs for every verified fact of one field."""
    found = []
    for document in checked_documents:
        for fact in document["facts"]:
            if fact["field"] == field and fact["verified"]:
                found.append((document, fact))
    return found


def check_amounts(facts, checked_documents):
    """The claimed amount must match one document total, or the sum of the document totals."""
    claimed = facts["claimed_amount"]
    totals = []
    for document, fact in verified_facts(checked_documents, "total_amount"):
        amount = checks.parse_number(fact["value"])
        if amount is not None:
            totals.append((document, amount))

    if claimed is None or len(totals) == 0:
        return []

    for document, amount in totals:
        if checks.amounts_equal(amount, claimed, AMOUNT_TOLERANCE):
            return []

    total_sum = 0.0
    written = []
    for document, amount in totals:
        total_sum = total_sum + amount
        written.append(document["doc_label"] + " " + format_amount(amount))

    if checks.amounts_equal(total_sum, claimed, AMOUNT_TOLERANCE):
        return []

    message = f"The claimed amount ({format_amount(claimed)}) does not match the document totals: " + ", ".join(written) + "."
    return [make_issue("amount_mismatch", message)]


def check_names(facts, checked_documents):
    """Every name on a document must match the policyholder or a name on the claim form."""
    details = facts["details"]
    known_names = [facts["policyholder_name"]]
    for key in ["patient_name", "driver_name", "business_name"]:
        if str(details.get(key, "")).strip() != "":
            known_names.append(details[key])

    issues = []
    for field in NAME_FIELDS:
        for document, fact in verified_facts(checked_documents, field):
            matched = False
            for known in known_names:
                if checks.names_match(fact["value"], known):
                    matched = True
            if not matched:
                message = f"The name '{fact['value']}' on the {document['doc_label']} does not match the claim form or the policyholder."
                issues.append(make_issue("name_mismatch", message, document["document_id"]))
    return issues


def check_form_values(facts, checked_documents):
    """Hospital name, vehicle registration and property address must match the claim form."""
    details = facts["details"]
    issues = []

    form_hospital = str(details.get("hospital_name", "")).strip()
    if form_hospital != "":
        for document, fact in verified_facts(checked_documents, "hospital_name"):
            if not checks.names_match(fact["value"], form_hospital):
                message = f"The hospital '{fact['value']}' on the {document['doc_label']} does not match the claim form."
                issues.append(make_issue("name_mismatch", message, document["document_id"]))

    form_registration = str(details.get("vehicle_registration", "")).strip()
    if form_registration != "":
        for document, fact in verified_facts(checked_documents, "vehicle_registration"):
            if checks.normalize_registration(fact["value"]) != checks.normalize_registration(form_registration):
                message = f"The registration '{fact['value']}' on the {document['doc_label']} does not match the claim form."
                issues.append(make_issue("registration_mismatch", message, document["document_id"]))

    form_address = str(details.get("property_address", "")).strip()
    if form_address != "":
        for document, fact in verified_facts(checked_documents, "property_address"):
            if not checks.addresses_match(fact["value"], form_address):
                message = f"The address '{fact['value']}' on the {document['doc_label']} does not match the claim form."
                issues.append(make_issue("address_mismatch", message, document["document_id"]))

    return issues


def check_dates(facts, checked_documents):
    """Dates must agree between documents, with the claim form, and with the date of loss."""
    issues = []

    loss_date = None
    if facts["loss_date"]:
        loss_date = datetime.fromisoformat(facts["loss_date"]).date()

    for field in DATE_FIELDS:
        found = []
        for document, fact in verified_facts(checked_documents, field):
            parsed = checks.parse_date(fact["value"])
            if parsed is not None:
                found.append((document, parsed))

        # The same date must not differ between documents
        different_dates = set()
        for document, parsed in found:
            different_dates.add(parsed)
        if len(different_dates) > 1:
            issues.append(make_issue("date_mismatch", f"The {field.replace('_', ' ')} is not the same in all documents."))

        # Compare with the claim form, or with the date of loss for an incident date
        reference = None
        allowed_days = 0
        if field == "incident_date":
            reference = loss_date
            allowed_days = DATE_TOLERANCE_DAYS
        elif field in ["admission_date", "discharge_date"]:
            reference = checks.parse_date(str(facts["details"].get(field, "")))

        if reference is None:
            continue

        for document, parsed in found:
            if not checks.dates_close(parsed, reference, allowed_days):
                message = f"The {field.replace('_', ' ')} on the {document['doc_label']} ({parsed}) does not match the claim ({reference})."
                issues.append(make_issue("date_mismatch", message, document["document_id"]))

    return issues


def cross_check(state):
    """Node: compare the checked documents with the claim form and with each other."""
    facts = state["facts"]
    checked_documents = state["checked"]

    issues = []
    issues.extend(check_amounts(facts, checked_documents))
    issues.extend(check_names(facts, checked_documents))
    issues.extend(check_form_values(facts, checked_documents))
    issues.extend(check_dates(facts, checked_documents))
    return {"issues": issues}


# ---------------------------------------------------------------------------
# Step 6: build the result
# ---------------------------------------------------------------------------


def build_result(state):
    """Node: collect the documents, issues and flags into the final result."""
    facts = state["facts"]
    listing = state["listing"]

    all_issues = []
    for document in state["checked"]:
        all_issues.extend(document["issues"])
    all_issues.extend(state["issues"])

    flags = []
    for issue in all_issues:
        if issue["code"] not in flags:
            flags.append(issue["code"])
    if len(listing["missing_documents"]) > 0:
        flags.append("missing_documents")

    # Missing documents alone only ask the customer for more, every other flag needs a person to look
    status = "complete"
    if flags == ["missing_documents"]:
        status = "incomplete"
    elif len(flags) > 0:
        status = "needs_review"

    documents_read = 0
    for document in state["checked"]:
        if not document["skipped"]:
            documents_read += 1

    result = {
        "agent": AGENT_NAME,
        "agent_version": AGENT_VERSION,
        "claim_id": facts["claim_id"],
        "claim_number": facts["claim_number"],
        "insurance_line": facts["line"],
        "status": status,
        "flags": flags,
        "documents_read": documents_read,
        "documents": state["checked"],
        "issues": all_issues,
        "missing_documents": listing["missing_documents"],
        "required_documents": listing["required_documents"],
    }
    return {"result": result}