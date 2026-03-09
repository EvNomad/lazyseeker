# LazySeeker — Interface Contracts

This document defines the contracts between the three development domains:
**Radar** (crawler), **Matcher/Tailor** (AI scoring & CV suggestions), and **Frontend** (React dashboard).

No agent may change a contract unilaterally. Changes require updating this file and notifying the other parties.

---

## 1. `companies.yaml` — Radar's source of truth

Owned by: **Radar**
Consumed by: Radar (startup), Frontend (Radar Status view, read-only)

```yaml
companies:
  - id: "uuid-v4"
    name: "Wix"
    career_page_url: "https://www.wix.com/jobs"
    linkedin_slug: "wix"   # optional; null to disable LinkedIn source
    active: true
```

Rules:
- `id` is a stable UUID; never regenerate for existing entries
- `active: false` disables crawling without removing the record
- `linkedin_slug: null` disables LinkedIn source for that company

---

## 2. `JobPosting` — Radar → DB → Matcher & Frontend

Owned by: **Radar** (writes), **Matcher** (reads + updates `score_*` fields), **Frontend** (reads)

```typescript
interface JobPosting {
  id: string;                    // UUID
  url: string;                   // unique
  url_hash: string;              // SHA256(url)
  company_id: string;            // FK → Company
  title: string;
  description: string;           // full JD text
  requirements: string | null;   // extracted if separate section exists
  language: "en" | "he" | "mixed";
  source: "career_page" | "linkedin";
  crawled_at: string;            // ISO 8601
  overall_score: number | null;  // 0–100; null until scored
  score_breakdown: ScoreBreakdown | null;
  score_status: "pending" | "scored" | "error";
  application_status: "new" | "reviewing" | "applied" | "rejected" | "archived";
  repost_of: string | null;      // FK → JobPosting.id; null if original
}
```

Rules:
- Radar sets `score_status = "pending"` on creation; Matcher updates it to `"scored"` or `"error"`
- Radar never touches `score_*` fields after initial insert
- Matcher never touches `url`, `url_hash`, `company_id`, `title`, `description`, `requirements`, `language`, `source`, `crawled_at`

---

## 3. `ScoreBreakdown` — Matcher → DB → Frontend

Owned by: **Matcher** (writes), **Frontend** (reads)

```typescript
interface ScoreBreakdown {
  overall_score: number;          // 0–100
  low_signal_jd: boolean;         // true if JD < 100 words; caps overall_score at 70
  dimensions: {
    role_fit:      { score: number; reasoning: string };
    stack_fit:     { score: number; reasoning: string };
    seniority_fit: { score: number; reasoning: string };
    location_fit:  { score: number; reasoning: string };
  };
  flags: string[];                // e.g. ["Hebrew JD", "Requires Java", "Series B startup"]
  summary: string;                // 2–4 sentence plain-English summary
}
```

Rules:
- `overall_score` must equal `dimensions` weighted average (or be explicitly justified if it deviates)
- When `low_signal_jd: true`, `overall_score` must be ≤ 70
- All `reasoning` strings must be non-empty
- `flags` may be empty array but must never be null

---

## 4. `Suggestion` — Tailor → DB → Frontend

Owned by: **Tailor/Matcher** (writes), **Frontend** (reads + updates `status`)

```typescript
interface Suggestion {
  id: string;                              // UUID
  job_id: string;                          // FK → JobPosting
  section: string;                         // e.g. "Experience — WorkflowCo"
  original: string;                        // exact text from master CV
  suggested: string;                       // reframed version
  rationale: string;                       // references specific JD language
  status: "pending" | "approved" | "rejected";
  cv_version: string;                      // SHA256(cv_markdown) at generation time
  created_at: string;                      // ISO 8601
}
```

Rules:
- Tailor writes `status = "pending"`; Frontend updates to `"approved"` or `"rejected"` only
- Max 6 suggestions per `job_id`
- `cv_version` is computed at generation time and never updated
- Frontend must warn if `cv_version !== SHA256(current cv_markdown)`

---

## 5. REST API — Backend → Frontend

Owned by: **Radar** (radar endpoints), **Matcher/Tailor** (scoring + suggestion endpoints), both serve via **FastAPI**
Consumed by: **Frontend**

All responses are JSON. Errors follow:
```typescript
{ "detail": string }   // FastAPI default
```

### Jobs

```
GET    /jobs
  Query: ?min_score=int &status=string &language=string &company_id=string
  Response: JobPosting[]

GET    /jobs/:id
  Response: JobPosting & { company: Company }

PATCH  /jobs/:id/status
  Body:    { application_status: JobPosting["application_status"] }
  Response: JobPosting

POST   /jobs/:id/tailor
  Response: Suggestion[]

POST   /jobs/:id/retry-score
  Response: { score_status: "pending" }   // scoring is async; poll or refresh
```

### Suggestions

```
GET    /jobs/:id/suggestions
  Response: Suggestion[]

PATCH  /suggestions/:id
  Body:    { status: "approved" | "rejected" }
  Response: Suggestion

GET    /jobs/:id/tailored-cv
  Response: text/markdown (Content-Disposition: attachment)
  Error 409 if no approved suggestions exist
```

### Radar

```
POST   /radar/run
  Response: { started: true }   // async; check /radar/log for results

GET    /radar/log
  Response: CrawlLogEntry[]

interface CrawlLogEntry {
  company_id: string;
  company_name: string;
  run_at: string;
  status: "success" | "error";
  new_postings: number;
  error_message: string | null;
}
```

### Profile

```
GET    /profile
  Response: UserProfile

PUT    /profile
  Body:    { cv_markdown?: string; preferences?: string }
  Response: UserProfile

interface UserProfile {
  id: string;
  cv_markdown: string;
  preferences: string;
  updated_at: string;
}
```

---

## 6. Score Badge Color Rules — Frontend rendering contract

| Score | Color |
|---|---|
| ≥ 80 | Green |
| 60–79 | Yellow |
| < 60 | Red |
| `score_status = "pending"` | Grey "Awaiting score" badge |
| `score_status = "error"` | Red "Score error" badge |
| `low_signal_jd = true` | Amber "Low signal JD" badge (shown alongside score) |
| `repost_of != null` | "Repost" label shown on card |

---

## Change Process

1. Draft the proposed change in a PR description or `docs/ai-sessions/` note
2. Update this file
3. Update the affected agent's system prompt in `.claude/agents/` if behavior changes
4. All three domains must be updated atomically if a contract changes (no partial deploys)
