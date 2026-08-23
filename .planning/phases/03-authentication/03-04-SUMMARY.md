---
phase: 03-authentication
plan: 04
subsystem: auth
tags: [file-locking, o-excl, stale-lock, sub-interpreters, multi-account, path-traversal, python38]

requires:
  - phase: 03-authentication
    provides: "Plan 03-01's resources/lib/auth/ package — the atomic token store this lock protects, the tmp_path store fixtures, and the no-Kodi-import property that lets a filesystem primitive be tested without a stub library"
  - phase: 03-authentication
    provides: "Plan 03-03's tests/test_auth_gates.py::test_no_forbidden_lock_primitives — the AST sweep that keeps fcntl and threading.Lock out of this package, green before this plan and still green after it"
provides:
  - "resources/lib/auth/lock.py — RefreshLock: exclusive-create acquire, the two-signal stale breaker, the backwards-clock guard, the race-safe break, touch and a tolerant release"
  - "store.validate_account_key / accounts_dir / token_path / lock_path / remove_account — one token file and one lock file per account, under a validated key"
  - "tests/test_refresh_lock.py — 28 tests including two-thread and two-process serialisation, both staleness signals and the future-dated guard"
  - "The proof that the loser adopts rather than exchanges: tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write"
affects: [03-05, 03-08, 03-10, 03-11, 03-13, browse-phase, multi-account]

tech-stack:
  added: []
  patterns:
    - "The lock is a filesystem name, not a Python object and not a record lock — the only primitive indifferent to which sub-interpreter is asking"
    - "Staleness answers two questions with two signals, and neither of them is process liveness"
    - "A key that will become a filename is validated against an allow-list alphabet and rejected, never sanitised"
    - "A wait is injected so the only correct sleep inside Kodi (waitForAbort) can be the production one and a capped no-op can be the test one"

key-files:
  created:
    - resources/lib/auth/lock.py
    - tests/test_refresh_lock.py
  modified:
    - resources/lib/auth/store.py
    - tests/test_token_store.py

key-decisions:
  - "LIFETIME_SECONDS is 90, set against the 65-second worst case of the short refresh profile plan 03-08 installs, with the transport's own 155-second default-profile computation recorded beside it and named as a load-bearing dependency"
  - "The future-dated guard carries a one-second tolerance, because the filesystem's timestamp and time.time() are not read through the same path and a file touched a moment ago can read back marginally ahead — without it the guard becomes a second breaker that fires on healthy locks"
  - "The future-reading count is consecutive, not cumulative: a count that survived an intervening healthy reading would break a live lock on the strength of one stale observation"
  - "release() unlinks only when this instance actually holds the lock, so an instance that lost the race cannot remove the winner's file"
  - "An unreadable or half-written lock file falls back to the age signal rather than counting as stale, because a lock file is created and then written and a contender can read it in the gap"
  - "The break is bounded by MAX_BREAKS and falls through to the wait when the rename fails, so a filesystem that refuses to rename an open file produces a refusal rather than a hot spin"
  - "An unsafe account key is rejected, never sanitised: a sanitiser maps two different keys onto one filename, which is the cross-account leak AUTH-20 exists to prevent arriving by a different road"

patterns-established:
  - "Pattern 1: a two-process property is proven with exactly one spawn, coordinated through files — the suite budget is two seconds and a multi-second lock test is the first thing anyone stops running"
  - "Pattern 2: a design decision that a later reader is likely to 'harden' is written into the source in the words that explain why hardening it is worse"
  - "Pattern 3: a validator is asserted at every entry point that could forget to call it, not only against the validator itself"
  - "Pattern 4: a test added after its implementation is proven non-vacuous by mutating the implementation and watching it fail"

requirements-completed: [AUTH-14, AUTH-20]

coverage:
  - id: D1
    description: "Two contenders in one process are serialised, and the second sees the first's write rather than performing its own exchange"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_two_threads_in_one_process_never_interleave"
        status: pass
      - kind: integration
        ref: "tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two processes serialise on the same lock, which is the half a threading.Lock cannot do and an fcntl record lock would appear to do while doing the opposite"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_two_processes_serialise"
        status: pass
    human_judgment: false
  - id: D3
    description: "The lock is an exclusive create at mode 0600 carrying the session identifier and nothing else, and neither forbidden primitive is reachable from the package"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_the_lock_is_created_exclusively_at_mode_0600"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_the_lock_file_carries_the_session_and_nothing_else"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_no_forbidden_lock_primitives"
        status: pass
    human_judgment: false
  - id: D4
    description: "A lock recorded under a previous Kodi session is stale on sight, with no waiting at all, however recently it was touched"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_a_lock_from_a_previous_session_is_stale_immediately"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_a_previous_session_lock_is_broken_however_recently_it_was_touched"
        status: pass
    human_judgment: false
  - id: D5
    description: "Age decides staleness within one session, from the lock file's own modification time, and the breaker never asks whether a process is alive"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_a_lock_older_than_the_lifetime_is_broken"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_a_lock_younger_than_the_lifetime_is_not_broken"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_the_breaker_never_asks_whether_a_process_is_alive"
        status: pass
    human_judgment: false
  - id: D6
    description: "A modification time in the future is unknown rather than fresh: re-read once, then broken, so a backwards clock step cannot make a lock permanent — and a single future reading does not arm the breaker for the rest of the wait"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_a_future_dated_lock_is_not_treated_as_fresh"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_a_future_dated_lock_that_becomes_sane_is_left_alone"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_one_future_reading_does_not_arm_the_breaker_for_the_whole_wait"
        status: pass
    human_judgment: false
  - id: D7
    description: "The lifetime exceeds the worst case of the request the lock protects, and the arithmetic and its owning plan are recorded in the source so the dependency cannot be undone silently"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_the_lifetime_exceeds_the_refresh_worst_case_and_says_why"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_the_module_records_that_an_imperfect_breaker_is_deliberate"
        status: pass
    human_judgment: false
  - id: D8
    description: "Losing the race is a return value, the break leaves no scratch behind and recreates rather than adopting, and a shutdown ends the wait immediately"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_losing_the_race_returns_false_rather_than_raising"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_breaking_leaves_no_scratch_behind"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_the_break_recreates_rather_than_adopting"
        status: pass
      - kind: unit
        ref: "tests/test_refresh_lock.py::test_a_shutdown_ends_the_wait_immediately"
        status: pass
    human_judgment: false
  - id: D9
    description: "Each account has its own token file and its own lock file; neither account's write is visible in the other's file and two accounts refreshing at once do not contend"
    requirement: "AUTH-20"
    verification:
      - kind: unit
        ref: "tests/test_token_store.py::test_neither_accounts_write_is_visible_in_the_others_file"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_two_accounts_refreshing_at_once_do_not_contend"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_two_accounts_get_two_token_files_and_two_lock_files"
        status: pass
    human_judgment: false
  - id: D10
    description: "Removing an account removes both of its files and a re-added account inherits no blob"
    requirement: "AUTH-20"
    verification:
      - kind: unit
        ref: "tests/test_token_store.py::test_removing_an_account_removes_its_token_and_its_lock"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_a_re_added_account_starts_with_nothing_inherited"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_removing_one_account_leaves_the_other_untouched"
        status: pass
    human_judgment: false
  - id: D11
    description: "The account key is asserted filename-safe rather than trusted, at every entry point that could join it into a path"
    requirement: "AUTH-20"
    verification:
      - kind: unit
        ref: "tests/test_token_store.py::test_an_unsafe_account_key_is_rejected (13 parameters)"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_every_path_producer_validates_before_it_joins (4 parameters)"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_the_subject_claim_out_of_an_identity_token_is_an_acceptable_key"
        status: pass
    human_judgment: false
  - id: D12
    description: "The isolated-cache-keys clause of AUTH-20 has no cache to isolate in this phase and is inherited by the browse phase, which must key its listing cache by account from the start"
    requirement: "AUTH-20"
    verification: []
    human_judgment: true
    rationale: "There is nothing here to assert against. The only cache consumers in the tree belong to a subsystem scheduled for deletion and their databases are global rather than per-account, so the clause is a constraint on a phase that has not been built. It is recorded in the ROADMAP against the browse phase; whether that phase honours it can only be checked when it lands (D-09, Finding D)"

duration: 20min
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 04: The Refresh Lock and the Per-Account Layout Summary

**Two token refreshes can no longer both write: an exclusive create excludes contenders a record lock would silently admit, a two-signal breaker clears a lock left by a crashed session without ever asking whether Kodi is running, and every account now owns a token file and a lock file under a key that is asserted filename-safe rather than trusted.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-08-23T03:17Z
- **Completed:** 2026-08-23T03:37Z
- **Tasks:** 2 of 2
- **Files created:** 2
- **Files modified:** 2
- **Suite:** 139 passed, 5 failed by construction, 1 skipped, 1.94s

## Accomplishments

- **The exclusion is proven against both contenders, not argued from the mechanism.** `test_two_threads_in_one_process_never_interleave` asserts the exact sequence `enter-A, exit-A, enter-B, exit-B`, and `test_two_processes_serialise` spawns a real second interpreter which reports back that it was refused while the parent held the lock *and* that it got in once the parent let go. Both halves are asserted: a lock that always refuses would pass the first on its own.
- **The property the lock actually exists for is now a test.** `test_the_second_contender_sees_the_first_contenders_write` races two contenders through acquire → read → exchange → write → release and asserts that exactly one exchange happened and the loser used what the winner wrote. That is AUTH-14's real requirement — serialisation is only the means — and mutating the acquire to drop `O_EXCL` turns it into `assert 2 == 1`.
- **The breaker answers two questions with two signals and neither of them is process liveness.** A differing session identifier means the holder is gone, and costs the caller not one wait — asserted by a recording sleep whose call list must be empty. Age means the holder is stuck, read from the lock file's own modification time so there is one clock on both sides of the comparison. `test_the_breaker_never_asks_whether_a_process_is_alive` reads the source back and rejects the textbook liveness check outright, because under Kodi that check never fires and a breaker that never breaks is worse than none.
- **The backwards-clock case is handled as a normal event, which on a box with no real-time clock it is.** A future-dated modification time is treated as *unknown*: re-read once, and broken on the second look, so it can neither be fresh forever nor be broken the instant a clock steps forward under a live holder. Three tests cover the three outcomes, including the one this executor discovered the hard way — see the deviations.
- **The lifetime is a computed number with its dependency written into the source.** Ninety seconds, against the 65-second worst case of the `tries=2, delay=5` profile plan 03-08 installs, with the transport's own `4*30 + 5 + 10 + 20 = 155` recorded beside it. `test_the_lifetime_exceeds_the_refresh_worst_case_and_says_why` fails if the number, the arithmetic or the owning plan leaves the file — so nobody can restore the default retry profile without meeting this constant on the way.
- **A key that becomes a filename is rejected, never cleaned up.** Thirteen unsafe keys — `..`, `a/b`, `a\b`, an absolute path, a NUL byte, a bare dot — are refused, and all three path producers are asserted to validate rather than only the validator itself. The identity token's real `sub` claim is asserted to *pass*, because a gate that fails closed on every sign-in is not a gate.

## Task Commits

1. **Task 1: The lock and its two-signal staleness test (TDD)** — `12feb03` (test, RED) → `dd965cd` (feat, GREEN)
2. **Task 2: One token file and one lock file per account (TDD)** — `8c99899` (test, RED) → `bbed8c7` (feat, GREEN)

## Files Created/Modified

- `resources/lib/auth/lock.py` — `RefreshLock`, `LIFETIME_SECONDS`, `POLL_SECONDS`, `MAX_BREAKS`, `FUTURE_TOLERANCE_SECONDS`, `acquire`, `touch`, `release`, and the private `_create` / `_staleness` / `_recorded_session` / `_break`. Imports `json`, `os`, `time`, `uuid` and nothing else.
- `tests/test_refresh_lock.py` — 28 tests: exclusion across threads and processes, both staleness signals, the future-dated guard and its tolerance, the shutdown path, the break's race-safety, and two source assertions that keep the reasoning in the file.
- `resources/lib/auth/store.py` — added `ACCOUNTS_DIRNAME`, `TOKEN_SUFFIX`, `LOCK_SUFFIX`, `SAFE_ACCOUNT_KEY`, `MAX_ACCOUNT_KEY_LENGTH`, `validate_account_key`, `accounts_dir`, `token_path`, `lock_path`, `remove_account`. The existing `read` / `write` / `merge_token_response` are untouched.
- `tests/test_token_store.py` — 30 new tests (17 → 47) covering the layout, removal, key validation and the two-contender integration property.

## Decisions Made

**Ninety seconds, not sixty and not one hundred and eighty.** The research offered both. A lifetime under the request's worst case breaks the lock of a *live, working* refresh, which produces exactly the double write the lock exists to prevent; a lifetime of three minutes means a genuinely wedged refresh blocks the other side for three minutes. The resolution is the one the research recommended — give the refresh its own short profile (plan 03-08) so the worst case is 65 seconds, and set the lifetime just clear of it. The number is in the source with the arithmetic and a shouted note that the dependency is load-bearing, and a test fails if either leaves.

**`release()` unlinks only when this instance holds the lock.** The research's sketch unlinks unconditionally. That is wrong for an instance that lost the race: its `release()` in a `finally` would remove the *winner's* lock file while the winner was still working. Holding is tracked explicitly and asserted by `test_release_without_an_acquire_removes_nothing`. The unlink still tolerates an absent file, because a holder whose lock was judged stale and broken is a case the design accepts rather than an error.

**An unreadable lock file falls back to the age signal.** A lock file is created and then written, so a contender can read it in the gap and see nothing at all. Reading that as "no session, therefore stale" would break a lock a microsecond after it was taken — the worst possible time. When the session cannot be read, age decides alone.

**The break is bounded and gives up gracefully.** `os.replace` on a file another holder still has open succeeds on POSIX and fails on Windows. A break that fails and then `continue`s is an unbounded hot spin, so a failed break falls through to the ordinary wait, and consecutive breaks are capped. On the target device neither guard ever fires; on the development host the first one does, and without it this suite would hang rather than fail.

**Rejection, not sanitisation, for the account key.** A sanitiser that strips separators maps `a/b` and `ab` onto one file — two accounts sharing one credential store, which is precisely the cross-account leak AUTH-20 exists to prevent, arriving by a different road. The error message names the offending characters rather than echoing the key, because the key identifies a person and the message may end up in a log.

## Deviations from Plan

### 1. [Rule 1 — Bug] The future-dated guard fired on healthy locks, and the count had to become consecutive

- **Found during:** Task 1, GREEN
- **Issue:** `test_a_future_dated_lock_that_becomes_sane_is_left_alone` failed: the acquire broke a lock whose clock had been corrected. Two causes compounded. First, `st_mtime` for a file touched a moment ago can read back marginally *ahead* of `time.time()` — they are not written and read through the same path — so a bare `age < 0` test intermittently reported a healthy lock as future-dated. Second, the re-read counter was cumulative over the whole `acquire`, so one such reading armed the breaker for every subsequent iteration; the traced run showed 201 staleness readings ending in a break that should never have happened.
- **Fix:** `FUTURE_TOLERANCE_SECONDS = 1.0`, so only a genuine step registers, and the counter now counts *consecutive* unknown readings and resets on any other verdict. Both are stated in comments as the failure they prevent.
- **New tests:** `test_a_lock_a_hair_ahead_of_the_clock_is_not_read_as_a_clock_step`, `test_the_future_tolerance_stays_far_below_the_lifetime` (so the tolerance cannot be widened into a hole in the age signal), `test_one_future_reading_does_not_arm_the_breaker_for_the_whole_wait`.
- **Files modified:** `resources/lib/auth/lock.py`, `tests/test_refresh_lock.py`
- **Commit:** `dd965cd`

### 2. [Rule 2 — Missing critical functionality] The break can fail, and the loop had to survive it

- **Found during:** Task 1, GREEN
- **Issue:** The planned sequence is rename-aside then retry the create, and on a failed rename the loop `continue`d — judging the lock stale again, failing to rename again, forever. `os.replace` on a file another handle still has open is refused on Windows, so the first test to hold a lock and break it from a second instance would have spun until the runner was killed rather than failing.
- **Fix:** `_break()` returns a boolean; a failed break falls through to the ordinary wait-and-deadline path, and `MAX_BREAKS` caps consecutive breaks so a peer that keeps recreating stale files produces a refusal rather than a spin. Both carry comments saying which host behaviour they exist for.
- **Files modified:** `resources/lib/auth/lock.py`
- **Commit:** `dd965cd`

### 3. [Rule 2 — Missing critical functionality] `release()` learned whether it holds anything

- **Found during:** Task 1, GREEN
- **Issue:** Following the research sketch, `release()` unlinked unconditionally. A loser's `release()` in a `finally` therefore deleted the winner's lock file — turning the ordinary losing path into a second, silent breaker.
- **Fix:** An explicit held flag, set on a successful create and cleared on release. Covered by `test_release_without_an_acquire_removes_nothing` and `test_release_is_safe_to_call_twice`.
- **Files modified:** `resources/lib/auth/lock.py`, `tests/test_refresh_lock.py`
- **Commit:** `dd965cd`

### 4. [Scope] The release-tolerance test injects the disappearance rather than staging it

- **Found during:** Task 1, GREEN
- **Issue:** The natural way to test "release tolerates a lock someone else broke" is to remove the file while a handle is open. POSIX allows that and Windows refuses it, so the staged version would have tested the lock on one platform and the platform on the other.
- **Fix:** `os.unlink` is monkeypatched to raise `FileNotFoundError` for the duration, which tests the tolerance itself and runs identically everywhere. The reason is in the test's docstring.
- **Files modified:** `tests/test_refresh_lock.py`
- **Commit:** `dd965cd`

### 5. [Scope] One test was written after its implementation, so it was proven by mutation

- **Found during:** Task 2, after GREEN
- **Issue:** `test_the_second_contender_sees_the_first_contenders_write` asserts the plan's headline truth — the second contender does not perform its own exchange — which the two tasks' own tests only covered in halves. It was added after both implementations existed, so it never had a RED phase.
- **Fix:** Rather than accept an untested test, `_create` was mutated from `O_EXCL` to `O_TRUNC` and the test run: `assert 2 == 1`, both contenders exchanged. `git checkout` restored the file and the test went green again.
- **Files modified:** `tests/test_token_store.py`
- **Commit:** `bbed8c7`

### 6. [Record accuracy] The vendor gate count is twenty-three, not twenty-two

- **Found during:** Final verification
- **Issue:** The plan's verification block expects `tests/test_vendor_gates.py` to report twenty-two green. It reports twenty-three.
- **Fix:** None needed — plan 03-03 added `test_runbook_contains_aadsts7000218` to that file after this plan was written. Twenty-three is the correct current count and all are green.

---

**Total deviations:** 6 (1 × Rule 1, 2 × Rule 2, 2 scope, 1 record accuracy)
**Impact on plan:** None on scope or shape. All six were found by the plan's own tests or by running its own verification; deviations 1–3 are the difference between a lock that passes its tests and a lock that works.

## Issues Encountered

**The future-dated guard was the hardest part of the plan, and not for the reason the research expected.** The research's concern is a television box stepping its clock backwards at boot. The failure that actually appeared was the opposite and much smaller: a file touched *right now* reading back a fraction of a second ahead of `time.time()`. A guard written for the dramatic case fired constantly on the mundane one, and because it fires by *breaking a lock*, its failure mode is the exact outcome the whole module exists to prevent. Both the tolerance and the consecutive-count fix are pinned by tests, and one of those tests caps the tolerance at a tenth of the lifetime so a later reader cannot widen it until the age signal means nothing.

**Two of the three implementation bugs came from following the research's sketch literally.** The sketch's `release()` unlinks unconditionally and its `acquire()` loop `continue`s after a break with no failure path. Both are correct as illustrations of the shape and wrong as code, and both produce silent damage rather than an exception — a deleted winner's lock and an infinite loop. This is worth recording because the sketch is otherwise excellent and it would be easy for a later plan to treat it as reference implementation.

**The suite budget survived a real process spawn.** The two-process test costs 0.14s and the whole new lock file 0.47s, but eight tests whose entire point is that an acquire is *refused* must each burn their full timeout. At the first draft's 0.05s each that put the suite at 2.26s; a `REFUSED = 0.02` constant with a comment explaining that the number is the price of every refusal test brought the total back to 1.94s — identical to the pre-plan baseline.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR |
|------|-----|-------|----------|
| 1 | `12feb03` — `ModuleNotFoundError: resources.lib.auth.lock` | `dd965cd` | not needed |
| 2 | `8c99899` — 29 failed, 17 passed | `bbed8c7` | not needed |

The one test added outside a RED phase (deviation 5) was proven non-vacuous by mutation instead.

## Known Stubs

None. No placeholder, TODO or hardcoded empty value in either file.

## Threat Flags

None. No new network endpoint, no new auth path, and the one new file-access pattern — a lock file beside each token file — is what the plan's `<threat_model>` registers. All five registered threats are addressed:

| Threat | Disposition | Where |
|---|---|---|
| T-03-16 account key to path | mitigate | `store.validate_account_key`, asserted at all three producers and against 13 unsafe keys |
| T-03-17 stale lock never broken | mitigate | Two signals, neither depending on process liveness, plus the future-dated guard and its tolerance |
| T-03-18 double break under a race | accept | Rename-aside-then-recreate; the residual case is absorbed by plan 03-08's adopt-the-winner path, and the source says so in those words |
| T-03-19 lock file contents | mitigate | `{"session": ...}` and nothing else, mode 0600 at creation, both asserted |
| T-03-20 cross-account leakage | mitigate | One file and one lock per key, asserted by writing two accounts and reading both back |

## Deferred to the Browse Phase

The isolated-cache-keys clause of AUTH-20 has **nothing to isolate in this phase**, and no cache was invented here in order to have something to isolate (D-09, Finding D). The only cache consumers in the tree belong to a subsystem scheduled for deletion, and their databases are global rather than per-account. The constraint is inherited by the browse phase, which builds the listing cache and must key it by account **from the start** — retrofitting a per-account key onto a shipped global cache means either a migration or a silent cross-account listing leak. This is already recorded in `ROADMAP.md` against that phase.

## User Setup Required

None.

## Next Phase Readiness

Ready. What the following plans need from here:

- **Plan 03-08 (the refresh path)** owns three things this plan depends on and one it hands over. It must (a) give the token refresh a `tries=2, delay=5` request profile — the 90-second lifetime is set against that and the source says so; (b) build the adopt-the-winner path on `invalid_grant`, which is the backstop that lets this breaker be imperfect; and (c) decide what the refresh does when `store.read` raises on a corrupt file. The shape of the caller loop is written out in `test_the_second_contender_sees_the_first_contenders_write` and can be lifted from there.
- **The Kodi layer** supplies both injected values. The session identifier is a `uuid4().hex` written to a home window property at service startup — window 10000 is shared across every sub-interpreter in one Kodi session and is cleared when Kodi restarts, which is what makes signal 1 work. The wait is `xbmc.Monitor().waitForAbort`; passing `time.sleep` instead would hold a shutdown open for the whole timeout, and `test_a_shutdown_ends_the_wait_immediately` is what that contract rests on.
- **The multi-account plans** get `accounts_dir(profile, create=True)`, `token_path`, `lock_path` and `remove_account`. The profile path must arrive already translated — nothing under `resources/lib/auth/` calls `xbmcvfs.translatePath` or knows that `special://` exists.
- **The 90-second lifetime is a live coupling, not a constant.** Anything that changes the refresh's retry profile must move it.

Everything added here runs on Python 3.8 (Kodi 19–21) and 3.14 (Kodi 22); no syntax newer than 3.8 is used, and `re.Pattern.fullmatch`, `os.fspath` and `os.makedirs(exist_ok=True)` are all available across that range.

## Self-Check: PASSED

Both created files exist on disk, both modified files carry the new symbols, and all four task commits resolve in `git log`.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
