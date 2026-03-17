import uuid
import hashlib
import pytest
from unittest.mock import patch, AsyncMock
from sqlmodel import Session, select

from backend.app.models.job_posting import JobPosting, Language, Source, ApplicationStatus, ScoreStatus
from backend.app.models.company import Company
from backend.app.services.radar import (
    hash_url, detect_language, posting_exists, find_archived_repost, save_posting
)
from backend.tests.fixtures.seed import make_company


# ---------------------------------------------------------------------------
# hash_url
# ---------------------------------------------------------------------------

def test_hash_url_deterministic():
    url = "https://example.com/jobs/123"
    assert hash_url(url) == hash_url(url)


def test_hash_url_different_urls():
    assert hash_url("https://a.com") != hash_url("https://b.com")


def test_hash_url_strips_whitespace():
    assert hash_url(" https://a.com ") == hash_url("https://a.com")


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

def test_detect_language_english():
    text = (
        "We are looking for a talented software engineer to join our growing platform team. "
        "You will design and build scalable backend systems, collaborate with product managers "
        "and frontend engineers, contribute to architecture decisions and code reviews. "
        "Strong Python skills are required, experience with FastAPI and SQLModel is a plus. "
        "We value curiosity, ownership, and a passion for shipping quality software."
    )
    result = detect_language(text)
    assert result == Language.en


def test_detect_language_hebrew():
    text = (
        "אנחנו מחפשים מהנדס תוכנה בכיר עם ניסיון של חמש שנים לפחות בפיתוח backend. "
        "המועמד יעבוד על מערכות בקנה מידה גדול, ינהל תהליכי פיתוח ויוביל צוות מהנדסים. "
        "דרישות: ניסיון בפייתון, ידע ב-FastAPI, ניסיון עם מסדי נתונים רלציוניים. "
        "יתרון לניסיון בענן ובארכיטקטורת מיקרו-שירותים."
    )
    result = detect_language(text)
    assert result == Language.he


def test_detect_language_mixed():
    text = "We need a developer. אנחנו מחפשים מפתח עם ניסיון."
    result = detect_language(text)
    # Mixed Hebrew/English — any Language value is acceptable; just assert no exception
    assert isinstance(result, Language)


def test_detect_language_short_text_fallback():
    result = detect_language("hello")
    assert isinstance(result, Language)


# ---------------------------------------------------------------------------
# posting_exists
# ---------------------------------------------------------------------------

def test_posting_exists_false_for_new_url(session):
    fake_hash = hashlib.sha256(b"https://new.example.com").hexdigest()
    assert posting_exists(fake_hash, session) is False


def test_posting_exists_true_after_insert(session):
    company = make_company(session)
    url = f"https://example.com/jobs/{uuid.uuid4()}"
    url_hash = hash_url(url)
    posting = JobPosting(
        url=url,
        url_hash=url_hash,
        company_id=company.id,
        title="Engineer",
        description="Build things.",
        language=Language.en,
        source=Source.career_page,
        score_status=ScoreStatus.pending,
        application_status=ApplicationStatus.new,
    )
    session.add(posting)
    session.commit()
    assert posting_exists(url_hash, session) is True


# ---------------------------------------------------------------------------
# save_posting
# ---------------------------------------------------------------------------

def _raw(url: str, title: str = "Engineer", description: str = "Build things.") -> dict:
    return {"url": url, "title": title, "description": description, "requirements": None}


def test_save_posting_new(session):
    company = make_company(session)
    raw = _raw(f"https://example.com/jobs/{uuid.uuid4()}")
    result = save_posting(raw, company, Source.career_page, session)
    assert result is not None
    assert result.score_status == ScoreStatus.pending
    assert result.application_status == ApplicationStatus.new


def test_save_posting_duplicate_url(session):
    company = make_company(session)
    url = f"https://example.com/jobs/{uuid.uuid4()}"
    raw = _raw(url)
    first = save_posting(raw, company, Source.career_page, session)
    assert first is not None

    second = save_posting(raw, company, Source.career_page, session)
    assert second is None

    url_hash = hash_url(url)
    rows = session.exec(select(JobPosting).where(JobPosting.url_hash == url_hash)).all()
    assert len(rows) == 1


def test_save_posting_repost_detection(session):
    company = make_company(session)
    # Seed an archived posting with title "SRE Lead"
    archived_url = f"https://example.com/jobs/{uuid.uuid4()}"
    archived = JobPosting(
        url=archived_url,
        url_hash=hash_url(archived_url),
        company_id=company.id,
        title="SRE Lead",
        description="Old posting.",
        language=Language.en,
        source=Source.career_page,
        score_status=ScoreStatus.scored,
        application_status=ApplicationStatus.archived,
    )
    session.add(archived)
    session.commit()
    session.refresh(archived)

    # Save a new posting with the same title
    new_url = f"https://example.com/jobs/{uuid.uuid4()}"
    raw = _raw(new_url, title="SRE Lead")
    result = save_posting(raw, company, Source.career_page, session)
    assert result is not None
    assert result.repost_of == archived.id


def test_save_posting_non_archived_same_title(session):
    company = make_company(session)
    # Seed a "new" (not archived) posting with title "SRE Lead"
    existing_url = f"https://example.com/jobs/{uuid.uuid4()}"
    existing = JobPosting(
        url=existing_url,
        url_hash=hash_url(existing_url),
        company_id=company.id,
        title="SRE Lead",
        description="Active posting.",
        language=Language.en,
        source=Source.career_page,
        score_status=ScoreStatus.pending,
        application_status=ApplicationStatus.new,
    )
    session.add(existing)
    session.commit()

    new_url = f"https://example.com/jobs/{uuid.uuid4()}"
    raw = _raw(new_url, title="SRE Lead")
    result = save_posting(raw, company, Source.career_page, session)
    assert result is not None
    assert result.repost_of is None


# ---------------------------------------------------------------------------
# crawl_company — last_crawled_at updated
# ---------------------------------------------------------------------------

@patch("backend.app.services.radar.fetch_static_page", new_callable=AsyncMock)
@patch("backend.app.services.radar.fetch_job_detail", new_callable=AsyncMock)
def test_last_crawled_at_updated(mock_detail, mock_static, session):
    mock_static.return_value = open("backend/tests/fixtures/wix_careers.html").read()
    mock_detail.return_value = {
        "url": "https://wix.com/jobs/1",
        "title": "Engineer",
        "description": (
            "Build stuff at Wix company with Python and other tools we use daily "
            "at our product teams."
        ),
        "requirements": None,
    }
    company = make_company(session)
    from backend.app.services.radar import crawl_company
    result = crawl_company(company, session)
    session.refresh(company)
    assert company.last_crawled_at is not None
