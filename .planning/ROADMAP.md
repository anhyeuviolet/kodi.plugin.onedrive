# Roadmap: OneDrive Kodi Add-on — Refactor

## Overview

The add-on's sign-in is unacceptable in one specific place: it routes the OAuth exchange through a third party, `drive-login.herokuapp.com`. That server was long assumed dead — it is not; it was measured alive on 2026-08-22 — but a third party holding the exchange, seeing which account is being connected, and being a single point of failure for every user is reason enough to replace it, and its liveness does not change that. Everything else still works, sitting on top of an unmaintained external module with an unpinnable version constraint. The journey is therefore: take ownership of that module first and alone, prove the pure parsing logic against real Graph JSON while an Azure registration is being stood up in parallel, then build in-add-on device-code authentication until a user can sign in from a sofa with a remote. Those two tracks converge at a Graph client that browses drives, at which point the self-hosted repository goes up immediately — its auto-update test has multi-hour latency and must overlap later work rather than block a release. Playback follows and delivers the core value: a file from OneDrive plays and keeps playing across a long pause and a seek. Then the deferrable cleanups — typed InfoTag setters, the modern settings schema, the deletion of the unauthenticated directory-listing server — and finally a release gate: one clean pass on real hardware with both account types, and a decision on where the embedded `client_id` will live long term.

The dominant risks here are silent, not hard. A discarded rotated refresh token works perfectly for 90 days and then kills every user at once. Vendoring while a sibling cloud-drive add-on is installed breaks only on clean installs. A stale repository index stops auto-updates for everyone except the maintainer. The success criteria below are written as mechanical checks — greps, log assertions, two-interpreter tests, a clean profile, a Business account, and a real Android device — because vigilance does not catch this class of failure and structure does.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Vendor Lift** - Take ownership of `script.module.clouddrive.common` v1.4.0, mechanically and alone (completed 2026-08-23)
- [ ] **Phase 2: Pure Core and CI Harness** - Extraction, paging and path logic proven against recorded Graph JSON, with CI enforcing the boundaries
- [ ] **Phase 3: Authentication** - Sign in from the couch: device code on the TV, entered on a phone
- [ ] **Phase 4: Browse** - Drives and folders navigate on a TV, and every failure says something useful
- [ ] **Phase 5: Distribution** - Updates arrive on the Android TV box by themselves after one URL entry
- [ ] **Phase 6: Play** - A file from OneDrive plays, and survives a long pause and a seek
- [ ] **Phase 7: Kodi Modernization** - Current Kodi APIs, the modern settings schema, and the deleted subsystems actually gone
- [ ] **Phase 8: Release Readiness** - One clean end-to-end pass on real hardware, and a `client_id` whose home will still exist next year

## Priority order (set 2026-08-23)

Phase numbers, phase goals and the requirement mapping are unchanged. What is recorded here is the order the phases are actually worked in, and why.

The goal is that this add-on runs on the owner's own **TCL Android TV 12**. The owner is the primary consumer; sharing it with anyone else is secondary. Anything that blocks that path is deferred to a later phase or milestone rather than solved in place.

**The path to the goal:** **Phase 3 (authentication) → Phase 2 (browse logic only) → Phase 4 (browse) → Phase 6 (play).**

Pulled forward out of Phase 5: **DIST-01 alone**, the build that produces an installable zip — and only at the point where the add-on first has to be installed on the TV. This is not distribution work and it is not a "public" concern: **installing an add-on on Android TV requires a zip to install from.** That is a constraint of the device, not a release decision. The rest of Phase 5 — the hosted repository, the unattended N to N+1 update — waits.

**Deferred:** Phase 7, Phase 8, and the CI harness (CI-01 to CI-05). Two items inside that deferred set are exceptions, because they hit the owner directly:

- **REL-01** — where the embedded `client_id` lives. The Microsoft 365 E5 Developer tenant renews on activity; if it lapses, the `client_id` dies for every installed copy at once, including the one on the owner's own television. That is an availability problem for the primary user, not a release formality.
- **Phase 7 criterion 4** — `SourceService`, its HTML index and the third-party error-reporting code removed from the tree, and nothing binding port 8586. That is security: an unauthenticated, enumerable index of the whole drive, reachable by any app on an Android box. It does not wait for a release that may never happen.

**Acceptance device, and what that does to the criteria below.** CI-06 was rewritten on the same date: the TCL Android TV 12 is the primary acceptance device, there is no standing obligation to pass on Windows or on a phone, and a stand-in at a comparable API level is acceptable only for OS-level questions — storage paths, file mode bits, `O_EXCL`, loopback binding — because those follow the API level rather than the form factor. Every phase's manual-acceptance criterion inherits that rewrite; where one below still reads "on Windows and on the Android phone", read the current CI-06 instead. This also resolves the four **CI-06 exception** notes in Phases 3, 4, 5 and 6, each of which existed because a phone could not answer a question about the television — D-pad and readability, listing timings on a low-end SoC, install-with-a-remote, hardware decode. Running those checks on the television answers them directly. Resolve each note when its phase is planned rather than deleting it here, so the reasoning stays attached to the criterion it belongs to.

## Parallel Tracks

The project config has `parallelization: true`, and two of these tracks are genuinely independent — Track V/P needs no token and no Azure registration, so it produces verifiable progress on day one instead of a week spent waiting on a portal.

```
  +- TRACK V/P - no auth required, start immediately -------------------+
  |  Phase 1  VENDOR LIFT      (mechanical, lands first and alone)      |
  |  Phase 2  PURE CORE + CI   (fixtures, greps, layering test)         |
  +--------------------------------+------------------------------------+
                                   |
  +- TRACK A - auth critical path -+------------------------------------+
  |  SETUP-01..04  Azure app registration (maintainer, not code)        |
  |  Phase 3  AUTHENTICATION   (store + O_EXCL lock -> device flow ->   |
  |           TokenProvider -> dialog -> account list)                  |
  +--------------------------------+------------------------------------+
                                   v
                            Phase 4  BROWSE   (tracks converge here)
                                   |
                    +--------------+--------------+
                    v                             v
            Phase 5  DISTRIBUTION         Phase 6  PLAY
            (N->N+1 wait runs long,               |
             overlapping 6 and 7)                 v
                    |                     Phase 7  KODI MODERNIZATION
                    +--------------+--------------+
                                   v
                     Phase 8  RELEASE READINESS
```

- **Phases 1-2 and Phase 3 run concurrently.** Phase 3's first three plans (token store and lock, device-code protocol, TokenProvider) need neither the vendored tree nor the Kodi runtime. Only the device-code dialog plan needs Phase 1 landed, because it reuses the vendored `pin-dialog.xml` skin.
- **Phase 5 and Phase 6 run concurrently.** Phase 5 exists early on purpose: Kodi's repository update check is periodic, so confirming an N to N+1 update arrives unaided has multi-hour latency. Starting that wait when browsing goes green lets it overlap Phases 6 and 7 instead of holding up a release.
- **Phase 1 never overlaps anything that rewrites code.** Interleaving the vendor commit with the rewrite destroys the ability to answer "did vendoring break this, or did my rewrite?".

## Phase Details

### Phase 1: Vendor Lift

**Goal**: The add-on carries its own complete, renamed copy of the common module, ships under its own identity, and depends on nothing outside `xbmc.python`, behaving exactly as it did before.
**Depends on**: Nothing (first phase; head of Track V/P, runs concurrently with Track A)
**Requirements**: VND-01, VND-02, VND-03, VND-04, VND-05, VND-06, VND-07, VND-08, VND-09, VND-10, VND-11, ID-01, ID-02, ID-03, ID-04, ID-05, KODI-01, KODI-02, SETUP-06, CI-06

The identity change (`plugin.onedrive` becomes `plugin.onedrive.kn`) belongs here because it touches the same files as the vendor lift and because it must land before anything writes to the new `addon_data` path. It also removes the need for any migration at all: a new id means a new profile, so the original add-on is never read from or written to.

**Prerequisites** (maintainer, not code — do these before the first file is copied):

  1. SETUP-06: provision a clean Kodi profile with `plugin.googledrive`, `plugin.dropbox` and `script.module.clouddrive.common` uninstalled, plus an Android phone running Kodi and reachable over `adb`. The TCL Android TV 12 box is the primary acceptance device — it is what this add-on is written for, and the emulator and phone stand in for it only where the question is an API-level one.
  2. Decide the vendored package name. Reversing it later means redoing every import. *(Decided: `resources/lib/vendor/clouddrive_common/`.)*

**Success Criteria** (what must be TRUE):

  1. A repo-wide grep returns zero hits for `script.module.clouddrive.common` and zero for `eval(`, and `addon.xml` declares no `<import>` other than `xbmc.python`.
  2. Kodi 19 mechanically refuses to install the add-on; Kodi 20, 21 and 22 install it and load both the plugin and service entry points. *(Not met, and not pursued: the multi-version matrix was dropped along with Windows. KODI-02 stays unchecked.)*
  3. On the clean profile from SETUP-06, with every sibling cloud-drive add-on and the external common module uninstalled, the add-on behaves as it did before the vendor commit and every dialog opens — including the one that writes `qr.png`, which is the one that lands on the sign-in screen. *(Corrected 2026-08-23: this line used to read "modulo the already-dead broker". The broker is not dead. Measured 2026-08-22 from the Android instrument, `drive-login.herokuapp.com` answered HTTP 200, issued a code, and the QR dialog rendered it with a 78-second expiry while the add-on polled `/pin/<code>` as designed. A fresh profile still shows an empty account list, but because nobody has signed in yet, not because the server is gone. The case for replacing the flow is unchanged and is not a liveness argument: a third party holds the OAuth exchange and sees which account is being connected. `VENDORED.md` and `README.md` were corrected on the same measurement.)*
  4. `VENDORED.md` records upstream URL, the `matrix` branch, version 1.4.0, the commit SHA, per-subtree licence and local modifications; both the GPL-3.0 and the Apache-2.0 licence files survive, and every outbound HTTP call in the vendored tree passes an explicit `timeout=`.
  5. Manual acceptance pass on Android over `adb`, on a clean profile — establishing the per-phase standard (CI-06) that every later phase inherits. The TCL Android TV 12 box is the primary acceptance device; it is exercised from Phase 3 onward, once the add-on does something a run on it would prove. *(Closed 2026-08-23: the Android acceptance pass ran on an Android 11 emulator. The Windows half was dropped — Windows is not a target for this add-on — which leaves criterion 2 unmet; see `01-07-SUMMARY.md`.)*

**Plans**: 7/7 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Environment and repository prerequisites: fork detach, clean profile, Android test phone, Kodi install matrix
- [x] 01-02-PLAN.md — The verification gate: pytest.ini and all 22 repository assertions, written before anything changes
- [x] 01-03-PLAN.md — Identity, Kodi gating, and the string-id namespace move into the 30000 block

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-04-PLAN.md — Vendor the module verbatim at a pinned commit, rename it, and merge its resources

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-05-PLAN.md — Resolve the eight hardcoded id lookups, vendor the QR encoder, and reduce the manifest to one import
- [x] 01-06-PLAN.md — Hardening: JSON serialization for both stores, explicit HTTP timeout

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-07-PLAN.md — Vendoring record, credits, dialog smoke action, install matrix and acceptance pass

### Phase 2: Pure Core and CI Harness

**Goal**: The extraction, paging and path logic is correct and proven against real Graph JSON, and CI enforces the boundaries that keep it that way.
**Depends on**: Phase 1 (the greps cannot go green until the vendor commit lands). Runs concurrently with Phase 3.
**Requirements**: BROWSE-02, BROWSE-03, BROWSE-04, BROWSE-07, BROWSE-16, CI-01, CI-02, CI-03, CI-04, CI-05, SETUP-05

**Prerequisites** (maintainer, not code):

  1. SETUP-05: one personal Microsoft account and one work/school account. *(Already satisfied — tokens were acquired live from both classes before Phase 1; see `.planning/research/SPIKE-DEVICE-CODE.md`.)* Fixtures must be recorded from both drive types — a suite green against one drive type proves nothing about the other, and reserved characters differ between them. **Narrowed 2026-08-23: OneDrive Business is the drive being used, so the Business fixture set is the immediate obligation and the Personal set is deferred, not deleted.** The requirement's own labelling rule is what makes that safe: an unlabelled fixture set silently starts reading as "both".

**Success Criteria** (what must be TRUE):

  1. CI fails the build on any occurrence of `client_secret`, `client_assertion`, `eval(`, or `script.module.clouddrive.common`, and on any `import xbmc*` outside `resources/lib/kodi/`.
  2. Fixture tests, recorded from a Business drive and labelled by source, cover item extraction, paging, per-segment path encoding (`Ryan's Files` to `Ryan's%20Files`, `Break#Out` to `Break%23Out`, `estimate%s.docx` to `estimate%25s.docx`) and OData literal quoting. *(The Personal fixture set is deferred, not dropped — the reserved-character sets differ between the two classes, so the Business set is not evidence about Personal and must not be relabelled as though it were.)*
  3. 1,500 fixture pages fed through the pager raise no `RecursionError`; cancelling mid-listing returns `[]` and never `None`; a search followed by a folder listing still returns folders; and a reshaped or truncated Graph response produces a handled error rather than a `KeyError`.
  4. CI runs pytest plus `kodi-addon-checker` against the nexus, omega and piers branches on every push, and is green.
  5. Manual acceptance per CI-06 — on the TCL Android TV 12, or on a named API-matched Android stand-in if the television cannot be driven: the add-on still installs and loads after the logic is extracted, with no user-visible change. Windows is not part of this pass.

**Plans**: TBD (4 expected)

### Phase 3: Authentication

**Goal**: A user signs in by reading a code off the TV and entering it on a phone, and stays signed in — with no server, no Azure setup, and no token copy-paste.
**Depends on**: The maintainer prerequisites below. Runs concurrently with Phases 1-2; only the device-code dialog needs Phase 1 landed, because it reuses the vendored `pin-dialog.xml` skin.
**Requirements**: SETUP-01, SETUP-02, SETUP-03, SETUP-04, AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, AUTH-08, AUTH-09, AUTH-10, AUTH-11, AUTH-12, AUTH-13, AUTH-14, AUTH-15, AUTH-16, AUTH-17, AUTH-18, AUTH-19, AUTH-20, AUTH-21, AUTH-22, AUTH-23

**Prerequisites** (maintainer, not code — the Azure registration blocks every live device-code test and must exist before the protocol work can be validated):

  1. SETUP-01: register the Azure application with `signInAudience: AzureADandPersonalMicrosoftAccount` and `requestedAccessTokenVersion: 2`, verified by reading the manifest back rather than trusting the portal UI. Once `signInAudience` is set to that value, the supported-accounts setting can no longer be changed in the UI — only through the manifest editor.
  2. SETUP-02: set `allowPublicClient: true`. This is the single most common device-code misconfiguration; left at its `false` default the token endpoint returns `AADSTS7000218` demanding `client_assertion` or `client_secret`, an error that actively misdirects toward embedding a secret.
  3. SETUP-03: no client secret and no certificate on the registration, and none anywhere in the repository — a secret in a GPL add-on is public by definition, and its presence turns the app confidential, which breaks device code outright.
  4. SETUP-04: write the registration runbook into the repo, including the `AADSTS7000218` symptom verbatim.
  5. SETUP-05 (already satisfied in Phase 2) supplies the personal and work/school accounts that AUTH-03 needs.

**Success Criteria** (what must be TRUE):

  1. On the TCL Android TV 12, sign-in completes end to end against the project's own registration with a **work/school (Business) account**, by reading a code off the screen and entering it on a phone, with no URL, username or password typed on the remote. A blocking or consent-requiring tenant produces a message naming the cause and pointing at the Expert-level custom `client_id` setting, and the exact `AADSTS` code it returns is recorded. **Narrowed 2026-08-23 to Business; the personal-account pass is deferred, not deleted** — the spike already acquired a token on a personal account, so what is deferred is the on-television pass, not the protocol question. **CI-06 exception resolved 2026-08-23:** the note existed because a phone cannot answer a television question — "read a code off the screen and enter it on a phone" is degenerate when the screen *is* the phone. Under the rewritten CI-06 the television is the acceptance device, so this criterion is checked directly on it and needs no proxy and no deferral to release.

  1a. **AUTH-18 is verifiable only in part, and must be recorded that way.** The E5 Developer tenant hosting this registration *permits* device code flow, so no blocking response can be produced from it on demand. Implement the error map defensively over the four known candidates — `AADSTS7000218` (public client flows still off), `AADSTS65001` (user or admin has not consented), `AADSTS50105`/`AADSTS53003` (Conditional Access blocking device code), `AADSTS7000014` (device_code rejected) — and mark AUTH-18 unverified against a genuinely blocking tenant rather than claiming it passes. Also make the terminal-error branch of `verify_device_code.py` persist the failing response to a file: it currently prints and discards, which is how an earlier observed failure was lost.

  2. The authorization request carries exactly `https://graph.microsoft.com/Files.Read offline_access openid profile`; a grep finds no `Files.Read.All`, no write scope, no `.default`, no `client_secret`, no `client_assertion`, and no reference to `sign-in-server` or any external broker anywhere in the tree. *(Qualified when planned, 2026-08-23: SETUP-04 requires the runbook to carry `AADSTS7000218` verbatim, and that error text names both forbidden parameters — so as written this criterion and SETUP-04 cannot both hold. Resolved the way the repository already resolves it: `docs/AZURE-REGISTRATION.md` joins `EXCLUDED_DOCS`, and pays for the exclusion with a positive assertion that reads it by name and requires the verbatim text. Same for the broker sweep and `README.md`/`VENDORED.md`, which are required to describe the old flow. The sweep's pattern is not softened anywhere.)*
  3. An automated test proves the persisted refresh token changed across two consecutive refreshes, and that a token response omitting `refresh_token` retains the previous one. A two-interpreter test shows the `O_EXCL` lock serialises refreshes and that a loser receiving `invalid_grant` re-reads the store and adopts the winner's token instead of signing the user out; no `threading.Lock` or `fcntl.lockf` appears in the auth package.
  4. The add-on root is the account list, with an "Add an account…" row and per-row re-authorise and remove. Labels come from Graph, Back or Esc during sign-in leaves no partially-created account, tokens and delta tokens and cache keys are isolated per account, and the background service never opens a sign-in dialog.
  5. Manual acceptance on Android TV: the code renders at the skin's largest font and is legible from a sofa, the expiry countdown ticks, "Get a new code" arrives focused on expiry, and any QR shown encodes only the server-supplied `verification_uri`. *(Restated when planned, 2026-08-23: "the largest font the skin offers" has no API behind it — Kodi resolves a `<font>` name against the active skin at render time and falls back silently when it cannot, logging nothing, which is how `pin-dialog.xml`'s `font12_title` has been rendering as `font13` since it was written. The mechanical half becomes: the `user_code` has a dedicated label control at a font of at least 60px in 1080i coordinates, named from Estuary's own `Font.xml`. The legibility half has no static check at all and is settled by a person reading the screen during the CI-06 pass, with the font actually in use recorded beside the verdict.)*
  6. **First run on the real target device.** The add-on is installed on the TCL television running Android TV 12, over network `adb`, and the same checklist the Android emulator ran in Phase 1 is repeated on it: both entry points load under the add-on's own id, the background service starts at login, all three dialogs open and render from the add-on's own skin directory, two openings of the QR dialog write two different image paths, and `grep -c Traceback` over the session log returns 0. This is the first time the add-on runs on the hardware it is written for — Phase 1's pass used an Android 11 emulator, one API level below it — so anything the emulator could not answer is answered here: real GPU rendering, D-pad focus order, readability from a sofa, performance on a low-end chip, and whether the television's own Android build restricts shell access to `Android/data`.

**Pulled forward into this phase** (each with the reason it could not wait):

  - **KODI-05 / KODI-06** — the versioned settings schema. AUTH-19's "Expert level" is declared by a `<level>` element that exists only in that schema, and `resources/settings.xml` still uses the format that predates it. Written against the current file, AUTH-19 is not implementable. The file is 28 lines and this phase edits it twice anyway.
  - **DIST-01 alone** — the installable zip. This phase's acceptance runs on the TCL, and installing on Android TV requires a zip. The priority order already sanctions pulling it forward "at the point where the add-on first has to be installed on the TV". Only the zip; the hosted repository and the unattended update stay in Phase 5.
  - **KODI-08** — third-party error reporting. Not a choice: AUTH-23 removes the accessor supplying the reporter's only URL, so the reporter either goes or is left with a broken reference.
  - **BROWSE-08, sign-in path only** — `get_account()` and `get_drives()`. Sign-in calls both, `GET /me` cannot answer under AUTH-04's locked scope set, and `/drives` is measured 403 on both account classes. The rest of the drive work stays in Phase 4.

**Plans**: 12/14 plans executed

Plans:

- [x] 03-01-PLAN.md — Tracer: device code requested, token merged, stored atomically and read back, with no Kodi in the path
- [x] 03-02-PLAN.md — The installable zip, built from the git index (DIST-01)
- [x] 03-03-PLAN.md — One gate harness, the auth gate file red by construction, and the registration runbook (SETUP-04)
- [x] 03-04-PLAN.md — The `O_EXCL` refresh lock, its two-signal stale breaker, and per-account isolation on disk
- [x] 03-05-PLAN.md — The AADSTS error map, and every string this phase will show
- [x] 03-06-PLAN.md — The sign-in dialog: a code control at a font that resolves, a countdown that does not steal focus, a second button
- [x] 03-07-PLAN.md — Refresh under the lock, the loser adopts the winner, and the startup threshold
- [x] 03-08-PLAN.md — Swap the broker for the device-code client: provider, account identity, and the two-clock sign-in loop
- [x] 03-09-PLAN.md — Account list with re-authorise, an explicit action mapping, and a log that carries no credentials
- [x] 03-10-PLAN.md — The background service's proactive refresh, which never prompts
- [x] 03-11-PLAN.md — The versioned settings schema, the Expert-level custom `client_id`, and the last broker rows
- [x] 03-12-PLAN.md — The disclaimer, the README and the modification record
- [ ] 03-13-PLAN.md — Live sign-in against the real registration, and the failure capture that no longer discards
- [ ] 03-14-PLAN.md — First run and acceptance on the TCL Android TV 12

**UI hint**: yes

### Phase 4: Browse

**Goal**: A signed-in user navigates their drives and folders on a TV at acceptable speed, and every failure state reads as an actionable sentence.
**Depends on**: Phase 2 and Phase 3 (the two tracks converge here)
**Requirements**: BROWSE-01, BROWSE-05, BROWSE-06, BROWSE-08, BROWSE-09, BROWSE-10, BROWSE-11, BROWSE-12, BROWSE-13, BROWSE-14, ERR-01, ERR-02, ERR-03

**Inherited constraint from Phase 3 (recorded 2026-08-23).** `AUTH-20` requires tokens, delta tokens and cache keys to be isolated per account. Phase 3 delivered the token half and could not deliver the cache half, because at that point no cache exists to isolate — the only `Cache` consumers belong to `SourceService`, which is global and is scheduled for deletion. **This phase builds the listing cache, so this phase owns that clause: key the cache by account from the first commit.** Retrofitting an account key onto a populated global cache means either a migration or a silent cross-account data leak, where one account's listings are served to another. Delta tokens carry the same rule and belong to the deferred `REST-04`.

**Success Criteria** (what must be TRUE):

  1. A user browses drives, folders and the pseudo-folders (Recent, Shared with me, Camera Roll) on a Business account, one page at a time without buffering the whole folder. A search containing a single quote succeeds, and names containing `#`, a space and a literal `%` resolve. **Narrowed 2026-08-23 to Business, the drive actually in use; the Personal pass is deferred, not deleted** — the reserved-character sets differ between the two classes, so a Business-only pass genuinely cannot find that class of bug and must not be written up as though it had.
  2. A request trace of an account load shows `/me/drive` and no bare `/drives` call; every outbound call carries a `timeout=`; a 429 is retried after exactly its `Retry-After`, slept via `Monitor.waitForAbort`; and a 401 retries exactly once. *(Corrected 2026-08-23: this line named `/me/drives`. Measured against live accounts, `/me/drives` returns 200 on business and **403 `accessDenied`** on personal, and `/drives` returns 403 on both; only `/me/drive` answers 200 for both classes. BROWSE-08 was corrected on that measurement and this line was missed. It also means the Business-first narrowing above costs no future work here — the endpoint in use already serves both account classes.)*
  3. Every `ListItem` is constructed with `offscreen=True`, items are added in chunks, thumbnails come from `$expand=thumbnails` at the smallest useful size, and a test asserts `endOfDirectory` is called exactly once per invocation including on the error path.
  4. No network, expired token, tenant-blocked, admin-consent-required and rate-limited each render as a distinct actionable sentence on screen, distinguishable from one another with no log, console or keyboard available to the user.
  5. Manual acceptance on the Android phone: a 500-item folder lists at an acceptable speed with the timings recorded, and quitting Kodi with that listing in flight shuts down cleanly. **CI-06 exception — resolve when planning this phase:** the clean-shutdown half transfers to the phone, the *timing* half does not. A phone is far faster than a 1–2 GB TV box, so a green timing here is not evidence about the target device. Either record the phone timing as a floor and re-check on the TV before release, or state the acceptable-speed threshold as a bound the phone must beat by a stated margin.

**Plans**: TBD (4 expected)
**UI hint**: yes

### Phase 5: Distribution

**Goal**: Updates arrive on the Android TV box by themselves, after the user enters one URL with a remote exactly once.
**Depends on**: Phase 4. Runs concurrently with Phase 6 — this phase is deliberately not last, because Kodi's repository update check is periodic and confirming an unaided N to N+1 update has multi-hour latency that must overlap Phases 6 and 7.
**Requirements**: DIST-01, DIST-02, DIST-03, DIST-04, DIST-05

**Note**: the builds published in this phase are maintainer test artifacts. The first release intended for existing v2.3.0 users is gated on Phase 8, because an existing user must not receive a build that cannot migrate their profile.

**Success Criteria** (what must be TRUE):

  1. A build produces `plugin.onedrive-<version>.zip` containing exactly one top-level `plugin.onedrive/` directory, and it installs from the Kodi file manager.
  2. The published repository is served over HTTPS, uses the `<dir>` schema with `<checksum verify="sha256">` and `<hashes>sha256</hashes>`, and contains no MD5 hash and no flat pre-Gotham layout.
  3. Installing the repository on the Android TV box takes exactly one URL entry with the remote and no further manual steps. **CI-06 exception — resolve when planning this phase:** the phone cannot make this claim. "One URL entry with the remote" is a remote-interaction assertion, and it is the whole point of the self-hosted repository, so it cannot be quietly dropped either. It either moves to release under CI-07 or becomes a use-and-report observation on the box.
  4. A throwaway N to N+1 pair published to that repository is confirmed to arrive on the box without anyone pressing "Check for updates" — verified by waiting out Kodi's periodic check, not by force-refreshing, since a maintainer who always force-refreshes is structurally unable to reproduce the failure users see.
  5. Every published version number is plain, with no pre-release suffix, because Kodi's Debian-style comparison sorts `3.0.0-beta` below `3.0.0`.

**Plans**: TBD (3 expected)

### Phase 6: Play

**Goal**: The core value — video, audio and images from OneDrive play on the TV and survive a long pause and a seek.
**Depends on**: Phase 4. Runs concurrently with Phase 5.
**Requirements**: PLAY-01, PLAY-02, PLAY-03, PLAY-04, PLAY-05, PLAY-06, PLAY-07, PLAY-08, PLAY-09

**Success Criteria** (what must be TRUE):

  1. Video, audio and image files play from a Business drive on the Android device. **Narrowed 2026-08-23 to Business; the Personal pass is deferred, not deleted.** **CI-06 exception — resolve when planning this phase:** the phone carries the substance here — container and codec handling, demuxer selection and `Range` behaviour are Kodi's Android build, not the form factor — but hardware decode capability differs between a phone SoC and a low-end TV box, so a green playback result on the phone is not evidence the box decodes the same file. Record the phone result at this gate and re-check codec coverage on the box before release.
  2. Kodi is never handed a Graph URL: the URL passed to `setResolvedUrl` is `http://127.0.0.1:<dynamically allocated port>/<per-session random token>/…`, `setResolvedUrl` is called exactly once per playback invocation, and a grep of directory item URLs and of any exported `.strm` finds no `@microsoft.graph.downloadUrl`. A guessed item id alone is not sufficient to reach the redirector.
  3. The real download-URL lifetime is measured at T+1, +5, +15, +30 and +60 minutes on a Business drive, and the numbers are recorded in the repo. **Narrowed 2026-08-23**: the Business measurement is the one that gates this phase; the Personal measurement is deferred. Keep the two recorded separately rather than generalising one number to both — the two drive classes are served by different back ends, and Business drives serve from SharePoint.
  4. Same-name subtitles are discovered across Kodi's full extension set including language suffixes and VOBsub `.idx`/`.sub` pairs, are served through the same redirector as media, and failure is silent.
  5. Manual acceptance on the Android phone: a file over two hours plays, is paused 20-30 minutes past the measured URL lifetime, resumes, and then seeks forward without error. This one transfers cleanly — what it exercises is Kodi's URL latch and Microsoft's URL lifetime, both platform-independent, and the deciding observation (does a seek produce a second request at the redirector?) is reproducible on Windows. Run PLAY-07 first: it decides whether this criterion is achievable with a redirector alone.

**Plans**: TBD (4 expected)

### Phase 7: Kodi Modernization

**Goal**: The add-on speaks current Kodi APIs, its settings screen uses the modern schema, and the deleted subsystems are actually gone from the tree.
**Depends on**: Phase 6 (deferred behind auth and playback on purpose — `setInfo` still works in Kodi 22 and only log-warns, and the calls being migrated live inside the vendored module)
**Requirements**: KODI-03, KODI-04, KODI-05, KODI-06, KODI-07, KODI-08, PLAY-10

**Success Criteria** (what must be TRUE):

  1. A full browse-and-play `kodi.log` contains zero `is deprecated` lines originating from this add-on.
  2. The typed InfoTag setters and the `int(ms // 1000)` duration fix land in the same commit — `git show` on that one commit contains both — and every video item lists without `TypeError`. Split across two commits, the setter commit crashes on every video item, because the typed setters are SWIG-bound to a real C++ `int` where `setInfo` silently truncated a float.
  3. `resources/settings.xml` is `<settings version="1">` with section, category and group structure, contains no `window(home).property(iskrypton)` condition, and no longer defines `allow_directory_listing`, `port_directory_listing` or `report_error`.
  4. `SourceService`, its HTML index and the third-party error-reporting code are gone from the tree; nothing binds port 8586, confirmed with `netstat`/`ss` on the Android box. **Pulled out of the Phase 7 deferral (2026-08-23)**: this one is security, not modernization — an unauthenticated, enumerable index of the whole drive that any app on the box can reach — so it is done when the code is deleted, not when Phase 7 is reached.
  5. Manual acceptance per CI-06, on the TCL Android TV 12: the restructured settings screen renders and navigates with a remote, and a full browse-and-play pass shows no regression. Windows is not part of this pass.

**Plans**: TBD (3 expected)
**UI hint**: yes

### Phase 8: Release Readiness

**Goal**: The add-on is fit to hand to someone else — one clean end-to-end pass on real hardware, and a `client_id` whose home will still exist next year.
**Depends on**: Phase 5 (a published repository to install from) and Phase 7.
**Requirements**: CI-07, REL-01

There is no migration phase. Under a new add-on id there is no prior profile to read, and even with the old id migration could carry almost nothing: refresh tokens are bound to a `client_id`, so they must be discarded, and the only remaining state — account display name and drive selection — is regenerated by signing in. The add-on installs alongside the original without touching it.

**Success Criteria** (what must be TRUE):

  1. One full acceptance pass on a clean Kodi profile on real Android TV hardware with a remote: install from the published repository, sign in, browse, and play — performed once with a Business account and once with a personal account, because the reserved-character and consent behaviours differ between them.
  2. Installing this add-on on a box that already has the original `plugin.onedrive` changes nothing about the original: separate `addon_data`, separate settings, both still work.
  3. A decision is recorded on where the embedded `client_id` lives. The Microsoft 365 E5 Developer tenant renews on activity; if it lapses, the `client_id` dies for every installed copy simultaneously. Either the tenant is confirmed durable, or the registration moves to one that does not expire.
  4. `CREDITS.md` and `LICENSE.txt` are present and accurate, and `addon.xml` names the current maintainer.

**Plans**: TBD (2 expected)

## Deferred to v2

Not in this roadmap, tracked in REQUIREMENTS.md: the restored services in dependency order — resume and watched-state sync (downstream of export), STRM library export (video only), slideshow, and opt-in delta change sync with its HTTP 410 `resyncChangesApplyDifferences` handling. Plus server-side `$orderby` and SharePoint document libraries as a supported target. `SourceService` is never restored; it is deleted in Phase 7.

## Progress

**Execution Order:**
Phases execute in numeric order, with two concurrent pairs: {1, 2} runs alongside 3, and 5 runs alongside 6.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Vendor Lift | 7/7 | Complete    | 2026-08-23 |
| 2. Pure Core and CI Harness | 0/4 | Not started | - |
| 3. Authentication | 12/14 | In Progress|  |
| 4. Browse | 0/4 | Not started | - |
| 5. Distribution | 0/3 | Not started | - |
| 6. Play | 0/4 | Not started | - |
| 7. Kodi Modernization | 0/3 | Not started | - |
| 8. Release Readiness | 0/2 | Not started | - |

---
*Roadmap created: 2026-08-22*
