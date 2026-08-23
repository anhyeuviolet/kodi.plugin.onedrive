---
phase: 03-authentication
plan: 10
subsystem: auth
tags: [startup-refresh, keepalive, background-service, needs-reauth-marker, pitfall-e, bounded-retry, python38]

requires:
  - phase: 03-authentication
    provides: "Plan 03-07's refresh.should_refresh threshold and its three-way outcome vocabulary — the whole classification this plan acts on, reused rather than restated"
  - phase: 03-authentication
    provides: "Plan 03-04's O_EXCL RefreshLock, which this plan is a second contender for by definition"
  - phase: 03-authentication
    provides: "Plan 03-09's CloudDriveAddon.NEEDS_REAUTH_KEY and the stale account row — the reader this plan is the writer for"
  - phase: 03-authentication
    provides: "Plan 03-08's Provider._post_port, Provider._lock_for and resolve_client_id — the Kodi-side ports this plan borrows rather than rebuilds"
  - phase: 03-authentication
    provides: "Plan 03-03's test_service_never_opens_a_dialog, which is a live gate over every line this plan added to the service closure"
provides:
  - "resources/lib/startup_refresh.py — check_accounts (the bounded, injectable startup check) and StartupRefreshService (its Kodi half)"
  - "startup_refresh.NEEDS_REAUTH_KEY = 'needs_reauth' — the writer half of the service's only channel to a user"
  - "startup_refresh.SKIPPED / ERRORED — the two outcomes that are this module's own, alongside refresh's three"
  - "startup_refresh.PASSES / RETRY_DELAY_SECONDS / ACQUIRE_TIMEOUT_SECONDS / LOCK_ATTEMPTS — the boot-time bound, with its arithmetic in the source"
  - "service.py runs the keepalive as a fifth service in ServiceUtil.run's list"
  - "tests/test_startup_refresh.py — sixteen assertions, none of which imports a Kodi module"
  - "tests/test_auth_gates.py::test_refresh_transport_is_built_from_the_pinned_profile now sweeps two files rather than one"
affects: [03-11, 03-12, 03-13, 03-14]

tech-stack:
  added: []
  patterns:
    - "A background keepalive is shaped like the listeners around it — name, start, stop — so the entry point stays one readable list, and the runner's own once-per-start thread is what makes it run once"
    - "A literal that must be equal in two files that may not import each other is written twice and held equal by a static assertion, never by a comment"
    - "A retry bound is stated as arithmetic against the constants it is made of, and the realistic case is stated next to the worst case so the number is not read as pessimism"
    - "The due set of a multi-pass loop is decided once, up front, so a retry cannot reach work the first pass excused"

key-files:
  created:
    - resources/lib/startup_refresh.py
    - tests/test_startup_refresh.py
  modified:
    - service.py
    - tests/test_auth_gates.py

key-decisions:
  - "The keepalive is handed to ServiceUtil.run as a fifth service rather than called before it. The runner starts each service once in its own daemon thread and then waits for the shutdown — it has no periodic set — so a service whose start() returns has run exactly once at Kodi start, which is what a keepalive wants. Running inside the runner also means the token exchange delays none of the four listeners, and the shutdown observation comes for free"
  - "The startup refresh takes ONE lock attempt of ten seconds where the plugin takes three of thirty. A plugin invocation has a user waiting on it and must eventually break a genuinely stuck lock; this caller has the opposite incentive, because a held lock means somebody else is already refreshing this account and the right answer is the next pass rather than contention"
  - "'needs_reauth' is written out twice rather than imported. Importing the account list would drag every dialog in the add-on into the service's import closure and turn AUTH-17's static assertion red, so the two literals are held equal by an assertion instead"
  - "The marker is cleared when a refresh succeeds on a marked account. Re-authorising through the plugin already clears it, so this covers the marker that should never have been written — and a marker that outlives the failure it recorded asks the user to sign in again for an account that is working"
  - "A successful refresh writes no record at all. Only the marker being set or cleared is a record write, because every write is a chance to leave a temporary file behind on a device that is power-cut rather than shut down"
  - "The notification reuses string 30043, the account list's own 'Sign-in needed' label, rather than adding a string of its own. The toast and the row are the same fact reaching the user by two routes and a second string would let them drift"
  - "test_refresh_transport_is_built_from_the_pinned_profile was widened from one file to two. The keepalive is the contender most likely to meet the lock rather than least, and a 155-second refresh under a 90-second lock reached only from the background service is one nobody would ever watch happen"

patterns-established:
  - "Pattern 1: a per-account loop that must be independent is written so that one account's failure is a value, not an exception — every failure mode of one account, including a record it cannot read, returns an outcome and the loop continues"
  - "Pattern 2: the abort-aware wait is read in three places — before the run, between passes, and before each account — because each answers a different question about how long the shutdown has been waiting"
  - "Pattern 3 (03-09's Pattern 2, met again): when two guards can both satisfy an assertion, the test distinguishes them by an argument rather than by a scripted sequence — a queue of answers lets the wrong guard pass the test, and the mutation is what exposes it"

requirements-completed: [AUTH-16]

coverage:
  - id: D1
    description: "A refresh runs at Kodi start for any account whose stored token was issued longer ago than the threshold, and an account inside the threshold costs no request at all"
    requirement: "AUTH-16"
    verification:
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_recently_issued_token_costs_no_request"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_an_old_token_is_refreshed_and_the_stored_grant_moves"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_blob_with_no_issue_time_is_treated_as_old"
        status: pass
      - kind: manual
        ref: "deferred to plan 03-14 on the television: the service starts at login, the log shows the check running once, no traceback and no dialog over the home screen"
        status: deferred
    human_judgment: true
    rationale: "That the check runs, refreshes and writes is proven against a real filesystem with an injected HTTP port. That Kodi actually starts the service at login on an Android TV box, and that the run finishes without a traceback in a real interpreter, is a property of doing it"
  - id: D2
    description: "The background service never opens an interactive surface, and a static assertion enforces it over the whole import closure of the service entry point"
    requirement: "AUTH-17"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_service_never_opens_a_dialog — the closure grew from 30 files to 31 and stayed green"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_the_module_opens_nothing_and_waits_on_nothing_blind"
        status: pass
    human_judgment: false
  - id: D3
    description: "Only a provider grant refusal records the needs-re-authorisation marker; a transport failure leaves the record and the token file exactly as they were"
    requirement: "AUTH-16"
    verification:
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_transport_failure_marks_nothing_and_changes_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_grant_failure_marks_the_record_and_leaves_the_token_file_alone"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_an_account_with_no_stored_grant_is_skipped_without_a_marker"
        status: pass
    human_judgment: false
  - id: D4
    description: "The marker goes on the account record and not into the token file, and it is added to the record rather than replacing it"
    requirement: "AUTH-17"
    verification:
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_grant_failure_marks_the_record_and_leaves_the_token_file_alone — the token file is compared byte for byte and the drives list is compared against the record it came from"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_the_marker_key_is_the_one_the_account_list_reads"
        status: pass
      - kind: manual
        ref: "deferred to 03-14 with 03-09's D10: no row has ever rendered in the stale state, because until this plan nothing wrote the marker"
        status: deferred
    human_judgment: true
    rationale: "The key is now written by one file and read by another and the two are asserted equal, which is everything static analysis can prove. Whether the row reads as actionable from a sofa is 03-14's"
  - id: D5
    description: "The startup attempt is bounded — a small number of passes with a shutdown-aware wait between them — and a shutdown stops it where it stands"
    requirement: "AUTH-16"
    verification:
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_the_retry_is_bounded"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_only_the_accounts_that_failed_are_retried"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_shutdown_stops_the_run_where_it_stands"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_shutdown_between_passes_stops_the_retry"
        status: pass
    human_judgment: false
  - id: D6
    description: "The refresh goes through the same per-account lock the plugin uses, on the same pinned transport profile"
    requirement: "AUTH-20"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_refresh_transport_is_built_from_the_pinned_profile — widened to sweep resources/lib/startup_refresh.py as well as the provider"
        status: pass
      - kind: other
        ref: "the lock is built by Provider._lock_for itself rather than by a second copy of it; check_accounts takes the factory by injection and the service hands it that function"
        status: pass
      - kind: manual
        ref: "no live contention has been produced: Kodi starting while the user opens the add-on immediately has not been staged on the television. Deferred to 03-14"
        status: deferred
    human_judgment: true
    rationale: "The lock's own race is proven by 03-04's two-thread and two-process tests, and this plan is proven to construct that same lock on that same path. That the two really do contend on an Android TV box at boot is the one thing only the box can answer"
  - id: D7
    description: "Accounts are processed independently: one failing does not prevent another refreshing, and neither does a record the check cannot read"
    requirement: "AUTH-20"
    verification:
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_one_failing_account_does_not_prevent_the_other_refreshing"
        status: pass
      - kind: unit
        ref: "tests/test_startup_refresh.py::test_a_record_the_check_cannot_read_does_not_stop_the_run"
        status: pass
    human_judgment: false

duration: 16m
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 10: The Startup Keepalive Summary

**The service now spends the refresh token at Kodi start for any account whose grant is older than
thirty days, and the one thing it can never do — ask the user anything — is enforced by an assertion
over its whole import closure rather than by a reviewer.**

## Performance

- **Duration:** 16 min
- **Tasks:** 2 of 2
- **Files created:** 2
- **Files modified:** 2
- **Suite:** 217 passed / 2 failed / 1 skipped → **233 passed / 2 failed / 1 skipped**

## Accomplishments

**A refresh at start, but not on every start.** `refresh.should_refresh` is the threshold and it was
already written and already tested; this plan is its first caller. A box switched on daily costs no
request and no write at all, which is the point — thirty days against a ninety-day window leaves
sixty days of margin, and a threshold near the edge only helps the device that needs no help.

**The failure that must not reach the user.** A television at boot frequently has no network, and
every failure looks alike from the response alone. `refresh.refresh` already separates the three
answers; what this plan adds is the discipline of acting on all three differently. A transport
failure leaves the record untouched, writes nothing, notifies nobody and comes back on the next
start. Only a provider grant refusal writes the marker. A test compares the whole blob on disk before
and after, so "changed nothing" means the bytes rather than the intent.

**The marker is on the record, not in the token file.** An unreadable token file is one of the
failure modes being signalled; the marker written into it would be a marker written into the thing
that is broken. The record is copied and one key added — never rebuilt — because the drives list is
what every account-list row and every stored export references, and a test compares it against the
record it came from rather than merely asserting the marker is present.

**The join with the account list is asserted, not documented.** 03-09 wrote the reader and named the
key in a comment addressed to this plan. The two files may not import each other: the account list
lives in the vendored tree and importing it would drag every dialog in the add-on into the service's
import closure, turning AUTH-17's assertion red. So the literal is written twice and an assertion
reads both — the reader's out of the AST, the writer's out of the module — and fails if they differ.

**A stale marker is cleared.** Re-authorising through the plugin already clears it, so this covers the
one the service should never have written. A marker that outlives the failure it recorded asks the
user to sign in again for an account that is working, which is the same false alarm the transport
classification exists to prevent, arriving a day later.

**Bounded, with the arithmetic in the source.** Three passes and a twenty-second abort-aware wait, set
by Wi-Fi association rather than by taste: a television switched on cold can take ten to twenty
seconds to get a route, and a single try misses that window on exactly the devices that need this
most. Worst case for one account is `3 * (10 + 65) + 2 * 20 = 265` seconds on a network that accepts
connections and never answers; the boot case this exists for is far cheaper, because with no route a
connect fails immediately. Both numbers are in the file, because a bound stated without its realistic
case reads as pessimism and gets "tidied".

**The lock budget is deliberately the opposite of the plugin's.** `refresh.refresh` defaults to three
acquire attempts of thirty seconds so a plugin invocation with a user waiting on it can eventually
break a genuinely stuck lock. This caller wants the reverse: a held lock means somebody else is
already refreshing this account, so one attempt of ten seconds and then the next pass. It is the same
lock, built by `Provider._lock_for` itself rather than by a second copy of the construction — one
implementation of "which file, whose session, which wait" is what makes the two processes contend at
all.

**Everything Kodi-shaped arrives by injection.** `check_accounts` takes the profile path, the lock
factory, the HTTP port, the abort-aware wait, the record writer and the notifier, so all sixteen
assertions run against a real filesystem with no stub Kodi library and the suite stays under four
seconds. `StartupRefreshService` is the only part of the file that knows Kodi exists, and its imports
are deferred into `start` for that reason.

**The entry point gained one line and lost none.** `ServiceUtil.run` starts each service once in its
own daemon thread and then waits for the shutdown; it has no periodic set. A service whose `start`
returns has therefore run exactly once at Kodi start, which is what a keepalive wants and what a
refresh on every poll would ruin. Last in the list, so the four servers claim their ports before the
token exchange begins. The four are otherwise untouched.

## Task Commits

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | RED — the startup keepalive | `34f1a01` | `tests/test_startup_refresh.py` |
| 1 | GREEN — the startup keepalive | `488d80c` | `resources/lib/startup_refresh.py`, `tests/test_auth_gates.py` |
| 2 | Run it from the service entry point | `4a1478d` | `service.py` |
| — | The between-passes assertion, rewritten stronger after its mutation survived | `7dcab84` | `tests/test_startup_refresh.py` |

## Gate State After This Plan

Baseline inherited: **217 passed, 2 failed, 1 skipped.** Now: **233 passed, 2 failed, 1 skipped.**

The two failures are unchanged and are not this plan's: `test_no_broker_references` still reads
`settings.xml:21` (03-11) and `addon.xml:55` (03-12), and `test_custom_client_id_setting` is 03-11's.
Neither was touched.

| Assertion | State | What this plan did to it |
|---|---|---|
| `test_service_never_opens_a_dialog` | **green** | Closure grew from 30 files to 31. The new file is inside it and was checked — verified explicitly rather than assumed, since a gate that silently stopped covering the module would look identical |
| `test_refresh_transport_is_built_from_the_pinned_profile` | **green** | Widened from one file to two. Its non-vacuity guard now fires per file, so a keepalive that stopped building its own transport turns it red rather than passing |

Sixteen assertions added in `tests/test_startup_refresh.py`. No assertion anywhere was weakened.

**Mutation checks: seven run, six caught on the first pass, one survivor fixed.**

| Mutation | Caught by |
|---|---|
| The marker is written on any non-success | `test_a_transport_failure_marks_nothing_and_changes_nothing` |
| The threshold is ignored and every account refreshed | `test_a_recently_issued_token_costs_no_request` |
| The record is rebuilt rather than copied | `test_a_grant_failure_marks_the_record_and_leaves_the_token_file_alone` |
| The pass bound is loosened | `test_the_retry_is_bounded` |
| The marker key drifts from the reader's | `test_the_marker_key_is_the_one_the_account_list_reads` |
| A successful refresh rewrites every record | `test_a_working_account_is_not_rewritten` |
| **The wait between passes is called and its answer thrown away** | **survived — see below** |

The survivor is the useful one. `test_a_shutdown_between_passes_stops_the_retry` scripted a queue of
answers for the abort-aware wait, and the per-account `wait(0)` consumed the True one pass later and
stopped the run anyway — so a version that called the delay and ignored what it said passed a test
named after reading it. The two guards are now distinguished by their argument: only a non-zero wait
reports the shutdown, and the test asserts both that the pause between passes *was* the abort-aware
wait given the retry delay, and that exactly one request was made. Re-run: seven of seven caught.

The harness held its own copy of the target, asserted its restore byte for byte after each mutation
and again at the end, and touched nothing else. Nothing restored the working tree.

## Deviations from Plan

### 1. [Rule 2 — Missing critical functionality] The pinned transport profile had no gate on this side

- **Found during:** Task 1.
- **Issue:** `test_refresh_transport_is_built_from_the_pinned_profile` reads exactly one file, the
  provider. This module builds a transport of its own for the same endpoint under the same lock, and
  a profile pinned in the provider and forgotten here would put a 155-second refresh under a
  90-second lock — a live lock the plugin is then entitled to break, which is T-03-49, the double
  write the lock exists to prevent. The keepalive is the contender most likely to meet the lock
  rather than least, since it runs at the moment the user opens the add-on.
- **Fix:** the sweep now iterates `REFRESH_TRANSPORT_FILES` and its non-vacuity guard fires per file.
  The transport is built inside `StartupRefreshService._refresh_port`, whose name carries `refresh`
  so the sweep's enclosing-function anchor holds.
- **Files modified:** `tests/test_auth_gates.py`.
- **Verification:** removing `tries=` from the new construction turns the gate red naming the file
  and line; restored from the harness's copy.
- **Committed in:** `488d80c`.

### 2. [Rule 2 — Missing critical functionality] A stale marker had no way to be cleared by the service

- **Found during:** Task 1.
- **Issue:** the plan describes writing the marker and says nothing about removing it. Re-authorising
  through the plugin clears it (03-09), but nothing cleared a marker that was written and then turned
  out to be wrong — and the whole reason the transport classification exists is that markers can be
  wrong. A marker that outlives its failure asks the user to sign in again for an account that works.
- **Fix:** a successful refresh on a record that carries the marker removes it, in one record write.
  A successful refresh on a record without it writes nothing at all, which is asserted separately so
  the clear cannot become an unconditional rewrite.
- **Files modified:** `resources/lib/startup_refresh.py`.
- **Committed in:** `488d80c`.

### 3. [Rule 2 — Missing critical functionality] A record the check cannot read

- **Found during:** Task 1.
- **Issue:** "accounts are independent" was specified against a refresh failing. A record with no
  `id`, or an id the token store refuses as a filename, raises before the refresh is reached — and an
  exception there would have ended the run, leaving every account after it in the iteration
  unrefreshed, silently, with the visible symptom appearing months later on a different account.
- **Fix:** an `ERRORED` outcome of this module's own. It records nothing, notifies nobody and is not
  retried — a crash repeated three times is still a crash — and the loop continues to the next
  account.
- **Files modified:** `resources/lib/startup_refresh.py`, `tests/test_startup_refresh.py`.
- **Committed in:** `34f1a01`, `488d80c`.

## Requirement Marks Kept, and Why

The known defect in the requirements-marking step was checked rather than trusted: the diff of
`.planning/REQUIREMENTS.md` was read line by line before it was committed.

| Requirement | Declared by | Mark | Reason |
|---|---|---|---|
| AUTH-16 | 03-07, 03-10 | **Complete** | 03-10 is the last plan declaring it. 03-07 wrote the threshold predicate; this plan is what makes a refresh actually run at start. Nothing later declares it |
| AUTH-17 | 03-03, 03-09, 03-10, **03-14** | **left Pending** | 03-14 is the last, and it is the one that watches the service start on the television without a dialog appearing. Marking it here would close it on a plan that cannot see the screen |
| AUTH-20 | 03-04, 03-09, **03-10** | left **Complete** | It was already marked by an earlier plan, which was premature at the time. This plan is the last declaring it and does deliver its part — the startup refresh takes the same per-account lock — so the mark is now correct rather than merely inherited |

Only `AUTH-16` was passed to the marking step. The bulk form named in the plan's frontmatter would
have flipped `AUTH-17` as well.

## What This Plan Did Not Prove

Everything here runs against a real filesystem and an injected HTTP port, and nothing here has run
inside Kodi. Three things are therefore still open, all of them 03-14's:

- **That Kodi starts the service at all on the box.** The extension point in `addon.xml` was already
  declared and needed no change, and the four existing services have never been watched starting on
  this device either.
- **That no dialog appears at boot.** The assertion proves nothing in the closure can open one. It
  cannot prove Kodi does not raise one for its own reasons over the same screen.
- **That the stale row renders.** 03-09 recorded this as the largest unverified thing it produced,
  because nothing wrote the marker. Something writes it now; nothing has yet seen the result.

## Deferred Items

No new items. The five carried in `deferred-items.md` are untouched, and item 3 —
`AccountManager.remove_drive` having no caller — was re-read while working in that file and remains
correct as recorded: this plan reads `get_accounts` and `save_account` and calls neither removal path.

## Self-Check: PASSED

Both created files exist and are tracked; all five commits resolve; no tracked file was deleted
anywhere in this plan's range.
