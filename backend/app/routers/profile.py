import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.db import get_session
from backend.app.models.user_profile import UserProfile

router = APIRouter(tags=["profile"])


class ProfileUpdate(BaseModel):
    cv_markdown: Optional[str] = None
    preferences: Optional[str] = None


def get_or_create_profile(session: Session) -> Optional[UserProfile]:
    """Return the single UserProfile row, or None if it doesn't exist."""
    return session.exec(select(UserProfile)).first()


@router.get("/profile", response_model=UserProfile)
def get_profile(session: Session = Depends(get_session)):
    profile = get_or_create_profile(session)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile", response_model=UserProfile)
def put_profile(body: ProfileUpdate, session: Session = Depends(get_session)):
    profile = get_or_create_profile(session)

    if profile is None:
        # Create new profile with provided values (use defaults for missing fields)
        profile = UserProfile(
            id=uuid.uuid4(),
            cv_markdown=body.cv_markdown or "",
            preferences=body.preferences or "",
            updated_at=datetime.utcnow(),
        )
    else:
        # Partial update: only overwrite fields that were provided
        if body.cv_markdown is not None:
            profile.cv_markdown = body.cv_markdown
        if body.preferences is not None:
            profile.preferences = body.preferences
        profile.updated_at = datetime.utcnow()

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
