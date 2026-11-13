from typing import TypedDict

from pydantic import BaseModel
from pydantic import Field


class ExtractedFact(BaseModel):
    """One value the model found in a document."""

    field: str = Field(description="The exact field name from the allowed list.")
    value: str = Field(description="The value copied exactly as written in the document.")
    page: int = Field(description="The page number where the value was found.")
    evidence_quote: str = Field(description="A short exact quote from that page that contains the value.")


class ExtractedLineItem(BaseModel):
    """One charged item with a printed amount."""

    description: str = Field(description="The name of the charged item.")
    amount: float = Field(description="The printed amount, without currency symbols.")
    page: int = Field(description="The page number where the line was found.")
    evidence_quote: str = Field(description="An exact copy of the line from that page.")


class DocumentExtraction(BaseModel):
    """What the language model must return for one document."""

    looks_like_expected_type: bool = Field(description="True if the text looks like the named type of document.")
    facts: list[ExtractedFact] = Field(default_factory=list, description="Values found in the document.")
    line_items: list[ExtractedLineItem] = Field(default_factory=list, description="Charged items, when expected.")
    notes: list[str] = Field(default_factory=list, description="Short notes about problems in the text.")


class DocumentReviewState(TypedDict, total=False):
    """The data that moves through the document review graph."""

    claim_id: str
    facts: dict
    listing: dict
    documents: list
    extractions: dict
    checked: list
    issues: list
    result: dict
    error: str