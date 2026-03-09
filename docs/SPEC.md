# LazySeeker — Project Specification v1.0

**Status:** Draft  
**Author:** TBD  
**Last Updated:** 2026-03-09  
**Target:** v1 MVP

---

## 1. Problem Statement

Job searching in the Israeli tech market is high-friction:

- Job alerts (LinkedIn, AllJobs, etc.) generate noise with poor semantic matching
- Assessing fit requires mentally cross-referencing your entire CV against every JD
- Each application ideally needs a slightly reframed CV, but doing this manually is tedious and inconsistent
- Many Israeli startup openings are scattered across company career pages, not aggregated in one place
- The feedback loop from applications is near-zero, making iteration difficult

**LazySeeker** is a personal AI agent that monitors Israeli tech companies and job sources, scores new openings against your profile with explained reasoning, and suggests targeted CV tweaks for high-fit roles — all managed through a React dashboard.

---

## 2. Goals

### v1 Goals
- Automatically discover new job openings from a curated list of Israeli tech companies
- Score each opening against the user's CV and preferences, with per-dimension explanations
- For high-fit roles, suggest honest, targeted CV tweaks as reviewable diff suggestions
- Present everything in a clean dashboard: radar, scores, suggestions, application status

### Non-Goals (v1)
- Automated application submission
- Email/calendar integration
- Multi-user support
- Mobile app
- Vector DB / full RAG pipeline (deferred to v2)

---

## 3. Users

**Single user: the developer themselves.**  
v1 is a personal tool, locally hosted. No auth, no multi-tenancy.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    React Dashboard                   │
│         (job list, scores, suggestions, tracker)     │
└───────────────────────┬─────────────────────────────┘
                        │ REST API
┌───────────────────────▼─────────────────────────────┐
│                   FastAPI Backend                    │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │    Radar    │  │   Matcher    │  │   Tailor   │  │
│  │  (crawler)  │  │  (scoring)   │  │  (CV diff) │  │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                │                │          │
│  ┌──────▼────────────────▼────────────────▼──────┐  │
│  │               SQLite (SQLModel)                │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │          Anthropic SDK (Claude Sonnet)         │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │         APScheduler (crawl jobs)               │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 5. Subsystems

### 5.1 Radar — Job Discovery

**Responsibility:** Find new job postings and normalize them into a standard schema.

**Sources (v1):**
- Curated list of Israeli tech companies with known career page URLs (stored in `companies.yaml`)
- LinkedIn job search (via RapidAPI LinkedIn wrapper or structured scraping)

**Behavior:**
- Runs on a configurable schedule (default: every 6 hours via APScheduler)
- Fetches each company's career page; extracts job listings using BeautifulSoup or Playwright (for JS-heavy pages)
- Normalizes each posting to `JobPosting` schema (see Section 6)
- Deduplicates by URL hash — existing postings are not re-scored
- Detects language (Hebrew / English) per posting and stores it as a flag
- Logs crawl results (success, failed, new postings found) per run

**Edge Cases:**
- Career page structure changes → crawler should fail gracefully and log, not crash
- Hebrew-only JDs → stored as-is; Matcher handles bilingual content
- Duplicate postings across sources → deduplicated by URL hash; title+company used as fallback

---

### 5.2 Matcher — Fit Scoring

**Responsibility:** Score each new job posting against the user's profile and explain the reasoning.

**Inputs:**
- `JobPosting` (title, description, requirements, company)
- User context: CV (markdown), preferences doc ("what I'm looking for")

**Behavior:**
- Triggered automatically after Radar stores a new posting
- Sends a structured prompt to Claude Sonnet with the JD and user context
- Claude returns a structured JSON score (see below)
- Score stored alongside the posting in SQLite

**Score Schema:**
```json
{
  "overall_score": 82,
  "dimensions": {
    "role_fit":      { "score": 85, "reasoning": "..." },
    "stack_fit":     { "score": 75, "reasoning": "..." },
    "seniority_fit": { "score": 90, "reasoning": "..." },
    "location_fit":  { "score": 80, "reasoning": "..." }
  },
  "flags": ["Hebrew JD", "Requires Java", "Series B startup"],
  "summary": "Strong match on seniority and role scope. Stack overlap is partial — they want Java but your Node/Python background maps well to their platform engineering needs."
}
```

**Prompt Design Principles:**
- System prompt includes full CV and preferences as context
- Scoring must be semantic, not keyword-based
- Reasoning must explain *how* the user's experience maps (or doesn't) to requirements
- Claude must flag gaps honestly — no inflating scores

**Edge Cases:**
- JD is very short or vague → score with lower confidence, flag as "low signal JD"
- JD is in Hebrew → pass as-is; Claude handles bilingual input
- Anthropic API timeout / error → retry once, then mark posting as `score_pending`

---

### 5.3 Tailor — CV Tweak Suggestions

**Responsibility:** For a selected job posting, suggest targeted, honest CV edits that better align with the JD.

**Inputs:**
- Selected `JobPosting`
- Master CV (markdown)

**Behavior:**
- Triggered manually by user from the dashboard
- Claude compares master CV to JD and returns a list of `Suggestion` objects
- Each suggestion targets a specific section and bullet in the CV
- User reviews suggestions in the dashboard: approve or reject each one
- Approved suggestions can be exported as a tailored CV (markdown → PDF)

**Suggestion Schema:**
```json
{
  "id": "uuid",
  "job_id": "uuid",
  "section": "Experience — WorkflowCo",
  "original": "Built internal workflow automation tools",
  "suggested": "Designed and shipped a workflow engine processing 10k+ daily executions, directly comparable to their stated platform scaling requirements",
  "rationale": "JD emphasizes 'scalable automation platforms' — surfacing the execution volume makes the parallel explicit",
  "status": "pending"
}
```

**Constraints (enforced via system prompt):**
- Suggestions must be reframings or elaborations of real experience — never fabrications
- Suggestions must reference specific JD language to justify the change
- No more than 6 suggestions per posting (avoid CV noise)

**Edge Cases:**
- CV is already well-aligned → return 0–2 minor suggestions, not forced rewrites
- User rejects all suggestions → no change to master CV; tailored version not generated
- Export to PDF fails → fall back to markdown download

---

## 6. Data Models

### JobPosting
| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| url | String | Unique; used for dedup |
| url_hash | String | SHA256 of URL |
| company_id | FK → Company | |
| title | String | |
| description | Text | Full JD text |
| requirements | Text | Extracted if separate |
| language | Enum(en, he, mixed) | |
| source | Enum(career_page, linkedin) | |
| crawled_at | DateTime | |
| overall_score | Int (0–100) | Null until scored |
| score_breakdown | JSON | Full score object |
| score_status | Enum(pending, scored, error) | |
| application_status | Enum(new, reviewing, applied, rejected, archived) | |

### Company
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| name | String | |
| career_page_url | String | |
| linkedin_slug | String | Optional |
| active | Boolean | Toggle crawling |
| last_crawled_at | DateTime | |

### Suggestion
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| job_id | FK → JobPosting | |
| section | String | CV section label |
| original | Text | |
| suggested | Text | |
| rationale | Text | |
| status | Enum(pending, approved, rejected) | |
| created_at | DateTime | |

### UserProfile
| Field | Type | Notes |
|---|---|---|
| id | UUID | Single row |
| cv_markdown | Text | Master CV |
| preferences | Text | Free-form "what I want" doc |
| updated_at | DateTime | |

---

## 7. API Endpoints (FastAPI)

### Jobs
- `GET /jobs` — list all postings, filterable by score, status, language
- `GET /jobs/{id}` — full posting + score breakdown
- `PATCH /jobs/{id}/status` — update application status
- `POST /jobs/{id}/tailor` — trigger Tailor for this posting

### Suggestions
- `GET /jobs/{id}/suggestions` — list suggestions for a posting
- `PATCH /suggestions/{id}` — approve or reject a suggestion
- `GET /jobs/{id}/tailored-cv` — export approved suggestions as tailored CV

### Radar
- `POST /radar/run` — manually trigger a crawl run
- `GET /radar/log` — recent crawl activity

### Profile
- `GET /profile` — retrieve CV and preferences
- `PUT /profile` — update CV or preferences

---

## 8. Frontend — React Dashboard

### Views

**Job Feed (main view)**
- List of postings sorted by score descending
- Filters: min score, application status, language, company
- Each row: company logo, title, score badge (color-coded), flags, date
- Click → opens Job Detail panel

**Job Detail Panel**
- Full JD text
- Score breakdown with per-dimension bar + reasoning text
- Application status selector
- "Generate CV Suggestions" button
- Link to original posting

**Suggestions View**
- Triggered from Job Detail
- Side-by-side diff: original vs suggested per bullet
- Rationale shown below each
- Approve / Reject buttons per suggestion
- "Export Tailored CV" button (only enabled if ≥1 approved)

**Radar Status**
- Last crawl time per company
- New postings found in last run
- Manual "Run Now" trigger
- Error log for failed crawls

**Profile Editor**
- CV (markdown editor)
- Preferences (free-form text)
- Save button

---

## 9. AI-Assisted Development Process

This project is also an exercise in AI-assisted development. The following process applies to every feature:

| Phase | Activity |
|---|---|
| **Spec** | Write feature spec in markdown; ask Claude to identify gaps, ambiguities, and missing edge cases |
| **Test Plan** | Claude drafts test cases from the spec before implementation begins |
| **Implementation** | Claude pair-programs; developer reviews and drives direction |
| **Code Review** | Claude reviews PR diff before merge; flags issues against spec |
| **Deploy** | GitHub Actions pipeline; Claude helps author workflow YAML |

All AI interactions during development are saved as markdown notes in `/docs/ai-sessions/` for reflection and future reference.

---

## 10. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python 3.12, FastAPI | Async, clean, familiar |
| AI | Anthropic SDK (raw), Claude Sonnet | Learning goal: no framework abstraction |
| ORM / DB | SQLModel + SQLite | Simple, no infra overhead for v1 |
| Scheduler | APScheduler | Lightweight, embedded |
| Scraping | httpx + BeautifulSoup, Playwright | BS4 for static pages, Playwright for JS-heavy |
| Frontend | React 18, Tailwind CSS, shadcn/ui | Clean, productive |
| Containerization | Docker Compose | Backend + frontend together |
| CI/CD | GitHub Actions | Lint, test, build, deploy |
| Deployment | Railway or self-hosted VPS | Simple one-click or Docker |

---

## 11. Repository Structure

```
lazyseeker/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/          # SQLModel data models
│   │   ├── routers/         # FastAPI routers (jobs, radar, profile, suggestions)
│   │   ├── services/
│   │   │   ├── radar.py     # Crawler logic
│   │   │   ├── matcher.py   # Scoring prompts & Claude calls
│   │   │   └── tailor.py    # CV diff prompts & suggestion logic
│   │   ├── prompts/         # System & user prompt templates
│   │   └── db.py
│   ├── tests/
│   ├── companies.yaml       # Curated company list
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   └── api/             # API client
│   └── package.json
├── docs/
│   ├── SPEC.md              # This file
│   ├── ai-sessions/         # Saved AI dev session notes
│   └── decisions/           # Architecture Decision Records
├── .github/
│   └── workflows/
│       └── ci.yml
└── docker-compose.yml
```

---

## 12. Open Questions (for Claude review)

The following questions are intentionally left open for AI-assisted review before implementation begins:

1. LinkedIn scraping may violate ToS — should we default to RapidAPI wrapper or build an official OAuth integration?
2. How should the Matcher handle very short JDs (< 100 words) where there's not enough signal to score reliably?
3. Should the master CV be versioned? If the user updates it after suggestions have been generated, existing suggestions may become stale.
4. What's the right dedup strategy when the same role is reposted after being closed?
5. Should `companies.yaml` be user-editable via the UI in v1, or config-file only?
6. How do we handle Hebrew-dominant JDs in the Tailor prompt — should we translate first or pass bilingual context directly to Claude?
7. What's the failure mode when the Anthropic API is unavailable? Should unscored jobs surface in the feed or be held back?

---

## 13. Build Milestones

| Week | Milestone |
|---|---|
| 1 | Radar: company config, crawler, SQLite schema, basic FastAPI endpoints, tests |
| 2 | Matcher: scoring prompt, structured output, dashboard job list with scores |
| 3 | Tailor: CV diff prompt, suggestion UI, approve/reject, CV export |
| 4 | Polish: scheduler, Hebrew handling, Docker Compose, GitHub Actions CI |

---

*This spec is a living document. All significant changes should be noted with date and rationale.*
