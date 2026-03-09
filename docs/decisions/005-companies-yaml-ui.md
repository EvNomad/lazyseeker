# ADR 005 — `companies.yaml` Editing: Config-File Only in v1

**Date:** 2026-03-09
**Status:** Accepted

## Context
Should users be able to add/edit companies via the dashboard UI, or is editing `companies.yaml` directly sufficient?

## Decision
Config-file only in v1. No UI CRUD for company management.

## Rationale
- LazySeeker is a single-user personal tool; editing a YAML file is acceptable
- A UI CRUD adds a full router, database migration, and frontend form for minimal gain
- The Radar Status view already shows per-company crawl state — enough visibility without editing

## Consequences
- `companies.yaml` is the source of truth for the company list; loaded at startup
- The Radar service reads from this file (or syncs it to the `Company` table at startup)
- Defer UI company management to v2 if file editing becomes a friction point
