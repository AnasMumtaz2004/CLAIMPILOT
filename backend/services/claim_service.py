import uuid
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from database.models import ApprovalDecision
from database.models import Claim
from database.models import ClaimAssignment
from database.models import ClaimDocument
from database.models import ClaimMessage
from database.models import ClaimStatusHistory
from database.models import ClaimTask
from database.models import Policy
from database.models import StaffReview
from database.models import User
from database.models import utc_now
from services.audit_service import add_audit
from services.email_service import send_claim_received
from database.models import WorkflowEvent
from database.models import AgentExecutionLog

# What the customer sees for each status
STATUS_INFO = {
    "draft": {"label": "Draft", "description": "Your claim is saved but not submitted yet."},
    "submitted": {"label": "Submitted", "description": "We have received your claim."},
    "documents_review": {"label": "Documents under review", "description": "We are checking your documents."},
    "info_required": {
        "label": "Additional information required",
        "description": "We need more from you. Check your messages and upload any requested documents.",
    },
    "policy_verification": {"label": "Policy verification", "description": "We are checking your claim against your policy."},
    "assessment": {"label": "Assessment in progress", "description": "We are assessing your claim."},
    "approval_review": {"label": "Under approval review", "description": "A claims officer is reviewing your claim."},
    "approved": {"label": "Approved", "description": "Your claim has been approved."},
    "rejected": {"label": "Rejected", "description": "Your claim was not approved. Check your messages for details."},
    "settled": {"label": "Settled", "description": "Your claim has been settled."},
    "closed": {"label": "Closed", "description": "This claim is closed."},
}

LINE_LABELS = {
    "health": "Health",
    "private_vehicle": "Private vehicle",
    "commercial": "Commercial",
    "home": "Home",
}

DOMAIN_FIELDS = {
    "health": [
        {"name": "patient_name", "label": "Patient name", "type": "text", "required": True},
        {"name": "hospital_name", "label": "Hospital name", "type": "text", "required": True},
        {"name": "admission_date", "label": "Admission date", "type": "date", "required": False},
        {"name": "discharge_date", "label": "Discharge date", "type": "date", "required": False},
        {"name": "diagnosis", "label": "Diagnosis", "type": "text", "required": True},
    ],
    "private_vehicle": [
        {"name": "vehicle_registration", "label": "Vehicle registration number", "type": "text", "required": True},
        {"name": "driver_name", "label": "Driver name", "type": "text", "required": False},
        {"name": "accident_location", "label": "Accident location", "type": "text", "required": True},
        {"name": "police_report_filed", "label": "Police report filed", "type": "select", "required": False, "options": ["yes", "no"]},
    ],
    "commercial": [
        {"name": "business_name", "label": "Business name", "type": "text", "required": True},
        {"name": "premises_address", "label": "Premises address", "type": "text", "required": False},
        {
            "name": "loss_type",
            "label": "Type of loss",
            "type": "select",
            "required": True,
            "options": ["fire", "theft", "water_damage", "other"],
        },
    ],
    "home": [
        {"name": "property_address", "label": "Property address", "type": "text", "required": True},
        {
            "name": "loss_type",
            "label": "Type of loss",
            "type": "select",
            "required": True,
            "options": ["fire", "theft", "water_damage", "storm", "other"],
        },
    ],
}

DOC_TYPE_LABELS = {
    "photo_front": "Photo: front of vehicle",
    "photo_rear": "Photo: rear of vehicle",
    "photo_left": "Photo: left side of vehicle",
    "photo_right": "Photo: right side of vehicle",
    "photo_closeup": "Photo: close-up of damage",
    "photo_damage": "Photo of the damage",
    "estimate": "Repair estimate",
    "police_report": "Police report",
    "discharge_summary": "Discharge summary",
    "bill": "Hospital bill",
    "prescription": "Prescription",
    "incident_report": "Incident report",
    "invoice": "Invoice or proof of purchase",
    "inventory_list": "List of damaged items",
    "other": "Other document",
}

DOC_TYPES_BY_LINE = {
    "health": ["discharge_summary", "bill", "prescription", "other"],
    "private_vehicle": ["photo_front", "photo_rear", "photo_left", "photo_right", "photo_closeup", "estimate", "police_report", "other"],
    "commercial": ["photo_damage", "incident_report", "invoice", "inventory_list", "other"],
    "home": ["photo_damage", "estimate", "incident_report", "invoice", "other"],
}

REQUIRED_DOCS_BY_LINE = {
    "health": ["discharge_summary", "bill"],
    "private_vehicle": ["photo_front", "estimate"],
    "commercial": ["photo_damage", "incident_report"],
    "home": ["photo_damage", "estimate"],
}

# Statuses where a claims officer can still make a decision
REVIEW_STATUSES = [
    "submitted",
    "documents_review",
    "policy_verification",
    "assessment",
    "approval_review",
]

# Statuses that mean the claim has a final outcome
DECIDED_STATUSES = ["approved", "rejected", "settled", "closed"]

# The views the staff queue can show
STAFF_VIEWS = ["all", "queue", "waiting", "escalated", "history"]

TASK_INFO_REQUEST = "info_request"
TASK_ESCALATION = "specialist_escalation"

# Each decision lists the statuses it allows and the status it leads to (None keeps it)
DECISION_RULES = {
    "approve": {"from": REVIEW_STATUSES, "to": "approved"},
    "reject": {"from": REVIEW_STATUSES, "to": "rejected"},
    "request_info": {"from": REVIEW_STATUSES, "to": "info_required"},
    "escalate": {"from": REVIEW_STATUSES, "to": None},
}

# Decisions that need an internal reason
REASON_REQUIRED = ["reject", "escalate"]

# Decisions that need a message the customer can read
MESSAGE_REQUIRED = ["reject", "request_info"]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def as_utc(dt):
    """Return the datetime as timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def status_label(status):
    """Return the customer-friendly label for a status code."""
    info = STATUS_INFO.get(status)
    if info is None:
        return status
    return info["label"]


def claim_to_dict(claim):
    """Convert a claim to a dictionary."""
    info = STATUS_INFO.get(claim.status, {"label": claim.status, "description": ""})

    loss_date = None
    if claim.loss_date is not None:
        loss_date = as_utc(claim.loss_date).isoformat()

    claimed_amount = None
    if claim.claimed_amount is not None:
        claimed_amount = float(claim.claimed_amount)

    submitted_at = None
    if claim.submitted_at is not None:
        submitted_at = as_utc(claim.submitted_at).isoformat()

    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "line": claim.line,
        "status": claim.status,
        "status_label": info["label"],
        "status_description": info["description"],
        "loss_date": loss_date,
        "claimed_amount": claimed_amount,
        "description": claim.description,
        "details": claim.details or {},
        "version": claim.version,
        "policy_id": claim.policy_id,
        "submitted_at": submitted_at,
        "created_at": as_utc(claim.created_at).isoformat(),
        "updated_at": as_utc(claim.updated_at).isoformat(),
    }


def staff_claim_to_dict(claim, customer, policy):
    """Convert a claim to a dictionary with customer and policy details for staff."""
    data = claim_to_dict(claim)
    data["customer_name"] = customer.full_name
    data["customer_email"] = customer.email
    data["policy_number"] = policy.policy_number
    return data


def policy_to_dict(policy):
    """Convert a policy to a dictionary."""
    return {
        "id": policy.id,
        "policy_number": policy.policy_number,
        "line": policy.line,
        "product": policy.product,
        "sum_insured": float(policy.sum_insured),
        "start_date": policy.start_date.isoformat(),
        "end_date": policy.end_date.isoformat(),
    }


def message_to_dict(msg):
    """Convert a message to a dictionary."""
    return {
        "id": msg.id,
        "claim_id": msg.claim_id,
        "sender_role": msg.sender_role,
        "body": msg.body,
        "created_at": as_utc(msg.created_at).isoformat(),
    }


def history_to_dict(entry):
    """Convert a status history entry to a dictionary."""
    return {
        "id": entry.id,
        "status": entry.status,
        "label": entry.label,
        "description": entry.description,
        "created_at": as_utc(entry.created_at).isoformat(),
    }


def get_claim_config():
    """Return form fields and document types for every insurance line."""
    lines = {}
    for line, fields in DOMAIN_FIELDS.items():
        document_types = []
        for doc_type in DOC_TYPES_BY_LINE[line]:
            document_types.append({
                "value": doc_type,
                "label": DOC_TYPE_LABELS[doc_type],
                "required": doc_type in REQUIRED_DOCS_BY_LINE[line],
            })
        lines[line] = {
            "label": LINE_LABELS[line],
            "fields": fields,
            "document_types": document_types,
        }
    return {"lines": lines}


def add_status_history(db, claim, status, actor_id, description=None):
    """Record a customer-safe status entry for a claim."""
    info = STATUS_INFO[status]

    # Use the standard text unless a custom one is given
    text = info["description"]
    if description is not None:
        text = description

    entry = ClaimStatusHistory(
        claim_id=claim.id,
        status=status,
        label=info["label"],
        description=text,
        actor_id=actor_id,
    )
    db.add(entry)


# ---------------------------------------------------------------------------
# Customer side
# ---------------------------------------------------------------------------


def get_own_claim(db, claim_id, user):
    """Return a claim owned by this customer or raise 404."""
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.claimant_id == user.id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return claim


def list_customer_policies(db, user):
    """Return this customer's policies as dictionaries."""
    policies = db.query(Policy).filter(Policy.owner_id == user.id).all()
    result = []
    for policy in policies:
        result.append(policy_to_dict(policy))
    return result


def list_customer_claims(db, user):
    """Return this customer's claims, newest activity first."""
    claims = db.query(Claim).filter(Claim.claimant_id == user.id).order_by(desc(Claim.updated_at)).all()
    result = []
    for claim in claims:
        result.append(claim_to_dict(claim))
    return result


def create_draft(db, user, body):
    """Create an empty draft claim on one of the customer's policies."""
    policy = db.query(Policy).filter(Policy.id == body.policy_id, Policy.owner_id == user.id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found.")
    if policy.line not in DOMAIN_FIELDS:
        raise HTTPException(status_code=400, detail="This policy type is not supported yet.")

    claim = Claim(
        policy_id=policy.id,
        claimant_id=user.id,
        line=policy.line,
        status="draft",
    )
    db.add(claim)
    db.flush()

    add_status_history(db, claim, "draft", user.id)
    add_audit(db, user.id, "draft_created", claim.id, {"policy_id": policy.id})
    db.commit()
    db.refresh(claim)
    return claim_to_dict(claim)


def update_draft(db, user, claim_id, body):
    """Save draft changes if the version the client sent is still current."""
    claim = get_own_claim(db, claim_id, user)
    if claim.status != "draft":
        raise HTTPException(status_code=400, detail="Only drafts can be edited.")

    allowed_fields = {}
    for field in DOMAIN_FIELDS[claim.line]:
        allowed_fields[field["name"]] = field

    # Reject unknown form fields and very long values
    for key, value in body.details.items():
        if key not in allowed_fields:
            raise HTTPException(status_code=400, detail=f"Unknown field: {key}")
        if len(value) > 500:
            raise HTTPException(status_code=400, detail=f"{allowed_fields[key]['label']} is too long.")

    loss_date = None
    if body.loss_date is not None:
        loss_date = as_utc(body.loss_date)

    claimed_amount = None
    if body.claimed_amount is not None:
        claimed_amount = Decimal(str(body.claimed_amount))

    # Only save if the version still matches, so an old tab cannot overwrite newer data
    changed_rows = db.query(Claim).filter(
        Claim.id == claim.id,
        Claim.version == body.version,
        Claim.status == "draft",
    ).update(
        {
            "loss_date": loss_date,
            "claimed_amount": claimed_amount,
            "description": body.description,
            "details": body.details,
            "version": body.version + 1,
            "updated_at": utc_now(),
        },
        synchronize_session=False,
    )

    if changed_rows == 0:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This draft was changed somewhere else. Reload it to get the latest version.",
        )

    db.commit()
    db.refresh(claim)
    return claim_to_dict(claim)


def find_submit_problems(db, claim, policy):
    """Return a list of things the customer must fix before submitting."""
    problems = []
    now = datetime.now(timezone.utc)

    if claim.loss_date is None:
        problems.append("loss date")
    else:
        loss_date = as_utc(claim.loss_date)
        if loss_date > now:
            problems.append("loss date cannot be in the future")
        elif loss_date < as_utc(policy.start_date) or loss_date > as_utc(policy.end_date):
            problems.append("loss date must be inside the policy period")

    if claim.claimed_amount is None or claim.claimed_amount <= 0:
        problems.append("claimed amount")

    details = claim.details or {}
    for field in DOMAIN_FIELDS[claim.line]:
        value = details.get(field["name"], "")
        if field["required"] and not value.strip():
            problems.append(field["label"].lower())

    uploaded_types = []
    rows = db.query(ClaimDocument.doc_type).filter(ClaimDocument.claim_id == claim.id).all()
    for row in rows:
        uploaded_types.append(row[0])

    for doc_type in REQUIRED_DOCS_BY_LINE[claim.line]:
        if doc_type not in uploaded_types:
            problems.append("document: " + DOC_TYPE_LABELS[doc_type].lower())

    return problems


def make_claim_number(now):
    """Return a unique claim number such as CLM-2026-A1B2C3D4."""
    return f"CLM-{now.year}-{uuid.uuid4().hex[:8].upper()}"


def submit_claim(db, user, claim_id):
    """Submit a complete draft. Submitting twice returns the same claim."""
    claim = get_own_claim(db, claim_id, user)

    # A claim that is already submitted is returned unchanged
    if claim.status != "draft":
        return claim_to_dict(claim)

    policy = db.query(Policy).filter(Policy.id == claim.policy_id).first()
    problems = find_submit_problems(db, claim, policy)
    if problems:
        raise HTTPException(status_code=400, detail="Fix these before submitting: " + ", ".join(problems))

    now = utc_now()
    claim_number = make_claim_number(now)

    # Only one request can move the claim out of draft
    changed_rows = db.query(Claim).filter(
        Claim.id == claim.id,
        Claim.status == "draft",
    ).update(
        {
            "status": "submitted",
            "claim_number": claim_number,
            "submitted_at": now,
            "version": Claim.version + 1,
            "updated_at": now,
        },
        synchronize_session=False,
    )

    if changed_rows == 0:
        db.rollback()
        db.refresh(claim)
        return claim_to_dict(claim)

    add_status_history(db, claim, "submitted", user.id)
    add_audit(
        db,
        user.id,
        "claim_filed",
        claim.id,
        {
            "claim_number": claim_number,
            "policy_id": policy.id,
            "claimed_amount": str(claim.claimed_amount),
        },
    )
    db.add(
        WorkflowEvent(
            claim_id=claim.id,
            event_type="claim.submitted",
            status="pending",
        )
    )

    db.commit()
    
    db.commit()
    db.refresh(claim)

    try:
        send_claim_received(db, user, claim, policy.policy_number)
        db.commit()
    except Exception:
        # An email problem must never undo a claim that is already filed
        db.rollback()

    return claim_to_dict(claim)


def respond_to_info_request(db, user, claim_id):
    """Let the customer say they have answered the information request."""
    claim = get_own_claim(db, claim_id, user)

    # Answering twice is harmless, so return the claim as it is
    if claim.status != "info_required":
        return claim_to_dict(claim)

    task = db.query(ClaimTask).filter(
        ClaimTask.claim_id == claim.id,
        ClaimTask.task_type == TASK_INFO_REQUEST,
        ClaimTask.status == "open",
    ).order_by(desc(ClaimTask.created_at)).first()

    # Go back to the stage the claim was in before we asked
    resume_status = "submitted"
    if task is not None and task.resume_status:
        resume_status = task.resume_status

    now = utc_now()
    changed_rows = db.query(Claim).filter(
        Claim.id == claim.id,
        Claim.status == "info_required",
    ).update(
        {
            "status": resume_status,
            "version": Claim.version + 1,
            "updated_at": now,
        },
        synchronize_session=False,
    )

    if changed_rows == 0:
        db.rollback()
        db.refresh(claim)
        return claim_to_dict(claim)

    if task is not None:
        task.status = "done"
        task.completed_at = now

    add_status_history(
        db,
        claim,
        resume_status,
        user.id,
        "Thank you. We have received your additional information.",
    )
    add_audit(db, user.id, "info_request_answered", claim.id, {"resume_status": resume_status})
    db.commit()
    db.refresh(claim)
    return claim_to_dict(claim)


def list_status_history(db, claim):
    """Return the customer-visible status history, oldest first."""
    entries = db.query(ClaimStatusHistory).filter(
        ClaimStatusHistory.claim_id == claim.id,
    ).order_by(ClaimStatusHistory.created_at).all()
    result = []
    for entry in entries:
        result.append(history_to_dict(entry))
    return result


def list_claim_messages(db, claim):
    """Return all messages on a claim, oldest first."""
    messages = db.query(ClaimMessage).filter(
        ClaimMessage.claim_id == claim.id,
    ).order_by(ClaimMessage.created_at).all()
    result = []
    for message in messages:
        result.append(message_to_dict(message))
    return result


def add_claim_message(db, user, claim, body):
    """Save a new message on a claim."""
    message = ClaimMessage(
        claim_id=claim.id,
        sender_id=user.id,
        sender_role=user.role,
        body=body.body,
    )
    db.add(message)
    db.flush()

    add_audit(db, user.id, "message_sent", claim.id, {"message_id": message.id})
    db.commit()
    return message_to_dict(message)


# ---------------------------------------------------------------------------
# Staff side: tasks, notes and assignment
# ---------------------------------------------------------------------------


def get_claim_for_staff(db, claim_id):
    """Return a submitted claim for staff or raise 404. Drafts stay private."""
    claim = db.query(Claim).filter(Claim.id == claim_id, Claim.status != "draft").first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return claim


def task_to_dict(task, claim_number):
    """Convert a task to a dictionary."""
    completed_at = None
    if task.completed_at is not None:
        completed_at = as_utc(task.completed_at).isoformat()

    return {
        "id": task.id,
        "claim_id": task.claim_id,
        "claim_number": claim_number,
        "task_type": task.task_type,
        "status": task.status,
        "title": task.title,
        "details": task.details,
        "created_at": as_utc(task.created_at).isoformat(),
        "completed_at": completed_at,
    }


def list_claim_tasks(db, claim):
    """Return all tasks of one claim, newest first."""
    tasks = db.query(ClaimTask).filter(ClaimTask.claim_id == claim.id).order_by(desc(ClaimTask.created_at)).all()
    result = []
    for task in tasks:
        result.append(task_to_dict(task, claim.claim_number))
    return result


def list_open_tasks(db):
    """Return open tasks across all claims, newest first."""
    rows = db.query(ClaimTask, Claim).join(
        Claim,
        ClaimTask.claim_id == Claim.id,
    ).filter(
        ClaimTask.status == "open",
    ).order_by(desc(ClaimTask.created_at)).limit(20).all()

    result = []
    for task, claim in rows:
        result.append(task_to_dict(task, claim.claim_number))
    return result


def has_open_escalation(db, claim_id):
    """Return True if the claim already has an open specialist review task."""
    task = db.query(ClaimTask).filter(
        ClaimTask.claim_id == claim_id,
        ClaimTask.task_type == TASK_ESCALATION,
        ClaimTask.status == "open",
    ).first()
    return task is not None


def close_open_tasks(db, claim_id, task_type, now):
    """Mark all open tasks of one type on a claim as done."""
    tasks = db.query(ClaimTask).filter(
        ClaimTask.claim_id == claim_id,
        ClaimTask.task_type == task_type,
        ClaimTask.status == "open",
    ).all()
    for task in tasks:
        task.status = "done"
        task.completed_at = now


def note_to_dict(note, staff_name):
    """Convert a private staff note to a dictionary."""
    return {
        "id": note.id,
        "note": note.note,
        "staff_name": staff_name,
        "created_at": as_utc(note.created_at).isoformat(),
    }


def list_staff_notes(db, claim):
    """Return private staff notes on a claim, newest first."""
    rows = db.query(StaffReview, User).join(
        User,
        StaffReview.staff_id == User.id,
    ).filter(
        StaffReview.claim_id == claim.id,
    ).order_by(desc(StaffReview.created_at)).all()

    result = []
    for note, staff in rows:
        result.append(note_to_dict(note, staff.full_name))
    return result


def add_staff_note(db, staff, claim_id, body):
    """Save a private note on a claim."""
    claim = get_claim_for_staff(db, claim_id)

    text = body.note.strip()
    if not text:
        raise HTTPException(status_code=400, detail="The note cannot be empty.")

    note = StaffReview(claim_id=claim.id, staff_id=staff.id, note=text)
    db.add(note)
    db.flush()

    add_audit(db, staff.id, "staff_note_added", claim.id, {"note_id": note.id})
    db.commit()
    return note_to_dict(note, staff.full_name)


def get_current_assignee(db, claim):
    """Return the officer the claim is assigned to, or None."""
    row = db.query(ClaimAssignment, User).join(
        User,
        ClaimAssignment.staff_id == User.id,
    ).filter(
        ClaimAssignment.claim_id == claim.id,
    ).order_by(desc(ClaimAssignment.created_at)).first()

    if row is None:
        return None

    assignment, officer = row
    return {
        "staff_id": officer.id,
        "staff_name": officer.full_name,
        "assigned_at": as_utc(assignment.created_at).isoformat(),
    }


def assign_claim_to_staff(db, staff, claim_id):
    """Assign a claim to the logged-in officer."""
    claim = get_claim_for_staff(db, claim_id)

    # Assigning to the same officer twice changes nothing
    current = get_current_assignee(db, claim)
    if current is not None and current["staff_id"] == staff.id:
        return current

    assignment = ClaimAssignment(
        claim_id=claim.id,
        staff_id=staff.id,
        assigned_by=staff.id,
    )
    db.add(assignment)
    db.flush()

    add_audit(db, staff.id, "claim_assigned", claim.id, {"staff_id": staff.id})
    db.commit()
    return get_current_assignee(db, claim)


# ---------------------------------------------------------------------------
# Staff side: decisions
# ---------------------------------------------------------------------------


def find_allowed_decisions(db, claim):
    """Return the decisions an officer can make on this claim right now."""
    allowed = []
    for decision, rule in DECISION_RULES.items():
        if claim.status not in rule["from"]:
            continue
        if decision == "escalate" and has_open_escalation(db, claim.id):
            continue
        allowed.append(decision)
    return allowed


def decision_to_dict(record, staff_name):
    """Convert a decision to a dictionary."""
    return {
        "id": record.id,
        "claim_id": record.claim_id,
        "decision": record.decision,
        "reason": record.reason,
        "customer_message": record.customer_message,
        "prior_status": record.prior_status,
        "prior_status_label": status_label(record.prior_status),
        "new_status": record.new_status,
        "new_status_label": status_label(record.new_status),
        "staff_name": staff_name,
        "created_at": as_utc(record.created_at).isoformat(),
    }


def list_decisions(db, claim):
    """Return the decision history of a claim, oldest first."""
    rows = db.query(ApprovalDecision, User).join(
        User,
        ApprovalDecision.staff_id == User.id,
    ).filter(
        ApprovalDecision.claim_id == claim.id,
    ).order_by(ApprovalDecision.created_at).all()

    result = []
    for record, staff in rows:
        result.append(decision_to_dict(record, staff.full_name))
    return result


def record_decision(db, staff, claim_id, decision, body):
    """Apply an officer decision to a claim and save it."""
    claim = get_claim_for_staff(db, claim_id)
    rule = DECISION_RULES[decision]
    reason = body.reason.strip()
    customer_message = body.customer_message.strip()

    # The claim must be in a stage where this decision is allowed
    if claim.status not in rule["from"]:
        label = status_label(claim.status)
        raise HTTPException(status_code=400, detail=f"A claim that is '{label}' cannot receive this decision.")

    if decision == "escalate" and has_open_escalation(db, claim.id):
        raise HTTPException(status_code=400, detail="This claim is already escalated for specialist review.")

    # Some decisions need a written reason or a message for the customer
    if decision in REASON_REQUIRED and not reason:
        raise HTTPException(status_code=400, detail="A reason is required for this decision.")
    if decision in MESSAGE_REQUIRED and not customer_message:
        raise HTTPException(status_code=400, detail="A message for the customer is required for this decision.")

    # Escalations are internal, so nothing is sent to the customer
    if decision == "escalate":
        customer_message = ""

    prior_status = claim.status
    new_status = rule["to"]
    if new_status is None:
        new_status = prior_status

    # Only apply the decision if nobody changed the claim in the meantime
    now = utc_now()
    changed_rows = db.query(Claim).filter(
        Claim.id == claim.id,
        Claim.status == prior_status,
    ).update(
        {
            "status": new_status,
            "version": Claim.version + 1,
            "updated_at": now,
        },
        synchronize_session=False,
    )

    if changed_rows == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="This claim was changed by someone else. Reload and try again.")

    record = ApprovalDecision(
        claim_id=claim.id,
        staff_id=staff.id,
        decision=decision,
        reason=reason,
        customer_message=customer_message,
        prior_status=prior_status,
        new_status=new_status,
    )
    db.add(record)
    db.flush()

    # The customer only sees a status entry when the status really changed
    if new_status != prior_status:
        add_status_history(db, claim, new_status, staff.id)

    # The customer message becomes a normal message on the claim
    if customer_message:
        message = ClaimMessage(
            claim_id=claim.id,
            sender_id=staff.id,
            sender_role=staff.role,
            body=customer_message,
        )
        db.add(message)

    if decision == "request_info":
        task = ClaimTask(
            claim_id=claim.id,
            task_type=TASK_INFO_REQUEST,
            status="open",
            title="Information requested from customer",
            details=customer_message,
            resume_status=prior_status,
            created_by=staff.id,
        )
        db.add(task)

    if decision == "escalate":
        task = ClaimTask(
            claim_id=claim.id,
            task_type=TASK_ESCALATION,
            status="open",
            title="Specialist review",
            details=reason,
            created_by=staff.id,
        )
        db.add(task)

    # A final decision ends any open specialist review
    if decision in ["approve", "reject"]:
        close_open_tasks(db, claim.id, TASK_ESCALATION, now)

    add_audit(
        db,
        staff.id,
        "decision_recorded",
        claim.id,
        {
            "decision_id": record.id,
            "decision": decision,
            "staff_role": staff.role,
            "prior_status": prior_status,
            "new_status": new_status,
            "reason": reason,
        },
    )
    db.commit()
    return decision_to_dict(record, staff.full_name)


# ---------------------------------------------------------------------------
# Staff side: queue, dashboard and claim detail
# ---------------------------------------------------------------------------


def list_staff_claims(db, view, line, search):
    """Return submitted claims for the staff queue, filtered by view, line and search."""
    if view not in STAFF_VIEWS:
        raise HTTPException(status_code=400, detail="Unknown view.")

    # Drafts never appear for staff
    query = db.query(Claim, User, Policy)
    query = query.join(User, Claim.claimant_id == User.id)
    query = query.join(Policy, Claim.policy_id == Policy.id)
    query = query.filter(Claim.status != "draft")

    if view == "queue":
        query = query.filter(Claim.status.in_(REVIEW_STATUSES))
    elif view == "waiting":
        query = query.filter(Claim.status == "info_required")
    elif view == "history":
        query = query.filter(Claim.status.in_(DECIDED_STATUSES))
    elif view == "escalated":
        escalated_ids = select(ClaimTask.claim_id).where(
            ClaimTask.task_type == TASK_ESCALATION,
            ClaimTask.status == "open",
        )
        query = query.filter(Claim.id.in_(escalated_ids))

    if line:
        query = query.filter(Claim.line == line)

    # Search matches claim number, customer name, customer email or policy number
    if search:
        pattern = "%" + search.strip() + "%"
        query = query.filter(
            or_(
                Claim.claim_number.ilike(pattern),
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                Policy.policy_number.ilike(pattern),
            )
        )

    # The work queue shows the oldest claims first, other views show the newest activity first
    if view == "queue":
        query = query.order_by(asc(Claim.submitted_at))
    else:
        query = query.order_by(desc(Claim.updated_at))

    rows = query.all()
    result = []
    for claim, customer, policy in rows:
        result.append(staff_claim_to_dict(claim, customer, policy))
    return result


def get_staff_dashboard(db):
    """Return counts, open tasks and recent status changes for the staff dashboard."""
    queue_count = db.query(func.count(Claim.id)).filter(Claim.status.in_(REVIEW_STATUSES)).scalar()
    waiting_count = db.query(func.count(Claim.id)).filter(Claim.status == "info_required").scalar()
    decided_count = db.query(func.count(Claim.id)).filter(Claim.status.in_(DECIDED_STATUSES)).scalar()

    escalated_count = db.query(func.count(func.distinct(ClaimTask.claim_id))).filter(
        ClaimTask.task_type == TASK_ESCALATION,
        ClaimTask.status == "open",
    ).scalar()

    rows = db.query(ClaimStatusHistory, Claim).join(
        Claim,
        ClaimStatusHistory.claim_id == Claim.id,
    ).filter(
        Claim.status != "draft",
        ClaimStatusHistory.status != "draft",
    ).order_by(desc(ClaimStatusHistory.created_at)).limit(10).all()

    recent_activity = []
    for entry, claim in rows:
        recent_activity.append({
            "id": entry.id,
            "claim_id": claim.id,
            "claim_number": claim.claim_number,
            "label": entry.label,
            "created_at": as_utc(entry.created_at).isoformat(),
        })

    return {
        "queue_count": queue_count,
        "waiting_count": waiting_count,
        "escalated_count": escalated_count,
        "decided_count": decided_count,
        "open_tasks": list_open_tasks(db),
        "recent_activity": recent_activity,
    }


def build_staff_claim_detail(db, claim):
    """Collect everything a claims officer needs to review one claim."""
    customer = db.query(User).filter(User.id == claim.claimant_id).first()
    policy = db.query(Policy).filter(Policy.id == claim.policy_id).first()

    # Staff also see the deductible and co-payment of the policy
    policy_data = policy_to_dict(policy)
    policy_data["deductible"] = float(policy.deductible)
    policy_data["copay_percent"] = float(policy.copay_percent)

    return {
        "claim": staff_claim_to_dict(claim, customer, policy),
        "policy": policy_data,
        "line_label": LINE_LABELS.get(claim.line, claim.line),
        "form_fields": DOMAIN_FIELDS.get(claim.line, []),
        "doc_type_labels": DOC_TYPE_LABELS,
        "messages": list_claim_messages(db, claim),
        "history": list_status_history(db, claim),
        "decisions": list_decisions(db, claim),
        "notes": list_staff_notes(db, claim),
        "tasks": list_claim_tasks(db, claim),
        "assignee": get_current_assignee(db, claim),
        "allowed_decisions": find_allowed_decisions(db, claim),
        "agent_runs": [
    {
        "agent_name": run.agent_name,
        "agent_version": run.agent_version,
        "status": run.status,
        "output": run.output,
        "error": run.error,
        "duration_ms": run.duration_ms,
        "created_at": run.created_at.isoformat(),
    }
    for run in (
        db.query(AgentExecutionLog)
        .filter(
            AgentExecutionLog.claim_id == claim.id
        )
        .order_by(
            AgentExecutionLog.created_at.asc()
        )
        .all()
    )
],
    }

# ---------------------------------------------------------------------------
# Facts for the AI agents
# ---------------------------------------------------------------------------


def get_submitted_claim(db, claim_id):
    """Return a submitted claim, or None. Drafts are never given to the agents."""
    return db.query(Claim).filter(Claim.id == claim_id, Claim.status != "draft").first()


def get_claim_facts(db, claim_id):
    """Return the facts an agent needs about a claim, or None when there is no such claim."""
    claim = get_submitted_claim(db, claim_id)
    if claim is None:
        return None

    customer = db.query(User).filter(User.id == claim.claimant_id).first()
    policy = db.query(Policy).filter(Policy.id == claim.policy_id).first()

    policy_facts = {"found": False}
    if policy is not None:
        policy_facts = {
            "found": True,
            "policy_number": policy.policy_number,
            "product": policy.product,
            "line": policy.line,
            "start_date": as_utc(policy.start_date).isoformat(),
            "end_date": as_utc(policy.end_date).isoformat(),
            "sum_insured": float(policy.sum_insured),
            "deductible": float(policy.deductible),
            "copay_percent": float(policy.copay_percent),
            "owner_matches": policy.owner_id == claim.claimant_id,
        }

    loss_date = None
    if claim.loss_date is not None:
        loss_date = as_utc(claim.loss_date).isoformat()

    claimed_amount = None
    if claim.claimed_amount is not None:
        claimed_amount = float(claim.claimed_amount)

    policyholder_name = ""
    if customer is not None:
        policyholder_name = customer.full_name

    return {
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "line": claim.line,
        "status": claim.status,
        "loss_date": loss_date,
        "claimed_amount": claimed_amount,
        "description": claim.description or "",
        "details": claim.details or {},
        "policyholder_name": policyholder_name,
        "policy": policy_facts,
    }


def check_claim_completeness(db, claim_id):
    """Check which required fields and documents are missing. Returns None when there is no such claim."""
    claim = get_submitted_claim(db, claim_id)
    if claim is None:
        return None

    details = claim.details or {}

    # The two fields every claim needs, then the required fields of its line
    required_fields = [
        {"name": "loss_date", "label": "Date of loss", "present": claim.loss_date is not None},
        {
            "name": "claimed_amount",
            "label": "Claimed amount",
            "present": claim.claimed_amount is not None and claim.claimed_amount > 0,
        },
    ]
    for field in DOMAIN_FIELDS.get(claim.line, []):
        if not field["required"]:
            continue
        value = str(details.get(field["name"], "")).strip()
        required_fields.append({"name": field["name"], "label": field["label"], "present": value != ""})

    documents = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim.id).all()
    uploaded_types = []
    for doc in documents:
        uploaded_types.append(doc.doc_type)

    required_documents = []
    for doc_type in REQUIRED_DOCS_BY_LINE.get(claim.line, []):
        required_documents.append({
            "doc_type": doc_type,
            "label": DOC_TYPE_LABELS[doc_type],
            "present": doc_type in uploaded_types,
        })

    # Photos are not meant to be read by OCR, so only other documents can have reading problems
    document_problems = []
    for doc in documents:
        if doc.doc_type.startswith("photo"):
            continue
        if doc.ocr_status == "failed":
            document_problems.append({"document_id": doc.id, "doc_type": doc.doc_type, "problem": "The text could not be read."})
        elif doc.ocr_status == "low_quality":
            document_problems.append({"document_id": doc.id, "doc_type": doc.doc_type, "problem": "The text was read with low confidence."})
        elif doc.ocr_status in ["pending", "processing"]:
            document_problems.append({"document_id": doc.id, "doc_type": doc.doc_type, "problem": "The text has not been read yet."})

    missing_fields = []
    for field in required_fields:
        if not field["present"]:
            missing_fields.append(field["label"])

    missing_documents = []
    for document in required_documents:
        if not document["present"]:
            missing_documents.append(document["label"])

    return {
        "claim_id": claim.id,
        "line": claim.line,
        "required_fields": required_fields,
        "required_documents": required_documents,
        "missing_fields": missing_fields,
        "missing_documents": missing_documents,
        "document_problems": document_problems,
        "is_complete": len(missing_fields) == 0 and len(missing_documents) == 0,
    }