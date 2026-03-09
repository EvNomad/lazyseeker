"""
Matcher Phase 1 — Backend skeleton tests (shared with Radar).

Verifies that all four SQLModel tables are created, JobPosting defaults
are correct, and the UserProfile single-row upsert pattern works.

All tests fail with ModuleNotFoundError until the backend skeleton is
implemented.
"""
import uuid
from sqlmodel import Session, select, text

from backend.app.db import create_db_and_tables
from backend.app.models.company import Company
from backend.app.models.job_posting import JobPosting, ScoreStatus, ApplicationStatus, Language, Source
from backend.app.models.user_profile import UserProfile
from backend.app.models.suggestion import Suggestion
from backend.app.routers.profile import get_or_create_profile


def test_db_creates_tables(engine):
    """All four tables — company, job_posting, user_profile, suggestion — must exist."""
    with Session(engine) as session:
        result = session.exec(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).all()
        table_names = {row[0] for row in result}

    assert "company" in table_names, "company table missing"
    assert "job_posting" in table_names, "job_posting table missing"
    assert "user_profile" in table_names, "user_profile table missing"
    assert "suggestion" in table_names, "suggestion table missing"


def test_job_posting_defaults(session):
    """
    A minimal JobPosting must have:
    - score_status == "pending"
    - application_status == "new"
    - overall_score is None
    """
    company = Company(
        id=uuid.uuid4(),
        name="Wix",
        career_page_url="https://www.wix.com/jobs",
    )
    session.add(company)
    session.commit()

    posting = JobPosting(
        id=uuid.uuid4(),
        url="https://www.wix.com/jobs/1",
        url_hash="deadbeef",
        company_id=company.id,
        title="Backend Engineer",
        description="Build scalable backend systems.",
        language=Language.en,
        source=Source.career_page,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)

    assert posting.score_status == ScoreStatus.pending
    assert posting.application_status == ApplicationStatus.new
    assert posting.overall_score is None


def test_user_profile_single_row_pattern(session):
    """
    The get_or_create_profile helper must return a UserProfile and ensure
    only one row ever exists in the table.
    """
    # Insert a pre-existing profile
    first = UserProfile(
        id=uuid.uuid4(),
        cv_markdown="# First CV",
        preferences="First preferences",
    )
    session.add(first)
    session.commit()

    # get_or_create_profile should return the existing row
    profile = get_or_create_profile(session)
    assert profile is not None

    # Only one row must exist
    all_profiles = session.exec(select(UserProfile)).all()
    assert len(all_profiles) == 1
