import uuid
from datetime import datetime
from datetime import timezone
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from database.connection import Base


def new_id():
    """Return a new UUID string."""
    return str(uuid.uuid4())


def utc_now():
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_id)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String(36), primary_key=True, default=new_id)
    policy_number = Column(String, unique=True, nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    line = Column(String, nullable=False)
    product = Column(String, nullable=False)
    version = Column(String, nullable=False, default="v1")
    sum_insured = Column(Numeric(14, 2), nullable=False)
    deductible = Column(Numeric(14, 2), nullable=False, default=0)
    copay_percent = Column(Numeric(5, 2), nullable=False, default=0)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    terms = Column(JSON, nullable=False, default=dict)


class Claim(Base):
    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_number = Column(String, unique=True, nullable=True)
    policy_id = Column(String(36), ForeignKey("policies.id"), nullable=False)
    claimant_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    line = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft", index=True)
    loss_date = Column(DateTime(timezone=True), nullable=True)
    claimed_amount = Column(Numeric(14, 2), nullable=True)
    description = Column(Text, nullable=False, default="")
    details = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class ClaimStatusHistory(Base):
    __tablename__ = "claim_status_history"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    status = Column(String, nullable=False)
    label = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="")
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False)
    doc_type = Column(String, nullable=False)
    original_path = Column(String, nullable=False)
    resized_path = Column(String, nullable=False, default="")
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String, nullable=False, index=True)
    image_hash = Column(String, nullable=False, default="", index=True)
    quality_score = Column(Float, nullable=True)
    exif = Column(JSON, nullable=False, default=dict)
    extracted = Column(JSON, nullable=False, default=dict)
    ocr_status = Column(String, nullable=False, default="pending", server_default="pending")
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    claim_id = Column(String(36), nullable=True, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    prev_hash = Column(String, nullable=False, default="")
    row_hash = Column(String, nullable=False, default="")


class ClaimMessage(Base):
    __tablename__ = "claim_messages"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    sender_role = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


# One row each time a claim is assigned to a claims officer
class ClaimAssignment(Base):
    __tablename__ = "claim_assignments"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    staff_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    assigned_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


# Private notes written by staff, never shown to customers
class StaffReview(Base):
    __tablename__ = "staff_reviews"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    staff_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


# Every decision a claims officer records, kept forever as history
class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    staff_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    decision = Column(String, nullable=False)
    reason = Column(Text, nullable=False, default="")
    customer_message = Column(Text, nullable=False, default="")
    prior_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


# Work items such as "waiting for customer" or "specialist review"
class ClaimTask(Base):
    __tablename__ = "claim_tasks"

    id = Column(String(36), primary_key=True, default=new_id)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False, index=True)
    task_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="open", index=True)
    title = Column(String, nullable=False)
    details = Column(Text, nullable=False, default="")
    resume_status = Column(String, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

# One row for every run of an AI agent, kept for debugging and accountability
class AgentExecutionLog(Base):
    __tablename__ = "agent_execution_logs"

    id = Column(String(36), primary_key=True, default=new_id)
    run_id = Column(String(36), nullable=False, index=True)
    claim_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String, nullable=False, index=True)
    agent_version = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    input_summary = Column(JSON, nullable=False, default=dict)
    output = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)