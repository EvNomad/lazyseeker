# LazySeeker — Claude Code Guide

## Project Overview

**LazySeeker** is a personal AI agent for monitoring Israeli tech job openings, scoring them against a CV, and suggesting targeted CV tweaks. Single-user, locally hosted. No auth, no multi-tenancy.

## Architecture

```
React Dashboard → FastAPI (REST) → SQLite (SQLModel)
                                 → Anthropic SDK (Claude Sonnet)
                                 → APScheduler (crawl jobs)
```

Three backend subsystems:
- **Radar** (`backend/app/services/radar.py`) — crawls company career pages and LinkedIn, deduplicates by URL hash
- **Matcher** (`backend/app/services/matcher.py`) — scores postings against user CV via Claude; stores structured JSON scores
- **Tailor** (`backend/app/services/tailor.py`) — generates honest, targeted CV tweak suggestions via Claude; user approves/rejects

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI |
| AI | Anthropic SDK (raw) — no LangChain or framework abstraction |
| ORM / DB | SQLModel + SQLite |
| Scheduler | APScheduler (embedded) |
| Scraping | httpx + BeautifulSoup; Playwright for JS-heavy pages |
| Frontend | React 18, Tailwind CSS, shadcn/ui |
| Containerization | Docker Compose |
| CI/CD | GitHub Actions |

## Repository Structure

```
lazyseeker/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/          # SQLModel data models
│   │   ├── routers/         # FastAPI routers (jobs, radar, profile, suggestions)
│   │   ├── services/
│   │   │   ├── radar.py
│   │   │   ├── matcher.py
│   │   │   └── tailor.py
│   │   ├── prompts/         # System & user prompt templates (plain text or .md)
│   │   └── db.py
│   ├── tests/
│   ├── companies.yaml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   └── api/             # API client (typed fetch wrappers)
│   └── package.json
├── docs/
│   ├── SPEC.md
│   ├── ai-sessions/         # Save notes from AI dev sessions here
│   └── decisions/           # Architecture Decision Records
├── .github/workflows/ci.yml
└── docker-compose.yml
```

## Development Workflow (AI-Assisted)

Every feature follows this order — do not skip phases:

1. **Spec** — write or update feature spec in `docs/`; identify gaps and edge cases before writing code
2. **Test Plan** — draft test cases from the spec before implementation
3. **Implementation** — pair-program; developer drives direction and reviews all AI output
4. **Code Review** — review the diff against the spec before merging
5. **Deploy** — GitHub Actions pipeline handles lint, test, build

Save notable AI dev session notes in `docs/ai-sessions/` as markdown files.

## Python Conventions

- Python 3.12; use `async`/`await` throughout FastAPI routes and service calls
- Type-annotate all function signatures; use `pydantic` / `SQLModel` models for all data shapes
- Use `httpx.AsyncClient` for HTTP calls (not `requests`)
- Never use bare `except`; catch specific exceptions and log them
- Crawlers must fail gracefully: log errors per-company, never crash the scheduler run
- All Claude API calls go through `backend/app/services/`; routers must not call Anthropic directly
- Prompts live in `backend/app/prompts/` as separate files — keep them out of service code
- After an Anthropic API error: retry once, then mark the record with the appropriate error status (e.g., `score_status = "error"`) — do not silently swallow failures

## Anthropic SDK Usage

- Use raw Anthropic SDK; avoid any abstraction framework (LangChain, etc.) — this is intentional
- Model: `claude-sonnet-4-6` (or the latest available Sonnet)
- Always use structured JSON output for Matcher and Tailor responses; validate the schema before persisting
- System prompt must include full CV and preferences as context for scoring calls
- Scoring must be semantic, not keyword-based; reasoning must explain the mapping honestly
- Tailor constraints (enforced in system prompt):
  - Suggestions must be reframings of real experience — no fabrications
  - Each suggestion must reference specific JD language as justification
  - Max 6 suggestions per posting

## Data Model Rules

- Deduplicate `JobPosting` by `url_hash` (SHA256 of URL); fallback: `title + company`
- Do not re-score an already-scored posting — check `score_status` before triggering Matcher
- `UserProfile` is a single-row table; always upsert, never insert a second row
- `Suggestion.status` transitions: `pending → approved | rejected` only; no reversion

## API Conventions

- REST endpoints follow the routes defined in `docs/SPEC.md §7` — do not invent new endpoints without updating the spec
- All list endpoints support filtering (score, status, language, company)
- Use `PATCH` for partial updates (status changes); use `PUT` for full resource replacement (profile)
- Return 422 with validation detail on bad input; return 500 with a structured error body on unexpected failures

## Frontend Conventions

- Use shadcn/ui components as the base; extend with Tailwind utility classes
- Keep API calls in `frontend/src/api/`; views and components must not call `fetch` directly
- Score badges are color-coded: ≥80 green, 60–79 yellow, <60 red
- The Suggestions view must show a side-by-side diff (original vs suggested) with rationale below
- "Export Tailored CV" is disabled until at least one suggestion is approved

## Testing

- Backend: pytest with async support (`pytest-asyncio`); test all service functions with mocked Claude responses
- Cover the key edge cases from the spec: short/vague JDs, Hebrew-only JDs, Anthropic API timeout, duplicate URLs, failed crawls
- Frontend: component tests for the Suggestions diff view and score badge rendering
- CI runs lint (ruff, eslint) + tests on every push

## Key Constraints

- v1 is single-user and local — do not add auth, multi-tenancy, or a vector DB
- Do not auto-submit applications — the tool informs and assists, never acts
- LinkedIn scraping: prefer the RapidAPI wrapper over direct scraping to avoid ToS issues; document the choice in `docs/decisions/`
- Hebrew JDs: pass bilingual content directly to Claude — no pre-translation step in v1
- PDF export failure: fall back to markdown download, never block the user

## Resolved Decisions

All open questions resolved on 2026-03-09. See `docs/SPEC.md §12` for the full table. Key implementation notes:

- **LinkedIn**: use RapidAPI wrapper; make the source toggleable per-company in `companies.yaml`
- **Short JDs**: if JD < 100 words, set `low_signal_jd: true` in score JSON and cap `overall_score` at 70
- **CV versioning**: store `cv_version` (SHA256) on each `Suggestion`; warn in UI when CV has changed, offer regenerate
- **Reposted roles**: new `JobPosting` with `repost_of` FK if `title + company` matches an archived posting
- **`companies.yaml`**: config-file only in v1; no UI editor
- **Hebrew JDs**: pass bilingual content directly to Claude; instruct it to respond in English
- **API unavailable**: surface jobs with `score_status = "pending"` badge; add per-job "Retry scoring" button
