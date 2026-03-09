# ADR 007 — Behavior When Anthropic API Is Unavailable

**Date:** 2026-03-09
**Status:** Accepted

## Context
If the Anthropic API is down or rate-limited, newly crawled postings cannot be scored. Should they be hidden or shown?

## Decision
- Always surface postings in the feed regardless of score status
- Unscored postings show `score_status = "pending"` with an "Awaiting score" badge
- Add a "Retry scoring" button on the job detail panel to manually re-trigger scoring for a single posting
- Retry logic: attempt once automatically on crawl; if it fails, set `score_status = "error"` and wait for manual retry

## Rationale
Hiding unscored jobs risks missing time-sensitive opportunities. The user should always see what was found and decide how to act.

## Consequences
- `score_status` enum: `pending | scored | error` (already in spec)
- Dashboard job list must handle all three states gracefully (no score badge, pending badge, error badge)
- `POST /jobs/{id}/retry-score` endpoint added (or reuse `POST /jobs/{id}/tailor` pattern) for manual retry
- APScheduler can run a periodic "retry pending scores" job as a background sweep
