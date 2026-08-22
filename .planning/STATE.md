---
gsd_state_version: '1.0'
status: planning
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-22)

**Core value:** Sign in from the couch with a remote, and play a file from OneDrive.
**Current focus:** Phase 1 — Vendor Lift

## Current Position

Phase: 1 of 8 (Vendor Lift)
Plan: 0 of 0 in current phase
Status: Ready to plan
Last activity: 2026-08-22 — Project initialized: research, requirements and roadmap complete

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Reconciled research positions live in `.planning/research/SUMMARY.md` under "Reconciled Conflicts" and "Corrected Premises" — treat both as decided, not as suggestions.

Load-bearing choices for current work:

- Device code flow with an embedded public `client_id`; no broker server, no client secret, ever
- Scope set is `Files.Read offline_access openid profile` — never `Files.Read.All`
- Vendor from the `matrix` branch (v1.4.0); `master` is 1.3.9, the Python 2 line
- Vendoring lands first and alone, so a regression can be attributed
- Token-refresh lock uses `os.open(..., O_CREAT|O_EXCL)` — the plugin and service are sub-interpreters in one process, so `threading.Lock` is not shared and `fcntl.lockf` does not exclude them
- `SourceService` and the port 8586 directory listing are deleted, not defaulted off
- The loopback 302 redirector is playback infrastructure, not a deferrable download service
- InfoTag migration is deferred behind auth and playback, but must land in the same commit as the integer-duration fix

### Pending Todos

None yet.

### Blockers/Concerns

- **Azure app registration is a maintainer prerequisite blocking Phase 3.** SETUP-01 through SETUP-04 are portal work, not code. `allowPublicClient` left at its `false` default returns `AADSTS7000218`, an error that actively misdirects toward embedding a client secret. Phases 1 and 2 run in parallel and are not blocked by this.
- **The project's load-bearing unknown:** whether this project's own (non-first-party) `client_id` behaves on the `/common` authority for both a personal and a work account. The live probes during research used a Microsoft first-party client. Everything downstream inherits the answer. Tested first in Phase 3.
- **A Business account and real Android TV hardware are required for release**, not optional. A Personal-only, desktop-only pass cannot find the reserved-character, consent, or performance classes of bug.
- **Existing users cannot be carried across.** Refresh tokens are bound to a `client_id`; the old ones belong to the broker's registration. Phase 8 makes the re-auth proactive and explained rather than avoidable.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Restored features | Resume/watched sync, STRM export (video only), slideshow, delta sync | v2 | 2026-08-22 |
| Browsing | Server-side `$orderby` | v2 | 2026-08-22 |
| Accounts | SharePoint document libraries as a tested target | v2 | 2026-08-22 |

## Session Continuity

Last session: 2026-08-22
Stopped at: Roadmap created and committed; 94 of 94 v1 requirements mapped across 8 phases
Resume file: None
