import asyncio
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlmodel import Session, select

from backend.app.config import CompanyConfig, COMPANIES_YAML_PATH, load_companies
from backend.app.models.company import Company


async def fetch_static_page(url: str, timeout: float = 10.0) -> str:
    """Fetch a static page and return its text content.

    Raises:
        httpx.HTTPStatusError: on non-2xx response.
        httpx.TimeoutException: on timeout.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text


# Keywords that indicate a job-related link.
_JOB_KEYWORDS = ("job", "career", "position", "opening", "role")


def extract_job_links(html: str, base_url: str) -> list[dict]:
    """Parse HTML and return a list of job link dicts with 'url' and 'title' keys.

    Only includes <a> tags whose href contains at least one job-related keyword.
    URLs are made absolute using base_url.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for anchor in soup.find_all("a", href=True):
        href: str = anchor["href"]
        if any(kw in href.lower() for kw in _JOB_KEYWORDS):
            absolute_url = urljoin(base_url, href)
            title = anchor.get_text(strip=True)
            results.append({"url": absolute_url, "title": title})
    return results


async def fetch_job_detail(url: str) -> dict:
    """Fetch an individual job page and extract title, description, and requirements.

    Returns a dict with keys: url, title, description, requirements.
    """
    html = await fetch_static_page(url)
    soup = BeautifulSoup(html, "html.parser")

    # Extract title: prefer <title> tag, fall back to first <h1>.
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        title = title_tag.get_text(strip=True)
    else:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

    description = soup.get_text(separator=" ", strip=True)
    requirements = None

    return {
        "url": url,
        "title": title,
        "description": description,
        "requirements": requirements,
    }


def sync_companies_to_db(session: Session, companies: list[CompanyConfig]) -> None:
    """Upsert companies into the DB. Matches on id; inserts if missing, updates if present.

    Does not delete companies that are no longer in the list.
    """
    for cfg in companies:
        existing = session.get(Company, cfg.id)
        if existing is not None:
            existing.name = cfg.name
            existing.career_page_url = cfg.career_page_url
            existing.linkedin_slug = cfg.linkedin_slug
            existing.active = cfg.active
            session.add(existing)
        else:
            company = Company(
                id=cfg.id,
                name=cfg.name,
                career_page_url=cfg.career_page_url,
                linkedin_slug=cfg.linkedin_slug,
                active=cfg.active,
            )
            session.add(company)
    session.commit()


@dataclass
class CrawlResult:
    company_id: str
    company_name: str
    new_postings: int
    status: Literal["success", "error"]
    error_message: Optional[str]


async def _crawl_company_async(company: Company) -> CrawlResult:
    """Internal async implementation of company crawl."""
    html = await fetch_static_page(company.career_page_url)
    links = extract_job_links(html, company.career_page_url)
    return CrawlResult(
        company_id=str(company.id),
        company_name=company.name,
        new_postings=len(links),
        status="success",
        error_message=None,
    )


def crawl_company(company: Company, session: Session) -> CrawlResult:
    """Fetch career page, extract job links, and return a CrawlResult.

    For Phase 2, new_postings is the count of extracted links (no DB persistence yet).
    """
    return asyncio.run(_crawl_company_async(company))


def run_crawl(session: Session) -> list[CrawlResult]:
    """Load active companies from DB, crawl each one, and return results.

    Each company is wrapped in try/except so a single failure does not abort the run.
    """
    statement = select(Company).where(Company.active == True)  # noqa: E712
    companies = session.exec(statement).all()

    results: list[CrawlResult] = []
    for company in companies:
        try:
            result = crawl_company(company, session)
        except Exception as exc:
            result = CrawlResult(
                company_id=str(company.id),
                company_name=company.name,
                new_postings=0,
                status="error",
                error_message=str(exc),
            )
        results.append(result)
    return results
