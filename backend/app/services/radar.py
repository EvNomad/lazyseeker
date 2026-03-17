import asyncio
import hashlib
import logging
import os
import uuid
from collections import deque
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

logger = logging.getLogger(__name__)

# Module-level crawl log and lock
_crawl_log: deque = deque(maxlen=500)
_crawl_lock = asyncio.Lock()


class CrawlTimeoutError(Exception):
    pass


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


async def fetch_with_playwright(url: str, timeout_ms: int = 30000) -> str:
    """Fetch a JS-heavy page using Playwright (headless Chromium).

    Raises:
        CrawlTimeoutError: if the page load times out.
    """
    from playwright.async_api import async_playwright
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=timeout_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    pass  # continue with whatever loaded
                return await page.content()
            finally:
                await browser.close()
    except PlaywrightTimeoutError:
        raise CrawlTimeoutError(f"Playwright timed out fetching {url}")


async def fetch_career_page(url: str) -> str:
    """Smart fetch: try static first, fall back to Playwright if no job links found."""
    html = await fetch_static_page(url)
    links = extract_job_links(html, url)
    if links:
        logger.debug("fetch_career_page: static fetch found %d links for %s", len(links), url)
        return html
    logger.debug("fetch_career_page: static fetch found 0 links for %s, falling back to Playwright", url)
    html = await fetch_with_playwright(url)
    return html


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


_LINKEDIN_RAPIDAPI_HOST = "linkedin-data-api.p.rapidapi.com"
_LINKEDIN_SEARCH_URL = f"https://{_LINKEDIN_RAPIDAPI_HOST}/search-jobs"
_LINKEDIN_ISRAEL_LOCATION_ID = "101620260"


async def fetch_linkedin_jobs(company_name: str, rapidapi_key: str) -> list[dict]:
    """Search LinkedIn jobs for a company via RapidAPI.

    Calls the linkedin-data-api RapidAPI endpoint with Israel as the location.
    Returns a list of dicts with 'url', 'title', 'description' keys.
    On HTTP error: logs and returns empty list (does not crash).
    """
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": _LINKEDIN_RAPIDAPI_HOST,
    }
    params = {
        "keywords": company_name,
        "locationId": _LINKEDIN_ISRAEL_LOCATION_ID,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _LINKEDIN_SEARCH_URL, headers=headers, params=params
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("LinkedIn fetch failed for %r: %s", company_name, exc)
        return []

    jobs = []
    for item in data.get("data", []):
        url = item.get("url") or item.get("jobUrl") or ""
        title = item.get("title") or ""
        description = item.get("description") or ""
        if url:
            jobs.append({"url": url, "title": title, "description": description})
    return jobs


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


@dataclass
class CrawlLogEntry:
    company_id: str
    company_name: str
    run_at: str  # ISO format datetime string
    status: Literal["success", "error"]
    new_postings: int
    error_message: Optional[str]


def get_crawl_log() -> list[CrawlLogEntry]:
    """Return crawl log entries in reverse chronological order (newest first)."""
    return list(reversed(list(_crawl_log)))


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


async def crawl_company_async(company: Company, session: Session) -> CrawlResult:
    """Async version: fetch career page, extract job links, persist new postings, and return a CrawlResult."""
    html = await fetch_career_page(company.career_page_url)
    links = extract_job_links(html, company.career_page_url)

    new_postings = 0
    for link in links:
        detail = await fetch_job_detail(link["url"])
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
    return asyncio.run(run_crawl_async(session))


async def run_crawl_async(session: Session) -> list[CrawlResult]:
    """Async version: load active companies from DB, crawl each one, and return results.

    Each company is wrapped in try/except so a single failure does not abort the run.
    Appends a CrawlLogEntry to _crawl_log for each company.
    Also fetches LinkedIn jobs for companies with use_linkedin=True in companies.yaml,
    provided the RAPIDAPI_KEY environment variable is set.
    """
    statement = select(Company).where(Company.active == True)  # noqa: E712
    companies = session.exec(statement).all()

    # Build a lookup of company id -> CompanyConfig for linkedin flag.
    try:
        company_configs = load_companies(COMPANIES_YAML_PATH)
        linkedin_enabled_ids = {
            str(cfg.id) for cfg in company_configs if cfg.use_linkedin
        }
    except Exception as exc:
        logger.warning("Could not load companies config for LinkedIn flags: %s", exc)
        linkedin_enabled_ids = set()

    rapidapi_key = os.environ.get("RAPIDAPI_KEY", "")
    if not rapidapi_key:
        logger.warning(
            "RAPIDAPI_KEY is not set — LinkedIn crawling will be skipped."
        )

    results: list[CrawlResult] = []
    for company in companies:
        try:
            result = await crawl_company_async(company, session)

            # LinkedIn crawl (if enabled for this company and key is available).
            if rapidapi_key and str(company.id) in linkedin_enabled_ids:
                linkedin_jobs = await fetch_linkedin_jobs(company.name, rapidapi_key)
                for job in linkedin_jobs:
                    save_posting(job, company, Source.linkedin, session)
                    result = CrawlResult(
                        company_id=result.company_id,
                        company_name=result.company_name,
                        new_postings=result.new_postings,
                        status=result.status,
                        error_message=result.error_message,
                    )

            log_entry = CrawlLogEntry(
                company_id=result.company_id,
                company_name=result.company_name,
                run_at=datetime.utcnow().isoformat(),
                status="success",
                new_postings=result.new_postings,
                error_message=None,
            )
        except Exception as exc:
            result = CrawlResult(
                company_id=str(company.id),
                company_name=company.name,
                new_postings=0,
                status="error",
                error_message=str(exc),
            )
            log_entry = CrawlLogEntry(
                company_id=str(company.id),
                company_name=company.name,
                run_at=datetime.utcnow().isoformat(),
                status="error",
                new_postings=0,
                error_message=str(exc),
            )
        _crawl_log.append(log_entry)
        results.append(result)
    return results
