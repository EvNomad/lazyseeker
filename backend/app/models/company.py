import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class Company(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    career_page_url: str
    linkedin_slug: Optional[str] = Field(default=None)
    active: bool = Field(default=True)
    last_crawled_at: Optional[datetime] = Field(default=None)
