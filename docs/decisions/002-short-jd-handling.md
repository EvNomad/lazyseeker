# ADR 002 — Short/Vague JD Handling

**Date:** 2026-03-09
**Status:** Accepted

## Context
JDs under ~100 words lack sufficient signal for reliable semantic scoring.

## Decision
- Add `low_signal_jd: bool` to the score JSON output schema
- Cap `overall_score` at 70 when `low_signal_jd` is true
- Show a "Low signal — JD is vague" badge in the dashboard job list and detail panel

## Rationale
Returning a high score on a vague JD would be misleading. Capping at 70 and flagging ensures the user knows the score is unreliable without hiding the posting.

## Consequences
- Matcher system prompt must instruct Claude to set `low_signal_jd: true` when the JD provides insufficient detail
- Score schema and `JobPosting.score_breakdown` JSON must include this field
- Dashboard must render the badge when the flag is present
