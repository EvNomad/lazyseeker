# LazySeeker — React Frontend Implementation Plan

**Date:** 2026-03-09

---

## Overview

The frontend is a greenfield React 18 + TypeScript + Vite + Tailwind + shadcn/ui application. The backend does not exist yet, so all phases must be buildable against mocked API responses. Each phase is a standalone PR.

| Phase | PR Title | Core Deliverable |
|---|---|---|
| 1 | `feat: frontend scaffold` | Vite project, toolchain, routing skeleton |
| 2 | `feat: typed API client and data mocks` | All interfaces, full API client, MSW mocks |
| 3 | `feat: Job Feed view` | Sortable/filterable list with score badges |
| 4 | `feat: Job Detail panel and Suggestions view` | Detail drawer, score bars, suggestion diff UI |
| 5 | `feat: Radar Status and Profile Editor views` | Radar panel and CV/preferences editor |
| 6 | `feat: Docker setup and CI integration` | Dockerfile, docker-compose update, GitHub Actions |

---

## Phase 1 — Frontend Scaffold

**PR title:** `feat: frontend scaffold — Vite + React 18 + TypeScript strict + Tailwind + shadcn/ui`

**Description:** Bootstrap the entire frontend toolchain with zero features. Establishes the file structure, dev server, build pipeline, linting, and a working app shell with client-side routing.

### Files to create

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── tailwind.config.ts
├── postcss.config.js
├── components.json               # shadcn/ui config
├── .env.example                  # VITE_API_BASE_URL=http://localhost:8000
├── .eslintrc.cjs
├── package.json
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css                 # Tailwind directives
    ├── lib/
    │   └── utils.ts              # shadcn/ui cn() helper
    ├── components/
    │   └── layout/
    │       ├── AppShell.tsx      # sidebar nav + main content slot
    │       └── NavLink.tsx       # active-state nav item
    └── views/
        ├── JobFeedView.tsx       # placeholder
        ├── JobDetailView.tsx     # placeholder
        ├── SuggestionsView.tsx   # placeholder
        ├── RadarView.tsx         # placeholder
        └── ProfileView.tsx       # placeholder
```

### Implementation steps

1. Initialise: `npm create vite@latest frontend -- --template react-ts`
2. Install: `tailwindcss postcss autoprefixer`, `@radix-ui/react-*` primitives, `class-variance-authority clsx tailwind-merge`, `lucide-react`, `react-router-dom`
3. `tsconfig.json`: `"strict": true`, `"baseUrl": "."`, path alias `"@/*": ["src/*"]`
4. `vite.config.ts`: path alias `@` → `src/`, proxy `/api` to `VITE_API_BASE_URL`
5. `tailwind.config.ts`: content glob covers `src/**/*.{ts,tsx}`; include shadcn/ui CSS variables in theme
6. Run `npx shadcn-ui@latest init` to generate `components.json` and base component stubs
7. `AppShell.tsx`: fixed left sidebar with nav items (Job Feed, Radar, Profile), right content area using `<Outlet />`
8. Routes in `App.tsx`:
   - `/` → `JobFeedView`
   - `/radar` → `RadarView`
   - `/profile` → `ProfileView`
   - `/jobs/:id` → `JobDetailView` (nested route so URL is shareable)
   - `/jobs/:id/suggestions` → `SuggestionsView`
9. Each view placeholder renders a `<h1>` with the view name
10. ESLint: `eslint-plugin-react`, `eslint-plugin-react-hooks`, `@typescript-eslint/eslint-plugin`, no `any` rule as error

### What to verify

- `npm run dev` starts; hot reload works
- All 5 routes render their placeholder heading
- `npm run build` produces `dist/` without TypeScript errors
- `npm run lint` passes with zero warnings
- No `any` types present

### What this PR enables

Unblocks all subsequent phases. Gives reviewers confidence the toolchain is sound before any real UI lands. Phase 6 (Docker/CI) can be opened as a draft PR immediately after this.

---

## Phase 2 — Typed API Client and Data Mocks

**PR title:** `feat: typed API client and MSW mocks for all endpoints`

**Description:** Implement all TypeScript interfaces from the contract, the full typed `fetch`-based API client, and Mock Service Worker fixtures so every view can be built and tested without a running backend.

### Files to create

```
frontend/src/
├── types/
│   └── index.ts               # All TypeScript interfaces from contracts
├── api/
│   ├── client.ts              # Base fetch wrapper (base URL, error handling)
│   ├── jobs.ts                # Job-related API calls
│   ├── suggestions.ts         # Suggestion-related API calls
│   ├── radar.ts               # Radar API calls
│   └── profile.ts             # Profile API calls
├── mocks/
│   ├── browser.ts             # MSW browser worker setup
│   ├── handlers/
│   │   ├── jobs.ts
│   │   ├── suggestions.ts
│   │   ├── radar.ts
│   │   └── profile.ts
│   └── fixtures/
│       ├── jobs.ts            # 8–10 JobPosting objects (varied scores/statuses/languages)
│       ├── suggestions.ts     # 4–5 suggestions (pending/approved/rejected mix)
│       ├── radar.ts           # 5 CrawlLogEntry objects (success + error)
│       └── profile.ts         # 1 UserProfile with multi-section markdown CV
└── lib/
    └── cv-hash.ts             # SHA256 via Web Crypto API for cv_version comparison
```

### Implementation steps

1. Install MSW: `npm install --save-dev msw`; run `npx msw init public/ --save`
2. Define all interfaces in `src/types/index.ts` verbatim from `docs/contracts/README.md`:
   - `JobPosting`, `ScoreBreakdown`, `Suggestion`, `UserProfile`, `CrawlLogEntry`, `Company`
3. `src/api/client.ts`:
   - `API_BASE` from `import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'`
   - `apiFetch<T>(path: string, options?: RequestInit): Promise<T>` — typed base wrapper
   - On non-2xx: parse `{ "detail": string }` body and throw typed `ApiError` class
   - Include `Content-Type: application/json` on mutating requests
4. `src/api/jobs.ts`:
   - `getJobs(params?: { min_score?: number; status?: string; language?: string; company_id?: string }): Promise<JobPosting[]>`
   - `getJob(id: string): Promise<JobPosting & { company: Company }>`
   - `patchJobStatus(id: string, application_status: JobPosting['application_status']): Promise<JobPosting>`
   - `postTailor(id: string): Promise<Suggestion[]>`
   - `postRetryScore(id: string): Promise<{ score_status: 'pending' }>`
5. `src/api/suggestions.ts`:
   - `getSuggestions(jobId: string): Promise<Suggestion[]>`
   - `patchSuggestion(id: string, status: 'approved' | 'rejected'): Promise<Suggestion>`
   - `getTailoredCv(jobId: string): Promise<Blob>`
6. `src/api/radar.ts`: `postRadarRun()`, `getRadarLog()`
7. `src/api/profile.ts`: `getProfile()`, `putProfile(body)`
8. `src/lib/cv-hash.ts`: `async function sha256(text: string): Promise<string>` using `crypto.subtle.digest`
9. MSW fixtures with realistic variety:
   - `jobs.ts`: cover all `score_status` values, all `application_status` values, both languages, one with `repost_of` set, one with `low_signal_jd: true`, one with `overall_score < 60`, one with `overall_score >= 80`
   - `suggestions.ts`: mix of `pending`/`approved`/`rejected` for one job
   - `radar.ts`: mix of `success` and `error` entries
10. Wire MSW in `src/main.tsx` (dev mode only)

### What to verify

- TypeScript strict compilation passes with all interfaces in use
- All API calls in Network panel go through `src/api/` functions — no inline `fetch`
- MSW intercepts requests in dev mode
- `getTailoredCv` returns a `Blob`; download trigger does not throw
- `sha256` produces a consistent 64-character hex string
- `ApiError` is thrown for mocked 4xx/5xx responses

### What this PR enables

Every subsequent view can be developed and tested without a running backend. Type system prevents interface drift. Mock fixtures provide repeatable states for all badge color rules and mismatch warnings.

---

## Phase 3 — Job Feed View

**PR title:** `feat: Job Feed view — sortable list, filters, score badges, flags`

**Description:** The main view. A filterable, sortable list of job postings with correct score badge color rules, flag chips, repost labels, and selection mechanism.

### Files to create / modify

```
frontend/src/
├── components/
│   ├── ui/
│   │   ├── badge.tsx
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   └── separator.tsx
│   ├── jobs/
│   │   ├── ScoreBadge.tsx            # All color/status badge rules
│   │   ├── JobCard.tsx               # Single row in the feed
│   │   ├── JobFeedFilters.tsx        # Filter bar
│   │   └── FlagChip.tsx              # Small chip for flag strings
├── hooks/
│   └── useJobs.ts                    # Data fetching + filter state
└── views/
    └── JobFeedView.tsx               # Replace placeholder
```

### Implementation steps

1. `npx shadcn-ui@latest add badge button input select separator scroll-area`
2. `ScoreBadge.tsx` — implement all badge rules from `docs/contracts/README.md §6` exactly:
   - `score_status = "pending"` → grey "Awaiting score"
   - `score_status = "error"` → red "Score error"
   - `overall_score >= 80` → green badge with score
   - `overall_score` 60–79 → yellow badge with score
   - `overall_score < 60` → red badge with score
   - `low_signal_jd = true` → additional amber "Low signal JD" badge alongside
   - Use `class-variance-authority` variants for color logic
3. `FlagChip.tsx`: small rounded chip for a single flag string
4. `JobCard.tsx`:
   - Props: `job: JobPosting`, `isSelected: boolean`, `onSelect: (id: string) => void`
   - Layout: company name (left), title (center-left), score badge (right), flags row, date
   - Show neutral "Repost" badge when `repost_of !== null`
   - Highlight row when `isSelected`; truncate long titles with hover tooltip
5. `JobFeedFilters.tsx`: controlled component with `filters` + `onChange` props. Controls: min score input, Status/Language/Company selects. Company options derived from loaded job list (no separate API call).
6. `useJobs.ts`: filter state, calls `getJobs(filters)`, re-fires on filter change. Default sort: score descending (null scores to bottom).
7. `JobFeedView.tsx`:
   - Renders `JobFeedFilters` + scrollable list of `JobCard`
   - Tracks `selectedJobId`; on selection navigates to `/jobs/:id`
   - Loading skeleton (`shadcn/ui Skeleton`) while `loading = true`
   - Empty state and error banner

### What to verify

- All 6 score badge color rules correct against fixtures (visual check)
- Repost label only on the fixture job with `repost_of` set
- Low signal JD amber badge alongside the score badge for the relevant fixture
- All 4 filters narrow the list correctly
- Selecting a card navigates to `/jobs/:id` without full page reload

### What this PR enables

Primary surface of the app is usable and reviewable. Confirms badge color contract is correctly implemented.

---

## Phase 4 — Job Detail Panel and Suggestions View

**PR title:** `feat: Job Detail panel, score dimension bars, Suggestions diff view`

**Description:** The two most complex views: a detail drawer with per-dimension score bars and action buttons, and the side-by-side suggestion diff UI with approve/reject controls, cv_version mismatch warning, and the export button.

### Files to create / modify

```
frontend/src/
├── components/
│   ├── ui/
│   │   ├── dialog.tsx
│   │   ├── progress.tsx
│   │   ├── textarea.tsx
│   │   └── alert.tsx
│   ├── jobs/
│   │   ├── ScoreDimensionBar.tsx         # Single dimension: label, bar, reasoning
│   │   ├── ScoreBreakdownPanel.tsx       # All 4 dimensions + summary + flags
│   │   ├── ApplicationStatusSelect.tsx   # Dropdown → PATCH /jobs/:id/status
│   │   └── RepostBanner.tsx              # Amber banner for repost_of
│   └── suggestions/
│       ├── SuggestionDiffCard.tsx        # Side-by-side diff + rationale + buttons
│       ├── CvVersionWarningBanner.tsx    # Amber mismatch warning
│       └── ExportCvButton.tsx            # Disabled until ≥1 approved
├── hooks/
│   ├── useJob.ts
│   └── useSuggestions.ts
└── views/
    ├── JobDetailView.tsx                 # Replace placeholder
    └── SuggestionsView.tsx              # Replace placeholder
```

### Implementation steps

**Job Detail:**

1. `npx shadcn-ui@latest add dialog progress textarea alert`
2. `useJob.ts`: calls `getJob(jobId)`, returns `{ job, loading, error, refetch }`
3. `ScoreDimensionBar.tsx`: dimension name, `Progress` bar (0–100), reasoning text. Bar color matches score thresholds.
4. `ScoreBreakdownPanel.tsx`: all 4 `ScoreDimensionBar` instances, summary text, flag chips, "Low signal JD" notice. Renders nothing when `score_breakdown` is null.
5. `ApplicationStatusSelect.tsx`: calls `patchJobStatus` on change; shows loading state; reverts and shows toast on error.
6. `RepostBanner.tsx`: amber banner shown only when `job.repost_of !== null`.
7. `JobDetailView.tsx`:
   - Uses `useJob(id)` from `useParams()`
   - Layout: header (title, company, date, source link, repost banner), `ScoreBreakdownPanel`, full JD text (in `dir="auto"` container for Hebrew), action bar
   - Action bar: `ApplicationStatusSelect`, "Generate CV Suggestions" button (calls `postTailor` then navigates to `/jobs/:id/suggestions`, shows spinner), "Retry Scoring" button (shown only when `score_status === 'pending' | 'error'`, calls `postRetryScore` then `refetch`, shows "Scoring queued" message), "View original posting" link

**Suggestions:**

8. `useSuggestions.ts`: calls `getSuggestions(jobId)`, exposes `approveSuggestion(id)` and `rejectSuggestion(id)` with optimistic local state updates.
9. `CvVersionWarningBanner.tsx`:
   - Fetches current profile; computes `sha256(currentCvMarkdown)` asynchronously
   - Shows amber banner if any `suggestion.cv_version !== sha256(currentCvMarkdown)`
   - Message: "Your CV has changed since these suggestions were generated. Consider regenerating."
10. `SuggestionDiffCard.tsx`:
    - Two-column grid: original (left, red tint) / suggested (right, green tint); rationale below
    - Approve (green outline) and Reject (red outline) buttons
    - `status === 'approved'`: show "Approved" chip, show only Reject; `status === 'rejected'`: show "Rejected" chip, show only Approve
    - Preserve whitespace in both text columns
11. `ExportCvButton.tsx`:
    - Props: `jobId: string`, `hasApproved: boolean`
    - `hasApproved = false`: renders `<Button disabled>Export Tailored CV</Button>` — disabled, NOT hidden
    - `hasApproved = true`: calls `getTailoredCv(jobId)`, triggers download via `URL.createObjectURL(blob)`; shows spinner during request; shows toast on 409
12. `SuggestionsView.tsx`: `CvVersionWarningBanner` at top, list of `SuggestionDiffCard`, `ExportCvButton` at bottom

### What to verify

- Score dimension bars have correct colors at 80, 75, 55 (boundary checks)
- `ApplicationStatusSelect` shows loading and reverts on error
- "Retry Scoring" button visible only for `pending` and `error` fixtures
- Side-by-side layout on desktop (≥1024px viewport)
- cv_version mismatch warning appears when fixture `cv_version` doesn't match hashed current CV
- No warning when versions match
- Export button is `disabled` (attribute check) when no suggestion is approved; enabled after one approval
- Optimistic approve/reject updates the card without a full refetch
- File download triggers against the mock handler
- Hebrew text in `description` renders in `dir="auto"` container

### What this PR enables

Core user workflow is complete end-to-end: view jobs → inspect scores → trigger suggestions → approve → export tailored CV. This is the highest-value PR in the project.

---

## Phase 5 — Radar Status View and Profile Editor

**PR title:** `feat: Radar Status view and Profile Editor`

**Description:** The two supporting views: a live radar status table with per-company crawl health and a manual trigger, plus a markdown editor for the CV and preferences textarea.

### Files to create / modify

```
frontend/src/
├── components/
│   ├── ui/
│   │   └── table.tsx
│   ├── radar/
│   │   ├── CrawlStatusTable.tsx     # Per-company: last run, new postings, status badge
│   │   ├── CrawlErrorLog.tsx        # Scrollable log of error entries
│   │   └── RunNowButton.tsx         # POST /radar/run with loading state
│   └── profile/
│       ├── CvEditor.tsx             # Monospace textarea with char count
│       └── PreferencesEditor.tsx    # Plain textarea
├── hooks/
│   ├── useRadarLog.ts               # Fetch + group by company_id
│   └── useProfile.ts                # Fetch + save
└── views/
    ├── RadarView.tsx                # Replace placeholder
    └── ProfileView.tsx              # Replace placeholder
```

### Implementation steps

**Radar Status:**

1. `npx shadcn-ui@latest add table`
2. `useRadarLog.ts`: calls `getRadarLog()`, groups by `company_id` (most recent entry per company for status table, all entries for error log). Returns `{ companies, allLogs, loading, error, refetch }`.
3. `CrawlStatusTable.tsx`: columns: Company, Last Run (relative time), New Postings, Status (green "OK" / red "Error" badge). Click error row scrolls to the company's entry in the error log.
4. `CrawlErrorLog.tsx`: filtered to `status === 'error'`; shows company name, timestamp, `error_message`. Empty state: "No errors".
5. `RunNowButton.tsx`: calls `postRadarRun()`; shows "Running..." with spinner; on success shows "Crawl started" and calls `refetch()` after 3 seconds.
6. `RadarView.tsx`: `RunNowButton` + `CrawlStatusTable` + `CrawlErrorLog`. Auto-refreshes log every 30 seconds via `setInterval` in `useEffect`.

**Profile Editor:**

7. `useProfile.ts`: calls `getProfile()` on mount; exposes `save(body)` calling `putProfile`. Returns `{ profile, loading, saving, error, save }`.
8. `CvEditor.tsx`: monospace `<textarea>` for markdown; character count below.
9. `PreferencesEditor.tsx`: plain `<textarea>` with placeholder.
10. `ProfileView.tsx`: controlled form with local `cvMarkdown` and `preferences` state. "Save" button calls `save()`; shows "Saved" confirmation for 2 seconds. "Unsaved changes" indicator when local state differs from loaded profile.

### What to verify

- Radar table renders one row per unique company in fixtures
- "Run Now" shows spinner and disables itself during request
- Error log empty when all fixture entries are success; populates for error entries
- Profile textarea initialized with fixture CV content
- "Unsaved changes" appears after editing
- Save button calls `putProfile` with current field values
- "Saved" confirmation appears and disappears after 2 seconds

### What this PR enables

All 5 views complete. App is feature-complete for v1. Backend team can integrate the real API against a fully-functional frontend.

---

## Phase 6 — Docker Setup and CI Integration

**PR title:** `feat: Docker setup for frontend and GitHub Actions CI`

**Description:** Adds a production Dockerfile for the frontend, integrates it into `docker-compose.yml`, and adds GitHub Actions for lint and build validation.

### Files to create / modify

```
frontend/
├── Dockerfile
└── nginx.conf

docker-compose.yml                   # Root-level (create or extend)

.github/
└── workflows/
    └── ci.yml
```

### Implementation steps

1. **`frontend/Dockerfile`** — multi-stage build:
   - Stage 1 (`builder`): `node:20-alpine`, `npm ci`, `npm run build`
   - Stage 2 (`runner`): `nginx:alpine`, copy `dist/` to `/usr/share/nginx/html/`; copy `nginx.conf`
   - Expose port 80
   - Build arg `VITE_API_BASE_URL` baked into bundle at build time

2. **`frontend/nginx.conf`**: `try_files $uri $uri/ /index.html;` for SPA routing; `gzip on`.

3. **`docker-compose.yml`**:
   ```yaml
   services:
     frontend:
       build:
         context: ./frontend
         args:
           VITE_API_BASE_URL: http://backend:8000
       ports:
         - "3000:80"
       depends_on:
         - backend
     backend:
       build: ./backend
       ports:
         - "8000:8000"
   ```
   If the backend team has already created this file, add only the `frontend` service block.

4. **`.github/workflows/ci.yml`**:
   - Triggers: `push` and `pull_request` on `main`
   - Jobs (parallel where possible):
     - `frontend-lint`: `npm ci`, `npm run lint`
     - `frontend-build`: `npm ci`, `npm run build` (depends on lint)
     - `frontend-test`: `npm ci`, `npm run test` (Vitest)

5. **Vitest + component tests**:
   - Install: `vitest @testing-library/react @testing-library/jest-dom jsdom`
   - Add `test` script to `package.json`: `vitest run`
   - `ScoreBadge.test.tsx`: test all 6 badge conditions from the contracts table
   - `SuggestionDiffCard.test.tsx`: test approve/reject button states and side-by-side layout presence

### What to verify

- `docker build -t lazyseeker-frontend frontend/` succeeds
- `docker run -p 3000:80 lazyseeker-frontend` serves app at `http://localhost:3000`
- Client-side routing works from nginx: `/radar` returns 200 (not 404)
- `docker compose up` starts both services
- `ScoreBadge.test.tsx` passes for all 6 conditions
- `SuggestionDiffCard.test.tsx` verifies Approve button disabled after approval

### What this PR enables

Application is fully containerised and continuously validated on every push. `docker compose up` gives a complete local environment to both teams.

---

## Cross-Cutting Notes

### RTL / Hebrew text
All `description` and `requirements` fields rendered inside `dir="auto"` — browser applies RTL automatically for Hebrew content without UI chrome changes.

### No state management library
Use `useState` and `useContext` only. Context is appropriate for: loaded `UserProfile` (needed by cv_version check without prop-drilling) and selected job ID if shared between feed and a panel.

### Async scoring feedback
After `POST /jobs/:id/retry-score`, show "Scoring queued — check back shortly" and re-fetch the job after a 5-second delay. Do not implement full polling in v1.

### Export fallback
If `getTailoredCv` fails (non-409), show a toast: "Export failed — try again". The markdown fallback is handled by the backend returning markdown as the response body.

---

## Dependency Graph

```
Phase 1 (scaffold)
    └── Phase 2 (API client + mocks)
            ├── Phase 3 (Job Feed)
            │       └── Phase 4 (Job Detail + Suggestions)
            └── Phase 5 (Radar + Profile)
    └── Phase 6 (Docker + CI) — draft PR can open after Phase 1
```

Phase 6 can be opened as a draft PR immediately after Phase 1 since it only depends on `package.json` scripts and build output.
