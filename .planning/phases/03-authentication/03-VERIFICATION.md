---
phase: 03-authentication
verified: 2026-08-23T09:20:41Z
status: human_needed
score: 4/6 must-haves verified
behavior_unverified: 2
overrides_applied: 0
deferred:
  - truth: "Success criterion 4, cache-key clause: 'tokens and delta tokens and cache keys are isolated per account'"
    addressed_in: "Phase 4"
    evidence: "ROADMAP.md Phase 4, 'Inherited constraint from Phase 3 (recorded 2026-08-23)': \"Phase 3 delivered the token half and could not deliver the cache half... This phase builds the listing cache, so this phase owns that clause: key the cache by account from the first commit.\" Delta tokens are in fact isolated (stored on the drive record inside the per-account row); only the cache half is outstanding."
  - truth: "Success criterion 1, blocking-tenant clause: a refusing tenant produces a message naming the cause and the exact AADSTS code is recorded"
    addressed_in: "Phase 8 / release, or never"
    evidence: "ROADMAP.md Phase 3 criterion 1a: 'mark AUTH-18 unverified against a genuinely blocking tenant rather than claiming it passes'. The E5 Developer tenant hosting this registration permits the grant, so the refusal cannot be produced on demand. The map and its escape hatch exist and are tested."
behavior_unverified_items:
  - truth: "Success criterion 5: on expiry, 'Get a new code' arrives already focused"
    test: "On the TCL Android TV 12, open Add an account and leave the sign-in dialog until the server-supplied expiry elapses (the countdown reaches 0:00)."
    expected: "The body text swaps to the expired sentence, the second button becomes visible, and focus is already on it — pressing OK on the remote without moving the directional pad requests a new code. Cancel remains reachable."
    why_human: "The transition lives in QRDialogProgress.set_expired(), an xbmcgui.WindowXMLDialog subclass that cannot be constructed outside Kodi. No test in the suite touches it; presence of setFocus(button) is not evidence that focus landed there on a real skin. 03-14 skipped this row."
  - truth: "Success criterion 6: first run on the real target device, all six rows"
    test: "Resume the 03-14 checklist on the television: (a) drive plugin://plugin.onedrive.kn/?action=_dialog_smoke and confirm all three dialogs render from this add-on's own skin directory; (b) confirm two openings of the QR dialog log two different image paths; (c) confirm the background service starts at login; (d) pull the session log and run grep -c Traceback."
    expected: "Three dialogs render; two distinct qr-<hex>.png paths; the service thread starts; the traceback count is 0."
    why_human: "Four of the six rows were recorded NOT RUN by 03-14. Each requires a real Kodi runtime on the target hardware; the repository contains no instrument that can answer any of them."
human_verification:
  - test: "Expiry path on the television — let the sign-in code expire without touching the remote."
    expected: "'Get a new code' becomes visible AND arrives already focused; pressing OK issues a fresh code with its own countdown, not a resumed one."
    why_human: "AUTH-06's focus clause. Implemented in QRDialogProgress.set_expired(); zero automated coverage; skipped by 03-14."
  - test: "Open the per-row context menu on an account row on the television."
    expected: "The menu offers Search, 'Sign in again' and Remove. Re-authorise completes without creating a second row; Remove takes the row away and leaves the 'Add an account…' row behind."
    why_human: "AUTH-22's second clause. The code paths are gated by tests, but the menu has never been opened on any device."
  - test: "Read the two dialog buttons (1003 Cancel, 1004 Get a new code) from a normal seat."
    expected: "Both are legible. They are font25_title (25px) beside a 120px code and a 37px body — the panel's only actionable elements are now its smallest text."
    why_human: "Deferred item 12. A two-line change with the geometry already in place if they read badly; only a person in front of the screen can say."
  - test: "Sign in with a personal Microsoft account on the television."
    expected: "The same end-to-end result the work/school account produced."
    why_human: "AUTH-03's second half. A deferred second run, not a design question — the spike already took a token on a personal account against this registration."
  - test: "Resume the four NOT RUN rows of the 03-14 device checklist (three dialogs, two QR image paths, service starts at login, traceback sweep)."
    expected: "As listed in 03-14-SUMMARY.md."
    why_human: "Real Kodi runtime on real hardware; no repository instrument can answer them."
---

# Phase 3: Authentication — Verification Report

**Phase Goal:** A user signs in by reading a code off the TV and entering it on a phone, and stays signed in — with no server, no Azure setup, and no token copy-paste.
**Verified:** 2026-08-23T09:20:41Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Sign-in completes end to end on the TCL Android TV 12 with a work/school account, code read off the screen and entered on a phone, nothing typed on the remote | ✓ VERIFIED | Observed by 03-14 on the TCL (Android 12, Kodi 21.2, stock Estuary). Protocol half proven off-device first by 03-13 through the shipped package against the live provider. The blocking-tenant sub-clause is carved out by the criterion's own 1a and recorded as AUTH-18 unverifiable — see Deferred |
| 2 | The authorization request carries exactly the four locked scopes; no `Files.Read.All`, no write scope, no `.default`, no `client_secret`, no `client_assertion`, no broker reference | ✓ VERIFIED | Independently re-swept over `git ls-files` (not the project's own gate). Only hit for `client_secret`/`client_assertion` is `docs/AZURE-REGISTRATION.md:108`, the documented exclusion, paid for by `test_runbook_contains_aadsts7000218`. Broker hits only in `README.md`/`VENDORED.md`, paid for by `test_the_replaced_flow_is_named_in_the_two_excluded_documents`. Behaviourally confirmed: the actual outbound `scope` field equals the locked string exactly, and the request carries no secret parameter |
| 3 | Automated proof the persisted refresh token rotates and that a response omitting `refresh_token` retains the previous one; a two-interpreter test shows the `O_EXCL` lock serialises and a loser adopts; no `threading.Lock` or `fcntl.lockf` in the auth package | ✓ VERIFIED | `test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens` compares whole tokens read back from disk. `test_two_processes_adopt_rather_than_both_exchange` spawns a real `subprocess.Popen([sys.executable, ...])`. `test_no_forbidden_lock_primitives` is an AST sweep with an explicit non-vacuity guard. Five mutations against this criterion were all caught — see Mutation Probes |
| 4 | Root is the account list with an "Add an account…" row and per-row re-authorise and remove; labels from Graph; Back leaves no partial account; per-account isolation; the service never prompts | ✓ VERIFIED (one clause deferred) | Account list, add row and the three-entry context menu are in `ui/addon.py::list_accounts`. AUTH-07 is structural: `_add_account` assembles in memory and writes only in its last two statements, gated by `test_the_signin_flow_stamps_without_writing_anything`. Labels come from the `id_token` `name` claim with a drive-owner fallback — never a literal. Tokens and locks are per-account files; delta tokens sit on the drive record inside the per-account row. **Cache keys are not isolated** — `Cache(self._addonid, …)` is global; the ROADMAP assigns that clause to Phase 4 by name |
| 5 | On Android TV: the code renders at the skin's largest font and is legible from a sofa, the countdown ticks, "Get a new code" arrives focused on expiry, any QR encodes only the server-supplied `verification_uri` | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Font, countdown and QR were all settled by a person on the television after `24702ff` (code at `WeatherTemp` 120px in a 152-high box; body block widened 156→364 which is what made the countdown visible at all; QR 280×280). **The focus-on-expiry clause was never observed.** `set_expired()` does call `setFocus(button)` under a once-only guard — present and wired — but `QRDialogProgress` has zero automated coverage, so nothing but a person on the device can close it. ROADMAP records this criterion as PARTLY MET |
| 6 | First run on the real target device: both entry points, service at login, all three dialogs from this add-on's skin dir, two differing QR image paths, `grep -c Traceback` = 0 | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Two rows of six. The add-on installed (Kodi file manager, USB) and opens from the video and music sections; no dialog appeared over the home screen at boot. **Four rows NOT RUN**: the three dialogs through `_dialog_smoke`, the two differing image paths, the service-starts-at-login row, and the traceback sweep. ROADMAP records this criterion as PARTLY MET and 03-14-SUMMARY.md marks every unrun row |

**Score:** 4/6 truths verified (2 present, behavior-unverified)

---

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | SC4's cache-key clause — listing caches keyed per account | Phase 4 | ROADMAP.md Phase 4 "Inherited constraint from Phase 3": *"This phase builds the listing cache, so this phase owns that clause: key the cache by account from the first commit."* Confirmed in code: `Cache(self._addonid, 'page'|'children'|'items', …)` in `service/source.py` and `ui/addon.py::_clear_cache` take no account key |
| 2 | SC1's blocking-tenant clause / AUTH-18 | not schedulable here | ROADMAP.md criterion 1a: *"mark AUTH-18 unverified against a genuinely blocking tenant rather than claiming it passes."* The error map covers all four named candidates and one more, each classifying to a distinct outcome with a distinct sentence, and is gated — but no tenant available to the project will refuse the grant |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `resources/lib/auth/device_code.py` | RFC 8628 grant, no Kodi, no sockets | ✓ VERIFIED | 203 lines. Two-member `CONTINUE_ON` allow-list; HTTP 400 + JSON classified as protocol; `TransportError` kept distinct from a terminal refusal; `read_identity_claims` re-pads a stripped JWT. Imported by `provider/onedrive.py` and `remote/provider.py`; data flows |
| `resources/lib/auth/store.py` | Atomic per-account token blob | ✓ VERIFIED | 236 lines. Sibling temp file (EXDEV on Android), unique name, `O_EXCL` create at `0600`, `fsync` before `os.replace`, unlink on any failure. Account key validated against a URL-safe-base64 fullmatch and **rejected, never sanitised** |
| `resources/lib/auth/lock.py` | `O_EXCL` refresh lock with a two-signal stale breaker | ✓ VERIFIED | 328 lines. Session identifier from a Kodi home-window property distinguishes "another sub-interpreter of this session" from "a process that died before Kodi restarted". `_recorded_session() is None` is explicitly *not* treated as stale |
| `resources/lib/auth/refresh.py` | Refresh under the lock, loser adopts | ✓ VERIFIED | 389 lines. `invalid_grant` is discriminated by re-reading the store: moved on ⇒ adopt, unchanged ⇒ `NEEDS_REAUTHORISATION`. Bounded adopt wait (3 × (timeout + 1s)), abort-aware sleep |
| `resources/lib/auth/errors.py` | AADSTS map returning identifiers, not sentences | ✓ VERIFIED | 237 lines. Case-sensitive `AADSTS\d+` pattern; unmapped path keeps the bare code; `admin_must_act` flag is what couples AUTH-18 to AUTH-19 |
| `resources/lib/auth_context.py` | The four things the pure package needs from Kodi | ✓ VERIFIED (see W6) | 136 lines, closed list of four. `waitForAbort` is the only sleep. **Imports `xbmc` outside `resources/lib/kodi/`** — a new CI-01 violation, recorded nowhere |
| `resources/lib/startup_refresh.py` | Proactive refresh at Kodi start that never prompts | ✓ VERIFIED | 389 lines. Wired into `service.py` as the fifth and last listener. `test_service_never_opens_a_dialog` and `test_the_module_opens_nothing_and_waits_on_nothing_blind` both catch a dialog import or call |
| `resources/settings.xml` | Versioned schema, Expert-level custom `client_id` | ✓ VERIFIED | 180 lines, `<settings version="1">`, section/category/group. `client_id` at `<level>3</level>` in `advanced`, empty default, `<allowempty>true</allowempty>`. No `iskrypton` visibility conditions; no sign-in-host row; no error-reporting category |
| `resources/skins/default/1080i/pin-dialog.xml` | Code control at a font Estuary defines, ≥60px | ✓ VERIFIED | Control 1005 = `WeatherTemp` (120px) in a 152-high box; QR 1001 at 280×280; body 1002 at `font37` in 798×364. Four gates hold the font chain, the head of it, Estuary membership, and box-fits-glyph |
| `docs/AZURE-REGISTRATION.md` | SETUP-04 runbook quoting `AADSTS7000218` verbatim | ✓ VERIFIED | 375 lines, nine sections. Quotes the response verbatim at line 108 and forbids the client-secret "fix" it invites; carries the manifest read-back query and the acceptance section 03-13 added |
| `tools/build_addon_zip.py` + `dist/…zip` | DIST-01 archive from the git index | ✓ VERIFIED | Rebuilt during verification. 74 entries, single top-level `plugin.onedrive.kn/`, `addon.xml` inside it, and `.planning`, `tests` and `tools` all absent |
| `tests/gatelib.py` + `tests/test_auth_gates.py` | The phase instrument | ✓ VERIFIED | Harness scans 62 shipped text files / 46 Python sources after exclusions — non-vacuous. 27 gates. Every gate carries an explicit non-vacuity guard |

**Level 4 (data-flow):** the account list renders `drive['display_name']`, which resolves through `AccountManager.get_account_display_name` to the account record written by `_add_account`, whose `name` comes from the `id_token` `name` claim (or the drive owner). Verified end to end by mutation: replacing the claim decode with a literal turns four named tests red. No hollow props, no static returns.

---

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `ui/addon.py::_add_account` | `auth/device_code.py` | `provider.request_device_code` → `poll_for_token` | ✓ WIRED | Two-clock loop in `_await_authorisation`; four named outcomes |
| `ui/addon.py::_acquire_tokens` | `auth/store.py::merge_token_response` | `store.merge_token_response({}, payload)` | ✓ WIRED | This is `c768699`. Mutation to `return payload` turns `test_the_signin_flow_stamps_the_token_before_returning_it` red |
| `remote/provider.py::refresh_access_tokens` | `auth/refresh.py::refresh` | `_lock_for` + `_post_port(tries, delay, backoff)` | ✓ WIRED | The transport profile is pinned by `test_refresh_transport_is_built_from_the_pinned_profile`, which sweeps **two** files since `488d80c` |
| `startup_refresh.py` | `remote/provider.py` refresh path | `StartupRefreshService` in `service.py` | ✓ WIRED | Last in the listener list so the four servers claim ports first |
| `ui/addon.py::route` | `_action_map()` | name→method table, no `getattr` | ✓ WIRED | Mutation reintroducing `getattr(self, self._action)` turns `test_dispatch_uses_an_explicit_mapping` red |
| `ui/addon.py::list_accounts` | `_reauthorise_account` / `_remove_account` | `addContextMenuItems` | ✓ WIRED | `test_the_account_list_offers_re_authorisation` inspects the `context_options.append` calls specifically, not just the name anywhere in the method |
| `_remove_account` | `store.remove_account` | token file + lock file unlinked | ✓ WIRED | `test_removing_an_account_deletes_its_stored_credential` |
| `_failure_sentence` | `resources/language/…/strings.po` | `_FAILURE_STRINGS` → `_addon_string` | ✓ WIRED | Every outcome maps to a distinct id in 30046–30058; `admin_must_act` appends 30045, which names the Advanced/Expert `client_id` box that `settings.xml` actually declares |
| `list_accounts` | "Add an account…" row | `xbmcplugin.addDirectoryItems` | ⚠️ WIRED, UNGATED | Present and observed on hardware, but **no test fails if the row is deleted** — see W3 |

---

### Behavioural Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full suite | `python -m pytest -q` | `256 passed, 1 skipped` (skip: POSIX mode bits not enforced on Windows, self-documenting) | ✓ PASS |
| Outbound scope is exactly the locked string | driven `device_code.request_device_code` with a recording port | `'https://graph.microsoft.com/Files.Read offline_access openid profile'`, exact match; no secret parameter | ✓ PASS |
| Verification URI comes from the server | same | `https://login.microsoft.com/device` returned by the port, not a literal | ✓ PASS |
| HTTP 400 + JSON pending is protocol | `device_code.poll_once` against a 400 port | `('authorization_pending', {...})` | ✓ PASS |
| Unknown error code stops the loop | same, with an invented code | `terminal` | ✓ PASS |
| Refresh token survives a response that omits it | two `merge_token_response` + `write` + `read` cycles on a real temp dir | access token advanced, refresh token retained, `date`/`issued_at` stamped, no `.tmp-` residue | ✓ PASS |
| Two accounts get two files and two locks | `store.token_path` / `lock_path` | distinct; `../../etc/passwd` raises `ValueError` | ✓ PASS |
| Every roadmap AADSTS candidate classifies distinctly | `errors.classify` on all five | five distinct outcomes; `admin_must_act` set on the two Conditional-Access-family codes; unmapped keeps the bare code | ✓ PASS |
| Label comes from the id_token | `read_identity_claims` on a padded and an unpadded JWT | claims decoded; garbage yields `{}` | ✓ PASS |
| DIST-01 archive | `python tools/build_addon_zip.py` then inspect | 74 entries, one top-level `plugin.onedrive.kn/`, no planning/tests/tools | ✓ PASS |
| Anything requiring a Kodi runtime | — | — | ? SKIP → human verification |

### Mutation Probes (instrument non-vacuity)

Twenty-one deliberate defects were injected into shipped source and the suite re-run. **Nineteen were caught by a named, targeted test; two were not.** Each mutation was reverted with `git checkout` and the tree left clean.

| Mutation | Caught by |
|---|---|
| Drop the `refresh_token` carry-forward (AUTH-12) | `test_an_empty_refresh_token_in_the_response_does_not_erase_the_stored_one` |
| Truncate the token file after `os.replace` (AUTH-11) | 48 tests |
| Widen the poll allow-list with `invalid_grant` (AUTH-09) | 1 test |
| Swap `Files.Read` for `Files.Read.All` (AUTH-04) | 4 tests |
| Treat HTTP 400 + JSON as transport failure (AUTH-10) | 8 tests |
| Label from a literal instead of the claim (AUTH-21) | 4 tests |
| Sanitise the account key instead of rejecting it | 16 tests |
| **`c768699` reverted** — return the raw poll payload | `test_the_signin_flow_stamps_the_token_before_returning_it` |
| Drop `issued_at` from the merge | 3 tests |
| **`51d4ee0` reverted** — token blob back in the exception message | `test_no_exception_message_carries_a_credential`, `test_the_invalid_token_message_is_built_from_field_names`, `test_the_rejection_does_not_print_the_token`, +1 |
| Stop redacting the request body in the report | 3 tests |
| Drop `refresh_token` from `REDACTED_FIELDS` | 2 tests |
| **`24702ff` reverted** — code label back to `font60` | `test_the_code_label_names_the_head_of_the_code_font_chain` |
| Body block back to the overflowing 156 height | `test_the_sign_in_boxes_can_hold_the_fonts_they_name` |
| Name a font Estuary does not define | 2 tests |
| `O_EXCL` → plain `O_CREAT` (AUTH-14) | 21 tests |
| Disable the `invalid_grant` adopt branch (AUTH-15) | 2 tests |
| Make the keepalive import a dialog module (AUTH-17) | collection error |
| Make the keepalive call a Kodi dialog (AUTH-17) | 2 tests |
| Write an account before the flow completes (AUTH-07) | `test_the_signin_flow_stamps_without_writing_anything` |
| Drop the re-authorise row from the context menu (AUTH-22) | `test_the_account_list_offers_re_authorisation` |
| Restore `getattr` dispatch in `route()` (AUTH-23) | `test_dispatch_uses_an_explicit_mapping` |
| Move `client_id` off Expert level (AUTH-19) | `test_custom_client_id_setting` |
| Delete an AADSTS code from the map (AUTH-18) | 2 tests |
| **Delete the "Add an account…" row** | ✗ **NOT CAUGHT** — 256 passed |
| **Disable the QR's https refusal (`_is_secure_url`)** | ✗ **NOT CAUGHT** — 256 passed |

**Verdict on the three in-run defect fixes.** All three are sound and each is held by a test that goes red when the fix is reverted. `c768699` was fixed at the correct seam — `merge_token_response` is pure and writes nothing, so AUTH-07's "nothing written until the last two statements" property survives, and the summary's reasoning for rejecting the two alternative sites checks out against the code. `51d4ee0` covers all four parts of the raised `RequestException` (message, URL, request data, headers) and the `_for_report` naming convention is what the widened gate reads. `24702ff` added 384 test lines and deleted none.

**Verdict on the phase instrument.** `tests/test_auth_gates.py` was edited by nine commits after 03-03 created it, which departs from 03-03's own must-have that it "not be edited again by any later plan in this phase". Every edit was audited: 671 lines were added by the three post-hoc fix commits with **zero deletions**, and the four earlier commits that did delete lines (45 in total) each *widened* a sweep — one file to two, dict-literal entries to dict-literal-plus-assignment, `Request` to `Request`-or-`_post_port`, and a re-authorise assertion that matched the name anywhere in the method to one that matches the menu specifically. No assertion in this file was ever weakened to let a change pass.

---

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist and no plan declares one. Step 7c: N/A for this project.

---

### Requirements Coverage

Every requirement id declared in the 14 PLAN frontmatters was cross-referenced against `.planning/REQUIREMENTS.md`. **All 27 ids named for this phase are claimed by at least one plan; there are no orphans.**

| Requirement | Source Plans | Status | Evidence |
|---|---|---|---|
| SETUP-01/02/03 | 03-03 | ✓ SATISFIED | Satisfied before Phase 1, manifest read back through Graph; runbook records the values |
| SETUP-04 | 03-03, 03-13 | ✓ SATISFIED | `docs/AZURE-REGISTRATION.md`, `AADSTS7000218` verbatim, gated by name |
| AUTH-01 | 03-08, 03-13, 03-14 | ✓ SATISFIED | Observed end to end on the TCL |
| AUTH-02 | 03-08, 03-11, 03-12, 03-13 | ✓ SATISFIED | Built-in `client_id` took a live token with no argument, no server |
| AUTH-03 | 03-08, 03-13, 03-14 | ? NEEDS HUMAN | **Pending is correct.** Work/school proven twice; the personal-account run is outstanding |
| AUTH-04 | 03-01, 03-03, 03-08, 03-13 | ✓ SATISFIED | Exact scope string confirmed on the wire and by sweep |
| AUTH-05 | 03-05, 03-06, 03-14 | ✓ SATISFIED | Settled by a person on stock Estuary at `WeatherTemp`; the failing `font60` reading is kept |
| AUTH-06 | 03-05, 03-06, 03-08, 03-14 | ? NEEDS HUMAN | **Pending is correct.** Countdown clause met; focus clause implemented but unobserved and untested |
| AUTH-07 | 03-06, 03-08, 03-14 | ✓ SATISFIED | Structural, plus `test_the_signin_flow_stamps_without_writing_anything` |
| AUTH-08 | 03-06, 03-08, 03-14 | ✓ SATISFIED (with W4) | Scanned on the device at 280×280. The https-refusal half is unwired from any test — see W4 |
| AUTH-09/10 | 03-01 | ✓ SATISFIED | Allow-list and 400-as-protocol both behaviourally confirmed |
| AUTH-11/12 | 03-01, 03-07, 03-08 | ✓ SATISFIED | Atomic write and carry-forward behaviourally confirmed |
| AUTH-13 | 03-07, 03-13 | ✓ SATISFIED | Whole tokens compared from disk; three distinct sha256 values live |
| AUTH-14/15 | 03-03, 03-04, 03-07 | ✓ SATISFIED | `O_EXCL`, two-interpreter subprocess test, adopt branch |
| AUTH-16 | 03-07, 03-10 | ✓ SATISFIED | `should_refresh` threshold well inside 90 days; run from `service.py` |
| AUTH-17 | 03-03, 03-09, 03-10, 03-14 | ✓ SATISFIED (weakest mark) | Code half gated twice. The device half is a negative observation whose premise — that the service ran — is unconfirmed. REQUIREMENTS.md says so in as many words |
| AUTH-18 | 03-03, 03-05, 03-09, 03-11, 03-13 | ? NEEDS HUMAN | **Pending / UNVERIFIABLE HERE is correct.** Map, escape hatch and tests exist; no tenant will refuse |
| AUTH-19 | 03-03, 03-08, 03-11 | ✓ SATISFIED | `<level>3</level>`, empty default, `allowempty`; string 30045 points at it by name |
| AUTH-20 | 03-04, 03-09, 03-10 | ⚠️ **PARTIAL, MARKED COMPLETE** | Tokens ✓, delta tokens ✓, **cache keys ✗**. See W1 |
| AUTH-21 | 03-01, 03-05, 03-08, 03-09, 03-13 | ✓ SATISFIED | From the `id_token`, never typed |
| AUTH-22 | 03-05, 03-09, 03-14 | ? NEEDS HUMAN | **Pending is correct.** Menu code present and gated; never opened on any device |
| AUTH-23 | 03-03, 03-08, 03-09, 03-11, 03-12 | ✓ SATISFIED | `signin.py` and `errorreport.py` deleted; setting removed; sweep clean |
| DIST-01 | 03-02, 03-12, 03-14 | ✓ SATISFIED | Rebuilt and inspected during verification; installed on the device |
| KODI-05/06 | 03-11 | ✓ SATISFIED | Versioned schema, no `iskrypton` conditions |
| KODI-08 | 03-09, 03-11 | ✓ SATISFIED | Reporter module, its eight call sites and its setting all gone |
| BROWSE-08 | 03-08 (sign-in path only) | ✓ CORRECTLY PENDING | Phase 3 took `get_account`/`get_drives`; the rest is Phase 4's, and the id stays Pending under Phase 4 |
| VND-09 | 03-12 | ✓ SATISFIED | `VENDORED.md` modification record re-measured against the tree during this verification and found accurate |
| CI-06 | 03-14 | ✓ SATISFIED | Discharged on the TCL itself, no stand-in, every unrun row recorded as unrun |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | `TBD` / `FIXME` / `XXX` in any file this phase modified | — | **None. Zero hits.** |
| — | — | `TODO` / `HACK` / `PLACEHOLDER` | — | **None. Zero hits.** |
| `resources/lib/addon.py` | 62–228 | `_dialog_smoke` temporary debug affordance ships in the installable archive and is reachable at `plugin://plugin.onedrive.kn/?action=_dialog_smoke` | ℹ️ Info | Deliberate, documented in the file, in `VENDORED.md`, and held in the action map by `test_the_dialog_affordance_stays_routable`. It is the only route to all three dialogs and SC6 still needs it. It touches no credential. Remove it in the same commit as its assertion once SC6's dialog rows are run |

---

## Findings

### W1 — AUTH-20 is marked Complete without the qualifier its siblings carry (WARNING)

`REQUIREMENTS.md:72` reads `- [x] **AUTH-20**: Multiple accounts are supported, with tokens, delta tokens, and cache keys isolated per account`, and the traceability row says only `Complete`.

Measured against the tree: tokens are isolated (`accounts/<key>.json`, `accounts/<key>.lock`), delta tokens are isolated (`change_token` sits on the drive record inside the per-account row that `SimpleKeyValueDb` keys by `account['id']`), and **cache keys are not** — `Cache(self._addonid, 'page'|'children'|'items', …)` in `service/source.py:50-52`, `source.py:411-413` and `ui/addon.py:1146-1148` take no account key at all.

The ROADMAP knows this. Phase 4's "Inherited constraint from Phase 3" names AUTH-20 explicitly, states that Phase 3 could not deliver the cache half, and assigns it to Phase 4 with the reason: *"Retrofitting an account key onto a populated global cache means either a migration or a silent cross-account data leak."* So the work is scheduled and will not be lost — but the requirement mark says the whole sentence is done.

AUTH-03, AUTH-05, AUTH-06, AUTH-17, AUTH-22, SETUP-05, SETUP-06, CI-06 and DIST-01 all carry precise inline qualifiers in this file. AUTH-20 is the only partially-met requirement in the phase that does not, and it is the one whose unmet clause is a cross-account leak.

**Fix:** append the qualifier to `REQUIREMENTS.md:72` and to the traceability row at line 237, naming Phase 4 as the owner of the cache clause. No code change.

### W2 — KODI-02's checkbox contradicts its own sentence, its table row and STATE.md (WARNING)

`REQUIREMENTS.md:111` is `- [x] **KODI-02**: … **Narrowed by decision on 2026-08-23 and deliberately left unchecked** …`. The line says it is unchecked and the box says it is checked. The traceability row at line 267 says `Narrowed — not met, moved out of Phase 1`, and `STATE.md` says *"KODI-02 stays unchecked"*. Three sources agree; the box is the outlier.

Traced through history: the box was `[ ]` in all fourteen commits up to and including `5f6271b`, and was flipped by **`c3c491e` — "docs(phase-1): complete phase execution"**, the last Phase 1 commit, which flipped five boxes at once (VND-07, VND-09, VND-10, ID-04, KODI-02, CI-06). The other four flips agree with their table rows; this one does not. It then survived all fourteen Phase 3 plans and their requirement-marking passes.

This is a confirmed instance of the premature-Complete flip the phase record warns about. It is a Phase 1 artefact, not a Phase 3 one, and it does not touch the Phase 3 goal — but it is the only false requirement mark in the file and it is exactly the kind that gets read later as a pass.

**Fix:** change `[x]` back to `[ ]` on `REQUIREMENTS.md:111`. One character.

### W3 — The "Add an account…" row has no regression gate (WARNING)

Deleting the three lines that append the add-account row to the listing leaves the suite at **256 passed**. That row is the first clause of AUTH-22 and the only route into sign-in for a user with no accounts; on a fresh install with an empty account list, losing it makes the add-on unusable with no failing test anywhere.

It *was* observed on the television (the 03-14 sign-in went through it), so the truth held once. What is missing is the gate that keeps it holding. `test_the_account_list_offers_re_authorisation` already parses `list_accounts` and would extend to this naturally.

### W4 — `QRDialogProgress` has zero automated coverage (WARNING)

`set_code`, `set_remaining`, `set_expired`, `reset_for_new_code`, `is_new_code_requested`, `format_remaining`, `_render_text` and `_is_secure_url` are all called from `_await_authorisation` and none is touched by any test. Renaming `_is_secure_url` out from under its call site leaves the suite at **256 passed** — meaning the refusal to encode a non-`https` sign-in address into a QR code, which exists precisely because a QR is a thing a person is told to point a camera at, is unheld.

The class subclasses `xbmcgui.WindowXMLDialog`, so most of it genuinely cannot be tested without Kodi. But `format_remaining` and `_is_secure_url` are both static, pure and Kodi-free, and are testable as they stand. This is also why AUTH-06's focus clause has no instrument short of a person on the device.

### W5 — Deferred item 15 is assigned to a plan that has already closed (WARNING)

Item 15 (Kodi on Android 12 lists folders but no files on external storage until the app's file permission is changed from "while using the app" to "always") is assigned to *"`README.md`'s build-and-install section, which 03-12 owns and which does not mention it"*. 03-12 is complete and `README.md:64-79` still does not mention it. Unlike items 4, 10, 11 and 12, which are forward-assigned to "whoever next edits X", this one names a finished owner and therefore has none.

The finding itself is well-judged — it fails in the shape most likely to be misread, an empty listing looks like an empty directory — and every future device session pays the cost again until it is written down. It is two sentences in a section that already exists.

### W6 — This phase added a new CI-01 violation and recorded it nowhere (WARNING)

CI-01 (Phase 2) requires that only `resources/lib/kodi/` import `xbmc*`. That directory does not exist. Phase 3 added `resources/lib/auth_context.py`, which imports `xbmc` at module level and sits directly under `resources/lib/`.

The module itself is exactly the thin adapter the architecture calls for — a closed list of four things, documented as such, and it is precisely what keeps `resources/lib/auth/` Kodi-free (independently confirmed: no `xbmc` import anywhere in that package). The problem is only its location, and the fix is a one-file move when Phase 2 lands. But nothing in `deferred-items.md`, the ROADMAP or the summaries records that Phase 3 running ahead of Phase 2 has moved CI-01's target.

### I1 — STATE.md's progress block is internally inconsistent (INFO)

`total_phases: 2` and `completed_phases: 2` against an eight-phase roadmap with Phase 3 in flight; `completed_plans: 21` against a Performance Metrics section reading `Total plans completed: 7` and a by-phase table listing only Phase 01. Bookkeeping noise, no bearing on the goal.

---

## Adversarial Checks Requested

**1. Current state of REQUIREMENTS.md against reality.** Machine-compared all 94 checklist marks against all 94 traceability rows. **One disagreement: KODI-02 (W2).** Separately, one unqualified overclaim: **AUTH-20 (W1)**. Every other Phase 3 mark holds against the tree — I verified AUTH-04, 07, 09, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 23, KODI-05/06/08 and DIST-01 by running or mutating the code rather than by reading the claim. **The three deliberate Pendings — AUTH-03, AUTH-06, AUTH-22 — plus AUTH-18 are all correct judgements and should not be closed.** AUTH-06's focus clause is implemented but has no instrument; AUTH-22's context menu is implemented and gated but has never been opened; AUTH-03's personal half is a run, not a design question; AUTH-18 cannot be produced on demand.

**2. VENDORED.md accuracy after the three post-03-12 fix commits.** Accurate. Each of `c768699`, `51d4ee0` and `24702ff` updated `VENDORED.md` in the same commit, and the "Fixed on hardware" block is new and correct. I re-measured line endings byte-by-byte from the git objects at the phase base and at HEAD across all twelve changed vendored files plus the skin: exactly `ui/addon.py`, `ui/utils.py` and `pin-dialog.xml` are LF and everything else is unchanged — exactly the three the record names — and the record's further claim that upstream is not uniform (`remote/provider.py` and `export.py` arrived LF) is also correct. The file-count arithmetic holds: twelve vendored files in the sign-in rewrite, two deleted, one skin, plus `oauth2.py` in the third block.

**3. `COVERAGE.md`.** Confirmed. It exists in no commit at the repository root and never has. The only `COVERAGE.md` in the index is `.planning/phases/01-vendor-lift/COVERAGE.md`, which the `.planning` top-level rule already excludes, so the `EXCLUDED_DOCS` entry does no work by either route. It is harmless today, and it is disclosed twice — in `VENDORED.md:73-79` and in deferred item 9 — with the correct reasoning that an entry doing nothing beside four that do is what the next reader has to disambiguate. The exclusions that *are* doing work are each paid for by a positive assertion, which I verified by name.

**4. Did Phase 3 absorb Phase 2, or leave a hole?** Neither absorption nor a hole in Phase 2's core: BROWSE-02/03/04/07/16 (extraction, paging, per-segment path encoding, OData quoting) are untouched, no Graph fixtures were recorded, and CI-01 to CI-05 are all correctly still Pending — in particular CI-05 was **not** claimed on the strength of `tests/gatelib.py`, which implements CI-05's content but not its CI-ness, and there is no workflow under `.github/`. Phase 3 did take `BROWSE-08`'s sign-in half as the roadmap sanctioned, and left the id Pending under Phase 4. The one real hole is **W6**: CI-01's layering target has moved and nobody wrote it down.

**5. DIST-01's move and in-place text edit.** Sound. The edit changed `plugin.onedrive-<version>.zip` / `plugin.onedrive/` to `plugin.onedrive.kn-…` and added the git-index clause. It was forced, not chosen: Kodi matches the archive's top-level directory against the id in the manifest inside it and refuses a mismatch, so the original text was unsatisfiable against the current add-on id. The change is annotated in place with that reasoning, the phase mapping moved from 5 to 3, and **both** count rows were updated consistently (`3. Authentication … 28`, `5. Distribution | DIST-02..05 | 4`). 03-12 flagged that 03-02 had marked it while 03-14 still declared it, and asked 03-14 to confirm rather than alter — which 03-14 did, on hardware. I rebuilt the archive during verification and confirmed the contract behaviourally.

**6. Is any deferred item a phase-goal gap wearing a deferral label?** I assessed all sixteen. **No.** The closest calls, in order:

- **Item 15** is the only one assigned to an artefact this phase owns and closed, so it has no forward owner (W5). It is install documentation, not the sign-in goal, so it is not a goal gap — but it is the one item that will otherwise sit unowned.
- **Item 1** (`import urllib` not binding `urllib.parse`, ten modules) touches the sign-in path directly, since `ui/addon.py` builds every plugin address through `urllib.parse.urlencode`. I checked the premise rather than accepting it: `import urllib.error` does leave `urllib.parse` bound, `resources/lib/addon.py` — the one module with no `urllib.error` import of its own — is reached only through `ui/addon.py` which has one, and the whole tree compiles and runs. Correctly characterised as fragile-but-working and correctly assigned to a sweep of its own.
- **Item 12** (the two buttons are now the smallest text on a panel that exists to be readable) is coupled to AUTH-06's unmet focus clause and to the directional-pad row 03-14 skipped. It is correctly forward-assigned to the next television session, and the record explicitly refuses to read the completed run as having looked and found nothing.
- **Item 11** (nothing stops the next comparison being built on the log redactor `fingerprint()`) is a missing gate rather than a defect — the shipped code was never wrong, and `test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens` compares whole tokens, which I confirmed by mutation. Correctly assigned.
- Items 2, 3, 4, 5, 7, 8, 9, 10 are benign and each is paired with the condition that discharges it. Items 13, 14 and 16 belong to Phases 4, 5 and 6 and are honestly written as reports rather than diagnoses.

---

## Gaps Summary

**There are no gaps in the code.** Every artefact this phase promised exists, is substantive, is wired, and carries real data through it; every key link is connected; no debt marker of any class appears in any file the phase touched; and twenty-one injected defects were caught nineteen times by named tests written for exactly the property being broken. The three defects found during the acceptance run were each fixed at a defensible seam and each is held by a test that goes red on revert, and the phase instrument was never once weakened to let a change pass.

What is outstanding is observation, not implementation. Two of the six roadmap criteria — 5 and 6 — are recorded by the ROADMAP itself as PARTLY MET, and this verification agrees with that reading rather than softening it. The unmet clauses are *present and wired in code but unexercised*: `set_expired()` does move focus onto the second button, and `_dialog_smoke` does reach all three dialogs, but a `setFocus` call in a Kodi dialog subclass is not evidence that focus landed, and the only instrument that can say otherwise is a person in front of the television. Thirteen checklist rows were marked NOT RUN or NOT OBSERVED by 03-14 and are reproduced in the human-verification list above.

The six warnings are all record-accuracy or instrument-coverage items, not functional blockers: two false or unqualified requirement marks (W1, W2), two missing gates for behaviour that is otherwise correct (W3, W4), one deferred item with no forward owner (W5), and one cross-phase constraint this phase moved without recording (W6). W1 and W2 are one line each. W3 and W4 are the two places where a deliberate change to shipped source leaves the suite fully green, and both are worth closing before the phase is treated as instrumented.

The phase goal — sign in from the couch with a remote, no server, no Azure setup, no token copy-paste — was achieved and was seen achieved on the hardware it exists for. What remains is finishing the reading.

---

_Verified: 2026-08-23T09:20:41Z_
_Verifier: Claude (gsd-verifier)_
