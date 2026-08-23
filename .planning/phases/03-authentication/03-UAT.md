---
status: testing
phase: 03-authentication
source: [03-VERIFICATION.md, 03-14-SUMMARY.md]
started: 2026-08-23
updated: 2026-08-23
---

# Phase 3 — outstanding human verification

Phase 3's automated work is finished: 14 plans, 260 tests passing, zero failing. What is
outstanding is **observation, not implementation** — the phase-3 verification found no missing
artefact, no stub and no unwired link.

Four rows of ROADMAP success criterion 6 have never been run. They are the rows the Android 11
emulator used in Phase 1 could not answer, which is the whole reason criterion 6 exists.

All four are run on the TCL Android TV 12 (Android 12, Kodi 21.2, stock Estuary). None needs a
code change.

Deferred by decision on 2026-08-23: run these after the hosted repository lands, so that each
attempt does not cost a USB round trip. See `deferred-items.md` for the install-route finding.

## Current Test

number: 1
name: The background service starts at login
expected: |
  Kodi starts the add-on's background service at login, and the startup keepalive runs once.
awaiting: user response

## Tests

### 1. The background service starts at login

expected: The service is running after Kodi starts. This is the row that carries the others:
"no dialog appeared over the home screen at boot" was already observed and recorded as PASS, but
it is a *negative* observation, and a service that never started produces exactly the same
screen. Until this row has a reading, AUTH-17's evidence rests on 03-10's code proof alone.
result: [pending]

### 2. All three dialogs open and render from the add-on's own skin directory

expected: The code dialog and the two export dialogs each open through the temporary dialog
affordance and render from `resources/skins/default/`, not from a Kodi or vendored fallback.
If a dialog does not appear in the action mapping at all, plan 03-09's routing change dropped
it and this checklist row is disarmed rather than passing.
result: [pending]

### 3. Two openings of the code dialog write two different image paths

expected: Opening the sign-in dialog twice produces two different QR image paths. Plan 01-05
gave the filename a fresh uuid4 per invocation precisely because Kodi's texture cache is keyed
by path: with a fixed name, a second sign-in renders the *previous* code and the user scans a
dead one. The failure is silent and looks like a working dialog.
result: [pending]

### 4. The session log carries no tracebacks

expected: `grep -c Traceback` over the session log returns 0.
note: Pulling an app-private Kodi log on Android 11+ needs the log copied to a public directory
first — recorded in Phase 1 and again in `deferred-items.md`. This is the fiddliest of the four.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

None found. These are unobserved rows, not known defects.

## Not in scope for these tests

Two requirements stay deliberately open and are **not** closed by this file:

- **AUTH-03** — the personal-account half. The spike already acquired a token on a personal
  account with this registration, so what is deferred is a second on-television pass, not a
  design question.
- **AUTH-18** — behaviour against a tenant that genuinely blocks the grant. No tenant available
  to this project blocks it, so no refusal can be produced on demand. Recorded as unverified on
  purpose: a pass claimed here is one nobody would ever go back and check.

One requirement moved rather than closed:

- **AUTH-20** — tokens and delta tokens are isolated per account; **cache keys are not**, and
  `Cache(self._addonid, …)` is still global. That clause belongs to Phase 4, which builds the
  listing cache and is told by the ROADMAP to key it by account from its first commit.

## Two reports found during acceptance, owned by later phases

Neither was investigated and neither has a root cause. Recorded so they are not rediscovered
from scratch:

- **Subtitles from the cloud** appeared once and were then inert. Likely Phase 6 (Play).
  Missing inputs: a session log and a repeatable trigger.
- **Mounting the cloud as a directory inside Kodi** does not work. Likely Phase 4 (Browse).
  Two things to rule out before reading any code: `service/source.py` still exists (its deletion
  is Phase 7, not Phase 1), and Phase 1 changed `allow_directory_listing` to default **false**.
