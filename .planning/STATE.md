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
Last activity: 2026-08-22 — Device code spike passed for both account classes; drive-enumeration requirement corrected

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

- Ships as `plugin.onedrive.kn` — separate add-on, own profile, no migration from v2.3.0
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

**Resolved 2026-08-22 — the load-bearing unknown is settled.** The `/common` authority works with this project's own `client_id` for both a work/school account and a personal Microsoft account, verified end-to-end before any code was written. Conditional Access on the E5 Developer tenant did not block device code flow. Evidence and the full endpoint matrix: `.planning/research/SPIKE-DEVICE-CODE.md`. Registration in use: `efe197b3-5c14-4d67-810f-e10406742a06`, SETUP-01 through SETUP-03 satisfied.

Open concerns:

- **The E5 Developer tenant hosting the `client_id` may not last.** Microsoft 365 Developer tenants renew on activity and the programme has tightened. If that tenant lapses, the embedded `client_id` dies for every installed copy simultaneously — the worst possible failure distribution. Registering under a personal Microsoft account instead would remove the expiry entirely. Decide before the first public release.
- **AUTH-18 cannot be fully verified yet.** No tenant that actually blocks third-party apps has been tested, so the exact `AADSTS` code that should trigger the custom `client_id` escape hatch is still unknown. The escape hatch is worthless if the user is never told it exists.
- **Real Android TV hardware is required for release**, not optional. Nothing about a 10-foot interface is verifiable from a desktop.
- **No migration path exists, by design.** The add-on ships under a new id (`plugin.onedrive.kn`) so there is no prior profile to read, and tokens could not have been carried over anyway. Anyone coming from v2.3.0 simply signs in.
- **Graph fixtures must be recorded from both drive classes.** The spike found real material worth capturing: Vietnamese names with diacritics and spaces on both drives, and the OneDrive Personal Vault, which Graph returns without a `folder` facet so naive detection renders it as a file (BROWSE-16).

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Restored features | Resume/watched sync, STRM export (video only), slideshow, delta sync | v2 | 2026-08-22 |
| Browsing | Server-side `$orderby` | v2 | 2026-08-22 |
| Accounts | SharePoint document libraries as a tested target | v2 | 2026-08-22 |

## Session Continuity

Last session: 2026-08-22
Stopped at: Migration phase dropped; 94 of 94 v1 requirements mapped across 8 phases
Resume file: None
