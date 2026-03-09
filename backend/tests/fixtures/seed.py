"""
Seed helpers used across all Matcher and Tailor test phases.
These functions will fail with ModuleNotFoundError until the backend
models are implemented.
"""
import uuid
from sqlmodel import Session, select

from backend.app.models.company import Company
from backend.app.models.job_posting import JobPosting, Language, Source, ScoreStatus, ApplicationStatus
from backend.app.models.user_profile import UserProfile


def make_company(session: Session) -> Company:
    """Insert and return a stub Company row."""
    company = Company(
        id=uuid.uuid4(),
        name="Test Company",
        career_page_url="https://testcompany.example.com/jobs",
        linkedin_slug=None,
        active=True,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def make_job_posting(
    session: Session,
    *,
    description: str = (
        "We are looking for a talented engineer to join our platform team. "
        "You will design and build scalable backend systems, collaborate with "
        "product managers and frontend engineers, and contribute to architecture "
        "decisions. Strong Python skills required, experience with FastAPI a plus."
    ),
    language: str = "en",
    score_status: str = "pending",
    company: Company | None = None,
) -> JobPosting:
    """Insert and return a stub JobPosting row."""
    if company is None:
        company = make_company(session)

    lang_map = {"en": Language.en, "he": Language.he, "mixed": Language.mixed}
    status_map = {
        "pending": ScoreStatus.pending,
        "scored": ScoreStatus.scored,
        "error": ScoreStatus.error,
    }

    posting = JobPosting(
        id=uuid.uuid4(),
        url=f"https://testcompany.example.com/jobs/{uuid.uuid4()}",
        url_hash=str(uuid.uuid4()),
        company_id=company.id,
        title="Software Engineer",
        description=description,
        language=lang_map[language],
        source=Source.career_page,
        score_status=status_map[score_status],
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def make_user_profile(
    session: Session,
    *,
    cv_markdown: str = "# My CV\n\n## Experience\n\nBuilt things at various companies.",
    preferences: str = "Looking for senior backend roles in Tel Aviv. Remote-friendly.",
) -> UserProfile:
    """Upsert and return a UserProfile row (single-row table)."""
    existing = session.exec(select(UserProfile)).first()
    if existing:
        session.delete(existing)
        session.commit()

    profile = UserProfile(
        id=uuid.uuid4(),
        cv_markdown=cv_markdown,
        preferences=preferences,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
