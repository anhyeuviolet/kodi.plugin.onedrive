---
phase: 03-authentication
plan: 01
subsystem: auth
tags: [oauth2, device-code, rfc8628, microsoft-entra, msgraph, atomic-write, pytest, python38]

requires:
  - phase: 01-vendor-lift
    provides: "The vendored clouddrive_common OAuth2 reader whose token blob contract this store must satisfy, and the no-Kodi-import test convention in tests/test_vendor_gates.py"
provides:
  - "resources/lib/auth/ — the first package in the tree with zero xbmc* imports, testable without a stub library"
  - "device_code.py — request_device_code, poll_once, next_interval, read_identity_claims, and the two-member CONTINUE_ON allow-list"
  - "store.py — read, atomic write at mode 0600, and merge_token_response with the keep-the-previous-refresh-token rule"
  - "tests/conftest.py — a scripted fake token endpoint and tmp_path-backed store fixtures the next four plans extend"
  - "The injected HTTP port contract: post(url, fields) -> (status, body)"
affects: [03-02, 03-03, 03-04, 03-05, refresh-lock, error-map, signin-dialog, multi-account]

tech-stack:
  added: []
  patterns:
    - "Kodi behind a port: the auth package receives an HTTP callable rather than importing urllib or xbmc"
    - "Poll classification returns (state, payload); the caller owns the loop, the interval and the deadline"
    - "Temp-sibling + fsync + os.replace for every credential write"

key-files:
  created:
    - resources/lib/auth/__init__.py
    - resources/lib/auth/device_code.py
    - resources/lib/auth/store.py
    - tests/conftest.py
    - tests/test_device_code.py
    - tests/test_token_store.py
  modified: []

key-decisions:
  - "One authority constant (/common) for both account classes, with no branch and no user-facing authority setting — the spike proved it across three live runs on two account types"
  - "A 400 with an unparseable body raises TransportError rather than classifying as a terminal protocol error, because a dead grant and a proxy error page demand opposite responses"
  - "The poll interval is state the caller carries; next_interval(interval, state) returns the next one, which is the only shape in which the RFC 8628 slow_down increase stays permanent"
  - "store.read raises on a corrupt file rather than returning {}, because a silent {} would look like a first sign-in and the next merge would drop a refresh token that was only unreadable"
  - "New files carry the project GPL banner without a copyright line, following tests/test_vendor_gates.py, rather than the verbatim entrypoint.py banner that would misattribute them to the 2017 upstream author"

patterns-established:
  - "Pattern 1: the HTTP port is a plain callable, post(url, fields) -> (status, body), injected at every call site — no socket is opened in any test"
  - "Pattern 2: the fake endpoint is a scripted queue that fails loudly when a loop polls once more than the test intended"
  - "Pattern 3: a filesystem property is tested against a real tmp_path directory, never a mock"
  - "Pattern 4: a mode assertion that a host does not enforce is made against the call the code makes (a recorded os.open) rather than against the resulting stat"

requirements-completed: [AUTH-04, AUTH-09, AUTH-10, AUTH-11, AUTH-12, AUTH-21]

coverage:
  - id: D1
    description: "One end-to-end path without Kodi: device code requested, one 400 pending poll read as protocol, one successful poll, merged, written atomically, read back identical"
    requirement: "AUTH-10"
    verification:
      - kind: unit
        ref: "tests/test_device_code.py::test_end_to_end_pending_then_token_is_merged_written_and_read_back"
        status: pass
    human_judgment: false
  - id: D2
    description: "The scope string is exactly the locked set and the authority is one constant for both account classes"
    requirement: "AUTH-04"
    verification:
      - kind: unit
        ref: "tests/test_device_code.py::test_scope_string_is_the_locked_set"
        status: pass
      - kind: unit
        ref: "tests/test_device_code.py::test_no_write_broad_or_application_wide_grant_is_requested"
        status: pass
      - kind: unit
        ref: "tests/test_device_code.py::test_one_authority_serves_both_account_classes"
        status: pass
    human_judgment: false
  - id: D3
    description: "The poll continuation is an allow-list of exactly two codes; an error code that exists in no reference is terminal"
    requirement: "AUTH-09"
    verification:
      - kind: unit
        ref: "tests/test_device_code.py::test_an_error_code_that_exists_in_no_reference_is_terminal"
        status: pass
      - kind: unit
        ref: "tests/test_device_code.py::test_continue_set_has_exactly_two_members"
        status: pass
    human_judgment: false
  - id: D4
    description: "A slow_down raises the interval by five seconds and it never comes back down on subsequent polls"
    requirement: "AUTH-09"
    verification:
      - kind: unit
        ref: "tests/test_device_code.py::test_the_slow_down_increase_is_permanent"
        status: pass
    human_judgment: false
  - id: D5
    description: "A token response omitting refresh_token keeps the previously stored one; one carrying it replaces it"
    requirement: "AUTH-12"
    verification:
      - kind: unit
        ref: "tests/test_token_store.py::test_merge_keeps_the_previous_refresh_token_when_the_response_omits_one"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_merge_replaces_the_refresh_token_when_the_response_carries_one"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_an_empty_refresh_token_in_the_response_does_not_erase_the_stored_one"
        status: pass
    human_judgment: false
  - id: D6
    description: "The write goes through a uniquely-named sibling temporary file created exclusively at mode 0600, synced before os.replace; an interrupted write leaves the previous file byte-identical and no scratch behind"
    requirement: "AUTH-11"
    verification:
      - kind: unit
        ref: "tests/test_token_store.py::test_write_creates_the_file_exclusively_at_mode_0600"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_the_temporary_file_is_a_sibling_of_the_target"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_an_interrupted_write_leaves_the_previous_file_byte_identical"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py::test_an_interrupted_write_leaves_no_temporary_file_behind"
        status: pass
    human_judgment: false
  - id: D7
    description: "Identity-token claims are decoded for display and local keying only, with no signature validation and no authorization decision taken from them"
    requirement: "AUTH-21"
    verification:
      - kind: unit
        ref: "tests/test_device_code.py::test_identity_claims_are_decoded_for_display_and_keying"
        status: pass
      - kind: unit
        ref: "tests/test_device_code.py::test_identity_claims_survive_an_unpadded_payload"
        status: pass
    human_judgment: true
    rationale: "The tests prove the decode works and that no signature is checked; that nothing downstream ever treats a claim as an authorization fact is a property of every future caller and can only be held by review"
  - id: D8
    description: "Nothing under resources/lib/auth/ imports a Kodi module, so the suite needs no stub library and runs in under two seconds"
    verification:
      - kind: unit
        ref: "tests/test_device_code.py::test_nothing_in_the_auth_package_imports_kodi"
        status: pass
      - kind: automated_ui
        ref: "python -m pytest tests -q  (64 passed, 1 skipped in 0.48s)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 01: The Device-Code Tracer Summary

**A device code can now be requested, polled through a pending 400 to a token, merged onto whatever was stored before and written atomically to disk — all of it without Kodi, without a socket, and in under half a second.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-23T02:22Z
- **Completed:** 2026-08-23T02:47Z
- **Tasks:** 3 of 3
- **Files created:** 6 (3 shipped modules, 3 test files)
- **Suite:** 64 passed, 1 skipped, 0.48s

## Accomplishments

- **The vertical slice runs end to end.** `test_end_to_end_pending_then_token_is_merged_written_and_read_back` drives a scripted endpoint through request → pending → token → merge → write → read, and asserts the blob comes back identical. Every remaining plan in the phase expands sideways from this test.
- **`resources/lib/auth/` is the first package in the tree with zero `xbmc*` imports.** That is what makes behavioural tests possible at all here: no Kodistubs, no fixtures beyond `tmp_path`, and the whole suite still finishes in half a second, which was the property `tests/test_vendor_gates.py` set out to protect.
- **The two failure modes that are invisible until they are catastrophic are pinned by proof, not assertion.** A merge that drops a rotated refresh token and a write that dies mid-flight are both proven — the second by comparing the previous file's bytes before and after a write that fails during serialisation.
- **The allow-list is proven to be an allow-list.** A test drives the endpoint with `AADSTS_this_code_exists_in_no_reference` and asserts the poll stops. Under a stop-list that code polls a live Microsoft endpoint forever.
- **The measured values from the spike are encoded as measured values.** `expires_in` comes from each response (the fixture uses 3655 and 4491, never 3600), `verification_uri` comes from the response, and both granted-scope strings from the two account classes are in the fixtures so an equality comparison on a granted scope cannot survive a test run.

## Task Commits

1. **Task 1: One path end to end (tracer, TDD)** — `216c244` (test, RED) → `d2b2ece` (feat, GREEN)
2. **Task 2: The full allow-list, the permanent slow-down, the terminal classification (TDD)** — `dffb762` (test, RED) → `0a4afa0` (feat, GREEN)
3. **Task 3: The merge rules and the crash-safety property (TDD)** — `d2429ee` (test)

## Files Created/Modified

- `resources/lib/auth/__init__.py` — zero-byte package marker, matching `resources/__init__.py` and `resources/lib/__init__.py`
- `resources/lib/auth/device_code.py` — the four constants (authority, client id, scope, `CONTINUE_ON`), `request_device_code`, `poll_once`, `next_interval`, `read_identity_claims`, and `TransportError`
- `resources/lib/auth/store.py` — `read`, `write` (temp sibling → 0600 exclusive create → fsync → `os.replace`), `merge_token_response`
- `tests/conftest.py` — `FakeTokenEndpoint`, the response factory (device code, pending, slow_down, terminal, token, refresh, synthetic id_token), and the `store_dir` / `store_path` fixtures
- `tests/test_device_code.py` — 25 tests, including the end-to-end tracer
- `tests/test_token_store.py` — 17 tests plus one POSIX-only mode check

## Decisions Made

**One authority for both account classes.** `AUTHORITY` is a single constant pointing at `/common`. The spike ran the flow three times across a work/school account and a personal one and `/common` served both, so there is no authority branch, no `consumers` fallback, and no setting for a user to get wrong.

**A transport failure is not a dead grant.** `poll_once` raises `TransportError` when the endpoint answers a 400 with a body that will not parse as JSON, rather than classifying it terminal. The two mean opposite things — one says the account must be authorised again, the other says a proxy answered — and collapsing them signs the user out because their Wi-Fi dropped. On a TV with no keyboard that is the worst outcome the module can produce. This also lines up with the research's `AUTH-16/E` requirement that a `URLError` must not set `needs_reauth`.

**The poll interval is the caller's state.** `next_interval(interval, state)` takes the interval the caller holds and returns the next one. This is the only shape in which "increased by 5 seconds for this and all subsequent requests" (RFC 8628 §3.5) actually holds: a loop that recomputed the wait from the server's original `interval` each tick would undo the increase immediately.

**`store.read` raises on a corrupt file.** Returning `{}` would be indistinguishable from a first sign-in, and the next merge would then start from nothing and write a blob with no refresh token — losing a credential that was only unreadable, not gone. `{}` is returned for an *absent* file only.

**`merge_token_response` takes an optional `now`.** Production passes nothing and gets `time.time()`. The parameter exists so a test can pin the clock, which is what makes the `date` / `issued_at` assertion exact rather than approximate.

## Deviations from Plan

### 1. [Rule 2 — Correctness of attribution] New files carry the project GPL banner, not the verbatim `entrypoint.py` banner

- **Found during:** Task 1
- **Issue:** The plan says to copy the nineteen-line banner from `entrypoint.py` verbatim. That banner opens with `Copyright (C) 2017 Carlos Guzman (cguZZman)` and names the file as part of the Cloud Drive Common Module. Applied verbatim to six files written from scratch in 2026, it asserts an authorship that is not true.
- **Fix:** Used the sixteen-line banner that `tests/test_vendor_gates.py` already carries — the identical GPL-3.0 notice with the false copyright line and the wrong module name removed. That file is the only precedent in the tree for a newly authored source file, and the gate's actual requirement (the string `GNU General Public License` within the first 25 lines) is met.
- **Files:** all six created files, except the zero-byte `__init__.py`
- **Verification:** `python -m pytest tests/test_vendor_gates.py -q` — 22 passed, `test_gpl_headers_intact` included.
- **Committed in:** `d2b2ece`, `216c244`

### 2. [Rule 2 — Missing critical functionality] `tests/conftest.py` puts the repository root on `sys.path`

- **Found during:** Task 1
- **Issue:** `from resources.lib.auth import ...` resolves under `python -m pytest` (which puts the working directory on the path) but not under a bare `pytest`. A test file that only runs one of the two ways is a test file that silently stops being run.
- **Fix:** Four lines in `conftest.py` inserting the repository root, with a comment stating that this is legal only because the vendor gates exclude `tests/` from the shipped-source sweeps, and that the shipped tree must still never touch `sys.path` because Kodi places the add-on root there itself.
- **Verification:** `test_no_syspath_mutation` stays green; the file lives under the one top-level directory that sweep excludes by design.
- **Committed in:** `216c244`

### 3. [Scope] Task 3 required no change to `store.py`

- **Found during:** Task 3
- **Issue:** The plan lists `resources/lib/auth/store.py` among Task 3's files, but the tracer had already built the module whole, as Task 1's action text specified. Every Task 3 test passed on first run.
- **Fix:** Rather than accept a green RED phase, the implementation was mutated three times to confirm the new tests can fail: dropping the refresh-token carry-over turned one test red, reversing the merge direction turned three red, and writing straight to the target instead of a temp sibling turned four red. The store was restored from git after each. Task 3 was then committed as a `test(...)` commit.
- **Verification:** three mutation runs, each followed by `git checkout -- resources/lib/auth/store.py`; final suite 64 passed, 1 skipped.
- **Committed in:** `d2429ee`

---

**Total deviations:** 3 (2 × Rule 2, 1 scope observation)
**Impact on plan:** None on scope or shape. Deviations 1 and 2 are corrections that make the plan's own intent hold; deviation 3 is the tracer working exactly as designed — the slice was production code, so the expansion task had nothing left to build in that module.

## Issues Encountered

**The headline AUTH-12 test did not pin the guard it appeared to pin.** `test_merge_keeps_the_previous_refresh_token_when_the_response_omits_one` survived the mutation that deleted the explicit carry-over block, because a response that *omits* the key is already handled by `dict.update` leaving the previous value alone. The explicit guard only fires when the response carries `refresh_token` as `''` or `None`. Rather than assume one test covered both, `test_an_empty_refresh_token_in_the_response_does_not_erase_the_stored_one` covers the guard and the original covers the merge direction — and the mutation runs confirm each catches its own mechanism.

**The 0600 assertion cannot be a stat check on this machine.** Development runs on Windows, which does not enforce POSIX mode bits, while the target is Android where from Android 11 the app's own data directory bypasses the storage abstraction layer and the mode genuinely applies. Split into two: a recorded `os.open` proving the call passes `0o600` with `O_CREAT | O_EXCL` (runs everywhere) and a masked stat check skipped on `nt` (runs on the platforms that enforce it). The mask, not an equality, so the failure names the exposure rather than a filesystem's bookkeeping bits.

## Tracer Feedback Gate

The tracer's `<verify>` was re-run end to end after its commit and before any expansion task: `pytest tests/test_device_code.py tests/test_token_store.py` green, `pytest tests/test_vendor_gates.py` 22 green, and the AST sweep reporting no Kodi import under the new package. No human-verify checkpoint was raised — the plan carries `autonomous: true`, declares no `checkpoint:*` task, and its entire verification surface is three commands with no URL, no UI and no device in it, so there is nothing a human could evaluate that the commands do not already answer.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR |
|------|-----|-------|----------|
| 1 | `216c244` — `ModuleNotFoundError: resources.lib.auth` | `d2b2ece` | not needed |
| 2 | `dffb762` — 5 failed, 20 passed | `0a4afa0` | not needed |
| 3 | `d2429ee` — no red; behaviour already built by the tracer, non-vacuity established by 3 mutations instead | n/a | not needed |

## Known Stubs

None. No placeholder, TODO or hardcoded empty value was left in any file this plan created.

## Threat Flags

None. No new network endpoint, auth path, file access pattern or schema change beyond what `<threat_model>` already registers. All six registered threats are addressed: T-03-01 and T-03-02 by the write sequence, T-03-03 by the comment and the absence of any authorization use, T-03-04 by the allow-list, T-03-05 by the server-supplied interval and the permanent increase, T-03-06 by a fixture set whose only credential-shaped strings are synthetic — asserted by `test_the_fake_endpoint_leaks_no_real_credential`, which reads `conftest.py` back and rejects anything JWT-shaped.

## User Setup Required

None — no external service configuration required. The embedded client id is the project's own registration, already verified live by the spike.

## Next Phase Readiness

Ready. The next plans have what they need:

- **The HTTP port contract** — `post(url, fields) -> (status, body)`. The real urllib adapter is still to be written; it must return `{'error': 'non_json_response', 'raw': ...}` when a body will not parse, which is the sentinel `poll_once` turns into `TransportError`, and it must pass `timeout=` or `test_all_http_calls_have_timeout` will fail it.
- **The poll loop's two clocks** — `poll_once` and `next_interval` are the pure half; the Kodi-side loop that owns `waitForAbort`, the countdown and the deadline is a later plan's work and must never call `time.sleep`.
- **The store** — `read`/`write`/`merge_token_response` are ready for `lock.py` and `refresh.py` to sit on top. Note that `store.read` raises on a corrupt file, so the refresh path needs a decision about that case.
- **The fixtures** — `tests/conftest.py`'s `FakeTokenEndpoint`, response factory and store fixtures are the harness the four remaining test files extend; `responses.refresh()` already exists and carries no `id_token`, which is what a real refresh looks like.

One caveat to carry forward: `resources/lib/auth/` runs on both Python 3.8 (Kodi 19–21) and 3.14 (Kodi 22), and nothing in it uses syntax newer than 3.8. That constraint applies to every file added to this package.

## Self-Check: PASSED

All 6 created files exist on disk; all 5 task commits resolve in `git log`.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
