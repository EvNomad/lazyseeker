import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class Language(str, Enum):
    en = "en"
    he = "he"
    mixed = "mixed"


class Source(str, Enum):
    career_page = "career_page"
    linkedin = "linkedin"


class ScoreStatus(str, Enum):
    pending = "pending"
    scored = "scored"
    error = "error"


class ApplicationStatus(str, Enum):
    new = "new"
    reviewing = "reviewing"
    applied = "applied"
    rejected = "rejected"
    archived = "archived"


class JobPosting(SQLModel, table=True):
    __tablename__ = "job_posting"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    url: str = Field(unique=True)
    url_hash: str = Field(index=True)
    company_id: uuid.UUID = Field(foreign_key="company.id")
    title: str
    description: str
    requirements: Optional[str] = Field(default=None)
    language: Language
    source: Source
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    overall_score: Optional[int] = Field(default=None)
    score_breakdown: Optional[str] = Field(default=None)  # JSON text
    score_status: ScoreStatus = Field(default=ScoreStatus.pending)
    application_status: ApplicationStatus = Field(default=ApplicationStatus.new)
    repost_of: Optional[uuid.UUID] = Field(default=None, foreign_key="job_posting.id")
