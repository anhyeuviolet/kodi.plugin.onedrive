---
phase: 03-authentication
plan: 07
subsystem: auth
tags: [token-rotation, refresh, invalid-grant, race, proactive-refresh, retry-profile, python38]

requires:
  - phase: 03-authentication
    provides: "Plan 03-01's store.read / store.write / merge_token_response — the keep-the-previous-refresh-token rule this module always goes through rather than reimplementing, and the injected post(url, fields) -> (status, body) port"
  - phase: 03-authentication
    provides: "Plan 03-04's RefreshLock and per-account layout — the acquire/release this refresh happens between, the LIFETIME_SECONDS = 90 the short request profile is pinned against, and the caller shape written out in tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write"
  - phase: 03-authentication
    provides: "Plan 03-05's errors.classify_response — the one table in the tree that knows what a provider code means"
provides:
  - "resources/lib/auth/refresh.py — refresh(): acquire, re-read, exchange, merge, write, release, with both adopt paths and the invalid-grant discrimination"
  - "should_refresh(blob, threshold_days, now) — the startup predicate, with an absent issue time counting as old"
  - "The three-outcome vocabulary the service and the plugin both switch on: SUCCEEDED, TRANSIENT, NEEDS_REAUTHORISATION"
  - "REQUEST_TRIES / REQUEST_DELAY_SECONDS / REQUEST_BACKOFF — the short transport profile the Kodi layer must hand the transport, and WORST_CASE_SECONDS with its arithmetic"
  - "tests/test_refresh.py — 37 tests including the rotation proof, both invalid-grant branches, five transport failures and the two-contender property in one process and in two"
affects: [03-08, 03-09, 03-10, 03-13, browse-phase]

tech-stack:
  added: []
  patterns:
    - "Every path that could use another contender's token re-reads the store FROM DISK; a snapshot taken before the race is never evidence about what happened during it"
    - "A provider response is not evidence about which of two things happened; the disk is"
    - "Failure is a three-valued outcome, not a boolean, because 'it did not work' contains two events with opposite correct responses"
    - "A constant coupled to another module's constant is pinned by a test that imports both, not by a comment that mentions one"

key-files:
  created:
    - resources/lib/auth/refresh.py
    - tests/test_refresh.py
  modified: []

key-decisions:
  - "The refresh gets its own short request profile (tries=2, delay=5, worst case 2*30+5 = 65 seconds) rather than the transport's default ladder, whose own comment computes 155 seconds; that is what lets RefreshLock.LIFETIME_SECONDS sit at 90 without holding the other contender for minutes, and the coupling is asserted by a test that imports both constants"
  - "The adopt-on-invalid-grant path is gated on the error value being exactly `invalid_grant`, which is the answer the provider gives for a redeemed-and-rotated token; widening it is a one-line change and the reason is recorded at the gate"
  - "Byte-identical, not 'was the file rewritten': a rewrite that stored the same token is not a rotation, and treating it as one would retry a genuinely dead grant forever with nothing on screen"
  - "The bounded wait is 3 * (30 + 1) = 93 seconds, deliberately just past the lock's 90-second lifetime, so a contender can be the one that breaks a genuinely stuck lock rather than leaving the stall to reappear on the next call"
  - "The startup threshold is 30 days against the 90-day window, not the research's suggested 60: a device switched on once every forty-five days skips a sixty-day threshold on one start and finds the grant dead on the next"
  - "should_refresh returns False for a blob with no refresh token, so an account that has never signed in does not send the service to the network and collect a needs-reauthorisation mark on every Kodi start"
  - "A server-side 5xx and the two RFC 6749 server-fault error values are transient, not grant failures — the provider having a bad half hour is not a statement about this account"

patterns-established:
  - "Pattern 1: a cross-process test signals readiness from inside the injected sleep, not before the call, because every wait in the code under test happens after it has read the store — which is what makes the parent's write land in the window the test is about"
  - "Pattern 2: a pair of tests that differ in exactly one input is stated a third time as a single assertion, so the thing being claimed (the response is not evidence, the disk is) is written down rather than inferred"
  - "Pattern 3: the transport-failure sweep is parametrised over five shapes of network failure and asserts the negative — outcome is never needs-reauthorisation — so a new failure shape has one obvious place to be added"

requirements-completed: [AUTH-15]

coverage:
  - id: D1
    description: "The persisted refresh token is different after each of two consecutive refreshes, and the newest is the one on disk"
    requirement: "AUTH-13"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_each_exchange_sends_the_token_the_previous_one_returned"
        status: pass
    human_judgment: false
  - id: D2
    description: "A response omitting a refresh token keeps the stored one and still advances the access token and the issue time"
    requirement: "AUTH-12"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_a_response_without_a_refresh_token_keeps_the_stored_one"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_a_response_without_a_refresh_token_still_advances_the_access_token"
        status: pass
    human_judgment: false
  - id: D3
    description: "An invalid-grant response whose store has moved on is adopted and produces no re-authorisation signal; the same response against a byte-identical stored token is a dead grant"
    requirement: "AUTH-15"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_an_invalid_grant_whose_store_moved_on_is_adopted_not_a_sign_out"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_an_invalid_grant_against_a_byte_identical_stored_token_is_a_dead_grant"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_two_invalid_grant_branches_are_told_apart_by_the_store_alone"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_a_store_that_moved_on_to_the_same_token_is_still_a_dead_grant"
        status: pass
    human_judgment: false
  - id: D4
    description: "A contender that cannot acquire the lock waits, re-reads from disk and uses the winner's token with no network call at all; one that acquires after the winner wrote does the same under the lock"
    requirement: "AUTH-15"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_a_contender_that_cannot_acquire_adopts_the_winners_token"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_a_contender_that_gets_the_lock_after_the_winner_wrote_does_not_exchange"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_a_loser_that_sees_no_change_gives_up_after_a_bounded_number_of_tries"
        status: pass
    human_judgment: false
  - id: D5
    description: "Two contenders produce exactly one exchange, proven as two threads in one process and as two processes"
    requirement: "AUTH-15"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_two_threads_in_one_process_produce_exactly_one_exchange"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_two_processes_adopt_rather_than_both_exchange"
        status: pass
    human_judgment: false
  - id: D6
    description: "No transport failure marks an account or changes the store; five shapes covered including a captive portal, a name that will not resolve and the provider's own 5xx"
    requirement: "AUTH-16"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_a_transport_failure_is_transient_and_marks_nothing (5 parameters)"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_lock_is_released_when_the_exchange_raises"
        status: pass
    human_judgment: false
  - id: D7
    description: "The startup predicate skips a recently-issued blob, takes an old one, takes one with no issue time at all, and declines a blob with no grant to spend"
    requirement: "AUTH-16"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_the_startup_check_skips_a_recently_issued_blob"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_startup_check_takes_an_old_blob"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_startup_check_treats_a_missing_issue_time_as_old"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_startup_check_declines_a_blob_with_nothing_to_refresh"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_threshold_sits_well_inside_the_ninety_day_window"
        status: pass
    human_judgment: false
  - id: D8
    description: "The short retry profile's worst case stays inside the lock's lifetime, and the arithmetic and the constant's name cannot leave the file without a test noticing"
    requirement: "AUTH-15"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_the_short_retry_profile_stays_inside_the_lock_lifetime"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_profile_names_the_lock_lifetime_beside_its_arithmetic"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_bounded_wait_outlives_the_lock_lifetime"
        status: pass
    human_judgment: false
  - id: D9
    description: "Rotation can be observed in a log without a token being in it: eight leading characters and no more"
    requirement: "AUTH-13"
    verification:
      - kind: unit
        ref: "tests/test_refresh.py::test_the_rotation_log_shows_eight_leading_characters_and_no_more"
        status: pass
      - kind: unit
        ref: "tests/test_refresh.py::test_the_fingerprint_of_an_absent_token_is_not_an_index_error"
        status: pass
    human_judgment: false
  - id: D10
    description: "That the provider actually issues a different refresh token on each use — as opposed to this code keeping whatever it is given"
    requirement: "AUTH-13"
    verification: []
    human_judgment: true
    rationale: "Not verifiable here and deliberately not claimed. Every assertion in this plan is driven by a scripted endpoint, so what is proven is that the add-on persists and re-sends whatever the provider returns. Whether the live provider returns something new is plan 03-13's live pass, which declares AUTH-13 for exactly that reason. The two halves together are the requirement; neither alone is"

duration: 20min
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 07: The Refresh Path, the Lost Race and the Startup Threshold Summary

**A token refresh now persists the rotated refresh token and is proven to — three distinct values across two refreshes, asserted against the file rather than a return value — and a contender that loses the race costs a wait rather than a sign-in, because `invalid_grant` is read against the disk instead of taken at face value.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-08-23T11:02Z
- **Completed:** 2026-08-23T11:22Z
- **Tasks:** 2 of 2
- **Files created:** 2
- **Files modified:** 0
- **Suite:** 204 passed, 5 failed by construction, 1 skipped, 2.5s (baseline was 167 / 5 / 1)

## Accomplishments

- **The phase's one non-negotiable proof exists and is not vacuous.** `test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens` runs the refresh twice against a scripted endpoint and asserts three refresh tokens in sequence all differ, with the newest on disk. Mutating `_exchange` to drop the response's `refresh_token` before merging — which is Pitfall 3 exactly, and is what most tutorial code does — turns it into `['refresh-token-0', 'refresh-token-0', 'refresh-token-0']` and takes two other tests down with it. Its companion, `test_each_exchange_sends_the_token_the_previous_one_returned`, closes the variant where the new token is stored and the original is still the one sent.
- **The lost race is told from a dead grant by the disk, and by nothing else.** The two fixtures differ in one thing: whether the stored refresh token changed while the request was in flight. Same error value, same code, same paragraph. A third test states that as one assertion so the claim is written down rather than inferred, and a fourth covers the case a weaker check would get wrong — a store that was rewritten with the *same* token has not moved on. Mutating the comparison from `rotated != used` to `rotated` turns five tests red.
- **Three outcomes, and only one of them can ask a user to sign in again.** Five shapes of network failure are swept — no route, a name that will not resolve, a captive portal's unparseable body, `temporarily_unavailable` and a 500 — and each is asserted to be transient, to leave the blob byte-identical, and specifically *not* to be the re-authorisation outcome. That is Pitfall E closed in the place it happens: a box that starts before its Wi-Fi is up.
- **Both adopt paths re-read from disk, and there are two of them for a reason.** One is the loser that never got the lock; the other is the contender that waited, got the lock, and would otherwise act on a blob it loaded before the previous holder wrote. The second is the easy one to leave out, and `test_a_contender_that_gets_the_lock_after_the_winner_wrote_does_not_exchange` is what makes leaving it out visible.
- **The two-contender property is proven in one process and in two.** The one-process case is the one that matters here, because in Kodi the plugin and the service are sub-interpreters inside one process: two threads enter with the same blob, exactly one spends the refresh token, and the loser is asserted to have adopted with `exchanged is False`. The two-process case is kept because its absence would read as an oversight; it costs one spawn and 0.1 seconds.
- **The number the previous plan pinned itself against is now in the tree with a test holding the two together.** `REQUEST_TRIES = 2, REQUEST_DELAY_SECONDS = 5`, worst case `2 * 30 + 5 = 65`, against `RefreshLock.LIFETIME_SECONDS = 90` — imported, not quoted, so `test_the_short_retry_profile_stays_inside_the_lock_lifetime` fails if either side moves. Plan 03-04 shouted in its own source that this dependency was load-bearing; it is now enforced rather than shouted.

## Task Commits

1. **Task 1: Refresh under the lock, and prove the stored token rotates (TDD)** — `5396b4d` (test, RED) → `8991333` (feat, GREEN)
2. **Task 2: Tell a lost race apart from a dead grant, and a dead network apart from both (TDD)** — `65b1236` (test, RED) → `3b10fdb` (feat, GREEN)

## Files Created

- `resources/lib/auth/refresh.py` (389 lines) — `SUCCEEDED` / `TRANSIENT` / `NEEDS_REAUTHORISATION`, the `Refreshed` namedtuple, `GRANT_TYPE`, `INVALID_GRANT`, `TRANSIENT_ERRORS`, `SERVER_ERROR_STATUS`, the request profile with `WORST_CASE_SECONDS` and `LOCK_LIFETIME_SECONDS`, the waiting profile, `fingerprint`, `refresh`, `_exchange`, `_is_server_error` and `should_refresh`. Imports `collections`, `time`, and three siblings from its own package. No Kodi module, no socket.
- `tests/test_refresh.py` (952 lines) — 33 test functions, 37 tests after parametrisation: the rotation proof, both invalid-grant branches, the two adopt paths, the bounded wait, the shutdown path, the finally-release, five transport failures, the failure-table routing, the startup predicate and its threshold, the log fingerprint, and the two-contender property in one process and in two.

## Decisions Made

**The short request profile lives here as constants, not as a `Request` this module builds.** The HTTP port arrives already constructed, which is the whole reason this package has no Kodi in it and no socket. So `REQUEST_TRIES`, `REQUEST_DELAY_SECONDS` and `REQUEST_BACKOFF` are values for the Kodi layer to hand to the transport's constructor, with the arithmetic beside them and `RefreshLock.LIFETIME_SECONDS` imported rather than quoted. Plan 03-08 has to actually pass them; a test in this file cannot check that it did, and the Next Phase Readiness section below says so.

**The adopt path is gated on the error value being exactly `invalid_grant`.** That is the provider's documented and observed answer for a refresh token that has already been redeemed and rotated, which is what a lost race produces. Doing the disk re-read for every refusal would also be safe — a store that moved on means a refresh succeeded, whatever the code — but it would blur what the gate is *for*, and the gate is the requirement. The comment at the gate says widening it is a one-line change if a different code is ever observed in the field.

**Byte-identical is the comparison, not "did the file change".** A rewrite that stored the same token is not a rotation. The weaker check would pass on it, adopt a dead token and retry forever with nothing on screen to say why — the same shape of silent failure as Pitfall 3, arriving from the other end. `test_a_store_that_moved_on_to_the_same_token_is_still_a_dead_grant` exists for that one line.

**Thirty days, not the sixty the research suggested.** Both satisfy "well inside" the ninety-day window, and sixty is what Pitfall 3 recommends. The failure case decides it: the refresh runs on Kodi start, so a device switched on once every forty-five days skips a sixty-day threshold on one start and finds the grant already dead on the next. Sixty days of margin costs one extra refresh per month on a box in daily use and rescues the box in occasional use, which is the one this whole keepalive exists for. The arithmetic is in the source beside the constant.

**`should_refresh` returns False for a blob with no refresh token.** Answering True would be defensible — the account *does* need attention — but it sends the service to the network on every Kodi start for an account that has never signed in, and collects a needs-reauthorisation mark each time. The predicate answers "is there something to refresh", and there is not.

**The bounded wait is 93 seconds, which is deliberately more than the lock's 90.** A contender whose whole budget expired before the lifetime could never be the one that breaks a genuinely stuck lock, so the stall would outlive the call and be waiting again on the next one. `test_the_bounded_wait_outlives_the_lock_lifetime` pins the relationship rather than the numbers.

**A 5xx is transient.** The provider having a bad half hour says nothing about this grant, and the same is true of the two RFC 6749 server-fault error values. Reading either as a dead grant would sign users out during somebody else's incident.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] A refresh has to survive the port raising, not only the port answering badly**

- **Found during:** Task 1
- **Issue:** The plan describes the transport failure case as a response shape. On this add-on's actual port it is at least as often an exception: `URLError`, `socket.timeout`, a name that will not resolve. Left unhandled it escapes `refresh()` and — because the exchange is inside the lock — the service's proactive refresh becomes an unhandled exception at Kodi start.
- **Fix:** The `post` call sits in a narrow `try` that classifies any exception as transient. Narrow on purpose: `store.write` is outside it, so a filesystem failure is not silently reported as a network hiccup.
- **New tests:** two of the five parameters in `test_a_transport_failure_is_transient_and_marks_nothing`, plus `test_the_lock_is_released_when_the_exchange_raises`, which asserts the lock file is gone afterwards.
- **Committed in:** `8991333`

**2. [Rule 2 — Missing critical functionality] The under-lock re-read, which the plan's five-step sketch does not contain**

- **Found during:** Task 1
- **Issue:** The research's ordered steps cover the contender that never gets the lock. They do not cover the one that waits, gets it, and then acts on the blob it read *before* the wait. That contender exchanges a refresh token the winner already redeemed — which is the double refresh the lock exists to prevent, arriving one step later than the case the lock was designed against.
- **Fix:** The blob is re-read from disk immediately after a successful acquire and compared against the access token held at entry, exactly as the loser path does. This is also what `tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write` sketched as the caller shape, so the shape is now in the tree rather than in a test's comment.
- **New test:** `test_a_contender_that_gets_the_lock_after_the_winner_wrote_does_not_exchange`.
- **Committed in:** `8991333`

**3. [Rule 2 — Missing critical functionality] A 5xx and the two server-fault error values are transient**

- **Found during:** Task 2
- **Issue:** The plan names "a transport failure — no route, name resolution failure, timeout" as the transient family. A provider that answers HTTP 500, or `temporarily_unavailable`, has produced a protocol answer, so by the plan's letter it would fall through to the grant-failure branch and sign users out during an incident on the provider's side.
- **Fix:** `SERVER_ERROR_STATUS` and `TRANSIENT_ERRORS` are checked before the refusal branch. Both are named in the source with the reason.
- **New tests:** three of the five parameters in `test_a_transport_failure_is_transient_and_marks_nothing`.
- **Committed in:** `3b10fdb`

**4. [Rule 2 — Missing critical functionality] `should_refresh` declines a blob with no grant in it**

- **Found during:** Task 2
- **Issue:** The plan's predicate is about the issue time alone. A blob with no refresh token — an account that has never signed in, or one whose file was truncated — has an absent issue time too, so the "absent means old" rule would return True for it and the service would attempt a refresh and mark the account on every single Kodi start.
- **Fix:** The no-grant case is answered first and answered False.
- **New test:** `test_the_startup_check_declines_a_blob_with_nothing_to_refresh`.
- **Committed in:** `3b10fdb`

### Scope Observations

**5. The plan's `acquire_timeout` and `attempts` had to become parameters**

- **Found during:** Task 1
- **Issue:** With the production values (a 30-second acquire, three attempts) every test whose point is that an acquire is *refused* would spend 30 seconds of wall time, and the suite's whole budget is about two seconds. The lock's own wait is injected, but its deadline is not.
- **Fix:** `refresh()` takes `acquire_timeout` and `attempts` with the production values as defaults. This is not only a test affordance — a caller with a foreground user waiting may reasonably want a shorter budget than the background service does.
- **Committed in:** `8991333`

**6. The two-process test signals readiness from inside the injected sleep**

- **Found during:** Task 1, after the first draft passed for the wrong reason
- **Issue:** The obvious shape — the child raises a flag, then calls `refresh()` — has a real race in the *test*, not in the code: the parent can write the winner's blob between the flag and the child's first `store.read`, and the child is then refreshing an already-fresh token. Correct behaviour, but not the behaviour under test, and it would have shown up as an intermittent failure months later.
- **Fix:** The flag is raised from inside the child's injected sleep. Every wait in `refresh()` happens after it has read the store, so a parent that waits for the flag knows the child is holding the old blob and is contending. The reasoning is in the child script's comment.
- **Committed in:** `8991333`

### Record Accuracy

**7. This plan's `<verify>` names `tests/test_refresh_lock.py`, which is 03-04's file and was not touched**

Both of the plan's verification commands were run as written and are green (`tests/test_refresh.py` 37 passed; `tests/test_token_store.py tests/test_refresh_lock.py` 75 passed, 1 skipped). Recorded only so a reader does not look for a change in `test_refresh_lock.py` and fail to find one — it is a regression check on the dependency, not a deliverable of this plan.

---

**Total deviations:** 7 (4 × Rule 2, 2 scope, 1 record accuracy)
**Impact on plan:** None on shape or scope. Deviations 1–4 are all the same species — a failure the plan classified as one thing that is, on this add-on's real inputs, two — and each of them, left in, produces the specific outcome the plan was written to prevent: a sign-in prompt for a reason that is not a dead grant.

## Issues Encountered

**The first version of the loser-adopt test passed against code that could not possibly have worked, and for an instructive reason.** It wrote the winner's blob *before* calling `refresh()`. But `refresh()` reads the store as its first act, so the contender entered already holding the winner's token, and the "did the access token change" comparison had nothing to compare. It failed — correctly — with `transient`, which is what sent me looking. The fix is that the winner's write happens from inside the injected wait, so it lands where a real one would: after this contender has read the store and lost the lock. The same insight is what makes the two-process test deterministic (deviation 6). **Every wait in this module is a window a test can write into, and it is the only window that reproduces the real ordering.**

**The mutation harness had to run after the GREEN commit, not before.** Plan 03-05 recorded this the hard way: `git checkout --` on an untracked file is a silent no-op, so mutations accumulate and the harness reports a suite catching things it is not. Both mutation runs here were made against committed files and restored with `git checkout`, and both were re-verified green afterwards.

**The two-process test costs 0.10 seconds, which looked too fast to be real.** It is real — the child writes a result file that only it can write, and the parent asserts `child.wait(60) == 0` before reading it. Warm bytecode caches and a child that does almost nothing but import and contend are why. Recorded because the instinct to distrust it is right, and the two assertions that make it non-vacuous are the ones to check.

## Requirements

**`AUTH-15` is complete and is marked complete.** It is the only one of this plan's four ids that no later plan in this phase declares, and everything it asks for is delivered and tested: the re-read from disk, the byte-for-byte comparison, the adoption, and the absence of any re-authorisation signal on the adopt path. Four tests cover it, and removing the comparison turns five red.

**`AUTH-13` is delivered here and deliberately left unticked.** The automated test it asks for exists and is the headline of this plan. But `03-13` also declares it, for the half this plan cannot reach: what is proven here is that the add-on persists and re-sends whatever the provider returns, and what `03-13` proves is that the live provider returns something new. Ticking it now would let the phase finish with the live pass unrun and the record saying otherwise. This is the same shared-id rule `03-05` had to enforce by hand, and it is enforced by hand again here.

**`AUTH-16` is delivered in part and left unticked.** The predicate, the threshold and the transport-versus-grant classification are all here and tested. What is not here is the thing the requirement's own words describe — "a proactive refresh runs on Kodi startup" — because nothing in this plan runs at startup or knows that Kodi exists. `03-10` wires this into the service and declares the id; it is the last declaring plan and it is the one that should tick it.

**`AUTH-12` was already complete before this plan ran,** marked by `03-01`, which built `merge_token_response`. It is still declared by `03-08` and `03-13`. Its mark was not made by this plan and has not been changed by it; this plan's contribution is that the merge is now actually *called* on the refresh path, and that `test_a_response_without_a_refresh_token_keeps_the_stored_one` proves it end to end rather than at the merge function alone.

**Marks kept: `AUTH-15` only.** `.planning/REQUIREMENTS.md` shows exactly two changed lines, both `AUTH-15`, one in the checklist and one in the traceability table. Verified with `git diff --stat` before committing, per the defect `03-05` found.

## Known Stubs

None. No placeholder, TODO, `FIXME` or hardcoded empty value in either file. Every branch in `refresh.py` is reachable and every one of them is covered by a named test.

The five failing assertions in `tests/test_auth_gates.py` are unchanged from the baseline this plan inherited (167 passed / 5 failed / 1 skipped → 204 / 5 / 1). They are `03-03`'s red-by-construction gates, their owners are named in that plan's Gate State table, none of them belongs to this plan and none was touched.

## Threat Flags

None. No new network endpoint (the token endpoint is `03-01`'s constant), no new auth path beyond the one this plan is for, no new file access pattern (the store's own `read` and `write`) and no schema change. All five registered threats are addressed:

| Threat | Disposition | Where |
|---|---|---|
| T-03-29 rotated token discarded | mitigate | The exchange goes through `store.merge_token_response` and nothing else; `test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens` asserts the persisted value changed, and the Pitfall 3 mutation turns it red |
| T-03-30 invalid grant on a lost race | mitigate | `store.read` after the refusal, and `rotated != used` byte-for-byte before any re-authorisation outcome is produced; four tests, and dropping the comparison turns five red |
| T-03-31 transient failure marks re-auth | mitigate | Three outcomes; only a provider grant refusal with a store that did not move produces `NEEDS_REAUTHORISATION`. Five failure shapes swept, each asserting the negative and asserting the blob unchanged |
| T-03-32 rotation logging | mitigate | `fingerprint()` returns eight characters and an ellipsis, with the reason at its definition. `test_the_rotation_log_shows_eight_leading_characters_and_no_more` asserts the whole token is absent, the first eight are present, and the ninth is not |
| T-03-33 lock held through a failure | mitigate | `lock.release()` is in a `finally`; `test_the_lock_is_released_when_the_exchange_raises` asserts the lock file is gone after a raising port |

## User Setup Required

None.

## Next Phase Readiness

Ready. Four things the following plans need from here, and one of them is a live coupling that no test in this file can enforce:

- **Plan 03-08 must actually build the refresh's `Request` with `refresh.REQUEST_TRIES`, `refresh.REQUEST_DELAY_SECONDS` and `refresh.REQUEST_BACKOFF`.** The constants and their arithmetic are here and pinned against `RefreshLock.LIFETIME_SECONDS`, but this package never constructs a transport, so nothing here can check that the Kodi layer passed them. A refresh built on the transport's defaults has a 155-second worst case against a 90-second lock, and the failure mode is a broken lock on a live refresh — silent, intermittent, and exactly what `03-04` set that constant to prevent.
- **Plan 03-10 gets `should_refresh` and the three outcomes.** The contract is: call `should_refresh(blob)` per account, and only when it says yes call `refresh(...)` with a `RefreshLock` on that account's lock file, the Kodi session id, `Monitor().waitForAbort` as the sleep, and the transport's post. Then: `SUCCEEDED` → nothing to do; `TRANSIENT` → nothing to do, try next start; `NEEDS_REAUTHORISATION` → write `needs_reauth` into the *account record* (not the token file, which may be the unreadable thing) and optionally notify. `AUTH-17` still forbids the service from opening a dialog, and nothing here opens one.
- **Plan 03-09's renderer gets `Refreshed.failure` when there is one**, which is the same `errors.Failure(outcome, code, admin_must_act)` triple `03-05` specified. `failure` is `None` on every outcome but `NEEDS_REAUTHORISATION`, and `failure.code` can be empty — `03-05`'s summary already flags that 30044 has a `%s` in it and that the empty case belongs to the screen.
- **The browse phase inherits this classification rather than inventing a second one.** "Signed out" versus "the network is down" is the same three-way split, and it is already made in one place.

`refresh.py` runs on Python 3.8 (Kodi 19–21) and 3.14 (Kodi 22). It uses `collections.namedtuple`, `frozenset`, percent formatting and nothing newer; there is no f-string, no walrus and no positional-only parameter in it.

## Self-Check: PASSED

Both created files exist on disk (`resources/lib/auth/refresh.py`, `tests/test_refresh.py`); all four task commits (`5396b4d`, `8991333`, `65b1236`, `3b10fdb`) resolve in `git log`; the working tree was clean of unintended changes before the documentation commit, and `git diff -- .planning/REQUIREMENTS.md` showed exactly the two `AUTH-15` lines.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
