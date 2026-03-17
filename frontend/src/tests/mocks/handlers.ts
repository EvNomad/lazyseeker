import { http, HttpResponse } from "msw";
import type { JobPosting, UserProfile, Suggestion } from "../../api/types";

const BASE = "http://localhost:8000";

export const STUB_JOB: JobPosting = {
  id: "job-1",
  url: "https://example.com/jobs/1",
  url_hash: "abc123",
  company_id: "company-1",
  title: "Backend Engineer",
  description: "We are looking for a backend engineer with Python experience.",
  requirements: null,
  language: "en",
  source: "career_page",
  crawled_at: "2026-03-17T10:00:00Z",
  overall_score: 82,
  score_breakdown: JSON.stringify({
    overall_score: 82,
    low_signal_jd: false,
    dimensions: {
      role_fit: { score: 85, reasoning: "Strong match" },
      stack_fit: { score: 80, reasoning: "Python/FastAPI" },
      seniority_fit: { score: 90, reasoning: "Senior level" },
      location_fit: { score: 70, reasoning: "Remote ok" },
    },
    flags: [],
    summary: "Good match. Strong backend. Minor gaps.",
  }),
  score_status: "scored",
  application_status: "new",
  repost_of: null,
};

export const STUB_JOB_PENDING: JobPosting = {
  ...STUB_JOB,
  id: "job-2",
  title: "Frontend Developer",
  overall_score: null,
  score_status: "pending",
};

export const STUB_JOB_LOW: JobPosting = {
  ...STUB_JOB,
  id: "job-3",
  title: "Junior Dev",
  overall_score: 45,
  score_status: "scored",
};

export const STUB_PROFILE: UserProfile = {
  id: "profile-1",
  cv_markdown: "# My CV",
  preferences: "Remote",
  updated_at: "2026-03-17T09:00:00Z",
};

export const STUB_SUGGESTION: Suggestion = {
  id: "suggestion-1",
  job_id: "job-1",
  section: "Experience",
  original: "10 years backend",
  suggested: "10 years backend Python/FastAPI",
  rationale: "JD emphasizes Python",
  status: "pending",
  cv_version: "abc123",
  created_at: "2026-03-17T10:30:00Z",
};

export const handlers = [
  http.get(`${BASE}/jobs`, () => HttpResponse.json([STUB_JOB, STUB_JOB_PENDING, STUB_JOB_LOW])),
  http.get(`${BASE}/jobs/:id`, ({ params }) =>
    HttpResponse.json({ ...STUB_JOB, id: params.id as string, company: null })
  ),
  http.patch(`${BASE}/jobs/:id/status`, () => HttpResponse.json(STUB_JOB)),
  http.post(`${BASE}/jobs/:id/retry-score`, () => HttpResponse.json({ score_status: "pending" })),
  http.post(`${BASE}/jobs/:id/tailor`, () => HttpResponse.json([STUB_SUGGESTION])),
  http.get(`${BASE}/jobs/:id/tailored-cv`, () =>
    new HttpResponse("# Tailored CV\n", { headers: { "Content-Type": "text/markdown" } })
  ),
  http.get(`${BASE}/profile`, () => HttpResponse.json(STUB_PROFILE)),
  http.put(`${BASE}/profile`, () => HttpResponse.json(STUB_PROFILE)),
  http.get(`${BASE}/jobs/:id/suggestions`, () =>
    HttpResponse.json({ suggestions: [STUB_SUGGESTION], cv_version_current: "abc123" })
  ),
  http.patch(`${BASE}/suggestions/:id`, () =>
    HttpResponse.json({ ...STUB_SUGGESTION, status: "approved" })
  ),
  http.post(`${BASE}/radar/run`, () => HttpResponse.json({ started: true })),
  http.get(`${BASE}/radar/log`, () => HttpResponse.json([])),
];
