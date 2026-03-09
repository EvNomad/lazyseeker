"""
Phase 1 — Backend skeleton tests.

All tests in this file will fail with ModuleNotFoundError until the
backend skeleton implementation is added (backend/app/main.py, models,
db.py). That is the expected and intentional state of this PR.
"""
import uuid
from sqlmodel import create_engine, Session, select, text

from backend.app.db import create_db_and_tables
from backend.app.main import app
from backend.app.models.company import Company
from backend.app.models.job_posting import JobPosting, ScoreStatus, ApplicationStatus, Language, Source


def test_db_create_tables(engine):
    """Both 'company' and 'job_posting' tables must exist after create_db_and_tables()."""
    with Session(engine) as session:
        result = session.exec(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).all()
        table_names = {row[0] for row in result}
    assert "company" in table_names
    assert "job_posting" in table_names


def test_healthz(client):
    """GET /healthz must return 200 with {"status": "ok"}."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_job_posting_defaults(session):
    """
    Inserting a minimal JobPosting must produce the correct default field values:
    - score_status == ScoreStatus.pending
    - application_status == ApplicationStatus.new
    - overall_score is None
    - repost_of is None
    """
    company = Company(
        id=uuid.uuid4(),
        name="Acme Corp",
        career_page_url="https://acme.example.com/jobs",
    )
    session.add(company)
    session.commit()

    posting = JobPosting(
        id=uuid.uuid4(),
        url="https://acme.example.com/jobs/1",
        url_hash="abc123",
        company_id=company.id,
        title="Backend Engineer",
        description="We are looking for a backend engineer.",
        language=Language.en,
        source=Source.career_page,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)

    assert posting.score_status == ScoreStatus.pending
    assert posting.application_status == ApplicationStatus.new
    assert posting.overall_score is None
    assert posting.repost_of is None


def test_company_model(session):
    """A Company must round-trip through the session with all fields intact."""
    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        name="Wix",
        career_page_url="https://www.wix.com/jobs",
        linkedin_slug="wix",
        active=True,
        last_crawled_at=None,
    )
    session.add(company)
    session.commit()

    fetched = session.get(Company, company_id)
    assert fetched is not None
    assert fetched.name == "Wix"
    assert fetched.career_page_url == "https://www.wix.com/jobs"
    assert fetched.linkedin_slug == "wix"
    assert fetched.active is True
    assert fetched.last_crawled_at is None


def test_self_referential_fk(session):
    """
    A JobPosting with repost_of pointing to another JobPosting must
    persist and resolve the FK correctly.
    """
    company = Company(
        id=uuid.uuid4(),
        name="Check Point",
        career_page_url="https://careers.checkpoint.com",
    )
    session.add(company)
    session.commit()

    parent = JobPosting(
        id=uuid.uuid4(),
        url="https://careers.checkpoint.com/jobs/100",
        url_hash="hash_parent",
        company_id=company.id,
        title="SRE Lead",
        description="Original posting for SRE Lead role.",
        language=Language.en,
        source=Source.career_page,
    )
    session.add(parent)
    session.commit()

    child = JobPosting(
        id=uuid.uuid4(),
        url="https://careers.checkpoint.com/jobs/200",
        url_hash="hash_child",
        company_id=company.id,
        title="SRE Lead",
        description="Reposted SRE Lead role.",
        language=Language.en,
        source=Source.career_page,
        repost_of=parent.id,
    )
    session.add(child)
    session.commit()
    session.refresh(child)

    assert child.repost_of == parent.id
