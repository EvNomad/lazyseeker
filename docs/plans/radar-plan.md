# Radar Subsystem — Implementation Plan

**Project:** LazySeeker
**Subsystem:** Radar (Job Discovery)
**Spec reference:** SPEC.md §5.1, §6, §7, §11; contracts/README.md §1–2, §5
**Date:** 2026-03-09

---

## Overview

The Radar subsystem is responsible for discovering new job postings and normalising them into the `JobPosting` schema. It is the entry point for all data in the system. Matcher and Frontend both consume what Radar produces, so getting the schema and contracts correct early is the highest-priority concern.

| Phase | Theme | Unblocks |
|---|---|---|
| 1 | Project skeleton + data models + DB | Everything else |
| 2 | Company config + static crawler | Core crawl loop |
| 3 | Language detection + deduplication | Data quality for Matcher |
| 4 | Playwright fallback + APScheduler + API endpoints | Scheduling and manual triggers |
| 5 | LinkedIn source + full test coverage | Full source coverage |

---

## Phase 1 — Project Skeleton, Data Models, and Database Setup

**PR title:** `feat(radar): backend skeleton, SQLModel models, and db setup`

**Description:** Establishes the `backend/` directory structure, installs dependencies, defines the `Company` and `JobPosting` SQLModel models, wires up the SQLite database connection, and creates the initial migration/init script. No business logic yet — this PR creates the foundation every subsequent PR builds on.

### Files to create

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── db.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── company.py
│   │   └── job_posting.py
│   ├── routers/
│   │   └── __init__.py
│   └── services/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   └── conftest.py
├── migrations/
│   └── init.sql          # DDL reference (SQLModel creates tables via create_all)
├── requirements.txt
└── .env.example
```

### Implementation steps

1. **`requirements.txt`** — pin all direct dependencies:
   ```
   fastapi>=0.111.0
   uvicorn[standard]>=0.29.0
   sqlmodel>=0.0.18
   httpx>=0.27.0
   beautifulsoup4>=4.12.0
   playwright>=1.44.0
   langdetect>=1.0.9
   apscheduler>=3.10.4
   pyyaml>=6.0.1
   python-dotenv>=1.0.1
   pytest>=8.2.0
   pytest-asyncio>=0.23.0
   pytest-httpx>=0.30.0
   ruff>=0.4.0
   ```

2. **`backend/app/models/company.py`** — define `Company` as a `SQLModel` table model:
   - Fields: `id` (UUID, primary key, default `uuid4`), `name` (str), `career_page_url` (str), `linkedin_slug` (Optional[str], nullable), `active` (bool, default True), `last_crawled_at` (Optional[datetime], nullable).

3. **`backend/app/models/job_posting.py`** — define `JobPosting` as a `SQLModel` table model:
   - Use Python `Enum` classes for `Language` (`en`, `he`, `mixed`), `Source` (`career_page`, `linkedin`), `ScoreStatus` (`pending`, `scored`, `error`), `ApplicationStatus` (`new`, `reviewing`, `applied`, `rejected`, `archived`).
   - Fields per SPEC.md §6 and contracts/README.md §2:
     - `url_hash`: `str`, indexed, unique.
     - `repost_of`: `Optional[UUID]`, `Field(default=None, foreign_key="job_posting.id")` — self-referential FK.
     - `score_breakdown`: `Optional[str]` (JSON stored as text).
     - `overall_score`: `Optional[int]`, nullable.
     - `score_status`: default `ScoreStatus.pending`.
     - `application_status`: default `ApplicationStatus.new`.
     - `crawled_at`: `datetime`, `Field(default_factory=datetime.utcnow)`.

4. **`backend/app/models/__init__.py`** — re-export `Company`, `JobPosting`, and all enums.

5. **`backend/app/db.py`**:
   - Read `DATABASE_URL` from environment (default: `sqlite:///./lazyseeker.db`).
   - Create `engine` using `create_engine` from `sqlmodel`.
   - Define `get_session()` as a FastAPI dependency (yields a `Session`).
   - Define `create_db_and_tables()` to call `SQLModel.metadata.create_all(engine)`.

6. **`backend/app/main.py`** — minimal FastAPI app:
   - Call `create_db_and_tables()` on startup lifespan event.
   - Include a basic `GET /healthz` route returning `{"status": "ok"}`.

7. **`backend/tests/conftest.py`** — pytest fixtures:
   - In-memory SQLite engine for tests (`sqlite:///:memory:`).
   - `db_session` fixture that creates tables and yields a session, rolling back after each test.
   - `test_client` fixture wrapping the FastAPI app with the test engine injected.

8. **`backend/.env.example`**:
   ```
   DATABASE_URL=sqlite:///./lazyseeker.db
   RAPIDAPI_KEY=your_key_here
   ```

9. **`backend/migrations/init.sql`** — human-readable DDL reference (not executed by the app; SQLModel's `create_all` is the source of truth).

### What to test

- `test_db_create_tables`: call `create_db_and_tables()` with an in-memory engine; assert that both tables exist by querying `sqlite_master`.
- `test_healthz`: `GET /healthz` returns 200 with `{"status": "ok"}`.
- `test_job_posting_defaults`: insert a minimal `JobPosting` and assert `score_status == "pending"`, `application_status == "new"`, `repost_of is None`.
- `test_company_model`: insert a `Company` and round-trip it; verify all fields persist correctly.
- `test_self_referential_fk`: insert a `JobPosting`, then insert a second with `repost_of` pointing to the first; verify the FK resolves.

### What this PR enables

All subsequent phases can import `Company`, `JobPosting`, and `get_session` directly. The Matcher team can begin reading the model contracts. CI can be wired up from this PR onwards.

---

## Phase 2 — Company Config (`companies.yaml`) and Static Crawler

**PR title:** `feat(radar): companies.yaml seed data and static-page crawler`

**Description:** Adds the `companies.yaml` config file with initial Israeli tech company seed data, implements the YAML loader, and builds the core crawl loop for static HTML career pages using `httpx` and `BeautifulSoup`. Does not yet handle JS-heavy pages, language detection, or deduplication.

### Files to create or modify

```
backend/
├── companies.yaml                          # NEW
├── app/
│   ├── services/
│   │   └── radar.py                        # NEW — core crawler service
│   └── config.py                           # NEW — YAML loader + app config
├── tests/
│   ├── test_radar_static.py                # NEW
│   └── fixtures/
│       ├── wix_careers.html                # NEW — static HTML fixture
│       └── monday_careers.html             # NEW — static HTML fixture
```

### Implementation steps

1. **`backend/companies.yaml`** — seed with 5–6 real Israeli tech companies. Use stable UUIDs (generate once, hard-code):

   ```yaml
   companies:
     - id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
       name: "Wix"
       career_page_url: "https://www.wix.com/jobs"
       linkedin_slug: "wix"
       active: true

     - id: "b2c3d4e5-f6a7-8901-bcde-f12345678901"
       name: "monday.com"
       career_page_url: "https://monday.com/jobs"
       linkedin_slug: "mondaydotcom"
       active: true

     - id: "c3d4e5f6-a7b8-9012-cdef-123456789012"
       name: "Fiverr"
       career_page_url: "https://www.fiverr.com/careers"
       linkedin_slug: "fiverr-international"
       active: true

     - id: "d4e5f6a7-b8c9-0123-defa-234567890123"
       name: "Walla! Communications"
       career_page_url: "https://walla.jobs"
       linkedin_slug: null
       active: true

     - id: "e5f6a7b8-c9d0-1234-efab-345678901234"
       name: "Check Point"
       career_page_url: "https://careers.checkpoint.com"
       linkedin_slug: "check-point-software-technologies"
       active: true
   ```

2. **`backend/app/config.py`**:
   - `CompanyConfig` Pydantic model: `id: UUID`, `name: str`, `career_page_url: str`, `linkedin_slug: Optional[str]`, `active: bool`.
   - `load_companies(yaml_path: Path) -> list[CompanyConfig]`: parse and validate `companies.yaml`. Raises `ValueError` on missing fields or invalid UUID.
   - `COMPANIES_YAML_PATH`: resolve relative to `backend/`; overridable via env var.

3. **`backend/app/services/radar.py`** — static crawler:

   - `fetch_static_page(url: str, timeout: float = 10.0) -> str`: uses `httpx.AsyncClient`. Raises `httpx.HTTPStatusError` on non-2xx.
   - `extract_job_links(html: str, base_url: str) -> list[dict]`: parses with BeautifulSoup. Heuristic: find `<a>` tags whose `href` contains `job`, `career`, `position`, `opening`, or `role`. Returns dicts with `url` (absolute) and `title` (link text, stripped).
   - `fetch_job_detail(url: str) -> dict`: fetches individual job page; extracts `title`, `description`, `requirements` (nullable).
   - `sync_companies_to_db(session: Session, companies: list[CompanyConfig]) -> None`: upserts each active company from YAML. Matches on `id`; does not delete removed companies — sets `active = False` instead.
   - `crawl_company(company: Company, session: Session) -> CrawlResult`: orchestrates a single company crawl. Returns a `CrawlResult` dataclass: `company_id`, `company_name`, `new_postings: int`, `status: Literal["success","error"]`, `error_message: Optional[str]`.
   - `run_crawl(session: Session) -> list[CrawlResult]`: iterates over all active companies, calls `crawl_company` for each, wraps each call in `try/except Exception`. Returns list of results.

### What to test

- `test_load_companies_valid`: load the real `companies.yaml`; assert 5 companies returned with valid UUIDs.
- `test_load_companies_invalid_uuid`: malformed `id` → `ValueError` raised.
- `test_fetch_static_page_success`: mock `httpx.AsyncClient.get` to return 200 with fixture HTML.
- `test_fetch_static_page_non_200`: mock 404 → `httpx.HTTPStatusError`.
- `test_fetch_static_page_timeout`: mock `httpx.TimeoutException` → propagates.
- `test_extract_job_links`: pass `wix_careers.html` fixture; assert ≥ 2 job link dicts returned.
- `test_sync_companies_to_db`: call twice; assert no duplicate rows, `active` flag respected.
- `test_crawl_company_error_does_not_crash_run`: mock one company to raise `Exception`; assert both results returned, failing one has `status == "error"`.

### What this PR enables

The crawl loop skeleton is runnable locally. Phase 3 can plug deduplication directly into `crawl_company`. Phase 4 can wire `run_crawl` to APScheduler and the `/radar/run` endpoint.

---

## Phase 3 — Language Detection and Deduplication

**PR title:** `feat(radar): language detection and URL-hash + repost deduplication`

**Description:** Adds language detection per posting (`en`/`he`/`mixed`), primary URL-hash deduplication, and secondary repost detection (title + company against archived postings). After this phase, the crawler persists deduplicated `JobPosting` rows to the database and sets `repost_of` where applicable.

### Files to create or modify

```
backend/
├── app/
│   └── services/
│       └── radar.py          # MODIFY — add dedup, language detection, DB persistence
├── tests/
│   └── test_radar_dedup.py   # NEW
```

### Implementation steps

1. **Language detection — `detect_language(text: str) -> Language`**:
   - Use `langdetect.detect` as the primary signal.
   - Hebrew heuristic: count Unicode characters in `\u0590`–`\u05FF`. If > 10% of alpha chars are Hebrew, text contains Hebrew.
   - Decision table:
     - `langdetect` returns `"iw"` or `"he"` AND Hebrew ratio > 30%: `Language.he`.
     - Hebrew ratio > 10% but also significant Latin content: `Language.mixed`.
     - Otherwise: `Language.en`.
   - Wrap `langdetect.detect` in `try/except LangDetectException`: fall back to Hebrew-ratio heuristic alone (short texts).

2. **`hash_url(url: str) -> str`**: `hashlib.sha256(url.strip().encode()).hexdigest()`.

3. **`posting_exists(url_hash: str, session: Session) -> bool`**: queries `JobPosting` by `url_hash`.

4. **`find_archived_repost(title: str, company_id: UUID, session: Session) -> Optional[UUID]`** (per ADR 004): find a `JobPosting` where title matches (case-insensitive, whitespace-normalized) AND `company_id` matches AND `application_status == ApplicationStatus.archived`. Return its `id` or `None`.

5. **`save_posting(raw: dict, company: Company, source: Source, session: Session) -> Optional[JobPosting]`**:
   - Compute `url_hash`; call `posting_exists` — return `None` if duplicate.
   - Detect language.
   - Call `find_archived_repost`.
   - Construct and insert `JobPosting` with `score_status = pending`, `application_status = new`, `repost_of` set if applicable.
   - Return the persisted posting.

6. Update `crawl_company` to call `save_posting` for each extracted job; count non-`None` returns as `new_postings`. Update `Company.last_crawled_at` at the end of each run.

### What to test

- `test_hash_url_deterministic`: same URL → same hash.
- `test_hash_url_different_urls`: different URLs → different hashes.
- `test_detect_language_english`, `test_detect_language_hebrew`, `test_detect_language_mixed`.
- `test_detect_language_short_text_fallback`: 5-char string → no exception, returns a `Language` value.
- `test_posting_exists_false_for_new_url`, `test_posting_exists_true_after_insert`.
- `test_save_posting_new`: new URL → `JobPosting` returned and persisted, `score_status == "pending"`.
- `test_save_posting_duplicate_url`: second call returns `None`, DB has exactly one row.
- `test_save_posting_repost_detection`: archived posting with same title+company → new posting has `repost_of` set.
- `test_save_posting_non_archived_same_title`: same title+company but `application_status == "new"` → `repost_of is None`.
- `test_last_crawled_at_updated`: assert `company.last_crawled_at` is set after crawl.

### What this PR enables

Database receives clean, deduplicated postings. Matcher can begin reading `JobPosting` rows with `score_status == "pending"`. ADR 004's repost contract is fully implemented.

---

## Phase 4 — Playwright Fallback, APScheduler, and API Endpoints

**PR title:** `feat(radar): Playwright fallback, APScheduler scheduling, and /radar API endpoints`

**Description:** Adds Playwright-based crawling for JS-heavy pages as a fallback, integrates APScheduler to run crawls every 6 hours, exposes `POST /radar/run` and `GET /radar/log` endpoints, and introduces an in-memory crawl log.

### Files to create or modify

```
backend/
├── app/
│   ├── main.py                   # MODIFY — register radar router, start scheduler
│   ├── services/
│   │   └── radar.py              # MODIFY — Playwright fallback, crawl log, scheduler init
│   ├── routers/
│   │   └── radar.py              # NEW — /radar/run and /radar/log
│   └── models/
│       └── crawl_log.py          # NEW — CrawlLogEntry dataclass
├── tests/
│   └── test_radar_api.py         # NEW
```

### Implementation steps

1. **`fetch_with_playwright(url: str, timeout_ms: int = 30000) -> str`**:
   - Launch Chromium headless via `async_playwright`.
   - Navigate with `page.goto(url, timeout=timeout_ms)`; wait for `networkidle` or 5s.
   - Return `page.content()`. Close browser in `finally`. Raise `CrawlTimeoutError` on `playwright.async_api.TimeoutError`.

2. **`fetch_career_page(url: str) -> str`** — smart fetch strategy:
   - Try `fetch_static_page` first.
   - If `extract_job_links` finds zero results, fall back to `fetch_with_playwright`.
   - Log which strategy was used at `DEBUG` level.

3. **`CrawlLogEntry` dataclass** — stored in module-level `deque(maxlen=500)`:
   ```python
   @dataclass
   class CrawlLogEntry:
       company_id: str
       company_name: str
       run_at: datetime
       status: Literal["success", "error"]
       new_postings: int
       error_message: Optional[str]
   ```
   `get_crawl_log() -> list[CrawlLogEntry]` returns entries in reverse-chronological order.

4. **Concurrent crawl guard**: module-level `asyncio.Lock`. `POST /radar/run` returns 409 if lock is held.

5. **APScheduler** in `main.py` lifespan:
   - `AsyncIOScheduler` with a job calling `run_scheduled_crawl` every 6 hours.
   - `run_scheduled_crawl` opens a DB session and calls `run_crawl`.
   - Respects the concurrent crawl guard.
   - Start on lifespan startup; shut down gracefully on lifespan shutdown.

6. **`backend/app/routers/radar.py`**:
   - `POST /radar/run` → check lock (409 if busy); spawn `run_crawl` as `BackgroundTask`; return `{"started": true}`.
   - `GET /radar/log` → return `get_crawl_log()` serialized to JSON per contracts README §5.

7. Register router in `main.py` with prefix `/radar`.

### What to test

- `test_fetch_with_playwright_success`: mock `async_playwright` → returns fixture HTML.
- `test_fetch_with_playwright_timeout`: mock raises `TimeoutError` → `CrawlTimeoutError`.
- `test_fetch_career_page_uses_static_when_links_found`: Playwright NOT called when BS4 finds links.
- `test_fetch_career_page_falls_back_to_playwright`: Playwright IS called when BS4 finds nothing.
- `test_crawl_log_appended_after_run`: one `CrawlLogEntry` per company in `_crawl_log`.
- `test_crawl_log_max_500`: 501 entries → `len(get_crawl_log()) == 500`.
- `test_post_radar_run_returns_started`: no crawl running → 200, `{"started": true}`.
- `test_post_radar_run_409_when_busy`: lock held → 409.
- `test_get_radar_log_empty`: fresh app → 200, `[]`.
- `test_get_radar_log_with_entries`: pre-populate log; assert response fields match.
- `test_get_radar_log_reverses_chronological_order`: newest entry first.

### What this PR enables

System is fully operational: scheduler runs every 6 hours. Frontend can integrate the Radar Status view against `GET /radar/log`. `POST /radar/run` enables the dashboard "Run Now" button.

---

## Phase 5 — LinkedIn Source and Full Test Coverage

**PR title:** `feat(radar): LinkedIn source via RapidAPI and complete test suite`

**Description:** Adds the LinkedIn job source using the RapidAPI LinkedIn wrapper. The source is controlled per-company via `linkedin_slug` in `companies.yaml`.

### Files to create or modify

```
backend/
├── app/
│   └── services/
│       ├── radar.py              # MODIFY — add LinkedIn crawl path
│       └── linkedin.py           # NEW — RapidAPI LinkedIn client
├── tests/
│   ├── test_linkedin.py          # NEW
│   └── test_radar_integration.py # NEW — full end-to-end crawl run with mocks
```

### Implementation steps

1. **`backend/app/services/linkedin.py`** — `LinkedInClient` class:
   - `__init__(self, api_key: str)`: store key, create `httpx.AsyncClient` with RapidAPI headers.
   - `async def search_jobs(self, company_slug: str, limit: int = 25) -> list[dict]`: calls RapidAPI endpoint; raises `httpx.HTTPStatusError` on non-2xx.
   - `async def get_job_detail(self, job_id: str) -> dict`.
   - `normalise_linkedin_job(raw: dict, company: Company) -> dict`: maps RapidAPI fields to internal posting dict. URL: `https://www.linkedin.com/jobs/view/{raw["id"]}`. `source = Source.linkedin`.

2. **Integration into `crawl_company`**:
   - After career page crawl, if `company.linkedin_slug is not None`, run LinkedIn search.
   - If `RAPIDAPI_KEY` env var is not set: log warning, skip LinkedIn entirely.
   - On HTTP 429: log and skip — do not retry in v1.
   - Dedup rules identical to career page source.

3. **`.env.example`**: add `RAPIDAPI_KEY=` with comment explaining it's optional.

4. **`test_radar_integration.py`**: full `run_crawl` with 3 mocked companies (one succeeds static, one falls back to Playwright, one fails completely). Assert log has 3 entries; DB has correct non-duplicate postings.

### What to test

- `test_linkedin_search_jobs_success`: mock httpx → normalised job list returned.
- `test_linkedin_search_jobs_non_200`: mock 429 → `httpx.HTTPStatusError`.
- `test_linkedin_search_jobs_missing_api_key`: env var not set → LinkedIn path skipped, no exception.
- `test_normalise_linkedin_job`: representative RapidAPI response → all required fields populated, `source == "linkedin"`, correct URL format.
- `test_linkedin_dedup_same_url`: two calls with same LinkedIn URL → one DB row.
- `test_linkedin_slug_null_skips_linkedin`: `linkedin_slug = None` → LinkedIn client never instantiated.
- `test_rapidapi_rate_limit_does_not_crash_run`: 429 → overall run continues, other companies processed.
- `test_full_crawl_run_integration`: 3 mocked companies → correct `CrawlLogEntry` statuses, correct DB posting counts, no exceptions escape.
- `test_repost_detection_across_sources`: career-page archived posting + LinkedIn repost with same title → `repost_of` set.

### What this PR enables

Radar subsystem is feature-complete per SPEC.md §5.1. Both sources operational and independently disableable. Matcher receives a steady stream of `score_status == "pending"` postings.

---

## Cross-Cutting Concerns

### Logging convention
Module-level `logger = logging.getLogger(__name__)`. Crawl results at `INFO`; HTTP errors at `WARNING`; unexpected exceptions at `ERROR` with full tracebacks via `logger.exception`.

### Error handling convention
- Never use bare `except`.
- Per-company errors caught at the `crawl_company` call site in `run_crawl` as `except Exception as e`.
- HTTP errors caught as `httpx.HTTPStatusError` or `httpx.RequestError`.
- Playwright errors caught as `playwright.async_api.Error`.

### No live HTTP in tests
All tests mock `httpx.AsyncClient` (using `pytest-httpx` or `respx`) and mock `async_playwright` using `unittest.mock.AsyncMock`. No test may make a real network call.

### Phase Sequencing

```
Phase 1 (skeleton + models + DB)
    └── Phase 2 (companies.yaml + static crawler)
            └── Phase 3 (language detection + dedup + DB persistence)
                    └── Phase 4 (Playwright + scheduler + API endpoints)
                            └── Phase 5 (LinkedIn + full test coverage)
```

Each phase is independently reviewable and deployable. Phases are strictly sequential — each builds directly on the prior.
