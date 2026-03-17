import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlmodel import Session, select

from backend.app.config import CompanyConfig, COMPANIES_YAML_PATH, load_companies
from backend.app.models.company import Company
from backend.app.models.job_posting import (
    JobPosting,
    Language,
    Source,
    ScoreStatus,
    ApplicationStatus,
)


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


def hash_url(url: str) -> str:
    """Return the SHA-256 hex digest of the stripped URL."""
    return hashlib.sha256(url.strip().encode()).hexdigest()


def detect_language(text: str) -> Language:
    """Detect whether text is English, Hebrew, or mixed."""
    try:
        from langdetect import detect
        from langdetect.lang_detect_exception import LangDetectException
    except ImportError:
        detect = None
        LangDetectException = Exception

    # Count alphabetic and Hebrew-range characters.
    alpha_chars = sum(1 for c in text if c.isalpha())
    hebrew_chars = sum(1 for c in text if "\u0590" <= c <= "\u05FF")
    hebrew_ratio = hebrew_chars / max(alpha_chars, 1)

    if detect is not None:
        try:
            lang = detect(text)
            if lang in ("iw", "he") and hebrew_ratio > 0.30:
                return Language.he
            if hebrew_ratio > 0.10:
                return Language.mixed
            return Language.en
        except LangDetectException:
            pass

    # Fallback: ratio only.
    if hebrew_ratio > 0.30:
        return Language.he
    if hebrew_ratio > 0.10:
        return Language.mixed
    return Language.en


def posting_exists(url_hash: str, session: Session) -> bool:
    """Return True if a JobPosting with the given url_hash already exists."""
    statement = select(JobPosting).where(JobPosting.url_hash == url_hash)
    result = session.exec(statement).first()
    return result is not None


def find_archived_repost(
    title: str, company_id: uuid.UUID, session: Session
) -> Optional[uuid.UUID]:
    """Find an archived posting for the same company with the same title (case-insensitive).

    Returns its id or None.
    """
    normalised = " ".join(title.split()).lower()
    statement = (
        select(JobPosting)
        .where(JobPosting.company_id == company_id)
        .where(JobPosting.application_status == ApplicationStatus.archived)
    )
    candidates = session.exec(statement).all()
    for candidate in candidates:
        if " ".join(candidate.title.split()).lower() == normalised:
            return candidate.id
    return None


def save_posting(
    raw: dict, company: Company, source: Source, session: Session
) -> Optional[JobPosting]:
    """Persist a job posting if it has not been seen before.

    Returns the new JobPosting or None if a duplicate URL was detected.
    """
    url = raw["url"]
    url_hash = hash_url(url)

    if posting_exists(url_hash, session):
        return None

    language = detect_language(
        raw.get("description", "") + " " + raw.get("title", "")
    )
    repost_of = find_archived_repost(raw["title"], company.id, session)

    posting = JobPosting(
        url=url,
        url_hash=url_hash,
        company_id=company.id,
        title=raw["title"],
        description=raw.get("description", ""),
        requirements=raw.get("requirements"),
        language=language,
        source=source,
        score_status=ScoreStatus.pending,
        application_status=ApplicationStatus.new,
        repost_of=repost_of,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


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


def crawl_company(company: Company, session: Session) -> CrawlResult:
    """Fetch career page, extract job links, persist new postings, and return a CrawlResult."""
    html = asyncio.run(fetch_static_page(company.career_page_url))
    links = extract_job_links(html, company.career_page_url)

    new_postings = 0
    for link in links:
        detail = asyncio.run(fetch_job_detail(link["url"]))
        result = save_posting(detail, company, Source.career_page, session)
        if result is not None:
            new_postings += 1

    company.last_crawled_at = datetime.utcnow()
    session.add(company)
    session.commit()

    return CrawlResult(
        company_id=str(company.id),
        company_name=company.name,
        new_postings=new_postings,
        status="success",
        error_message=None,
    )


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
