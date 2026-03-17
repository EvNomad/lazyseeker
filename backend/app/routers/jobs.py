import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from pydantic import BaseModel

from backend.app.db import get_session
from backend.app.models.job_posting import JobPosting, ApplicationStatus, ScoreStatus
from backend.app.models.company import Company
from backend.app.services.matcher import score_job_posting
from backend.app.routers.profile import get_or_create_profile

router = APIRouter(prefix="/jobs", tags=["jobs"])


class StatusUpdate(BaseModel):
    application_status: str


@router.get("")
def list_jobs(
    min_score: Optional[int] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    company_id: Optional[uuid.UUID] = None,
    session: Session = Depends(get_session),
) -> list[JobPosting]:
    query = select(JobPosting)

    if min_score is not None:
        query = query.where(JobPosting.overall_score >= min_score)

    if status is not None:
        try:
            status_val = ApplicationStatus(status)
            query = query.where(JobPosting.application_status == status_val)
        except ValueError:
            return []

    if language is not None:
        from backend.app.models.job_posting import Language
        try:
            lang_val = Language(language)
            query = query.where(JobPosting.language == lang_val)
        except ValueError:
            return []

    if company_id is not None:
        query = query.where(JobPosting.company_id == company_id)

    return list(session.exec(query).all())


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, session: Session = Depends(get_session)):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    company = session.get(Company, job.company_id)
    data = job.model_dump(mode="json")
    data["company"] = company.model_dump(mode="json") if company else None
    return data


@router.patch("/{job_id}/status")
def patch_job_status(
    job_id: uuid.UUID,
    body: StatusUpdate,
    session: Session = Depends(get_session),
):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        job.application_status = ApplicationStatus(body.application_status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.application_status}")
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/retry-score")
def retry_score(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    job = session.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.score_status == ScoreStatus.scored:
        raise HTTPException(status_code=409, detail="Job is already scored")

    profile = get_or_create_profile(session)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    job.score_status = ScoreStatus.pending
    session.add(job)
    session.commit()

    background_tasks.add_task(score_job_posting, job, profile, session)

    return {"score_status": "pending"}
