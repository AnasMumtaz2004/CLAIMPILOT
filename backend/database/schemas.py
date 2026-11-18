from datetime import datetime
from pydantic import BaseModel
from pydantic import Field


class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=72)


class DraftCreate(BaseModel):
    policy_id: str


class DraftUpdate(BaseModel):
    version: int
    loss_date: datetime | None = None
    claimed_amount: float | None = Field(default=None, ge=0)
    description: str = Field(default="", max_length=2000)
    details: dict[str, str] = Field(default_factory=dict)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


# The reason is private to staff, the customer message is shown to the customer
class DecisionRequest(BaseModel):
    reason: str = Field(default="", max_length=2000)
    customer_message: str = Field(default="", max_length=2000)


class StaffNoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)