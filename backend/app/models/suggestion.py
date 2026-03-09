import uuid
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel


class SuggestionStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Suggestion(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="jobposting.id")
    section: str
    original: str
    suggested: str
    rationale: str
    status: SuggestionStatus = Field(default=SuggestionStatus.pending)
    cv_version: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
