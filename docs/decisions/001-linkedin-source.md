# ADR 001 — LinkedIn Source: RapidAPI Wrapper

**Date:** 2026-03-09
**Status:** Accepted

## Context
LinkedIn's ToS prohibits unauthorized scraping. Options were: (a) RapidAPI wrapper, (b) official OAuth integration, (c) skip LinkedIn entirely.

## Decision
Use a RapidAPI LinkedIn wrapper in v1.

## Rationale
- This is a personal tool; risk of ToS enforcement is low and accepted by the sole user
- Official OAuth requires app review and is disproportionate for personal use
- Makes LinkedIn a first-class source without the complexity of OAuth flows

## Consequences
- LinkedIn source must be easily disableable per-company via `companies.yaml` (set `linkedin_slug: null` or `active: false`)
- If RapidAPI wrapper becomes unavailable or rate-limited, the LinkedIn source degrades gracefully — career page crawling continues unaffected
- Revisit OAuth integration if the tool ever becomes multi-user (v2+)
