# Matcher & Tailor Implementation Plan

## Context and Dependencies

The Matcher/Tailor work depends on `JobPosting` existing in the database (written by Radar). Since the backend does not exist yet, Phase 1 bootstraps the shared infrastructure (DB, models, app skeleton), allowing Phase 2 onward to proceed in parallel with Radar development. Phases 2–6 use seed fixtures for `JobPosting` rows so they are never blocked on Radar being merged.

---

## Phase 1 — Backend Bootstrap: DB, Models, App Skeleton

**PR title:** `feat: backend skeleton — FastAPI app, SQLModel DB, JobPosting/Company/UserProfile models`

**Description:** Stand up the FastAPI application, SQLite database engine, and the three SQLModel models that every subsequent phase depends on. This is the foundation all other PRs build on.

**Files to create:**

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── db.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── company.py
│   │   ├── job_posting.py
│   │   ├── user_profile.py
│   │   └── suggestion.py
│   └── routers/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   └── conftest.py
└── requirements.txt
```

**Implementation steps:**

1. `requirements.txt` — list: `fastapi`, `uvicorn[standard]`, `sqlmodel`, `anthropic`, `pytest`, `pytest-asyncio`, `httpx` (for test client).

2. `backend/app/db.py` — create a SQLite engine using `create_engine("sqlite:///./lazyseeker.db")`, a `get_session` dependency yielding a `Session`, and a `create_db_and_tables()` function calling `SQLModel.metadata.create_all(engine)`.

3. `backend/app/models/company.py` — `Company` SQLModel table with all fields from SPEC §6: `id` (UUID, primary key, default `uuid4`), `name`, `career_page_url`, `linkedin_slug` (nullable), `active` (bool, default True), `last_crawled_at` (nullable datetime).

4. `backend/app/models/job_posting.py` — `JobPosting` SQLModel table with all fields from SPEC §6. Use Python `Enum` types for `language` (`en`/`he`/`mixed`), `source` (`career_page`/`linkedin`), `score_status` (`pending`/`scored`/`error`), `application_status` (`new`/`reviewing`/`applied`/`rejected`/`archived`). `score_breakdown` stored as `Optional[str]` (JSON text column). `overall_score` is `Optional[int]`. `repost_of` is `Optional[str]` (FK string, SQLite has no enforced FK by default). `score_status` defaults to `"pending"`.

5. `backend/app/models/user_profile.py` — `UserProfile` SQLModel table: `id` (UUID), `cv_markdown` (Text), `preferences` (Text), `updated_at` (datetime, default `datetime.utcnow`). Single-row design; enforce in service layer, not DB constraint.

6. `backend/app/models/suggestion.py` — `Suggestion` SQLModel table: all fields from contracts README §4. `status` Enum: `pending`/`approved`/`rejected`. `cv_version` (str, non-nullable). `created_at` (datetime, default `datetime.utcnow`).

7. `backend/app/main.py` — create `FastAPI()` app, call `create_db_and_tables()` on startup via `@app.on_event("startup")`, include router stubs (empty routers to be filled by later phases).

8. `backend/tests/conftest.py` — `pytest` fixtures: in-memory SQLite engine, session fixture, `TestClient` fixture wrapping the FastAPI app with the in-memory DB. Use `pytest-asyncio` `asyncio_mode = "auto"` in `pyproject.toml` or `pytest.ini`.

**Tests:**

- `test_db_creates_tables` — call `create_db_and_tables()` against the in-memory engine; assert all four tables exist.
- `test_job_posting_defaults` — insert a minimal `JobPosting` (url, url_hash, company_id, title, description) and assert `score_status == "pending"`, `application_status == "new"`, `overall_score is None`.
- `test_user_profile_single_row_pattern` — insert two `UserProfile` rows; verify the service-layer upsert function (to be written) replaces rather than inserts.

**What this PR enables:** Every downstream phase. Phase 2 (UserProfile) and Phase 3 (Matcher service) can both branch from this.

---

## Phase 2 — UserProfile Endpoints + Seed Fixtures

**PR title:** `feat: UserProfile GET/PUT endpoints and test fixtures`

**Description:** Implement the `/profile` REST endpoints and the seed fixture mechanism that all future test phases need to inject `JobPosting` rows without depending on Radar.

**Files to create/modify:**

```
backend/
├── app/
│   └── routers/
│       └── profile.py
├── tests/
│   ├── conftest.py          (modify — add fixtures)
│   └── fixtures/
│       └── seed.py
```

**Implementation steps:**

1. `backend/app/routers/profile.py` — two endpoints:
   - `GET /profile` — fetch the single `UserProfile` row; if none exists return a 404 with `{"detail": "Profile not found"}`.
   - `PUT /profile` — accept body `{ cv_markdown?: str, preferences?: str }`. Upsert: if a row exists update it, otherwise insert one. Always set `updated_at = datetime.utcnow()`. Return the full `UserProfile`.
   - Upsert helper `get_or_create_profile(session)` — shared by both endpoints and the Matcher service.

2. Register the router in `main.py`.

3. `backend/tests/fixtures/seed.py` — a module with helper functions used across all test files:
   - `make_company(session) -> Company` — inserts a stub Company row.
   - `make_job_posting(session, *, description="...", language="en", score_status="pending") -> JobPosting` — inserts a `JobPosting` with all required fields. `description` parameter allows tests to vary JD length.
   - `make_user_profile(session, *, cv_markdown="...", preferences="...") -> UserProfile` — upsert a profile.

**Tests (`backend/tests/test_profile.py`):**

- `test_get_profile_404_when_empty` — GET /profile on fresh DB; assert 404.
- `test_put_profile_creates_on_first_call` — PUT /profile `{cv_markdown: "# My CV", preferences: "I want remote"}` → 200, response contains both fields, `id` is a UUID, `updated_at` is set.
- `test_put_profile_updates_existing` — PUT twice; assert single row in DB (no duplicates), second call's values win.
- `test_put_profile_partial_update` — PUT with only `cv_markdown`; assert `preferences` is unchanged.
- `test_get_profile_returns_existing` — PUT then GET; assert response matches PUT body.

**What this PR enables:** Phase 3 (Matcher) and Phase 5 (Tailor) both need `UserProfile` in tests. The seed fixtures unblock all test phases that need `JobPosting` rows.

---

## Phase 3 — Matcher Service: Prompt Templates, Scoring, score_status

**PR title:** `feat: Matcher service — fit scoring via Claude tool_use, ScoreBreakdown, retry-once`

**Description:** The core scoring logic. Reads `JobPosting` + `UserProfile`, builds the structured prompt, calls Claude with `tool_use` to enforce `ScoreBreakdown`, validates, persists. Includes short-JD handling, Hebrew pass-through, and retry-once on API error. Does not yet include the HTTP endpoint (that is Phase 4).

**Files to create:**

```
backend/
├── app/
│   ├── prompts/
│   │   ├── matcher_system.md
│   │   └── matcher_user.md
│   └── services/
│       └── matcher.py
├── tests/
│   └── test_matcher.py
```

**Implementation steps:**

1. `backend/app/prompts/matcher_system.md` — the Matcher system prompt template. Placeholders: `{cv_markdown}`, `{preferences}`. Content must:
   - Explain you are a career advisor scoring a job posting against a CV.
   - Instruct Claude to score semantically (how experience maps, not keyword count).
   - Instruct Claude to flag gaps honestly and never inflate scores.
   - Include: "The job description may be in Hebrew or a mix of Hebrew and English. Always respond in English."
   - Instruct: "If the job description is fewer than 100 words, set `low_signal_jd` to `true`."
   - Instruct: "When `low_signal_jd` is `true`, `overall_score` must be 70 or lower."
   - State that `flags` must be an array (never null); may be empty.
   - State that each `reasoning` field must be a non-empty string.
   - State that `summary` must be 2–4 sentences.

2. `backend/app/prompts/matcher_user.md` — user turn template. Placeholder: `{job_description}`. Simple: "Score the following job posting:\n\n{job_description}".

3. `backend/app/services/matcher.py` — define a module-level `anthropic.AsyncAnthropic()` client.

   Define a Pydantic model `ScoreBreakdown` (not a SQLModel table — just a validator):
   ```python
   class DimensionScore(BaseModel):
       score: int
       reasoning: str

   class ScoreBreakdown(BaseModel):
       overall_score: int
       low_signal_jd: bool
       dimensions: dict[str, DimensionScore]  # keys: role_fit, stack_fit, seniority_fit, location_fit
       flags: list[str]
       summary: str

       @validator("overall_score")
       def cap_low_signal(cls, v, values):
           if values.get("low_signal_jd") and v > 70:
               raise ValueError("overall_score must be ≤ 70 when low_signal_jd is true")
           return v
   ```

   Define the Claude tool schema `score_job_posting` that mirrors `ScoreBreakdown` exactly. This is the `tools` list passed to `client.messages.create()`.

   Define `async def score_job_posting(job: JobPosting, profile: UserProfile, session: Session) -> None`:
   - Load prompt templates from `backend/app/prompts/` using a path relative to the module file.
   - Substitute `{cv_markdown}`, `{preferences}` into system prompt; `{job_description}` into user prompt.
   - Build messages list: `[{"role": "user", "content": user_prompt}]`.
   - Call Claude with `tools=[score_job_posting_tool]`, `tool_choice={"type": "tool", "name": "score_job_posting"}`, `model="claude-sonnet-4-6"`.
   - On `anthropic.APIError` or any `Exception` from the first call: retry once (same call).
   - On second failure: set `job.score_status = "error"`, commit, return.
   - On success: extract `tool_use` block from response, parse JSON input to `ScoreBreakdown`.
   - On `ValidationError`: log the raw response, set `score_status = "error"`, commit, return.
   - On success: check `low_signal_jd` flag; if True and `overall_score > 70`, cap it at 70 as a defensive post-processing step.
   - Write `job.overall_score`, `job.score_breakdown` (JSON-serialized string), `job.score_status = "scored"`, commit.

4. Prompt loading: use a module-level helper `_load_prompt(name: str) -> str` that reads from the `prompts/` directory.

   **Retry-once pattern:**
   ```python
   last_exc = None
   for attempt in range(2):
       try:
           response = await client.messages.create(...)
           break
       except anthropic.APIError as e:
           last_exc = e
   else:
       job.score_status = "error"
       session.add(job)
       session.commit()
       return
   ```

**Tests (`backend/tests/test_matcher.py`):**

All tests mock `anthropic.AsyncAnthropic.messages.create` using `unittest.mock.AsyncMock` or `pytest-mock`.

Mock helper: define `make_tool_use_response(breakdown_dict)` that returns a fake `anthropic.types.Message` with a `tool_use` content block containing the given dict as `input`.

- `test_happy_path_scored` — mock returns valid `ScoreBreakdown` JSON (overall_score=82, low_signal_jd=False). Assert `job.score_status == "scored"`, `job.overall_score == 82`, all four dimension keys present.
- `test_short_jd_cap_at_70` — JD with < 100 words. Mock returns `low_signal_jd=True, overall_score=85`. Assert `job.overall_score <= 70`.
- `test_short_jd_already_capped` — mock returns `low_signal_jd=True, overall_score=65`. Assert `overall_score == 65` (not further modified).
- `test_hebrew_jd_passes_through` — JD with Hebrew text. Assert the `messages.create` call receives the Hebrew text unmodified. Assert scoring proceeds normally.
- `test_api_error_retries_once_then_error` — mock raises `anthropic.APIError` on both calls. Assert `messages.create` called exactly twice. Assert `job.score_status == "error"`.
- `test_api_error_retries_once_succeeds` — mock raises on first call, succeeds on second. Assert called exactly twice. Assert `job.score_status == "scored"`.
- `test_malformed_json_response` — mock returns a `tool_use` block with `input` missing required fields. Assert `job.score_status == "error"`, nothing persisted to `score_breakdown`.
- `test_flags_never_null` — mock returns `flags=[]`. Assert persisted `ScoreBreakdown` has `flags == []`.
- `test_does_not_touch_radar_fields` — after scoring, assert `job.url`, `job.url_hash`, `job.title`, `job.description`, `job.language` are unchanged.

**What this PR enables:** Phase 4 (HTTP endpoint) can be reviewed in isolation after this is merged. Also unblocks Phase 5 (Tailor).

---

## Phase 4 — Matcher HTTP Endpoints: GET/PATCH Jobs + retry-score

**PR title:** `feat: jobs router — GET /jobs, GET /jobs/{id}, PATCH /jobs/{id}/status, POST /jobs/{id}/retry-score`

**Description:** Wire the Matcher service into FastAPI. Add the jobs listing and detail endpoints. Add the `retry-score` endpoint.

**Files to create/modify:**

```
backend/
├── app/
│   └── routers/
│       └── jobs.py          (create)
│   └── main.py              (modify — register router)
├── tests/
│   └── test_jobs_router.py  (create)
```

**Implementation steps:**

1. `backend/app/routers/jobs.py`:

   - `GET /jobs` — query `JobPosting` table. Support query params: `min_score: Optional[int]`, `status: Optional[str]`, `language: Optional[str]`, `company_id: Optional[str]`. Return `list[JobPosting]`.

   - `GET /jobs/{id}` — fetch single `JobPosting` by ID. 404 if not found. Join with `Company` and return posting + `company` nested object.

   - `PATCH /jobs/{id}/status` — accept `{ application_status: str }`, validate against the enum, update and return. Return 422 on invalid status value.

   - `POST /jobs/{id}/retry-score` — fetch posting; if `score_status == "scored"` return 409. Set `score_status = "pending"`, commit, enqueue scoring as `BackgroundTask`. Return `{"score_status": "pending"}` immediately.

2. `JobPostingRead` Pydantic response model with all `JobPosting` fields plus optional `company: Optional[CompanyRead]`.

**Tests (`backend/tests/test_jobs_router.py`):**

- `test_get_jobs_empty` — fresh DB; GET /jobs → 200, empty list.
- `test_get_jobs_returns_postings` — seed 3 postings; GET /jobs → list of 3.
- `test_get_jobs_filter_min_score` — seed postings with scores 90, 60, 30; GET /jobs?min_score=65 → only score=90 returned.
- `test_get_jobs_filter_language` — seed `he` and `en` postings; GET /jobs?language=he → only Hebrew.
- `test_get_job_by_id` — seed one posting; GET /jobs/{id} → posting with `company` nested.
- `test_get_job_404` — GET /jobs/nonexistent-id → 404.
- `test_patch_job_status_valid` — PATCH /jobs/{id}/status `{application_status: "reviewing"}` → 200.
- `test_patch_job_status_invalid` — PATCH `{application_status: "flying"}` → 422.
- `test_retry_score_returns_pending` — seed error posting; mock `score_job_posting`; POST retry-score → 200, `{"score_status": "pending"}`.
- `test_retry_score_409_if_already_scored` — posting with `score_status="scored"`; POST retry-score → 409.

**What this PR enables:** Frontend can start consuming job list and detail endpoints. Phases 5 and 6 are unblocked.

---

## Phase 5 — Tailor Service: CV Diff Prompts, Suggestion Generation, cv_version

**PR title:** `feat: Tailor service — CV diff suggestions via Claude, cv_version SHA256, max-6 enforcement`

**Files to create:**

```
backend/
├── app/
│   ├── prompts/
│   │   ├── tailor_system.md
│   │   └── tailor_user.md
│   └── services/
│       └── tailor.py
├── tests/
│   └── test_tailor.py
```

**Implementation steps:**

1. `backend/app/prompts/tailor_system.md` — Tailor system prompt. Placeholders: `{cv_markdown}`. Must enforce:
   - Suggestions are reframings of real experience — never fabrications.
   - Every suggestion references specific JD language as justification.
   - If CV is well-aligned, return 0–2 suggestions — no forced rewrites.
   - Max 6 suggestions.
   - Bilingual: "The job description may be in Hebrew or a mix of Hebrew and English. Always respond in English."
   - Output via `generate_suggestions` tool call only.

2. `backend/app/prompts/tailor_user.md` — user turn. Placeholder: `{job_description}`.

3. `backend/app/services/tailor.py`:

   Pydantic model `SuggestionInput`:
   ```python
   class SuggestionInput(BaseModel):
       section: str
       original: str
       suggested: str
       rationale: str
   ```

   `generate_suggestions` tool schema: `{"suggestions": list[SuggestionInput]}`.

   `async def generate_suggestions(job, profile, session) -> list[Suggestion]`:
   - `cv_version = hashlib.sha256(profile.cv_markdown.encode()).hexdigest()`
   - Call Claude with `tool_choice={"type": "tool", "name": "generate_suggestions"}`.
   - On error: raise `TailorError`.
   - Enforce max 6 (truncate and log if Claude returns more).
   - If called again for the same job: delete existing `pending` suggestions, preserve `approved`/`rejected`.
   - Bulk-insert, commit, return.

   Pure helper `assemble_tailored_cv(cv_markdown: str, suggestions: list[Suggestion]) -> str` — string-replace each `original` with `suggested`. Append `## Unmatched Suggestions` section for any `original` not found verbatim.

   `cv_version_for_profile(profile: UserProfile) -> str` — module-level pure function.

**Tests (`backend/tests/test_tailor.py`):**

- `test_happy_path_suggestions` — mock returns 3 valid suggestions; assert 3 rows, `status="pending"`, `cv_version` is 64-char hex.
- `test_max_6_enforced` — mock returns 8; assert only 6 persisted.
- `test_cv_version_is_sha256_of_markdown` — compute expected hash manually; assert match.
- `test_hebrew_jd_passes_through` — Hebrew JD; assert Claude call receives it unmodified.
- `test_api_error_raises_tailor_error` — mock raises `anthropic.APIError`; assert `TailorError` raised.
- `test_malformed_response_raises` — partial `SuggestionInput` (missing `rationale`); assert `TailorError` raised.
- `test_regenerate_replaces_pending_keeps_approved` — seed 2 pending + 1 approved; call again; assert 2 pending replaced, approved preserved.
- `test_cv_version_mismatch_detection` — seed suggestions with old `cv_version`; update profile; assert `cv_version_for_profile(new_profile) != suggestion.cv_version`.

**What this PR enables:** Phase 6 (Tailor router, suggestion CRUD, tailored CV export).

---

## Phase 6 — Tailor & Suggestion Endpoints + Tailored CV Export

**PR title:** `feat: tailor router — POST /tailor, GET/PATCH suggestions, GET /tailored-cv`

**Files to create/modify:**

```
backend/
├── app/
│   └── routers/
│       ├── jobs.py          (modify — add tailor and tailored-cv endpoints)
│       └── suggestions.py   (create)
│   └── main.py              (modify — register suggestions router)
├── tests/
│   └── test_tailor_router.py (create)
```

**Implementation steps:**

1. Add to `backend/app/routers/jobs.py`:

   `POST /jobs/{id}/tailor`:
   - 404 if job or profile missing.
   - Call `generate_suggestions()`; on `TailorError` return 502.
   - Return suggestion list.

   `GET /jobs/{id}/tailored-cv`:
   - 409 if no approved suggestions.
   - Assemble markdown via `assemble_tailored_cv()`.
   - Add `X-CV-Version-Warning` header if any suggestion's `cv_version` differs from current.
   - Return `text/markdown` attachment.

2. `backend/app/routers/suggestions.py`:

   `GET /jobs/{id}/suggestions`:
   - Return `{"suggestions": [...], "cv_version_current": cv_version_for_profile(profile)}`.

   `PATCH /suggestions/{id}`:
   - Accept `{ status: "approved" | "rejected" }`.
   - 409 if suggestion already `approved` or `rejected` (transitions are final).
   - 422 on invalid status value.

**Tests (`backend/tests/test_tailor_router.py`):**

- `test_post_tailor_happy_path` — mock `generate_suggestions`; POST /jobs/{id}/tailor → 200, suggestion list.
- `test_post_tailor_404_no_job` — → 404.
- `test_post_tailor_404_no_profile` — job exists, no profile → 404.
- `test_post_tailor_502_on_ai_error` — mock raises `TailorError` → 502.
- `test_get_suggestions_empty` — GET /jobs/{id}/suggestions → empty list.
- `test_get_suggestions_returns_all` — seed 3 suggestions; GET → list of 3.
- `test_patch_suggestion_approve` — PATCH `{status: "approved"}` → 200.
- `test_patch_suggestion_reject` — PATCH `{status: "rejected"}` → 200.
- `test_patch_suggestion_invalid_status` — PATCH `{status: "maybe"}` → 422.
- `test_patch_suggestion_transition_final` — approve then attempt reject → 409.
- `test_tailored_cv_happy_path` — 1 approved suggestion; GET tailored-cv → 200, `text/markdown`, attachment header, body contains `suggested` text.
- `test_tailored_cv_409_no_approved` — 2 pending suggestions; GET tailored-cv → 409.
- `test_tailored_cv_cv_version_mismatch_header` — old `cv_version` on suggestion; updated profile; GET → 200 + `X-CV-Version-Warning` header.
- `test_tailored_cv_unmatched_suggestion` — approved suggestion's `original` not in CV; GET → 200, `## Unmatched Suggestions` section present.

**What this PR enables:** Complete end-to-end Matcher + Tailor backend.

---

## Summary Table

| Phase | PR Title | Blocked By |
|---|---|---|
| 1 | Backend skeleton — DB, models, app | Nothing |
| 2 | UserProfile endpoints + seed fixtures | Phase 1 |
| 3 | Matcher service — scoring, retry, validation | Phase 2 |
| 4 | Jobs router — GET/PATCH + retry-score endpoint | Phase 3 |
| 5 | Tailor service — CV diff, suggestions, cv_version | Phase 2 |
| 6 | Tailor router — POST /tailor, CRUD suggestions, export | Phase 4 + Phase 5 |

Phases 3 and 5 can be developed in parallel once Phase 2 is merged.

---

## Cross-Cutting Notes

**Prompt loading pattern** — load at module import time (not per-request):
```python
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")
```

**Anthropic SDK mock pattern** — single injection point:
```python
@pytest.fixture
def mock_anthropic(mocker):
    mock = mocker.patch("backend.app.services.matcher.anthropic_client.messages.create",
                        new_callable=AsyncMock)
    return mock
```

**Tool use enforcement** — always use `tool_choice={"type": "tool", "name": "<tool_name>"}` to force structured output and eliminate plain-text responses.
