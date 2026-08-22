# Roadmap: OneDrive Kodi Add-on — Refactor

## Overview

The add-on is dead in one specific place: sign-in went with a Heroku free dyno in November 2022. Everything else still works, sitting on top of an unmaintained external module with an unpinnable version constraint. The journey is therefore: take ownership of that module first and alone, prove the pure parsing logic against real Graph JSON while an Azure registration is being stood up in parallel, then build in-add-on device-code authentication until a user can sign in from a sofa with a remote. Those two tracks converge at a Graph client that browses drives, at which point the self-hosted repository goes up immediately — its auto-update test has multi-hour latency and must overlap later work rather than block a release. Playback follows and delivers the core value: a file from OneDrive plays and keeps playing across a long pause and a seek. Then the deferrable cleanups — typed InfoTag setters, the modern settings schema, the deletion of the unauthenticated directory-listing server — and finally a release gate: one clean pass on real hardware with both account types, and a decision on where the embedded `client_id` will live long term.

The dominant risks here are silent, not hard. A discarded rotated refresh token works perfectly for 90 days and then kills every user at once. Vendoring while a sibling cloud-drive add-on is installed breaks only on clean installs. A stale repository index stops auto-updates for everyone except the maintainer. The success criteria below are written as mechanical checks — greps, log assertions, two-interpreter tests, a clean profile, a Business account, and a real Android device — because vigilance does not catch this class of failure and structure does.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Vendor Lift** - Take ownership of `script.module.clouddrive.common` v1.4.0, mechanically and alone
- [ ] **Phase 2: Pure Core and CI Harness** - Extraction, paging and path logic proven against recorded Graph JSON, with CI enforcing the boundaries
- [ ] **Phase 3: Authentication** - Sign in from the couch: device code on the TV, entered on a phone
- [ ] **Phase 4: Browse** - Drives and folders navigate on a TV, and every failure says something useful
- [ ] **Phase 5: Distribution** - Updates arrive on the Android TV box by themselves after one URL entry
- [ ] **Phase 6: Play** - A file from OneDrive plays, and survives a long pause and a seek
- [ ] **Phase 7: Kodi Modernization** - Current Kodi APIs, the modern settings schema, and the deleted subsystems actually gone
- [ ] **Phase 8: Release Readiness** - One clean end-to-end pass on real hardware, and a `client_id` whose home will still exist next year

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

  1. SETUP-06: provision a clean Kodi profile with `plugin.googledrive`, `plugin.dropbox` and `script.module.clouddrive.common` uninstalled, plus an Android phone running Kodi and reachable over `adb`. The Android TV box is the deployment target, not a test device — see CI-06.
  2. Decide the vendored package name. Reversing it later means redoing every import. *(Decided: `resources/lib/vendor/clouddrive_common/`.)*

**Success Criteria** (what must be TRUE):

  1. A repo-wide grep returns zero hits for `script.module.clouddrive.common` and zero for `eval(`, and `addon.xml` declares no `<import>` other than `xbmc.python`.
  2. Kodi 19 mechanically refuses to install the add-on; Kodi 20, 21 and 22 install it and load both the plugin and service entry points.
  3. On the clean profile from SETUP-06, with every sibling cloud-drive add-on and the external common module uninstalled, the add-on behaves as it did before the vendor commit (modulo the already-dead broker) and every dialog opens — including the one that writes `qr.png`, which is the one that lands on the sign-in screen.
  4. `VENDORED.md` records upstream URL, the `matrix` branch, version 1.4.0, the commit SHA, per-subtree licence and local modifications; both the GPL-3.0 and the Apache-2.0 licence files survive, and every outbound HTTP call in the vendored tree passes an explicit `timeout=`.
  5. Manual acceptance pass on Windows and on the Android phone over `adb`, on a clean profile — establishing the per-phase standard (CI-06) that every later phase inherits. The Android TV box is the deployment target, not a test device; it is checked before release.

**Plans**: 2/7 plans executed

Plans:
**Wave 1**

- [ ] 01-01-PLAN.md — Environment and repository prerequisites: fork detach, clean profile, Android test phone, Kodi install matrix
- [x] 01-02-PLAN.md — The verification gate: pytest.ini and all 22 repository assertions, written before anything changes
- [x] 01-03-PLAN.md — Identity, Kodi gating, and the string-id namespace move into the 30000 block

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-04-PLAN.md — Vendor the module verbatim at a pinned commit, rename it, and merge its resources

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 01-05-PLAN.md — Resolve the eight hardcoded id lookups, vendor the QR encoder, and reduce the manifest to one import
- [ ] 01-06-PLAN.md — Hardening: JSON serialization for both stores, explicit HTTP timeout

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 01-07-PLAN.md — Vendoring record, credits, dialog smoke action, install matrix and acceptance pass

### Phase 2: Pure Core and CI Harness

**Goal**: The extraction, paging and path logic is correct and proven against real Graph JSON, and CI enforces the boundaries that keep it that way.
**Depends on**: Phase 1 (the greps cannot go green until the vendor commit lands). Runs concurrently with Phase 3.
**Requirements**: BROWSE-02, BROWSE-03, BROWSE-04, BROWSE-07, BROWSE-16, CI-01, CI-02, CI-03, CI-04, CI-05, SETUP-05

**Prerequisites** (maintainer, not code):

  1. SETUP-05: one personal Microsoft account and one work/school account. Fixtures must be recorded from both drive types — a suite green against one drive type proves nothing about the other, and reserved characters differ between them.

**Success Criteria** (what must be TRUE):

  1. CI fails the build on any occurrence of `client_secret`, `client_assertion`, `eval(`, or `script.module.clouddrive.common`, and on any `import xbmc*` outside `resources/lib/kodi/`.
  2. Fixture tests, recorded from both a Personal and a Business drive and labelled by source, cover item extraction, paging, per-segment path encoding (`Ryan's Files` to `Ryan's%20Files`, `Break#Out` to `Break%23Out`, `estimate%s.docx` to `estimate%25s.docx`) and OData literal quoting.
  3. 1,500 fixture pages fed through the pager raise no `RecursionError`; cancelling mid-listing returns `[]` and never `None`; a search followed by a folder listing still returns folders; and a reshaped or truncated Graph response produces a handled error rather than a `KeyError`.
  4. CI runs pytest plus `kodi-addon-checker` against the nexus, omega and piers branches on every push, and is green.
  5. Manual acceptance on Windows and on the Android phone: the add-on still installs and loads after the logic is extracted, with no user-visible change.

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

  1. On real Android TV hardware, sign-in completes end to end against the project's own registration — once with a personal Microsoft account and once with a work/school account — by reading a code off the screen and entering it on a phone, with no URL, username or password typed on the remote. A blocking or consent-requiring tenant produces a message naming the cause and pointing at the Expert-level custom `client_id` setting, and the exact `AADSTS` code it returns is recorded. **CI-06 exception — resolve when planning this phase:** the phone cannot proxy this one. "Read a code off the screen and enter it on a phone" is degenerate when the screen *is* the phone, and "no URL or password typed on the remote" is a remote-interaction claim. The token exchange and the `AADSTS` mapping are verifiable on the phone; the 10-foot flow itself is a TV check, so it either moves to release or becomes a use-and-report observation.
  2. The authorization request carries exactly `https://graph.microsoft.com/Files.Read offline_access openid profile`; a grep finds no `Files.Read.All`, no write scope, no `.default`, no `client_secret`, no `client_assertion`, and no reference to `sign-in-server` or any external broker anywhere in the tree.
  3. An automated test proves the persisted refresh token changed across two consecutive refreshes, and that a token response omitting `refresh_token` retains the previous one. A two-interpreter test shows the `O_EXCL` lock serialises refreshes and that a loser receiving `invalid_grant` re-reads the store and adopts the winner's token instead of signing the user out; no `threading.Lock` or `fcntl.lockf` appears in the auth package.
  4. The add-on root is the account list, with an "Add an account…" row and per-row re-authorise and remove. Labels come from Graph, Back or Esc during sign-in leaves no partially-created account, tokens and delta tokens and cache keys are isolated per account, and the background service never opens a sign-in dialog.
  5. Manual acceptance on Windows and Android TV: the code renders at the skin's largest font and is legible from a sofa, the expiry countdown ticks, "Get a new code" arrives focused on expiry, and any QR shown encodes only the server-supplied `verification_uri`.

**Plans**: TBD (5 expected)
**UI hint**: yes

### Phase 4: Browse

**Goal**: A signed-in user navigates their drives and folders on a TV at acceptable speed, and every failure state reads as an actionable sentence.
**Depends on**: Phase 2 and Phase 3 (the two tracks converge here)
**Requirements**: BROWSE-01, BROWSE-05, BROWSE-06, BROWSE-08, BROWSE-09, BROWSE-10, BROWSE-11, BROWSE-12, BROWSE-13, BROWSE-14, ERR-01, ERR-02, ERR-03

**Success Criteria** (what must be TRUE):

  1. A user browses drives, folders and the pseudo-folders (Recent, Shared with me, Camera Roll) on both a Personal and a Business account, one page at a time without buffering the whole folder. A search containing a single quote succeeds, and names containing `#`, a space and a literal `%` resolve on both drive types — both must be exercised, because their reserved-character sets differ and a single-account-type pass cannot find this class of bug.
  2. A request trace of an account load shows `/me/drives` and no bare `/drives` call; every outbound call carries a `timeout=`; a 429 is retried after exactly its `Retry-After`, slept via `Monitor.waitForAbort`; and a 401 retries exactly once.
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

  1. Video, audio and image files play from both a Personal and a Business drive on the Android device. **CI-06 exception — resolve when planning this phase:** the phone carries the substance here — container and codec handling, demuxer selection and `Range` behaviour are Kodi's Android build, not the form factor — but hardware decode capability differs between a phone SoC and a low-end TV box, so a green playback result on the phone is not evidence the box decodes the same file. Record the phone result at this gate and re-check codec coverage on the box before release.
  2. Kodi is never handed a Graph URL: the URL passed to `setResolvedUrl` is `http://127.0.0.1:<dynamically allocated port>/<per-session random token>/…`, `setResolvedUrl` is called exactly once per playback invocation, and a grep of directory item URLs and of any exported `.strm` finds no `@microsoft.graph.downloadUrl`. A guessed item id alone is not sufficient to reach the redirector.
  3. The real download-URL lifetime is measured at T+1, +5, +15, +30 and +60 minutes separately on a Personal and a Business drive, and the numbers are recorded in the repo.
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
  4. `SourceService`, its HTML index and the third-party error-reporting code are gone from the tree; nothing binds port 8586, confirmed with `netstat`/`ss` on Windows and on the Android box.
  5. Manual acceptance on Windows and Android TV: the restructured settings screen renders and navigates with a remote, and a full browse-and-play pass shows no regression.

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
| 1. Vendor Lift | 2/7 | In Progress|  |
| 2. Pure Core and CI Harness | 0/4 | Not started | - |
| 3. Authentication | 0/5 | Not started | - |
| 4. Browse | 0/4 | Not started | - |
| 5. Distribution | 0/3 | Not started | - |
| 6. Play | 0/4 | Not started | - |
| 7. Kodi Modernization | 0/3 | Not started | - |
| 8. Release Readiness | 0/2 | Not started | - |

---
*Roadmap created: 2026-08-22*
