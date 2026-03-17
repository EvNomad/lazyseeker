"""Tests for Phase 5 — LinkedIn integration via RapidAPI."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.models.company import Company
from backend.app.models.job_posting import Source
from backend.app.services.radar import fetch_linkedin_jobs, run_crawl_async


# ---------------------------------------------------------------------------
# fetch_linkedin_jobs tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_linkedin_returns_empty_on_http_error():
    """When httpx raises HTTPError, fetch_linkedin_jobs returns [] and does not crash."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPError("connection failed")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_linkedin_jobs("Wix", "fake-key")

    assert result == []


@pytest.mark.asyncio
async def test_fetch_linkedin_parses_response():
    """When httpx returns a valid response, fetch_linkedin_jobs parses jobs correctly."""
    sample_payload = {
        "data": [
            {
                "url": "https://linkedin.com/jobs/view/1",
                "title": "Software Engineer",
                "description": "Build great products",
            },
            {
                "url": "https://linkedin.com/jobs/view/2",
                "title": "Product Manager",
                "description": "Lead product strategy",
            },
        ]
    }

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=sample_payload)
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_linkedin_jobs("Wix", "fake-key")

    assert len(result) == 2
    assert result[0]["url"] == "https://linkedin.com/jobs/view/1"
    assert result[0]["title"] == "Software Engineer"
    assert result[0]["description"] == "Build great products"
    assert result[1]["url"] == "https://linkedin.com/jobs/view/2"
    assert result[1]["title"] == "Product Manager"


# ---------------------------------------------------------------------------
# run_crawl_async LinkedIn integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_crawl_skips_linkedin_when_no_key(session):
    """When RAPIDAPI_KEY is empty, LinkedIn fetch is never called."""
    company = Company(
        id=uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Wix",
        career_page_url="https://www.wix.com/jobs",
        linkedin_slug="wix",
        active=True,
    )
    session.add(company)
    session.commit()

    async def fake_crawl_company_async(company, session):
        from backend.app.services.radar import CrawlResult
        return CrawlResult(
            company_id=str(company.id),
            company_name=company.name,
            new_postings=0,
            status="success",
            error_message=None,
        )

    with patch("backend.app.services.radar.crawl_company_async", side_effect=fake_crawl_company_async), \
         patch("backend.app.services.radar.fetch_linkedin_jobs", new_callable=AsyncMock) as mock_linkedin, \
         patch.dict("os.environ", {"RAPIDAPI_KEY": ""}):
        await run_crawl_async(session)

    mock_linkedin.assert_not_called()


@pytest.mark.asyncio
async def test_run_crawl_calls_linkedin_for_enabled_company(session, tmp_path):
    """When RAPIDAPI_KEY is set and use_linkedin=True for a company, LinkedIn fetch is called."""
    company_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    company = Company(
        id=uuid.UUID(company_id),
        name="Wix",
        career_page_url="https://www.wix.com/jobs",
        linkedin_slug="wix",
        active=True,
    )
    session.add(company)
    session.commit()

    # Write a temporary companies.yaml with use_linkedin=true for Wix.
    yaml_content = (
        "companies:\n"
        f"  - id: '{company_id}'\n"
        "    name: 'Wix'\n"
        "    career_page_url: 'https://www.wix.com/jobs'\n"
        "    linkedin_slug: 'wix'\n"
        "    active: true\n"
        "    use_linkedin: true\n"
    )
    yaml_file = tmp_path / "companies.yaml"
    yaml_file.write_text(yaml_content)

    async def fake_crawl_company_async(company, session):
        from backend.app.services.radar import CrawlResult
        return CrawlResult(
            company_id=str(company.id),
            company_name=company.name,
            new_postings=0,
            status="success",
            error_message=None,
        )

    with patch("backend.app.services.radar.crawl_company_async", side_effect=fake_crawl_company_async), \
         patch("backend.app.services.radar.fetch_linkedin_jobs", new_callable=AsyncMock, return_value=[]) as mock_linkedin, \
         patch("backend.app.services.radar.COMPANIES_YAML_PATH", yaml_file), \
         patch.dict("os.environ", {"RAPIDAPI_KEY": "test-rapidapi-key"}):
        await run_crawl_async(session)

    mock_linkedin.assert_called_once_with("Wix", "test-rapidapi-key")
