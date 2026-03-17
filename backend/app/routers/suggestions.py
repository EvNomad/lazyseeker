import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.db import get_session, engine
from backend.app.models.job_posting import JobPosting
from backend.app.models.suggestion import Suggestion, SuggestionStatus
from backend.app.models.user_profile import UserProfile
from backend.app.routers.profile import get_or_create_profile
from backend.app.services.tailor import (
    cv_version_for_profile,
    generate_suggestions,
    assemble_tailored_cv,
)

router = APIRouter(tags=["suggestions"])


class SuggestionStatusUpdate(BaseModel):
    status: str


@router.get("/jobs/{job_id}/suggestions")
def get_suggestions(job_id: uuid.UUID, session: Session = Depends(get_session)):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = get_or_create_profile(session)
    cv_version_current = cv_version_for_profile(profile) if profile else ""

    suggestions = list(
        session.exec(select(Suggestion).where(Suggestion.job_id == job_id)).all()
    )

    return {"suggestions": suggestions, "cv_version_current": cv_version_current}


@router.patch("/suggestions/{suggestion_id}")
def patch_suggestion(
    suggestion_id: uuid.UUID,
    body: SuggestionStatusUpdate,
    session: Session = Depends(get_session),
):
    suggestion = session.get(Suggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # Validate the requested status
    try:
        new_status = SuggestionStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Invalid status: {body.status}"
        )

    # Block transitions back to pending
    if new_status == SuggestionStatus.pending:
        raise HTTPException(
            status_code=422, detail="Cannot set status back to pending"
        )

    # Block reversion: approved → rejected or rejected → approved
    if suggestion.status != SuggestionStatus.pending:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot change status from {suggestion.status} to {new_status}",
        )

    suggestion.status = new_status
    session.add(suggestion)
    session.commit()
    session.refresh(suggestion)
    return suggestion


@router.post("/jobs/{job_id}/tailor")
def post_tailor(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = get_or_create_profile(session)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    background_tasks.add_task(_run_generate_suggestions, job.id, profile.id)

    return {"status": "generating"}


def _run_generate_suggestions(job_id: uuid.UUID, profile_id: uuid.UUID) -> None:
    """Open a fresh session and run suggestion generation — safe to use as a BackgroundTask."""
    with Session(engine) as session:
        job = session.get(JobPosting, job_id)
        profile = session.get(UserProfile, profile_id)
        if job is None or profile is None:
            return
        asyncio.run(generate_suggestions(job, profile, session))


@router.get("/jobs/{job_id}/tailored-cv")
def get_tailored_cv(job_id: uuid.UUID, session: Session = Depends(get_session)):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = get_or_create_profile(session)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    approved_suggestions = list(
        session.exec(
            select(Suggestion).where(
                Suggestion.job_id == job_id,
                Suggestion.status == SuggestionStatus.approved,
            )
        ).all()
    )

    if not approved_suggestions:
        raise HTTPException(status_code=400, detail="No approved suggestions")

    tailored_cv = assemble_tailored_cv(profile.cv_markdown, approved_suggestions)

    return Response(content=tailored_cv, media_type="text/plain")
