# ADR 004 — Dedup Strategy for Reposted Roles

**Date:** 2026-03-09
**Status:** Accepted

## Context
A company may close a role and repost it later, often with a different URL. URL-hash dedup alone would treat this as a fresh posting every time.

## Decision
- Primary dedup: URL hash (existing behavior)
- On new crawl: if a posting with the same `title + company` exists with `application_status = "archived"`, create a new `JobPosting` but set `repost_of` (FK → `JobPosting.id`) pointing to the original
- Score the new posting normally (the JD may have changed)
- Do not surface the repost as "new" in the feed if the score is within ±5 points of the original — show a "Repost" badge instead

## Rationale
Avoids noise from repeated reposts while still capturing genuine role changes. The user can still see the repost but won't be misled into thinking it's a different opportunity.

## Consequences
- `JobPosting` gains an optional `repost_of: UUID | null` FK field
- Radar must run the title+company check after URL-hash dedup passes
- Dashboard renders a "Repost" badge when `repost_of` is set
