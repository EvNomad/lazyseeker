# ADR 003 — CV Versioning Strategy

**Date:** 2026-03-09
**Status:** Accepted

## Context
If the user updates their master CV after suggestions have been generated, those suggestions may reference outdated content.

## Decision
- Store a `cv_version` field (SHA256 hash of `UserProfile.cv_markdown`) on each `Suggestion` row at creation time
- When the UI loads suggestions, compare the stored hash against the current CV hash
- If they differ, show a warning: "Your CV has changed since these suggestions were generated" with an option to regenerate

## Rationale
Full version history (storing past CV snapshots) is unnecessary complexity for v1. A hash is sufficient to detect staleness and prompt the user.

## Consequences
- `Suggestion` model gains a `cv_version: str` field (non-nullable)
- `UserProfile` does not change — the hash is computed from `cv_markdown` on the fly
- Regenerating suggestions replaces all `pending` suggestions for the job; `approved`/`rejected` ones are preserved (or the user is warned)
- Full CV history deferred to v2
