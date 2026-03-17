import uuid
from datetime import datetime
from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profile"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cv_markdown: str = Field(default="")
    preferences: str = Field(default="")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
