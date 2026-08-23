---
phase: 03-authentication
plan: 13
subsystem: auth
tags: [live-verification, device-code, refresh-rotation, granted-scope, failure-capture, measurement, instrument-error]

requires:
  - phase: 03-authentication
    provides: "Plan 03-03's docs/AZURE-REGISTRATION.md and its acceptance-check section — the document this plan writes the measured values into, and its by-name gate"
  - phase: 03-authentication
    provides: "Plan 03-01's device_code protocol module and atomic store — driven live here rather than against a scripted endpoint"
  - phase: 03-authentication
    provides: "Plan 03-07's refresh.refresh, its lock and its fingerprint redactor — the rotation this plan proves against the real provider"
  - phase: 03-authentication
    provides: "Plan 03-08's CLIENT_ID and the direct sign-in wiring — the identifier the harness takes by default"
  - phase: 03-authentication
    provides: "Plan 03-10's startup keepalive, which shares the lock and store this run exercised"
provides:
  - ".planning/research/live_sign_in.py — a live harness that DRIVES the shipped auth package rather than reimplementing the flow"
  - "live_sign_in.rotation_digest — a whole-token SHA-256 digest that refuses any input already shortened"
  - "live_sign_in PASS / FAIL / INCONCLUSIVE, with exit statuses 0 / 1 / 2"
  - "verify_device_code.capture_failure and report_capture — both failure branches now persist the response they used to discard"
  - ".gitignore rules for device-code-failure-*.json and the live scratch profile"
  - "docs/AZURE-REGISTRATION.md section 6 — the measured granted scope, name claim, drive owner, six expiry readings and three rotation digests, plus what remains unmeasurable"
affects: [03-14, 04]

tech-stack:
  added: []
  patterns:
    - "A live harness supplies only what the package under test refuses to contain — an HTTP port and a place to put the result — so the code being exercised is the code that ships"
    - "A value chosen to REDACT cannot be reused to DISCRIMINATE; the function that discriminates refuses any input that is already shortened, so the substitution cannot be made twice"
    - "A verdict gets a third reading — inconclusive — whenever its input might not separate the two it is deciding between"
    - "An ignore rule for generated evidence lands in the same commit as the code that starts writing it, never later"
    - "A measured absence is recorded as a measurement, not left as a silence that reads as an untested gap"

key-files:
  created:
    - .planning/research/live_sign_in.py
  modified:
    - .planning/research/verify_device_code.py
    - .gitignore
    - docs/AZURE-REGISTRATION.md
    - .planning/REQUIREMENTS.md
    - .planning/phases/03-authentication/deferred-items.md

decisions:
  - "The rotation check digests whole tokens instead of comparing refresh.fingerprint output, and refresh.fingerprint itself is left exactly as shipped — its eight-character contract is deliberate and other callers depend on it"
  - "A granted scope may only ever be tested by membership, never by equality, prefix or position — measured, not inferred"
  - "AUTH-18 stays Pending and is annotated UNVERIFIABLE HERE rather than being marked complete"
  - "AUTH-01 and AUTH-03 stay Pending because 03-14 still declares them; AUTH-03 is annotated as half-done rather than silently left bare"
  - "The personal-account pass through the shipped package is deferred, not dropped"

metrics:
  duration: "~1h including two live grants"
  tasks: 3
  files_changed: 6
  commits: 5
  completed: 2026-08-23

status: complete
---

# Phase 3 Plan 13: Live Sign-In Verification Summary

The shipped auth package acquired and rotated a real token against this project's own registration
with a real work/school account — and the first attempt to measure the rotation was wrong in a way
worth more than the result.

## What was done

Everything in this phase up to here was proven against a fake endpoint. That is the right way to
test the logic and it says nothing about whether this registration, this scope set and this
authority still behave as the spike measured them. This plan closed that gap off the television
first, deliberately: a failure here is a protocol problem, a failure on the television after
passing here is a Kodi problem, and one session that does both gives a failure that could be either.

**Task 1 — the reference implementation keeps what it cannot reproduce** (`a43ae9c`).
`verify_device_code.py` had two failure branches that printed the failing response and returned.
The response class they discarded — a tenant that refuses the grant — is precisely the one this
project cannot produce on demand, and an earlier observed failure was lost exactly that way. Both
branches now write the whole response, unredacted, to a timestamped file beside the script and print
the path. Nothing is redacted because the fields a redactor would strip are the ones that diagnose
it; a collision inside the same second takes a counter, so a second run cannot overwrite the first
run's evidence.

The `.gitignore` rule for `device-code-failure-*.json` landed **in that same commit**, before
anything could write one. That ordering was load-bearing (T-03-59) and no earlier plan added it.
Verified rather than assumed:

```
.gitignore:17:.planning/research/device-code-failure-*.json	.planning/research/device-code-failure-20260101-000000.json
```

**Task 2 — a harness that drives the shipped package** (`8e79e03`, fixed in `a6d7d8b`).
`live_sign_in.py` supplies only the two things `resources/lib/auth/` deliberately refuses to
contain — an HTTP port and somewhere to put the result — and lets the shipped modules do everything
else: `request_device_code`, `poll_once`, `next_interval`, `read_identity_claims`,
`merge_token_response`, `write`, and `refresh.refresh` holding a real `RefreshLock`. A harness that
reimplemented the flow would prove the provider works and prove nothing about what ships (T-03-61).

Real credentials reach disk while it runs, so the scratch profile lives outside the repository, the
harness refuses both an in-repository path and anything shaped like a Kodi profile — it deletes the
account file it writes — and the profile is removed at the end unless asked otherwise (T-03-58).
Both refusals were tested.

**Task 3 — the live grant.** Completed by the maintainer on a phone with a work/school account in
the E5 tenant. Values recorded in `docs/AZURE-REGISTRATION.md` section 6 (`a679701`).

## What was measured

| What | Measured |
|---|---|
| granted scope, verbatim | `openid profile email https://graph.microsoft.com/Files.Read` |
| `name` claim | present — `Kei NAS` |
| `sub` claim | 43 characters, URL-safe base64, filename-safe as issued |
| drive owner `displayName` | `Kei NAS` |
| `driveType` | `business` |
| expiry, run 1 | `[5091, 4919, 4189]` |
| expiry, run 2 | `[4637, 4326, 4211]` |
| rotation digests | `sha256:bf92b757a58b`, `sha256:1b8a11103c33`, `sha256:b0dc7a23cd00` |
| failure codes | none, in either run |

**The granted scope is not the requested scope, twice over.** `email` came back although it was
never requested, and `offline_access` is absent although a refresh token was issued. The ordering
differs too. So a granted scope may only ever be tested by **membership of the scope actually cared
about** — never by equality with the requested string, never by prefix, never by position. Written
the obvious way, such a check passes on the author's account and fails on somebody else's.

**Six expiry readings, all different.** Any constant for this value anywhere in the tree would be
wrong by measurement rather than by taste.

**Rotation proven live.** Three digests over three whole tokens, all different: the provider
rotates on every use and the rotated value reaches disk through `store.write`. The automated test
from 03-07 proves the code keeps what it is given; this proves the provider gives something new.

**D-01 closes in the good direction, and the branch is still untested.** The `name` claim is
present, so the label path ran and the fallback to the drive owner's display name was never
exercised. The fallback does have a real source on this account and the two agree, which settles the
design question the spike left open. It does not test the branch, and the runbook says so.

**Two measured absences, recorded as measurements.** No failure code appeared at any point in
either run, and no capture file was written. The capture path exists and works — it was smoke-tested
and the artefact deleted — and nothing exercised it because this tenant permits the grant. That is
a finding, not a hole in the checking.

## The finding that matters most: an instrument built from a redactor

**The first live run reported `FAIL` on the rotation. The add-on was fine. The instrument was not.**

`rotate()` built its comparison from `refresh.fingerprint()` and put the results through a set.
That function is a **log redactor**: eight leading characters, written by 03-08 so that a Kodi log
a user pastes into a public forum cannot carry a credential. Its short length is the entire point
of it.

Every refresh token this registration issues begins `1.AXEAuM`. Three genuinely different tokens
therefore rendered identically, and the check reported that rotation was not reaching disk — the
phase's highest-consequence requirement, failing, on evidence that could not have shown anything
else.

The part worth carrying forward is not that the FAIL was wrong. It is that **a PASS from the same
code would have been unearned in exactly the same way**. An instrument that cannot separate two
cases produces a verdict with no information in it, and the verdict's confidence is unrelated to
its content. Had the tokens happened not to share a prefix, this would have gone green and the
phase would have recorded rotation as proven on the strength of a check that never worked.

This is the same error 03-08 caught inside the redactor itself, where a nine-character user code
redacted to eight became the live code with a typo. **Prefix length is load-bearing, and a value
chosen for one purpose does not transfer to another.** The redactor was reached for because it was
right there in the module and its output looked exactly like an identifier.

Three things changed, and only in the harness:

1. The comparison is a SHA-256 digest over each **whole** token, printed as twelve hex characters
   **with the length it was computed over**, so the output shows what was measured instead of asking
   to be trusted.
2. `rotation_digest` **refuses** any input that is already shortened — a redaction ends in `...` —
   because digesting a redaction discriminates exactly as badly while looking authoritative. The
   substitution cannot be made a second time by a different road.
3. The verdict has a third reading. `INCONCLUSIVE` when fewer than three tokens were observed or one
   is absent, with exit statuses 0 / 1 / 2. A binary verdict computed from a possibly
   non-discriminating input is what produced the confident wrong answer.

`refresh.fingerprint` was **not** touched. Its contract is deliberate and shipped callers depend on
it; this was a harness fault throughout. `git diff HEAD -- resources/` is empty for this plan.

Worth stating plainly: the shipped automated proof was never wrong. `test_refresh.py::test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens`
compares whole tokens read back from the file on disk. Nothing *asserts* that it must, though, and
nothing stops the next comparison from being built on `fingerprint()` again — logged as deferred
item 11 with the gate that would pay for it.

## Deviations from Plan

**1. [Rule 1 - Bug] The rotation check could not discriminate**
- **Found during:** Task 3, from the maintainer's first live run
- **Issue:** `rotate()` compared `refresh.fingerprint()` output; all three tokens share the leading
  run `1.AXEAuM`, so three distinct tokens compared equal and the run reported a false FAIL
- **Fix:** whole-token SHA-256 digest, a guard refusing pre-shortened input, and a three-way verdict
- **Files modified:** `.planning/research/live_sign_in.py`, `docs/AZURE-REGISTRATION.md`
- **Commit:** `a6d7d8b`
- **Cost:** one extra live grant, which the runbook records rather than hides

**2. [Rule 2 - Missing critical functionality] A second ignore rule for the scratch profile**
- **Found during:** Task 1
- **Issue:** the plan's ignore requirement covered the capture files; the harness also writes a real
  refresh token, and a default path is a thing people override carelessly
- **Fix:** `.planning/research/live-scratch/` ignored as a second line of defence, with the harness
  refusing an in-repository path as the first
- **Commit:** `a43ae9c`

## Checkpoint history

Task 3 was a `blocking` human-verify and was presented twice. The first presentation returned an
uninformative FAIL, was correctly rejected as inconclusive rather than recorded as a rotation
failure, and the fault was diagnosed to the harness. The second presentation carried the already-measured
values forward rather than asking for them again, and asked only for the rotation reading.

## Requirement marks

Ten ids were declared; **three were marked**, and the reasoning for each is on the requirement line.

| Id | Action | Why |
|---|---|---|
| SETUP-04 | → Complete | the runbook exists, is tracked, is gated by name, and now carries its acceptance record |
| AUTH-02 | → Complete | the built-in `client_id` acquired a live token with no setup, no server and no token copy-paste |
| AUTH-13 | → Complete | automated proof in 03-07 plus live confirmation here — both halves |
| AUTH-01 | left Pending | 03-14 declares it and it is about the television |
| AUTH-03 | left Pending, annotated | 03-14 declares it, and the personal-account half is deferred |
| AUTH-18 | left Pending, annotated UNVERIFIABLE HERE | the plan's own prohibition; no tenant available blocks the grant |
| AUTH-04, AUTH-12, AUTH-21, SETUP-05 | untouched | already Complete before this plan |

**DIST-01 carried forward untouched.** 03-12 flagged that it is marked Complete although 03-14 still
declares it. Not this plan's to change; repeated here so 03-14 sees it rather than rediscovering it.

## Threat mitigations

| Threat | Disposition | How |
|---|---|---|
| T-03-58 live token disclosure | mitigated | scratch profile outside the tree, two path refusals, removed at end, only digests printed |
| T-03-59 captured failure bodies | mitigated | ignore rule committed before any capture could be written, verified with `git check-ignore`; nothing from either run staged |
| T-03-60 unobservable tenant behaviour | transferred | recorded as unverified in the runbook and as UNVERIFIABLE HERE on the requirement |
| T-03-61 harness reimplementing the flow | mitigated | the harness imports and drives the shipped package; `resources/` is untouched by this plan |

## Known Stubs

None. The label fallback is unexercised rather than stubbed — it has a real implementation and a
real source, and no account was available that would make it run.

## Test suite

`235 passed, 0 failed, 1 skipped` — unchanged from the baseline, checked after each task.

## Self-Check: PASSED

- `.planning/research/live_sign_in.py` — FOUND
- `.planning/research/verify_device_code.py` — FOUND, both branches persist
- `docs/AZURE-REGISTRATION.md` — FOUND, acceptance record present
- Commits `a43ae9c`, `8e79e03`, `a6d7d8b`, `a679701` — all FOUND
- `git status --porcelain` clean before the final commit; `git ls-files | grep device-code-failure` returns nothing; scratch profile absent from disk
