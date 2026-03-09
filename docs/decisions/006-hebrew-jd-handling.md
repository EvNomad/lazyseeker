# ADR 006 — Hebrew JD Handling in Tailor Prompt

**Date:** 2026-03-09
**Status:** Accepted

## Context
Some JDs are Hebrew-dominant or fully Hebrew. Options: (a) pre-translate to English before sending to Claude, (b) pass bilingual content directly.

## Decision
Pass bilingual content directly to Claude. Instruct Claude in the system prompt to always respond in English regardless of JD language.

## Rationale
- Claude Sonnet handles Hebrew well natively
- Pre-translation adds latency, an extra API call, and potential loss of nuance
- Consistent with Matcher behavior (already passes Hebrew JDs as-is)
- Simpler code path — no translation layer to maintain

## Consequences
- Matcher and Tailor system prompts must include: "The job description may be in Hebrew or a mix of Hebrew and English. Always respond in English."
- The `language` field on `JobPosting` (en / he / mixed) is still detected and stored — useful for UI filtering and user awareness
- No translation service dependency in v1
