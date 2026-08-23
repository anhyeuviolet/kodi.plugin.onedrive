# Requirements: OneDrive Kodi Add-on — Refactor

**Defined:** 2026-08-22
**Core Value:** Sign in from the couch with a remote, and play a file from OneDrive.

Scope note: this is a brownfield refactor. Requirements below describe the target state, not new product surface. Where the existing add-on already does something, the requirement is that it keeps working after the rewrite. Every requirement is checkable against either an automated test or a named manual acceptance step on real hardware.

### Standing scope notes (set 2026-08-23)

These two narrow several requirements at once. They are written here so the narrowing is stated in one place rather than re-argued in each.

**S1 — The goal is that this add-on runs on the owner's TCL Android TV 12.** That device is the primary acceptance device and the primary consumer. Sharing the add-on with anyone else is secondary. Anything that blocks the TCL path is deferred to a later phase or milestone rather than solved in place, and anything that does not serve it is not a per-phase obligation. Windows is not a target. See CI-06.

**S2 — OneDrive Business is the current drive type.** The owner uses a work/school account. Personal remains in scope as a requirement and is **deferred, not deleted**: it is tested later, not now. Where a requirement demands both drive types, the immediate obligation is Business; the Personal half stays written down and unchecked until it is exercised.

This narrowing is known to cost no future work on the one place it could have. `.planning/research/SPIKE-DEVICE-CODE.md` measured the drive endpoints against live accounts: `GET /me/drives` returns 200 on business and **403 `accessDenied`** on personal, `GET /drives` returns 403 on both, and **`GET /me/drive` returns 200 on both**. BROWSE-08 already fixes `/me/drive` as the endpoint, so the endpoint the add-on uses already serves both account classes. Deferring Personal testing therefore defers a test, not a design decision, and nobody should "optimise" the Personal half away on the grounds that only Business is being exercised.

## v1 Requirements

### Setup (maintainer prerequisites — not code)

- [x] **SETUP-01**: An Azure application is registered with `signInAudience: AzureADandPersonalMicrosoftAccount` and `requestedAccessTokenVersion: 2`, verified by reading the manifest back rather than trusting the portal UI. **Satisfied before Phase 1**: registration `efe197b3-5c14-4d67-810f-e10406742a06`, both values read back through Graph — not from the portal UI, which is exactly what this requirement asks for. Evidence: `.planning/research/SPIKE-DEVICE-CODE.md`
- [x] **SETUP-02**: `allowPublicClient: true` is set on that registration; leaving the `false` default makes the token endpoint demand a client secret. **Satisfied before Phase 1**: the manifest read back shows `isFallbackPublicClient: true`, which is the Graph API name for the same setting the portal labels "Allow public client flows". Device code flow completed against it in three live runs, which it could not have done at the `false` default. Evidence: `.planning/research/SPIKE-DEVICE-CODE.md`
- [x] **SETUP-03**: No client secret or certificate exists on the registration, and none appears anywhere in the repository. **Satisfied before Phase 1**: `passwordCredentials` and `keyCredentials` both empty in the manifest read back through Graph, and no secret has ever been committed. Evidence: `.planning/research/SPIKE-DEVICE-CODE.md`
- [x] **SETUP-04**: A written registration runbook lives in the repo, including the `AADSTS7000218` symptom of skipping SETUP-02. **Satisfied by 03-03 and completed by 03-13**: `docs/AZURE-REGISTRATION.md` is tracked, quotes the `AADSTS7000218` response verbatim and forbids the client-secret "fix" it invites, and carries the manifest values needed to recreate the registration. `tests/test_vendor_gates.py::test_runbook_contains_aadsts7000218` asserts all of that by name, so the document cannot silently lose it. 03-13 added the acceptance section: what a live sign-in through the shipped package returned, and what it could not tell anyone
- [x] **SETUP-05**: Two test accounts are available — one personal Microsoft account and one work/school account. **Satisfied before Phase 1**: tokens were acquired live from two distinct work/school accounts in the E5 tenant and from one personal Microsoft account, the last confirmed genuine by the well-known MSA tenant id `9188040d-6c67-4c5b-b112-36a304b66dad`. Evidence: `.planning/research/SPIKE-DEVICE-CODE.md`. **Narrowed by S2**: both accounts exist and both work, but the drive being exercised from here on is the Business one; Personal-drive fixtures and passes are deferred, not dropped
- [x] **SETUP-06**: A clean test environment exists — a Kodi profile with no sibling cloud-drive add-ons installed, plus an Android instrument running Kodi and reachable over `adb`. The **TCL Android TV 12 is the primary acceptance device** — it is what this add-on is written for; a phone or emulator stands in for it only on API-level questions (see CI-06). **Qualified**: no Android phone was ever connected. An emulator stood in — AVD `kodi_api30`, system image `android-30;google_apis;x86_64`, Android 11 / API 30, software-rendered through SwiftShader — recorded as an approved substitution in `.planning/phases/01-vendor-lift/01-01-SUMMARY.md` deviation 1. Its storage-regime, file-mode and `adb` claims hold; D-pad focus, ten-foot readability, real GPU and codec behaviour and low-end performance are untested, and its API level is one below the TCL's

### Vendoring

- [x] **VND-01**: `script.module.clouddrive.common` v1.4.0 is vendored into the repo from the `matrix` branch, not the `master` branch, which carries the Python 2 / Kodi 18 line
- [x] **VND-02**: The vendored package is renamed under this add-on's namespace, with the name decided before the first file is copied
- [x] **VND-03**: The module's `resources/` contents are merged into this add-on's existing `resources/` rather than vendored as a second importable top-level package
- [x] **VND-04**: Every hardcoded `script.module.clouddrive.common` id lookup resolves to this add-on's own id, version, and profile directory
- [x] **VND-05**: The vendored account store uses JSON instead of `repr()` and `eval()`
- [x] **VND-06**: Every outbound HTTP call passes an explicit `timeout=`
- [x] **VND-07**: The module's own `xbmc.service` extension point is folded into this add-on's `service.py`, with an explicit decision recorded about what survives
- [x] **VND-08**: Skin XML and media are copied and every dialog construction site's path argument is updated
- [x] **VND-09**: `VENDORED.md` records upstream URL, branch, version, commit SHA, per-subtree licence, and local modifications; both the GPL-3.0 and Apache-2.0 licence files are preserved
- [x] **VND-10**: The add-on behaves identically after the vendor commit, verified on a clean profile with every sibling cloud-drive add-on uninstalled, with every dialog opening
- [x] **VND-11**: The external `<import>` of `script.module.clouddrive.common` is removed from `addon.xml`

### Identity and attribution

- [x] **ID-01**: The add-on id becomes `plugin.onedrive.kn`, and every `plugin://` reference, profile path, and internal id lookup follows it — so this is a genuinely separate add-on that can never collide with the official `plugin.onedrive` in the Kodi repository
- [x] **ID-02**: `provider-name` in `addon.xml` names the current maintainer, and the display name distinguishes this add-on from the original in the Kodi UI
- [x] **ID-03**: `LICENSE.txt` (GPL-3.0-or-later) is retained unchanged and every existing copyright notice is preserved — the code is a derivative work and the licence requires this
- [x] **ID-04**: A `CREDITS.md` (or a README section) states that the add-on originates from `plugin.onedrive` by Carlos Guzman (cguZZman) and bundles `script.module.clouddrive.common`, with licences named
- [x] **ID-05**: The repository no longer belongs to the upstream fork network, and its commit history is preserved rather than squashed — squashing would destroy the attribution record while keeping the code

### Authentication

- [x] **AUTH-01**: A user signs in by reading a code off the TV and entering it on a phone, without typing a URL, username, or password on the remote. **Observed by 03-14 on the TCL Android TV 12** (Android 12, Kodi 21.2, stock Estuary): a work/school account was added end to end from the television — the code was read off the screen and entered on a phone, and nothing was typed on the remote. This is the project's core value, seen for the first time on the hardware it exists for
- [x] **AUTH-02**: The add-on ships a public `client_id` and requires no Azure setup, no server, and no token copy-paste from the user. **Verified live by 03-13**: the harness took the built-in `CLIENT_ID` with no argument and acquired a real token from the live provider through the shipped auth package. No registration was made, no broker or server was contacted — `AUTH-23` removed the last of that — and the user's only input was a code typed on a phone, which is not a token
- [ ] **AUTH-03**: Sign-in works for both a personal Microsoft account and a work/school account against the chosen authority — verified end-to-end with the project's own registration, not a first-party client. **Still Pending after 03-14, and now half done twice over**: the work/school half was proven live through the shipped package by 03-13 and again on the television by 03-14. The personal-account half remains a **deferred second run** — the spike already acquired a token on a personal account against this registration, so what is outstanding is a run, not a design question. The requirement says both, and both is not what has happened
- [x] **AUTH-04**: The requested scope set is `https://graph.microsoft.com/Files.Read offline_access openid profile`, fully qualified, with no `Files.Read.All`, no write scope, and no `.default`
- [x] **AUTH-05**: The device-code dialog renders the code at the largest font the skin offers, legible from a sofa. **Settled by 03-14 by a person reading a screen**, which is the only instrument that exists — a skin resolves a font name at render time and substitutes silently. **It failed on the first build**: at `font60` the code was legible but small from a normal seat, and `font60` was never the largest font Estuary offers. It passes at `WeatherTemp` (120px) after `24702ff`, read on stock Estuary so no substitution is in play. A requirement that needed a fix to pass is a different fact from one that passed first time, and the failing reading is kept for that reason
- [x] **AUTH-06**: The dialog shows a live expiry countdown and, on expiry, offers a focused "Get a new code" action. **Both halves are now read, and they were read at different times — which is why the record keeps both dates.** The **countdown clause** passed on the television during 03-14, and only after `24702ff`: control 1002 had been overflowing its box since 03-06 and the line pushed out of view was the countdown itself, so it had never been visible on any device. The **focus clause** was left Pending by 03-14, deliberately, because the expiry path was skipped; it was observed in a **later session on 2026-08-23, after 03-14's summary had been written** — on expiry the "get a new code" action arrives already focused, and the directional pad reaches both dialog buttons in order. **This mark rests entirely on the human reading.** Phase-3 verification measured `QRDialogProgress` and found **zero automated coverage**: `set_code`, `set_remaining`, `set_expired`, `reset_for_new_code`, `is_new_code_requested`, `format_remaining` and `_render_text` are all called from `_await_authorisation` and none is touched by any test. `set_expired()` does call `setFocus(button)` under a once-only guard, but a `setFocus` call inside an `xbmcgui.WindowXMLDialog` subclass is not evidence that focus landed on a real skin — a person in front of the television is the only instrument this requirement has, and the mark is exactly as strong as that one reading
- [x] **AUTH-07**: Cancelling sign-in with Back or Esc leaves no partially-created account behind. **Observed by 03-14**: leaving sign-in with Back returned an account list exactly as it was. The remote has no Esc key, so Back is the only form the acceptance device can produce. The code half is pinned independently by `tests/test_auth_gates.py::test_the_signin_flow_stamps_without_writing_anything` from `c768699`, which holds the no-write property at the seam that fix touched so the cheap repair cannot be taken later. The repeat form — a second sign-in cancelled part-way — was not separately reported
- [x] **AUTH-08**: Any QR code shown encodes only the server-supplied `verification_uri`; the verification URI is never hardcoded, because it differs per authority. **Observed by 03-14**: the image was scanned with a phone camera and resolved to the address the dialog showed. It scans at **280x280** after `24702ff`; at the shipped 150x150 it was readable but small. The "encodes only the `verification_uri`" half is structural and already proven — the provider returns no `verification_uri_complete`, the encoder is fed the provider's own address and nothing else, and an insecure source is refused
- [x] **AUTH-09**: The token-polling loop is an allow-list — it continues only on `authorization_pending` and `slow_down`, and stops on anything else
- [x] **AUTH-10**: Pending polls arriving as HTTP 400 with a JSON body are parsed as protocol responses, not treated as transport failures
- [x] **AUTH-11**: Refresh tokens are stored as atomically-written JSON under `special://profile/addon_data/`, never in a Kodi setting
- [x] **AUTH-12**: Every token response is written back in full; when a response omits `refresh_token`, the previous one is retained
- [x] **AUTH-13**: An automated test proves the persisted refresh token changes across two consecutive refreshes. **Satisfied by 03-07**: `tests/test_refresh.py::test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens` asserts three distinct values read back **from the file on disk**, comparing whole tokens. **Confirmed live by 03-13**: the same property held against the real provider through the shipped store — `sha256:bf92b757a58b`, `sha256:1b8a11103c33`, `sha256:b0dc7a23cd00`. The automated half proves the code keeps what it is given; the live half proves the provider gives something new
- [x] **AUTH-14**: Concurrent refresh across the plugin and the service is serialised by an `os.open(..., O_CREAT|O_EXCL)` lock with a stale-lock breaker; neither `threading.Lock` nor `fcntl.lockf` is used for this
- [x] **AUTH-15**: A refresh that loses the race and receives `invalid_grant` re-reads the store and adopts the winner's token rather than signing the user out
- [x] **AUTH-16**: A proactive refresh runs on Kodi startup well inside the 90-day refresh-token lifetime
- [x] **AUTH-17**: The background service never opens a sign-in dialog; only the plugin may prompt interactively. **Code half proven by 03-10; observable half seen by 03-14** — no dialog appeared over the home screen at boot on the television. **Named weakness, recorded rather than smoothed over**: that is a negative observation from ordinary use, reported as "nothing unusual seen", and the separate checklist row "the background service starts at login" was not reported, so the premise that the service ran at all is unconfirmed on this device. It is the weakest of the marks 03-14 made
- [ ] **AUTH-18**: A tenant that blocks the app produces a specific message naming the cause and pointing at the custom `client_id` setting — not a generic failure
- [x] **AUTH-19**: A custom `client_id` setting exists at Expert level, empty by default
- [ ] **AUTH-20**: Multiple accounts are supported, with tokens, delta tokens, and cache keys isolated per account. **Two of the three clauses are delivered; the third is not, and this was marked Complete unqualified until phase-3 verification measured it.** Tokens are isolated — `accounts/<key>.json` and `accounts/<key>.lock`, one pair per account, with an unsafe key rejected rather than sanitised so two keys can never map onto one file. Delta tokens are isolated — `change_token` sits on the drive record inside the per-account row. **Cache keys are not**: `Cache(self._addonid, 'page'|'children'|'items', …)` in `service/source.py:50-52`, `source.py:411-413` and `ui/addon.py:1146-1148` takes no account key at all. **Phase 4 owns the outstanding clause by name** — see the ROADMAP's "Inherited constraint from Phase 3" — because Phase 4 is where the listing cache is built and keying it by account from the first commit is the only way to avoid either a migration or a silent cross-account leak. Left unchecked on the same rule that leaves AUTH-06 and AUTH-22 unchecked: a conjunction with an unmet clause is not marked. This is the one whose unmet clause is a leak between accounts rather than an unobserved reading, which is why it is not qualified into a pass
- [x] **AUTH-21**: Account labels come from Graph; no account name is ever typed on a remote
- [x] **AUTH-22**: The add-on root is the account list, with an "Add an account…" row and a per-row context menu offering re-authorise and remove. **Marked on exactly what was seen, and the wording matters.** The root is the account list and the add-account row works — the television sign-in went through it during 03-14. The per-row context menu, which 03-14 left unopened, was **opened in a later session on 2026-08-23, after that summary had been written, and was observed offering both re-authorise and remove**. The requirement's own sentence asks that the menu *offer* those two actions, and the menu was seen offering them. **What is NOT known: whether either action was exercised end to end.** Re-authorising without creating a second row, and removing a row and leaving the add-account row behind, are two separate checklist rows in `03-14-SUMMARY.md` and both are still NOT RUN. Nothing here should be read as saying the actions were tried. Their code paths are gated — `test_the_account_list_offers_re_authorisation` reads the menu entries specifically, `test_removing_an_account_deletes_its_stored_credential` covers the removal, and since 2026-08-23 `test_the_account_list_always_offers_a_route_into_sign_in` drives the listing and holds the add-account row itself, which nothing did before — so this is unobserved behaviour with a code proof behind it, the same shape AUTH-17 is recorded in
- [x] **AUTH-23**: The `sign-in-server` setting and every code path referencing an external OAuth broker are gone

### Browsing

- [ ] **BROWSE-01**: Folders list correctly for personal and business drives, one page at a time, without buffering the whole folder. **S2**: the immediate obligation is the Business drive; the Personal half is deferred, not dropped
- [ ] **BROWSE-02**: Pagination is iterative, so a very large folder cannot hit a recursion limit
- [ ] **BROWSE-03**: Cancelling mid-listing returns an empty list, never `None`, and never crashes
- [ ] **BROWSE-04**: A search does not corrupt subsequent folder listings — no request-scoped state persists on the provider between calls
- [ ] **BROWSE-05**: Names containing `#`, spaces, and literal `%` resolve correctly, verified on both a Personal and a Business drive because the reserved-character sets differ. **S2**: verify on Business now; the Personal verification is deferred and must not be deleted — the differing reserved-character sets are the entire reason this requirement names both
- [ ] **BROWSE-06**: Search queries containing a single quote succeed
- [ ] **BROWSE-07**: Graph responses are read defensively; a missing or reshaped field produces a handled error, not a `KeyError` traceback
- [ ] **BROWSE-08**: Drive access uses `GET /me/drive`, the only endpoint verified to work for both account classes — `/me/drives` returns 403 on personal accounts and `/drives` returns 403 on both. See `.planning/research/SPIKE-DEVICE-CODE.md`
- [ ] **BROWSE-09**: One central HTTP layer honours `Retry-After` on 429, sleeps via `Monitor.waitForAbort`, and retries once on 401
- [ ] **BROWSE-10**: Every `ListItem` is constructed with `offscreen=True`, and items are added in chunks
- [ ] **BROWSE-11**: `endOfDirectory` is called exactly once per invocation, including on the error path
- [ ] **BROWSE-12**: Thumbnails are fetched via `$expand=thumbnails` at the smallest useful size
- [ ] **BROWSE-13**: Existing pseudo-folders (Recent, Shared with me, Camera Roll) keep working
- [ ] **BROWSE-14**: A 500-item folder lists at an acceptable speed on real Android TV hardware
- [ ] **BROWSE-16**: `extract_item()` correctly classifies the OneDrive Personal Vault, which Graph returns without a `folder` facet and which naive folder detection therefore renders as a file

### Playback

- [ ] **PLAY-01**: Video, audio, and image files play from both personal and business drives. **S2**: Business now, Personal deferred
- [ ] **PLAY-02**: A loopback HTTP endpoint answers each request by resolving a fresh download URL and returning a 302; Kodi is never handed a Graph URL directly
- [ ] **PLAY-03**: The redirector binds to a dynamically allocated port and requires a per-session random path token, so a guessed item id is not sufficient
- [ ] **PLAY-04**: The download URL is resolved at play time on every request and is never cached, never placed in a directory item URL, and never written into an exported `.strm`
- [ ] **PLAY-05**: `setResolvedUrl` is called exactly once per playback invocation
- [ ] **PLAY-06**: Seeking works, including after a 20–30 minute pause on real Android TV hardware
- [ ] **PLAY-07**: The real download-URL lifetime is measured separately for Personal and Business drives and the numbers are recorded. **S2**: the Business measurement is the one that gates Phase 6; the Personal measurement is deferred. Keep them separate rather than generalising one number to both — the two drive classes are served by different back ends
- [ ] **PLAY-08**: Same-name subtitles are discovered across Kodi's full extension set, including language suffixes and VOBsub `.idx`/`.sub` pairs, and failure is silent
- [ ] **PLAY-09**: Subtitles are served through the same redirector as media, for the same expiry reason
- [ ] **PLAY-10**: Durations reach Kodi as integers

### Kodi modernization

- [x] **KODI-01**: `addon.xml` declares `<import addon="xbmc.python" version="3.0.1"/>`, installing on Kodi 20, 21, and 22 and being rejected by Kodi 19. **Qualified**: the declaration itself is verified in the file. The Kodi-19-refusal half is evidenced **only** by a harvested `kodi.log` from an uncontrolled, unobserved Kodi 19.5 run on an unverified profile — the log really does carry `The dependency on xbmc.python version 3.0.1 could not be satisfied`, and that content was re-read, but no controlled observed run was ever performed and re-reading a file cannot fix that. The install half has controlled evidence for Kodi 21.3 on Android only; 20 and 22 rest on the same class of uncontrolled log. `.planning/phases/01-vendor-lift/01-07-SUMMARY.md` escalates this for a decision. The checkbox stands on acceptance of that evidence, not on a controlled run
- [ ] **KODI-02**: The add-on installs and runs on Kodi 20 Nexus, 21 Omega, and 22 Piers. **Narrowed by decision on 2026-08-23 and deliberately left unchecked**: the multi-version install matrix was dropped along with the Windows leg, because this add-on targets one device — a TCL television running Android TV 12 — and backwards compatibility across Kodi versions is not being pursued. Uncontrolled logs from an interrupted run show Kodi 20.5 and 22.0-BETA1 installing the zip and starting both entry points, but that is not an acceptance pass and is not treated as one. If the requirement is still wanted, it is verified at the release stage; see `.planning/phases/01-vendor-lift/01-07-SUMMARY.md`. **The box itself said the opposite of this sentence for the whole of Phase 3.** It was `[ ]` in every commit up to `5f6271b` and was flipped to `[x]` by `c3c491e`, the Phase 1 completion commit, which flipped five boxes at once; the other four agree with their traceability rows and this one never did. It then survived all fourteen Phase 3 plans and their requirement-marking passes, and phase-3 verification found it by machine-comparing all 94 checkboxes against all 94 traceability rows — it was the only disagreement in the file. Restored to `[ ]` on 2026-08-23, which is what this sentence, the traceability row and `STATE.md` have all said throughout. **It stays unchecked rather than being narrowed into a pass**: the decision was that Windows and the four-version Kodi matrix are not targets, and a requirement dropped by decision is not a requirement met
- [ ] **KODI-03**: List items use typed InfoTag setters, and this lands in the same commit as the integer-duration fix
- [ ] **KODI-04**: A full browse-and-play `kodi.log` contains zero `is deprecated` warnings from this add-on
- [x] **KODI-05**: `resources/settings.xml` uses the `<settings version="1">` schema with section, category, and group structure
- [x] **KODI-06**: Krypton-era visibility conditions are gone
- [ ] **KODI-07**: The `SourceService`, its HTML index, and both the `allow_directory_listing` and `port_directory_listing` settings are deleted from the codebase
- [x] **KODI-08**: Third-party error reporting code and the `report_error` setting are deleted; errors go to `kodi.log` only

### Release readiness

- [ ] **REL-01**: The registration hosting the embedded `client_id` is one the project can keep indefinitely — the Microsoft 365 E5 Developer tenant renews on activity, and if it lapses the `client_id` dies for every installed copy at once. Decided before anyone is told to install

### Quality and CI

- [ ] **CI-01**: Only `resources/lib/kodi/` imports `xbmc*`; an automated test enforces this. **Phase 3 moved this requirement's target, and the move is recorded rather than acted on.** `resources/lib/kodi/` does not exist in the tree. Phase 3 added `resources/lib/auth_context.py`, which imports `xbmc` at module level and sits directly under `resources/lib/` — one directory above the only place CI-01 permits it. The module is the thin adapter this requirement's architecture calls for: a closed list of four things, documented as such, and it is precisely what keeps `resources/lib/auth/` free of any `xbmc` import at all. Only its location is wrong. **Phase 3 did not restructure it**: where the adapter directory lives and what the enforcing test reads are Phase 2's design, Phase 2 has not been planned, and a phase running ahead of another does not get to settle that other phase's layout. Recorded as deferred item 17 in `.planning/phases/03-authentication/deferred-items.md`, with **Phase 2 named as owner**
- [ ] **CI-02**: Unit tests cover item extraction, pagination, path encoding, and OData literal quoting against recorded Graph JSON
- [ ] **CI-03**: Graph fixtures are recorded from both a Personal and a Business drive and are labelled by source. **S2**: record the Business set now; the Personal set is deferred. The labelling requirement is what makes the deferral safe — an unlabelled fixture set silently becomes "both"
- [ ] **CI-04**: CI runs the test suite plus `kodi-addon-checker` against the nexus, omega, and piers branches
- [ ] **CI-05**: CI fails on any occurrence of `client_secret`, `client_assertion`, `eval(`, or `script.module.clouddrive.common`
- [x] **CI-06**: Every phase carries a manual acceptance pass on the **TCL Android TV 12**, which is the primary acceptance device — it is the machine this add-on is written for and the only one whose failures matter to the goal. It is exercised from Phase 3 onward, the first point at which a run on it proves something an emulator could not; Phase 1 and Phase 2 predate that. There is **no standing obligation to pass on Windows or on a phone**: Windows is not a target. A stand-in — an Android phone or emulator at a comparable API level — is acceptable **only** for OS-level questions: storage paths, file mode bits, `O_EXCL`, loopback binding. Those follow the API level rather than the form factor, so an API-matched instrument answers them soundly. It answers nothing about D-pad focus order, ten-foot readability, real GPU and codec behaviour, or performance on a low-end SoC. Where the TCL genuinely cannot be driven for a phase, the pass is recorded as run on a stand-in, with the stand-in named and its limits stated — never written up as a TV pass
- [ ] **CI-07**: The release gate requires at least one full acceptance pass on a clean profile using a Business account

### Error handling

- [ ] **ERR-01**: Every failure state renders as a distinct, actionable sentence on screen — there is no log, console, or keyboard available to a TV user
- [ ] **ERR-02**: No network, expired token, tenant-blocked, admin-consent-required, and rate-limited states are each distinguishable from one another
- [ ] **ERR-03**: Quitting Kodi with a large listing in flight shuts down cleanly

### Distribution

- [x] **DIST-01**: A build produces an installable zip named `plugin.onedrive.kn-<version>.zip` with a single top-level `plugin.onedrive.kn/` directory, and its contents come from the git index rather than a filesystem walk
  - *Corrected in phase 3 (plan 03-02).* The original text named `plugin.onedrive`, written before this add-on took its own id. Kodi resolves an installed add-on by matching the archive's top-level directory against the id in the manifest inside it and refuses a mismatch at install, so the requirement as written was unsatisfiable against the current id. Pulled forward from phase 5 because installing on the TCL Android TV 12 requires an archive and phase 3's acceptance runs on that device.
- [ ] **DIST-02**: A self-hosted Kodi repository is published over HTTPS using the `<dir>` schema and SHA-256 checksums, never MD5 and never the flat pre-Gotham layout
- [ ] **DIST-03**: Installing the repository on Android TV requires entering a URL exactly once
- [ ] **DIST-04**: An N to N+1 update is confirmed to arrive without the user pressing "Check for updates"
- [ ] **DIST-05**: Published version numbers carry no pre-release suffix, which Kodi's version comparison sorts below the plain version

## v2 Requirements

Deferred. Tracked, not in the current roadmap.

### Restored features

- **REST-01**: Resume and watched-state sync
- **REST-02**: STRM library export, video only
- **REST-03**: Slideshow, without continuous background polling
- **REST-04**: Delta change sync, opt-in and default off, treating HTTP 410 with `resyncChangesApplyDifferences` as the invalidation signal and restarting from the `Location` header, never persisting a `None` change token

### Browsing enhancements

- **BROWSE-15**: Server-side `$orderby`, applied consistently with Kodi's own sort methods so that sorting is not silently limited to the loaded page

### Accounts

- **AUTH-24**: SharePoint document libraries as a supported, tested target

## Out of Scope

| Feature | Reason |
|---------|--------|
| Kodi 19 Matrix support | Keeping it forces the legacy settings schema and untyped InfoTag paths; the target platforms run Kodi 20+ |
| Self-hosting or maintaining an OAuth broker | The entire point of the auth rewrite is that no server is needed |
| Requiring users to register their own Azure app | A remote-and-TV audience cannot do this; the embedded `client_id` exists to avoid it |
| Browser-redirect or loopback-redirect login flow | Device code covers TV and desktop with one implementation; a second flow doubles the auth surface for marginal gain |
| Local HTTP directory-listing server (`SourceService`, port 8586) | Unauthenticated, an enumerable index of the whole drive, reachable by any app on an Android box, on by default, no remote-control use case, and the feature it serves is documented broken upstream. Distinct from the loopback 302 redirector, which is required |
| Third-party error reporting | OAuth stack traces carry tenant names, user principal names, drive ids, and file paths |
| `Files.Read.All`, `Sites.Read.All`, any write scope | Over-privileged for a read-only browser; every extra scope raises the chance a tenant admin blocks the app |
| Music STRM export | Kodi's music library does not support `.strm`; the sibling add-on ships it and documents it as broken |
| Byte-proxying playback through the add-on | The redirector hands off to Kodi's own reader; proxying bytes through Python costs CPU on constrained Android hardware for no benefit |
| Bundled subtitle search service | Kodi already has subtitle add-ons; duplicating that is scope creep |
| Slideshow auto-refresh | Requires continuous delta polling, the documented source of this category's CPU and memory complaints |
| Submitting to the official Kodi repository | Its review process adds constraints a primarily personal project does not need |
| Additional localizations | English suffices; the existing `en_gb` and `he_il` files stay as-is |
| New features beyond v2.3.0 parity | This is a refactor — restore what exists, then stop |

## Traceability

Mapped during roadmap creation. Every v1 requirement belongs to exactly one phase.

Phase names: 1 Vendor Lift · 2 Pure Core and CI Harness · 3 Authentication · 4 Browse · 5 Distribution · 6 Play · 7 Kodi Modernization · 8 Existing-User Migration and Release.

Cross-cutting notes. `CI-06` (per-phase manual acceptance on the TCL Android TV 12, the primary acceptance device, from Phase 3 onward; a stand-in only for API-level questions; no Windows obligation) is established in Phase 1 and inherited as a standard by every later phase; `CI-07` is the release gate and sits in the final phase. `ERR-01` to `ERR-03` land in Phase 4, the first point at which the central HTTP layer, the auth error map, and the listing error paths all exist, so the failure states can be shown to be distinguishable from one another rather than asserted piecemeal. `SETUP-01` to `SETUP-04` are the Azure registration and appear as a maintainer prerequisite block on Phase 3, not as implementation work; `SETUP-01`, `-02` and `-03` were satisfied by the owner before Phase 1 and are already checked, so only the `SETUP-04` runbook is outstanding there. `PLAY-10` sits in Phase 7 rather than Phase 6 because `KODI-03` requires the float-to-int duration fix to land in the same commit as the typed InfoTag setters.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 3 | Complete — satisfied before Phase 1, manifest read back through Graph |
| SETUP-02 | Phase 3 | Complete — `isFallbackPublicClient: true` in the manifest |
| SETUP-03 | Phase 3 | Complete — `passwordCredentials`/`keyCredentials` empty, none in repo |
| SETUP-04 | Phase 3 | Complete — `docs/AZURE-REGISTRATION.md`, gated by name; acceptance section recorded by 03-13 |
| SETUP-05 | Phase 2 | Complete — tokens acquired live from two work/school accounts and one personal |
| SETUP-06 | Phase 1 | Complete — qualified: emulator stood in for the phone |
| VND-01 | Phase 1 | Complete |
| VND-02 | Phase 1 | Complete |
| VND-03 | Phase 1 | Complete |
| VND-04 | Phase 1 | Complete |
| VND-05 | Phase 1 | Complete |
| VND-06 | Phase 1 | Complete |
| VND-07 | Phase 1 | Complete |
| VND-08 | Phase 1 | Complete |
| VND-09 | Phase 1 | Complete |
| VND-10 | Phase 1 | Complete |
| VND-11 | Phase 1 | Complete |
| ID-01 | Phase 1 | Complete |
| ID-02 | Phase 1 | Complete |
| ID-03 | Phase 1 | Complete |
| ID-04 | Phase 1 | Complete |
| ID-05 | Phase 1 | Complete |
| AUTH-01 | Phase 3 | Complete — set by 03-14. A work/school account was added end to end from the TCL Android TV 12 by reading the code off the screen and entering it on a phone; nothing was typed on the remote |
| AUTH-02 | Phase 3 | Complete — built-in `client_id` acquired a live token, no setup and no server |
| AUTH-03 | Phase 3 | Pending — half done. 03-13 verified a work/school account end-to-end through the project's own registration and the shipped package. The personal-account pass through that package is deferred; the spike already acquired a token on a personal account against this registration, so what is outstanding is a second live run, not a design question. **03-14 did not close it either**: the work/school half is now proven on the television as well, and no personal account was signed in there |
| AUTH-04 | Phase 3 | Complete |
| AUTH-05 | Phase 3 | Complete — set by 03-14, by a person reading the screen. Failed the first reading at `font60`; passes at `WeatherTemp` (120px) after `24702ff`, on stock Estuary |
| AUTH-06 | Phase 3 | Complete — both halves read, at different times. Countdown on the television during 03-14 and only after `24702ff` (it had never been visible before: control 1002 overflowed since 03-06 and the countdown was the line pushed out). The **focused expiry action** was observed in a later session on 2026-08-23, after 03-14's summary was written; the d-pad reaches both buttons in order. `QRDialogProgress` has **zero automated coverage**, so this mark rests entirely on that human reading |
| AUTH-07 | Phase 3 | Complete — set by 03-14. Back out of sign-in left the account list unchanged on the device; the remote has no Esc. Held at the code seam by `test_the_signin_flow_stamps_without_writing_anything` (`c768699`) |
| AUTH-08 | Phase 3 | Complete — set by 03-14. Scanned with a phone camera and resolved to the address the dialog showed, at 280x280 after `24702ff`; the encodes-only-the-address half is structural and was already proven |
| AUTH-09 | Phase 3 | Complete |
| AUTH-10 | Phase 3 | Complete |
| AUTH-11 | Phase 3 | Complete |
| AUTH-12 | Phase 3 | Complete |
| AUTH-13 | Phase 3 | Complete — automated proof in 03-07, confirmed against the live provider in 03-13 |
| AUTH-14 | Phase 3 | Complete |
| AUTH-15 | Phase 3 | Complete |
| AUTH-16 | Phase 3 | Complete |
| AUTH-17 | Phase 3 | Complete — set by 03-14, and the weakest of its marks. No dialog appeared over the home screen at boot ("nothing unusual seen"), on top of 03-10's code proof. The "service starts at login" row was not reported, so the premise of the negative observation is unconfirmed on this device |
| AUTH-18 | Phase 3 | Pending — UNVERIFIABLE HERE. The message and the escape hatch exist and the error table is tested, but no tenant available to this project blocks the grant, so the refusal cannot be produced on demand. Recorded as a gap on purpose: a pass claimed here is one nobody would ever go back and check |
| AUTH-19 | Phase 3 | Complete |
| AUTH-20 | Phase 3 | Partial — tokens and delta tokens are isolated per account by Phase 3; **cache keys are not**, and `Cache(self._addonid, …)` is still global. The remaining clause moves to Phase 4, which builds the listing cache and is told by the ROADMAP to key it by account from the first commit. Was marked Complete unqualified until phase-3 verification measured all three clauses against the tree |
| AUTH-21 | Phase 3 | Complete |
| AUTH-22 | Phase 3 | Complete — the root is the account list, the add-account row was used to sign in on the television, and the per-row context menu was **opened in a later session on 2026-08-23 and seen offering re-authorise and remove**, which is the requirement's own sentence. **Not claimed: that either action was exercised.** Both of those checklist rows are still NOT RUN; the paths are gated by tests, so this is unobserved behaviour with a code proof, not an unproven one |
| AUTH-23 | Phase 3 | Complete |
| BROWSE-01 | Phase 4 | Pending |
| BROWSE-02 | Phase 2 | Pending |
| BROWSE-03 | Phase 2 | Pending |
| BROWSE-04 | Phase 2 | Pending |
| BROWSE-05 | Phase 4 | Pending |
| BROWSE-06 | Phase 4 | Pending |
| BROWSE-07 | Phase 2 | Pending |
| BROWSE-08 | Phase 4 | Pending |
| BROWSE-09 | Phase 4 | Pending |
| BROWSE-10 | Phase 4 | Pending |
| BROWSE-11 | Phase 4 | Pending |
| BROWSE-12 | Phase 4 | Pending |
| BROWSE-13 | Phase 4 | Pending |
| BROWSE-14 | Phase 4 | Pending |
| BROWSE-16 | Phase 2 | Pending |
| PLAY-01 | Phase 6 | Pending |
| PLAY-02 | Phase 6 | Pending |
| PLAY-03 | Phase 6 | Pending |
| PLAY-04 | Phase 6 | Pending |
| PLAY-05 | Phase 6 | Pending |
| PLAY-06 | Phase 6 | Pending |
| PLAY-07 | Phase 6 | Pending |
| PLAY-08 | Phase 6 | Pending |
| PLAY-09 | Phase 6 | Pending |
| PLAY-10 | Phase 7 | Pending |
| KODI-01 | Phase 1 | Complete — qualified: the Kodi 19 refusal has uncontrolled evidence only |
| KODI-02 | Phase 1 | Narrowed — not met, moved out of Phase 1. The checkbox contradicted this row from `c3c491e` until 2026-08-23 and is now restored to unchecked; if the requirement is still wanted it is verified at the release stage, not here |
| KODI-03 | Phase 7 | Pending |
| KODI-04 | Phase 7 | Pending |
| KODI-05 | Phase 3 | Complete |
| KODI-06 | Phase 3 | Complete |
| KODI-07 | Phase 7 | Pending |
| KODI-08 | Phase 3 | Complete |
| CI-01 | Phase 2 | Pending — and its target moved while it waited. `resources/lib/kodi/` does not exist, and Phase 3 added `resources/lib/auth_context.py`, which imports `xbmc` outside it. Stated, not fixed: the layout is Phase 2's call. See deferred item 17 |
| CI-02 | Phase 2 | Pending |
| CI-03 | Phase 2 | Pending |
| CI-04 | Phase 2 | Pending |
| CI-05 | Phase 2 | Pending |
| CI-06 | Phase 1 | Complete — standing obligation, discharged for Phase 3 by 03-14's run on the TCL Android TV 12 itself. No stand-in was substituted and every row that could not be run is recorded as not run rather than omitted; the transparency prohibition held |
| CI-07 | Phase 8 | Pending |
| REL-01 | Phase 8 | Pending |
| ERR-01 | Phase 4 | Pending |
| ERR-02 | Phase 4 | Pending |
| ERR-03 | Phase 4 | Pending |
| DIST-01 | Phase 3 | Complete — **confirmed by 03-14 and 03-12's flag discharged.** 03-12 recorded that 03-02 had marked this while 03-14 still declared it, and asked 03-14 to confirm rather than alter it. The archive the build wrote installed through Kodi's own file manager on the television, from a USB drive, so the mark is now earned rather than merely defensible. Installing by URL does not work on that device — a Phase 5 problem, recorded as deferred item 16, and not a DIST-01 failure |
| DIST-02 | Phase 5 | Pending |
| DIST-03 | Phase 5 | Pending |
| DIST-04 | Phase 5 | Pending |
| DIST-05 | Phase 5 | Pending |

**Coverage by phase:**

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1. Vendor Lift | VND-01..11, ID-01..05, KODI-01, KODI-02, SETUP-06, CI-06 | 20 |
| 2. Pure Core and CI Harness | CI-01..05, BROWSE-02, BROWSE-03, BROWSE-04, BROWSE-07, BROWSE-16, SETUP-05 | 11 |
| 3. Authentication | AUTH-01..23, SETUP-01..04, DIST-01 | 28 |
| 4. Browse | BROWSE-01, BROWSE-05, BROWSE-06, BROWSE-08..14, ERR-01..03 | 13 |
| 5. Distribution | DIST-02..05 | 4 |
| 6. Play | PLAY-01..09 | 9 |
| 7. Kodi Modernization | KODI-03..08, PLAY-10 | 7 |
| 8. Release Readiness | CI-07, REL-01 | 2 |

**Coverage:**

- v1 requirements: 94 total
- Mapped to phases: 94
- Unmapped: 0 ✓

---
*Requirements defined: 2026-08-22*
*Traceability mapped: 2026-08-22*
