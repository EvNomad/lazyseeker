import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.config import load_companies, COMPANIES_YAML_PATH
from backend.app.services.radar import (
    CrawlResult,
    extract_job_links,
    fetch_static_page,
    run_crawl,
    sync_companies_to_db,
)
from backend.app.models.company import Company

# Path to HTML fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Config / YAML loading tests
# ---------------------------------------------------------------------------


def test_load_companies_valid():
    """Load the real companies.yaml and verify all 5 entries are valid."""
    companies = load_companies(COMPANIES_YAML_PATH)
    assert len(companies) == 5
    names = {c.name for c in companies}
    assert "Wix" in names
    assert "monday.com" in names
    assert "Fiverr" in names
    assert "Walla! Communications" in names
    assert "Check Point" in names
    # All IDs should be valid UUIDs (Pydantic enforces this on load)
    for company in companies:
        assert isinstance(company.id, uuid.UUID)


def test_load_companies_invalid_uuid(tmp_path):
    """A YAML with a malformed UUID should raise ValueError."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        "companies:\n"
        "  - id: 'not-a-uuid'\n"
        "    name: 'Bad Corp'\n"
        "    career_page_url: 'https://example.com'\n"
        "    linkedin_slug: null\n"
        "    active: true\n"
    )
    with pytest.raises(ValueError):
        load_companies(bad_yaml)


# ---------------------------------------------------------------------------
# fetch_static_page tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_static_page_success():
    """A 200 response should return the response text."""
    mock_response = MagicMock()
    mock_response.text = "Hello"
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()  # no-op

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_static_page("https://example.com")

    assert result == "Hello"


@pytest.mark.asyncio
async def test_fetch_static_page_non_200():
    """A 404 response should raise httpx.HTTPStatusError."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_static_page("https://example.com/missing")


# ---------------------------------------------------------------------------
# extract_job_links tests
# ---------------------------------------------------------------------------


def test_extract_job_links_finds_links():
    """Job links from wix_careers.html should be returned with absolute URLs."""
    html = (FIXTURES_DIR / "wix_careers.html").read_text()
    links = extract_job_links(html, base_url="https://www.wix.com")
    assert len(links) >= 2
    for link in links:
        assert "url" in link
        assert "title" in link
        assert link["url"].startswith("https://")


def test_extract_job_links_ignores_non_job_links():
    """The /about link should be excluded since it contains no job keyword."""
    html = (FIXTURES_DIR / "wix_careers.html").read_text()
    links = extract_job_links(html, base_url="https://www.wix.com")
    urls = [link["url"] for link in links]
    assert not any("about" in url for url in urls)


# ---------------------------------------------------------------------------
# sync_companies_to_db tests
# ---------------------------------------------------------------------------


def test_sync_companies_to_db(session):
    """Two calls with the same 2 configs should result in exactly 2 rows."""
    from backend.app.config import CompanyConfig

    configs = [
        CompanyConfig(
            id=uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
            name="Wix",
            career_page_url="https://www.wix.com/jobs",
            linkedin_slug="wix",
            active=True,
        ),
        CompanyConfig(
            id=uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901"),
            name="monday.com",
            career_page_url="https://monday.com/jobs",
            linkedin_slug="mondaydotcom",
            active=True,
        ),
    ]

    sync_companies_to_db(session, configs)
    sync_companies_to_db(session, configs)  # second call — should not duplicate

    from sqlmodel import select

    rows = session.exec(select(Company)).all()
    assert len(rows) == 2


def test_sync_companies_inactive_not_inserted(session):
    """An inactive company IS inserted but with active=False."""
    from backend.app.config import CompanyConfig

    configs = [
        CompanyConfig(
            id=uuid.UUID("c3d4e5f6-a7b8-9012-cdef-123456789012"),
            name="Inactive Corp",
            career_page_url="https://inactive.example.com",
            linkedin_slug=None,
            active=False,
        ),
    ]

    sync_companies_to_db(session, configs)

    from sqlmodel import select

    rows = session.exec(select(Company)).all()
    assert len(rows) == 1
    assert rows[0].active is False


# ---------------------------------------------------------------------------
# run_crawl error isolation test
# ---------------------------------------------------------------------------


def test_crawl_company_error_does_not_crash_run(session):
    """A crawl failure for one company should not abort the run; error is captured."""
    # Seed 2 companies
    company_a = Company(
        id=uuid.uuid4(),
        name="Good Company",
        career_page_url="https://good.example.com/jobs",
        linkedin_slug=None,
        active=True,
    )
    company_b = Company(
        id=uuid.uuid4(),
        name="Bad Company",
        career_page_url="https://bad.example.com/jobs",
        linkedin_slug=None,
        active=True,
    )
    session.add(company_a)
    session.add(company_b)
    session.commit()

    # Patch fetch_static_page so bad company raises, good company returns HTML.
    # fetch_static_page is async so the mock must also be async.
    good_html = (FIXTURES_DIR / "wix_careers.html").read_text()

    async def fake_fetch(url: str, timeout: float = 10.0):
        if "bad" in url:
            raise Exception("network down")
        return good_html

    with patch("backend.app.services.radar.fetch_static_page", side_effect=fake_fetch):
        results = run_crawl(session)

    assert len(results) == 2

    error_results = [r for r in results if r.status == "error"]
    assert len(error_results) == 1
    assert error_results[0].error_message is not None
    assert "network down" in error_results[0].error_message
