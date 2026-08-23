---
gsd_state_version: 1.0
milestone: v1.4.0
milestone_name: milestone
current_phase: 03
current_phase_name: authentication
status: verifying
stopped_at: Completed 03-14-PLAN.md - Phase 03 fully executed, awaiting verification
last_updated: "2026-08-23T09:04:33.955Z"
last_activity: 2026-08-23
last_activity_desc: Phase 03 execution started
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 21
  completed_plans: 21
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-22)

**Core value:** Sign in from the couch with a remote, and play a file from OneDrive.
**Current focus:** Phase 03 — authentication

## Current Position

Phase: 03 (authentication) — EXECUTING
Plan: 14 of 14
Status: Phase complete — ready for verification
stands, its Windows rows were descoped because Windows is not a target. Phase criterion 2 (the Kodi
19/20/21/22 install matrix) is therefore **unmet by decision, not satisfied**, and KODI-02 stays unchecked.
Verification found four record-accuracy gaps and no functional blocker; all four are now closed — the
QR encoder's provenance is in `VENDORED.md` and `CREDITS.md`, two modification counts were corrected
against the tree, KODI-01 and SETUP-06 carry inline qualifications, and the ROADMAP's "already-dead
broker" parenthetical was corrected to the measurement.
Last activity: 2026-08-23 — Phase 03 execution started

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 7
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 7 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P02 | 30min | 2 tasks | 3 files |
| Phase 01 P03 | 20min | 2 tasks | 5 files |
| Phase 01 P04 | 15min | 2 tasks | 44 files |
| Phase 01 P05 | 20min | 2 tasks | 14 files |
| Phase 01 P06 | 12min | 2 tasks | 4 files |
| Phase 01 P01 | 2h | 3 tasks | 1 files |
| Phase 01 P07 | ~2h | 3 tasks | 3 files |
| Phase 03 P01 | 25min | 3 tasks | 6 files |
| Phase 03 P02 | 12min | 2 tasks | 3 files |
| Phase 03 P03 | 30 min | 3 tasks | 5 files |
| Phase 03 P04 | 20min | 2 tasks | 4 files |
| Phase 03 P05 | 35min | 2 tasks | 4 files |
| Phase 03 P06 | 25min | 2 tasks | 2 files |
| Phase 03 P07 | 20min | 2 tasks | 2 files |
| Phase 03 P08 | 22m | 3 tasks | 6 files |
| Phase 03 P09 | 3h22m | 3 tasks | 12 files |
| Phase 03 P10 | 16m | 2 tasks | 4 files |
| Phase 03 P11 | 26m | 2 tasks | 3 files |
| Phase 03 P12 | 45m | 3 tasks | 5 files |
| Phase 3 P13 | ~1h | 3 tasks | 6 files |
| Phase 03 P14 | ~2h | 3 tasks | 12 files |

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
- [Phase 1]: Phase 1 gates live in one pytest file written before any change; the exclusion set is defined once and every sweep carries a non-vacuity guard
- [Phase 1]: The string-id gate asserts 30012 absent and 32012 present: 32012 is the vendored module's own string and stays, only this add-on's copy is deleted
- [Phase 1]: Add-on identity is plugin.onedrive.kn / OneDrive KN / Kenny Nguyen, version 1.0.0 (not the 3.0.0 research floated: the two ids never version-compare)
- [Phase 1]: kodi.wiki Language_support confirmed verbatim: 30000-30999 is reserved for plugins, 32000-32999 for scripts - research assumption A1 is now verified
- [Phase 1]: allow_directory_listing defaults to false: a recorded behaviour deviation, complete rather than partial because the new id means no user has a stored true
- [Phase 1]: Vendored files are staged with core.autocrlf=false so their blobs are byte-identical to upstream at df68e9a; git would otherwise normalise CRLF to LF on files with no prior index entry
- [Phase 1]: The vendored package lives at resources/lib/vendor/clouddrive_common/ and the rename is anchored on a line-start import prefix, never a bare substring, so the six add-on-id literals could not be corrupted
- [Phase 1]: The module's 89 string ids stay at 32000-32088 untouched; five are resolved at runtime and two of those are persisted in the exports store, so renumbering them would invalidate stored rows
- [Phase 1]: Utils.get_class and Utils.get_fqn are deleted: they were the only string-based import mechanism in the tree and had no callers, so a text sweep over imports is now a complete proof of a rename
- [Phase ?]: common_addon_id is None, not this add-on's own id literal: None makes the common Addon object and this add-on's the same object, where a literal would make them two that happen to agree and break again at the next rename
- [Phase ?]: The QR image filename carries a fresh uuid4 hex per invocation, because Kodi's texture cache is keyed by path and a fixed name lets a repeat sign-in render the previous code
- [Phase ?]: pyqrcode is vendored from the Kodi omega add-on zip (1.2.1+matrix.4) rather than PyPI: it is the build the add-on was tested against and the only distribution bundling the MIT PNG writer
- [Phase ?]: test_gpl_headers_intact is made licence-aware via a per-file FOREIGN_NOTICES map rather than GPL-stamping BSD/MIT source, which the test's own closing assertion forbids
- [Phase ?]: All four repr( write sites converted to JSON, not the two the plan names; db.setmany and cache.setmany are write sites too
- [Phase ?]: The page cache stores a response body as bytes, a third shape JSON cannot carry; decoded at the write site in source.py, the exact inverse of the read path's Utils.encode
- [Phase ?]: Request.HTTP_TIMEOUT_SECONDS = 30 is **still unmeasured** after 01-07 — no throttling was applied on any platform, and the value's justification is marginal Android TV Wi-Fi, a condition no run has been near. It must not be reported as validated; retry loop worst case 155s recorded, not bounded
- [Phase ?]: Android acceptance instrument is an API 30 emulator (Android 11), not a physical phone; storage-regime claims hold, ten-foot/GPU claims do not
- [Phase ?]: Pulling an app-private Kodi log over adb needs root on Android 11+; a retail device must copy the log to a public directory first
- [Phase ?]: Kodi 22 pinned to 22.0 Piers beta1 rather than a nightly, for a fixed version string and a published checksum
- [Phase ?]: Kodi 22 ships Python 3.14 while 19/20/21 ship 3.8 — a compatibility gate is needed before Phase 2 leans on the matrix
- [Phase 1]: Windows is not a target for this add-on; the Windows acceptance leg and the four-version Kodi install matrix are dropped by the owner's decision. KODI-02 stays unchecked rather than narrowed into a pass
- [Phase 1]: The TCL Android TV 12 is the primary acceptance device, not a pre-release checkbox; its first acceptance run is recorded against Phase 3, the first phase after which a run on it proves something the emulator could not
- [Scope]: CI-06 is rewritten around that: per-phase acceptance on the TCL from Phase 3 onward, no standing Windows or phone obligation, and a stand-in accepted only for API-level questions (storage paths, file mode bits, `O_EXCL`, loopback binding) because those follow the API level rather than the form factor
- [Scope]: OneDrive Business is the drive type in use. Wherever a requirement demands both classes the immediate obligation is Business and the Personal half is deferred, not deleted — the reserved-character sets differ, so a Business pass is not evidence about Personal
- [Scope]: The Business-first narrowing costs no future work: measured, `/me/drives` is 403 on personal and 200 on business, `/drives` is 403 on both, and `/me/drive` is 200 on both. BROWSE-08 already fixes `/me/drive`, so the endpoint in use already serves both account classes. ROADMAP Phase 4 criterion 2 still named `/me/drives` and was corrected
- [Scope]: Phase order to the goal is 3 (auth) → 2 (browse logic only) → 4 (browse) → 6 (play), with DIST-01 alone pulled forward from Phase 5 when the add-on first needs installing on the TV — installing on Android TV requires a zip, which is a device constraint, not a distribution or "public" concern
- [Scope]: Deferred — Phase 7, Phase 8 and the CI harness (CI-01..05), with two exceptions that hit the owner directly: REL-01 (if the E5 tenant lapses the embedded `client_id` dies for every installed copy, including the TV's) and Phase 7 criterion 4 (deleting `SourceService`, its HTML index and the third-party error reporter, and confirming nothing binds port 8586 — that is security)
- [Scope]: SETUP-01, SETUP-02, SETUP-03 and SETUP-05 are satisfied and now checked, each read back through Graph rather than trusted from the portal UI. SETUP-04 stays open — no registration runbook exists in the repo, and it must carry the `AADSTS7000218` symptom verbatim
- [Phase 3]: One authority constant (/common) serves both account classes; no branch, no user-facing authority setting
- [Phase 3]: An unparseable 400 raises TransportError rather than classifying terminal - a dead grant and a proxy error page demand opposite responses
- [Phase 3]: The poll interval is state the caller carries; next_interval() is what keeps the RFC 8628 slow_down increase permanent
- [Phase 3]: store.read raises on a corrupt token file; {} is returned only for an absent one, so a merge cannot start from nothing and drop a refresh token
- [Phase 3]: DIST-01 is corrected in place: the archive's top-level directory is plugin.onedrive.kn, from the manifest, because Kodi refuses an install whose directory disagrees with the id inside
- [Phase 3]: The archive's member list comes from the git index with an exclusion list over first path components, never a filesystem walk and never a hand-maintained include list
- [Phase 03]: The gate harness lives in tests/gatelib.py and nowhere else; a second gate file imports it rather than restating the exclusion set, because two exclusion sets drift and a drifting one is how a gate stops checking anything
- [Phase 03]: docs/AZURE-REGISTRATION.md is the fifth entry in EXCLUDED_DOCS and is paid for by test_runbook_contains_aadsts7000218; the credential pattern is never softened to let a required quote through
- [Phase 03]: The unanswerable-endpoint gate matches the whole parsed path, never a prefix: /me/ normalises to /me and is the call sign-in makes first, so a prefix test written against /me/drives would miss the only failure that breaks sign-in outright
- [Phase 03]: tests/test_auth_gates.py is written once in plan 03-03 and is not edited again by any later plan in this phase; a plan that wants to change an assertion rather than satisfy it must raise it instead
- [Phase 03]: The refresh lock lifetime is 90s, set against the 65s worst case of the tries=2 refresh profile plan 03-08 installs; the transport's 155s default-profile figure is recorded beside it and a test fails if the arithmetic or the owning plan leaves the source
- [Phase 03]: An unsafe account key is rejected, never sanitised: a sanitiser maps two different keys onto one filename, which is the cross-account leak AUTH-20 exists to prevent
- [Phase 03]: RefreshLock.release unlinks only when that instance actually holds the lock; the research sketch's unconditional unlink turns a loser's finally block into a silent second breaker of the winner's lock
- [Phase 03]: The AADSTS table returns identifiers, not words: a symbolic outcome plus the bare code, with the sentence chosen by the Kodi layer from the catalogue, so the table is testable without Kodi and the copy exists in one place
- [Phase 03]: admin_must_act answers 'can the person holding the remote clear this themselves?', not severity: consent, both MFA codes and an expired password are not marked, because sending that person to an administrator sends them away from the action that works
- [Phase 03]: AADSTS7000218 is not an administrator outcome and its message says adding a secret will not help; after shipping only somebody who set their own client id can reach it
- [Phase 03]: The honest union of the roadmap and pitfall codes is twelve; AADSTS70019 (device code expired) is a deliberate thirteenth because it is the terminal refusal a fifteen-minute window produces most often
- [Phase 03]: The whole phase's English copy landed in one commit (30036-30058) with the exact-equality partition gate widened beside it, so four later plans add screens without touching the gate
- [Phase ?]: The sign-in dialog leads with the code at font60 across the full panel width; the QR is secondary at 150px, because the provider never returns verification_uri_complete
- [Phase ?]: Focus in QRDialogProgress is set at transitions only (onInit, expiry, return from expiry) and never inside a method the countdown calls once a second
- [Phase ?]: This add-on's 30000-block strings must be read through xbmcaddon.Addon().getLocalizedString; KodiUtils.localize routes every id below 32000 to Kodi's own catalogue and silently returns the wrong string
- [Phase ?]: The refresh keeps its own short request profile (tries=2, delay=5, worst case 65s) rather than the transport's 155-second default, so RefreshLock.LIFETIME_SECONDS=90 can sit above it without holding the other contender for minutes
- [Phase ?]: A lost race is told from a dead grant by re-reading the store from disk and comparing the stored refresh token byte-for-byte against the rejected one; nothing in the provider's response distinguishes them
- [Phase ?]: Refresh failures classify into three outcomes (succeeded, transient, needs-reauthorisation) and only a provider grant refusal produces the third, so a box that boots before its network never asks for a sign-in
- [Phase ?]: The startup threshold is 30 days against the 90-day window, not 60: a device switched on once every forty-five days would skip a sixty-day threshold and find the grant already dead on the next start
- [Phase ?]: The refresh transport is built from refresh.REQUEST_TRIES/REQUEST_DELAY_SECONDS/REQUEST_BACKOFF through one factory, pinned by a static gate on the argument names rather than the numbers, so the 65-second worst case and RefreshLock's 90-second lifetime cannot move apart
- [Phase ?]: A credential shorter than twice the eight-character report prefix is redacted entirely: keeping eight of a nine-character user_code is the live code with one character missing
- [Phase ?]: A provider refusal during sign-in is shown with dialog.ok, not raised: raising routes it through the failure handler, which still offers to send an error report to the third party this phase is removing
- [Phase ?]: Request path literals stay written out at the call site rather than behind a constant, because test_no_unanswerable_provider_endpoint can only read a whole literal
- [Phase ?]: VENDORED.md is left to 03-12 even though 03-08 deletes a vendored file; the change record is handed over in 03-08-SUMMARY.md rather than written by two plans into one document
- [Phase 03]: A plugin address selects an entry in an explicit mapping, never an attribute on an object. A stop-list was refused in the source: the namespace it filters grows with every method added, a mapping does not
- [Phase 03]: Re-authorising as a different account writes nothing and says which account signed in — the alternative binds one person's credential to another person's row, silently, on a shared television
- [Phase 03]: The error reporter is deleted rather than disabled, with its six call sites in five other modules rewritten to log a stack trace; KODI-08 still waits on 03-11's settings row and no shared-id gate will say so
- [Phase ?]: The startup keepalive is a service in the runner's list rather than a call before it: ServiceUtil.run starts each service once in its own daemon thread, so the token exchange delays no listener and the shutdown observation comes for free
- [Phase ?]: The startup refresh takes one lock attempt of ten seconds against the plugin's three of thirty: a held lock means somebody else is already refreshing this account, so the right answer is the next pass rather than contention
- [Phase ?]: The needs_reauth literal is written out twice rather than imported, because importing the account list would drag every dialog in the add-on into the service's import closure; a static assertion holds the two equal
- [Phase ?]: The settings schema conversion was pulled out of Phase 7 into Phase 3: the <level> element AUTH-19 needs exists only in the versioned schema, so the requirement was unimplementable against the old file
- [Phase ?]: resume_playing and save_resume_watched are declared at Advanced, not Basic. Their Krypton visibility condition was constantly false on any supported Kodi, so dropping it as KODI-06 requires would otherwise have put two settings that do nothing in front of an ordinary user
- [Phase ?]: The stale-settings-row assertion was widened to read the <data> child as well as the action attribute. The versioned schema has no action attribute, so left alone the assertion would have kept running and stopped being able to fail
- [Phase ?]: client_id declares allowempty, because empty is the value that means 'use the built-in registration' and without it the keyboard dialog will not accept the setting's own default
- [Phase ?]: Only AUTH-19, KODI-05, KODI-06 and KODI-08 were marked Complete by 03-11. AUTH-02, AUTH-18 and AUTH-23 are declared by later plans and stay Pending
- [Phase ?]: The manifest disclaimer states the shipped flow; the third party's source link and self-hosting invitation are dropped, not reworded, because they now describe nothing
- [Phase ?]: Three vendored files converted CRLF to LF during this phase are recorded in VENDORED.md rather than converted back; a conversion is itself a whole-file rewrite and would bury the problem a commit deeper
- [Phase ?]: resources/skins/ is named as vendored surface: ten of the 38 copied files live outside resources/lib/vendor/, which the record never said
- [Phase ?]: Only AUTH-23 was marked Complete by 03-12. AUTH-02 is declared by 03-13 and DIST-01 by 03-14, so neither is 03-12's to close; VND-09 was already Complete and is now true again
- [Phase ?]: A granted scope may only be tested by membership, never by equality, prefix or position: the live provider returned 'openid profile email https://graph.microsoft.com/Files.Read' - email unrequested, offline_access absent despite a refresh token
- [Phase ?]: A value chosen to redact cannot be reused to discriminate: comparing refresh.fingerprint output reported a false rotation FAIL, and a PASS from it would have been equally unearned
- [Phase ?]: [Phase 03]: The add-on ran on the TCL Android TV 12 for the first time and signed in from the sofa; AUTH-01 is observed rather than argued. Android 12, Kodi 21.2, stock Estuary, installed from a USB drive through Kodi's own file manager with no network debugging channel ever opened
- [Phase ?]: [Phase 03]: AUTH-05 passes only after 24702ff took the code to WeatherTemp (120px); it failed at font60. The largest font a skin offers is a fact about the skin's Font.xml, not about the number in the layout
- [Phase ?]: [Phase 03]: AUTH-06 and AUTH-22 are left Pending at the end of the phase because a clause of each was never observed - the focused expiry action and the per-row context menu. A conjunction with an unmeasured half is not marked
- [Phase 03]: Both closed after phase verification, on readings taken later on 2026-08-23. AUTH-06: on expiry "get a new code" arrives already focused, and the d-pad reaches both buttons in order - the mark rests entirely on that, because QRDialogProgress has zero automated coverage. AUTH-22: the per-row context menu was opened and seen OFFERING re-authorise and remove, which is the requirement's own sentence; whether either action works end to end is still unrun and is not claimed
- [Phase 03]: KODI-02's checkbox was restored to unchecked. It had disagreed with its own sentence, its traceability row and STATE.md since c3c491e, the Phase 1 completion commit, and survived all fourteen Phase 3 plans. It stays unchecked rather than narrowed into a pass: a requirement dropped by decision is not a requirement met
- [Phase 03]: AUTH-20 is unchecked, not Complete. Tokens and delta tokens are isolated per account; cache keys are not, and Phase 4 owns that clause by name because it builds the listing cache. The same conjunction rule that governs AUTH-06 and AUTH-22 applies, and this is the one whose unmet clause is a leak between accounts
- [Phase 03]: Phase 3 added a CI-01 violation - resources/lib/auth_context.py imports xbmc outside resources/lib/kodi/, which does not exist. Recorded against the requirement, against ROADMAP Phase 2 and as deferred item 17, and deliberately NOT fixed: the adapter layout is Phase 2's design and Phase 2 has not been planned
- [Phase ?]: [Phase 03]: A credential reached a television screen, not a log: OAuth2._validate_access_tokens built its message from the token blob and _handle_exception renders that onto a Kodi dialog. The redaction rule now covers every raise in shipped source, not just assignments to report names
- [Phase ?]: [Phase 03]: Installing by URL does not work on Android TV - add-source browse needs a directory listing and a repository install is itself a zip install - so every device re-test costs a USB round trip. Phase 5's problem, recorded rather than worked around

### Pending Todos

None yet.

### Blockers/Concerns

**Resolved 2026-08-22 — the load-bearing unknown is settled.** The `/common` authority works with this project's own `client_id` for both a work/school account and a personal Microsoft account, verified end-to-end before any code was written. Conditional Access on the E5 Developer tenant did not block device code flow. Evidence and the full endpoint matrix: `.planning/research/SPIKE-DEVICE-CODE.md`. Registration in use: `efe197b3-5c14-4d67-810f-e10406742a06`. **SETUP-01, SETUP-02, SETUP-03 and SETUP-05 are checked off as of 2026-08-23** on that evidence — `signInAudience: AzureADandPersonalMicrosoftAccount`, `requestedAccessTokenVersion: 2`, `isFallbackPublicClient: true`, `passwordCredentials`/`keyCredentials` empty, and tokens acquired live from two work/school accounts and one personal account. **SETUP-04 stays open**: there is no registration runbook in the repo, and the registration cannot be recreated from anything written down here.

**Settled 2026-08-22 — the Android device question, both halves.** The maintainer has an Android TV box running Android 11/12, and it is the primary design target. It is **not** a test device: driving it for a per-phase acceptance pass is too inconvenient to be honest about doing. So CI-06 now reads: per-phase acceptance on Windows and on an **Android phone** running Kodi over `adb`; the TV is exercised by use and checked before release.

> **Superseded 2026-08-23, and CI-06 has now been rewritten to match.** The maintainer has directed that the TCL Android TV 12 is the **primary acceptance device**, and that Windows is not a target at all. The Windows and phone halves of CI-06 are dropped; the emulator and phone stand in for the TCL only on API-level questions. The first run on the TCL itself is recorded against **Phase 3**, deferred on timing rather than on priority: Phase 1 leaves the add-on able to install and open dialogs and nothing more. The paragraph below still holds on the technical point — an API-matched Android instrument is a sound proxy for storage and locking questions and not for D-pad, readability or performance — but read "checked before release" as no longer the plan. The four **CI-06 exception** notes in ROADMAP Phases 3, 4, 5 and 6 exist because a phone could not answer a question about the television; running those checks on the television resolves them, and each is resolved when its phase is planned rather than deleted in bulk.

The phone is a sound proxy for every OS-level question — storage paths, file mode bits, `O_EXCL`, loopback binding — because those follow the API level, not the form factor, and the phone matches the box's Android 11/12 storage regime. It is not a proxy for D-pad focus, 10-foot readability, or low-end performance, and no criterion pretends otherwise: four phase criteria that made TV-only claims (Phase 3 sign-in flow, Phase 4 listing timings, Phase 5 install-with-a-remote, Phase 6 playback) are marked in ROADMAP.md with a **CI-06 exception** to resolve when those phases are planned.

Two consequences worth carrying forward. **Android 11/12 kills Pitfall 18 on this device** — from Android 11 the app's own `Android/data` bypasses FUSE, so `chmod 0600` genuinely applies and no other app can read the profile. That removes the Android amplifier from the `eval()` threat model here, though not for users on Android 9/10 boxes (Fire OS 7 is Android 9), so the design still assumes the worst case. And **the two decisive playback tests need no Android at all**: the URL-latch question is Kodi C++ core, reproducible on the Windows Kodi 21.3 already installed, and the `downloadUrl` lifetime question is pure HTTP against a token `verify_device_code.py` already obtains. Both are runnable before Phase 1 starts, and PLAY-07's result decides Phase 6's ordering.

Open concerns:

- **The E5 Developer tenant hosting the `client_id` may not last.** Microsoft 365 Developer tenants renew on activity and the programme has tightened. If that tenant lapses, the embedded `client_id` dies for every installed copy simultaneously — the worst possible failure distribution. Registering under a personal Microsoft account instead would remove the expiry entirely. Decide before the first public release.
- **AUTH-18 cannot be fully verified yet.** No tenant that actually blocks third-party apps has been tested, so the exact `AADSTS` code that should trigger the custom `client_id` escape hatch is still unknown. The escape hatch is worthless if the user is never told it exists.
- **No migration path exists, by design.** The add-on ships under a new id (`plugin.onedrive.kn`) so there is no prior profile to read, and tokens could not have been carried over anyway. Anyone coming from v2.3.0 simply signs in.
- **Graph fixtures must be recorded from both drive classes.** The spike found real material worth capturing: Vietnamese names with diacritics and spaces on both drives, and the OneDrive Personal Vault, which Graph returns without a `folder` facet so naive detection renders it as a file (BROWSE-16). **Narrowed 2026-08-23**: the Business set is recorded now, the Personal set is deferred. The requirement's labelling rule is what keeps this honest — an unlabelled fixture set silently starts reading as "both".
- **SETUP-04 is the only open Azure prerequisite.** The registration exists, works, and has been read back through Graph, but nothing in the repo says how to recreate it. The runbook must carry the `AADSTS7000218` symptom verbatim — that is the error a `false` `allowPublicClient` produces, and it actively misdirects toward embedding a client secret.
- ~~01-07 acceptance pass: the install matrix on Kodi 19/20/21.3/22 and the Windows acceptance row cannot run from this shell.~~ **Closed 2026-08-23, and not by being solved.** The session blocker later cleared, and the leg was then dropped by decision — Windows is not a target. The Android row remains filled and clean; the Windows rows remain unfilled and are recorded as such. **KODI-02 is not met and stays unchecked.**
- **The Kodi 19 refusal has only uncontrolled evidence.** A harvested log from an unobserved run shows Kodi 19.5 refusing the zip for the declared reason (`The dependency on xbmc.python version 3.0.1 could not be satisfied`), on an unverified profile. KODI-01 is left checked on that basis and flagged, not silently accepted — the maintainer decides whether to re-run it once cleanly.
- **The Phase 1 acceptance row ran on an Android 11 emulator, one API level below the TCL Android TV 12 it stands in for.** Nothing about API 31, real GPU, D-pad focus, readability or low-end performance is established. The first run on the TCL is recorded against Phase 3.
- Plans 03-08 and 03-09 both verify with pytest tests/test_auth_gates.py -k (broker or redact) and neither can be green there: the broker sweep also reads the settings row (03-11) and the manifest disclaimer (03-12), and the redaction sweep also reads ui/addon.py and errorreport.py (03-09). Read the named sites; do not weaken the sweeps.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Restored features | Resume/watched sync, STRM export (video only), slideshow, delta sync | v2 | 2026-08-22 |
| Browsing | Server-side `$orderby` | v2 | 2026-08-22 |
| Accounts | SharePoint document libraries as a tested target | v2 | 2026-08-22 |
| Drive type | OneDrive Personal — fixtures, browse pass, playback pass, download-URL lifetime | Deferred, not dropped | 2026-08-23 |
| Platforms | The Windows acceptance leg and the Kodi 19/20/21/22 install matrix (KODI-02) | Dropped — not a target | 2026-08-23 |
| Distribution | Phase 5 apart from DIST-01 — hosted repository, unattended N to N+1 update | Deferred | 2026-08-23 |
| Phases | Phase 7 apart from criterion 4; Phase 8 apart from REL-01; CI harness CI-01..05 | Deferred | 2026-08-23 |

## Session Continuity

Last session: 2026-08-23T09:04:33.933Z
Stopped at: Completed 03-14-PLAN.md - Phase 03 fully executed, awaiting verification
Resume file: None
