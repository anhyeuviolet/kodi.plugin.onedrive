# Project Research Summary

**Project:** OneDrive Kodi Add-on — Refactor (`plugin.onedrive`)
**Domain:** Kodi 20/21/22 cloud-storage media add-on, Microsoft Graph backend, in-add-on OAuth 2.0 device authorization grant, Android-TV-first
**Researched:** 2026-08-22
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is a rescue-and-rewrite of an abandoned Kodi cloud-drive add-on whose only real defect from the user's point of view is that sign-in is dead: the upstream OAuth broker was a Heroku free dyno that stopped existing in November 2022, and the family of add-ons it belonged to has not been touched since 2023-01-21. Experts build this class of add-on the same way rclone and every TV-class OAuth client does — an embedded **public** `client_id` with no secret, RFC 8628 device code against `login.microsoftonline.com/common`, refresh tokens persisted on-device in the add-on profile directory, and a thin plugin that hands Kodi a URL rather than proxying bytes. Every piece of that is achievable with the CPython 3.11 stdlib Kodi already ships; MSAL Python is not viable here (absent from every Kodi repo, drags in compiled `cryptography`), and neither is `oauthlib` (no device-grant client).

The recommended approach is therefore: **hand-roll ~120 lines of device-code protocol on `urllib.request`, vendor-and-replace `script.module.clouddrive.common` rather than vendor-and-patch it, and enforce a hard architectural rule that no module below a named `kodi/` boundary may `import xbmc*`.** That single rule converts every bug listed under "Core path correctness" in PROJECT.md — `_extra_parameters` leakage, `items.extend(None)`, path encoding, OData quoting, float durations, recursive pagination — from manual-acceptance-only into CI-catchable pure-function tests. Structurally the add-on becomes `kodi/` (boundary) → `provider/` → `graph/` → `auth/`, with a quarantined `vendor/` tree holding the deferred subsystems (export, slideshow, player, download) that get deleted file-by-file as each is restored or dropped.

The dominant risks are not technical difficulty; they are **invisible-until-late** failures. Discarding the rotated refresh token works perfectly in development and kills every user simultaneously ~90 days after sign-in. Vendoring while a sibling cloud-drive add-on is installed keeps the hardcoded `script.module.clouddrive.common` lookups working on the maintainer's machine and breaks only on clean installs. An Azure registration missing `allowPublicClient: true` returns `AADSTS7000218` telling you to add a client secret — the exact thing the design forbids. A stale repository index means auto-updates silently stop for everyone except the maintainer, who always force-refreshes. Mitigation is structural: CI greps (`client_secret`, `eval(`, `script.module.clouddrive.common`, `import xbmc` below the boundary), a fixture test asserting the persisted refresh token *changes* across two refreshes, and an acceptance matrix that mandates a clean profile, a Business account, and a real Android TV box on Wi-Fi.

## Key Findings

### Recommended Stack

Zero runtime dependencies beyond `xbmc.python`. Everything the add-on needs — HTTP, JSON, ISO-8601 parsing, atomic file replacement — is in the CPython 3.11 stdlib Kodi 20 bundles, and `kodi-addon-checker`'s "unused `script.module` dependency" rule actively punishes declaring anything you do not import. Target Python **3.11** (Kodi 20 Nexus is the floor at CPython 3.11.0); 3.12+ syntax is out.

**Core technologies:**
- **`<import addon="xbmc.python" version="3.0.1"/>`** — the entire ABI answer in one line. Installs on Kodi 20/21/22, mechanically rejected by Kodi 19, and matches the linter's `advised` value on `nexus`, `omega` and `piers`.
- **Python stdlib `urllib.request` + `json`** — all Graph and OAuth HTTP. Zero install-time dependency resolution on Android TV, no stale `certifi` 2023 CA bundle, trivially fakeable in tests. Critical: OAuth pending polls arrive as **HTTP 400** with a JSON body, so `HTTPError` must be caught and `e.read()` parsed.
- **Microsoft identity platform v2.0, `/common` authority, device authorization grant** — the only authority admitting both personal and work/school accounts. Verified live 2026-08-22: `expires_in=900`, `interval=5`, `verification_uri_complete` is **not** returned, and `verification_uri` differs per authority so it must never be hardcoded.
- **Microsoft Graph `v1.0`** (never `beta`) — drives, children, search, delta, `@microsoft.graph.downloadUrl`.
- **`<settings version="1">`** schema (`section/category/group/setting`); custom `client_id` at `<level>3</level>` (Expert) so it is reachable but invisible to normal users.
- **Profile-directory JSON token store** — `xbmcvfs.translatePath('special://profile/addon_data/plugin.onedrive/')`, atomic `os.replace()`, `chmod 0600` best-effort. Never Kodi settings: those render in the UI and are swept into every forum log upload.
- **Dev/CI only:** `Kodistubs` 21.0.0, `kodi-addon-checker` 0.0.36, `pytest`, `unittest.mock`.

**Explicitly rejected:** MSAL Python, `cryptography`, `PyJWT`, `oauthlib`/`requests_oauthlib`, `six`, `dateutil`, `inputstreamhelper`, the `.default` scope, any client secret, MD5 repo hashes, the flat pre-`<dir>` repository schema.

### Expected Features

**Must have (table stakes — v1):**
- Device-code sign-in dialog: code at the largest font the skin offers, QR as a secondary URL shortcut (it can only carry `verification_uri`, never the code), live expiry countdown, Back/Esc cancel leaving no partial account, focused "Get a new code" on expiry.
- Embedded public `client_id` + `offline_access` — without `offline_access` there is no refresh token and the add-on re-prompts hourly, which on a TV reads as total failure.
- Secure token storage + single-flight silent refresh with rotation write-back.
- Multiple accounts **with per-account isolation from day one** (tokens, delta tokens, cache keys). Retrofitting isolation later is a rewrite. Labels come from Graph, never typed on a remote.
- Account/drive root listing as the switcher — the add-on root *is* the account list, with a trailing "Add an account…" row and a per-row context menu (re-authorise / remove).
- Folder browsing, page-at-a-time, chunked `addDirectoryItems`, `offscreen=True` on every `ListItem`.
- **Loopback 302 redirector** — required by playback, ~80 lines, not deferrable (Reconciled Conflicts #4).
- Video/audio/image playback with seek; same-name subtitle auto-discovery (full Kodi extension set, language suffixes, VOBsub `.idx`+`.sub` pairs, fail-silent).
- Thumbnails for image and video listings via `$expand=thumbnails` at the smallest useful size.
- The full 15-state error/empty-state set — on a TV there is no log, no console, no keyboard, so every failure must be a distinct actionable sentence.
- Custom `client_id` advanced setting.
- **Deletion** of `SourceService` / `allow_directory_listing` / `port_directory_listing`.

**Should have (competitive, v1.x):**
- Search across a drive (Graph `search(q=…)` with `''`-escaped literals).
- Server-side `$orderby` — genuinely better than incumbents, because `xbmcplugin.addSortMethod` only sorts the page you loaded.
- Pseudo-folders (Recent, Shared with me, Camera Roll) — near-free, already implemented.
- **STRM library export (video only)** — the category's biggest differentiator; it promotes a cloud folder into the Kodi library with scraped art, watched flags and resume. Music `.strm` does not work in Kodi and must never ship.
- Resume / watched-state sync — **downstream of export**, not a peer; `dbid`/`dbtype` recovery keys off the exported `.strm`.
- Delta change sync — pulled in by export, opt-in, default off.

**Defer / never:**
- Slideshow auto-refresh (needs continuous delta polling — the documented source of the category's CPU/RAM complaints).
- SharePoint as a first-class target; additional localisations.
- **Never:** music STRM export, byte-proxy playback, the unauthenticated directory-listing server, a bundled subtitle-search service, a second (browser-redirect) auth flow, third-party error reporting.

### Architecture Approach

A four-layer package with one hard rule: **`resources/lib/kodi/` is the only package allowed to `import xbmc*`**, enforced by a five-line CI layering test. Everything below it — `auth/`, `graph/`, `provider/` — is plain Python, testable against recorded Graph JSON with no Kodi stubs. Above it, `entrypoint.py` and `service.py` are ~10–20 lines each. Vendored upstream code lives quarantined at `resources/lib/vendor/`, reached only through thin adapters, and shrinks to nothing as subsystems are restored or dropped.

**Major components:**
1. **`kodi/`** — `routes.py` (dispatch table with an explicit one-terminator-per-invocation contract), `listing.py` (`Item` → `ListItem` via typed InfoTags, chunked adds), `play.py` (resolve → `setResolvedUrl`), `dialogs.py`, `shared.py` (`Window(10000)` cache + the `O_EXCL` cross-interpreter mutex), `settings.py`.
2. **`provider/onedrive.py`** — OneDrive semantics: drives, folders, search, subtitles, pseudo-folders, and the pure `extract_item()` that fixture tests target.
3. **`graph/`** — `client.py` (one authenticated request, 401→refresh-once, 429/`Retry-After`, absolute-URL passthrough, **no mutable per-request state on `self`**), `paging.py` (generator over `@odata.nextLink`), `paths.py` (per-segment percent-encoding, OData literal quoting), `errors.py`.
4. **`auth/`** — split four ways because they change for different reasons: `device_flow.py` (protocol only), `store.py` (atomic JSON + `refresh_lock`), `tokens.py` (value object + expiry math), `session.py` (`TokenProvider`, the **only** place a refresh ever happens; `InteractiveTokenProvider` for the plugin, `SilentTokenProvider` for the service, which may never open a dialog).
5. **`vendor/`** — quarantine for export, download, player, source services. Deleted file-by-file.

Playback data flow: directory URLs carry `driveid` + `item_id` only; the preauth `1drv.com` URL is minted **at play time, every time**, never cached, never embedded in a `.strm`.

### Critical Pitfalls

1. **Discarding the rotated refresh token.** Entra returns a *new* `refresh_token` on every refresh and does not revoke the old one — so naive code appears to work until the original hits its 90-day lifetime and every user dies at once. Always write back the full token response; if the response omits `refresh_token`, keep the previous one, never the reverse. Unit-test that the persisted token *changed* across two refreshes. Add a ~60-day proactive keepalive on Kodi startup.
2. **Vendoring while a sibling add-on is installed.** Six hardcoded `script.module.clouddrive.common` lookups (including `ui/dialog.py:126`, which writes `qr.png` into the *common module's* profile — the bug lands exactly on the sign-in screen) keep resolving if `plugin.googledrive` or `plugin.dropbox` is present. Worst possible failure distribution. CI grep to zero hits + a clean-profile acceptance test.
3. **`allowPublicClient` left at its `false` default.** `AADSTS7000218` demands `client_assertion` or `client_secret`, actively misdirecting toward embedding a secret. Fix in the Azure portal, and enforce with a CI grep forbidding `client_secret`/`client_assertion` anywhere in the repo, forever.
4. **`@microsoft.graph.downloadUrl` expiring mid-playback.** Microsoft documents "might expire within minutes" and publishes no duration. Resolve at play time only; `Range` must target the download URL host, not `/content`; never cache the resolved URL. Acceptance test: 2h+ file, pause 30 min, resume, seek.
5. **Concurrency on the token store, solved with the wrong primitive.** `fcntl.lockf` record locks are per-process and will not exclude two CPython sub-interpreters of the same Kodi process — it passes a naive two-terminal test and protects nothing in production. Use `os.open(path, O_CREAT|O_EXCL)` with a stale-lock breaker, double-check inside the lock, persist before use, and treat a first `invalid_grant` as a possible lost race (re-read the store; if the persisted refresh token differs, adopt the winner).
6. **Ignoring `Retry-After` on 429.** Microsoft is blunt: throttled requests still accrue against your limits. One central HTTP layer, sleep exactly `Retry-After` via `Monitor.waitForAbort`, exponential backoff only when the header is absent. Also: `urlopen` currently has **no `timeout=`**, which on marginal Android TV Wi-Fi hangs the add-on forever — one keyword argument.

## Reconciled Conflicts

The four researchers disagreed on six points. Resolved positions follow; the roadmapper should treat these as decided.

### 1. Process model — ARCHITECTURE.md wins, and the question is non-blocking anyway

**Correct:** `entrypoint.py` and `service.py` are **CPython sub-interpreters on separate threads inside the single Kodi OS process** (`CPythonInvoker`), not separate OS processes. STACK.md's "separate processes" phrasing is wrong. ARCHITECTURE.md read the invoker semantics directly; STACK.md asserted the process model in passing while making a different (and correct) point about single-writer discipline.

**Consequences:** module globals, singletons and `threading.Lock` are **not** shared; `Window(10000)` properties **are** (C++-backed); `fcntl.lockf` POSIX record locks are per-process and therefore **silently fail to exclude the two interpreters** on Linux and Android.

**Do this:** use `os.open(path, O_CREAT|O_EXCL|O_WRONLY)` with a 60-second stale-lock breaker and a `Monitor.waitForAbort`-based retry sleep. This is correct under *both* process models — atomic across OS processes and across sub-interpreters, and it works on Windows where `flock(2)` does not exist. **Because the safe design is correct either way, the process-model question does not block any phase.** It is worth one cheap two-interpreter confirmation test on Android (see Empirical Unknowns), but no decision waits on it. What *is* load-bearing regardless: never use `threading.Lock` or a module-global singleton for cross-entry-point state, and never use `fcntl.lockf`.

### 2. InfoTag migration — PITFALLS.md wins: it is a deferrable cleanup, not a blocker

**Correct:** `ListItem.setInfo` is still present and functional in `xbmc/xbmc` **master** (Kodi 22 Piers), `xbmc/interfaces/legacy/ListItem.cpp:375`, emitting only `LOGWARNING "…is deprecated and might be removed in future Kodi versions."` PITFALLS.md read the source at master; STACK.md and ARCHITECTURE.md correctly describe typed setters as the Kodi 20+ *API direction* but overstate the urgency as a hard requirement. PROJECT.md inherits the overstatement ("Kodi 20+ requirement").

**Do this:** schedule the InfoTag migration as its own **Kodi-modernization phase after vendoring**, not as a blocker in front of auth or browse. It cannot precede vendoring because the `setInfo` calls live in `clouddrive/common/ui/addon.py` lines 424, 439 and 583 — i.e. inside the module you are vendoring, not in `resources/lib/provider/onedrive.py`. Any other ordering produces rework.

**The float-duration interaction is why this is not free.** `setInfo` parses via `strtol` on a string, so `duration = ms / 1000` (true division → float) was *silently truncated*. The typed setters are SWIG-bound to real C++ `int`, so the same value raises **`TypeError` on every video item**. Therefore **`int(ms // 1000)` and the setter migration must land in the same commit** — fixing the float earlier is harmless, fixing it later means the migration commit is a crash. Acceptance criterion is cheap and objective: grep a full browse+play `kodi.log` for `is deprecated` and require zero hits.

Related, resolved the same way: STACK.md wants `<import addon="xbmc.python" version="3.0.1"/>`; PITFALLS.md notes `3.0.0` would also install everywhere. Both are right about the mechanism. **Declare `3.0.1`** — it grants no new API, but it mechanically enforces the "Kodi 19 is dropped" decision rather than relying on convention, and it is the linter's `advised` value on all three branches.

### 3. Scope of "vendoring" — both are right about different halves; here is the single statement

ARCHITECTURE.md is right about the **destination**: for the core path this is replacement, not patching. Roughly **8 KB** of vendored source survives as running code (`exception.py` and `utils.py` fragments plus `pin-dialog.xml`), about **73 KB** goes to quarantine, about **32 KB** is deleted outright, and `ui/addon.py` at **41.5 KB** — one god class holding routing, listing, playback, settings, account setup, drive selection, search UI and slideshow — is where the schedule risk lives.

PITFALLS.md is right about the **sequencing**: vendoring must come first anyway, because `setInfo`, the OAuth layer, the dialog controllers and the skin XML all live inside the module, and because the **package-rename decision must be made before a single file is copied** (reversing it later means redoing every import).

**Reconciled statement of what the vendor phase delivers — a small mechanical phase with a large, precise definition of done:**

- Copy verbatim from the **`matrix` branch** (v1.4.0), or better, from an installed working 1.4.0 directory. The GitHub default branch is 1.3.9 / Python 2.
- **Rename the package.** `clouddrive/` → `resources/lib/vendor/onedrive_common/` (or equivalent under this add-on's namespace). Do not keep the name to minimise the diff.
- Do **not** vendor the module's top-level `resources/` package as a top-level package — merge its `settings.xml`, `language/` and `skins/` into this add-on's existing `resources/` and delete the stray `resources/__init__.py`. A second importable top-level `resources` is a live ambiguity, amplified by the Kodi 20 `sys.path` ordering regression (xbmc#22985).
- Resolve all six hardcoded `script.module.clouddrive.common` lookups to this add-on's own id/profile/version. CI grep → zero hits.
- Fold the module's own `<extension point="xbmc.service" start="login">` into this add-on's `service.py`, deliberately, deciding what survives.
- Copy skin XML + media and update every `WindowXMLDialog` construction site's path argument.
- Replace `repr()`/`eval()` in the account store with `json.dumps`/`json.loads`. CI grep for `eval(` → zero.
- Preserve `LICENSE.txt` (GPL-3.0) **and** `clouddrive/common/cache/LICENSE` (Apache-2.0) — or drop the licence with the file it covers. Write `VENDORED.md` with upstream URL, branch, version, commit SHA, per-subtree licence, and local modifications.
- **Acceptance: the add-on behaves identically after the vendor commit (modulo the already-dead broker), with every sibling cloud-drive add-on uninstalled, on a clean profile, and every dialog opens.**

Then, and only then, the core path is built fresh alongside it, and `vendor/` shrinks file-by-file. Phase sizing follows directly: **"vendor the module" is small and mechanical; "replace `ui/addon.py`" is the single largest phase in the project.**

### 4. The loopback HTTP redirector — FEATURES.md wins; PROJECT.md's deferral is corrected

**Correct:** the thing PROJECT.md calls "Background download service" is not a downloader. `clouddrive/common/service/download.py` is a **~78-line loopback HTTP handler** whose whole job is to answer `do_GET` by resolving a *fresh* `@microsoft.graph.downloadUrl` and returning a `302`. `CloudDriveAddon.play()` never hands Kodi a Graph URL — it builds `http://127.0.0.1:<port>/…` and passes that to `setResolvedUrl`, and does the same for every subtitle in `setSubtitles`. Evidence: direct source read, HIGH confidence.

**Corrected position: the loopback 302 redirector ships in the play phase. It is table-stakes infrastructure, not a restored feature.** Move it out of PROJECT.md's "Restored features (after core works)" list entirely. It is ~80 lines, has no relationship to background downloading, and its absence means the play phase must instead own an explicit, tested decision to hand Kodi a raw expiring URL and accept mid-playback failure. Do not let that be discovered *during* the play phase.

**This also resolves ARCHITECTURE.md's open question.** ARCHITECTURE.md hypothesised (LOW confidence) that `SourceService` might be the fix for pause-then-seek-after-expiry, and that if confirmed, `SourceService` moves up the roadmap. It does not need to: the DownloadService redirector already solves expiry **by construction** — every Kodi re-open, on any seek, pause or network blip, hits loopback and gets a newly signed URL, with no token-refresh logic in the play path at all. Subtitles ride the same redirector for the same reason. The pause-then-seek device test still runs in the play phase (it is cheap and it measures real URL lifetime), but it is now a *confirmation* test rather than a decision gate, and **`SourceService` stays deleted regardless of its outcome** (see #5).

**Two things share the name "the HTTP server" and must never be judged together:** `DownloadService` (302 re-signer, no index, URLs keyed on high-entropy Graph item IDs) is required; `SourceService` (HTML index of the whole drive on port 8586) is an anti-feature.

**Harden the redirector in v1, not later:** a per-session random path token so a guessed item ID is not sufficient, and a dynamically allocated port rather than a fixed one.

### 5. Port 8586 / `allow_directory_listing` — one recommendation: delete it

**Do this: delete `SourceService`, `service/source.py`, `html.py`, and both the `allow_directory_listing` and `port_directory_listing` settings. Do not restore it, do not merely default it off, do not gate it behind a warning, and do not spend vendor-phase time verifying its binding behaviour.**

FEATURES.md's case is decisive, and PITFALLS.md's "verify then flip the default" position is the more cautious but strictly worse option, because it spends investigation budget on a feature whose *best case* is still a liability:

1. It is unauthenticated — `service/base.py` contains no token, password or authorisation check of any kind.
2. Loopback is not a security boundary on Android: every installed app on the TV box can reach `127.0.0.1:8586`.
3. It is an **index**, therefore enumerable — the entire OneDrive tree, names, structure and download links, browsable with no credentials. Categorically worse than the redirector, whose URLs cannot be listed.
4. It is on by default, so the exposure exists on every install.
5. The feature it serves — "Use Drive as a source" — is documented as **not currently working** by the sibling add-on's own README. You would be restoring an attack surface to support a broken feature.
6. It has no Android TV use case at all; its purpose is a file-manager workflow, precisely the interaction PROJECT.md's constraints rule out.

Verifying the binding therefore changes nothing: if it binds to loopback exactly as claimed, points 1–6 all still hold. The remaining "is it really loopback-bound" question is retained under Empirical Unknowns only as a *disclosure* matter for existing users who have been running it with the default `true` — not as an input to this decision. Note the migration consequence: `allow_directory_listing` is currently defined **twice** (this add-on's `settings.xml` and the module's own), and existing installs have `true` stored. Removing the setting orphans the stored value rather than clearing it, so the migration must clear it explicitly.

### 6. Graph scopes — STACK.md wins; PROJECT.md's `Files.Read.All` assumption is corrected

**Correct scope set, final:**

```
https://graph.microsoft.com/Files.Read offline_access openid profile
```

Graph's own reference lists **`Files.Read` as the least-privileged permission** for `GET /drives/{id}/items/{id}/children` **and** for `GET /me/drives`, for *both* Delegated (work or school) and Delegated (personal Microsoft account). `Files.Read.All` appears only as a *higher-privileged alternative*; requesting it enlarges the consent prompt and materially raises the odds a Business tenant admin blocks the app — the single failure this project has no code-level answer for. ARCHITECTURE.md's incidental `offline_access Files.Read Files.Read.All User.Read` line is superseded.

- `offline_access` — **required**, or no refresh token is issued and the add-on re-prompts hourly.
- `openid` — recommended: yields an `id_token` with a stable `sub` for keying multiple accounts locally.
- `profile` — recommended: gives a display name for the account chooser without a `/me` round trip.
- `User.Read` — **drop.** Only needed if you call `/me`; `profile` + `id_token` already cover the label. Fewer scopes, shorter consent, fewer tenant blocks.
- `Files.Read.All`, `Sites.Read.All`, `Files.ReadWrite*` — **never in v1.** Revisit `Files.Read.All` only per-user if a real SharePoint case appears.
- `.default` — not appropriate: it prompts for every registered permission and cannot be combined with `offline_access`/`openid` in one request.

Use the **fully-qualified** form (`https://graph.microsoft.com/Files.Read`), not the bare one — unambiguous and survives any future default-resource change.

## Corrected Premises

Assumptions in PROJECT.md (and in the research brief) that the research disproved. Each needs a PROJECT.md edit.

| Assumption in PROJECT.md | Reality | Consequence |
|---|---|---|
| Requirements written assuming **`Files.Read.All`** | `Files.Read` is documented as least-privileged and **sufficient** for `/me/drives` and `/children` on both personal and work/school | Request `Files.Read offline_access openid profile`. Materially lowers tenant-admin block risk — the one failure mode the add-on cannot code around |
| Delta invalidation returns **`resyncRequired`** | Graph v1.0 returns **HTTP 410 Gone** with `resyncChangesApplyDifferences` / `resyncChangesUploadDifferences` plus a `Location` header carrying a fresh `nextLink`. `resyncRequired` is the retired OneDrive-API-v1 name | Code handling only `resyncRequired` means **the resync path never fires**. Handle 410 explicitly and restart from `Location`. Deferred to the restored-services phase |
| Vendoring = clone the `clouddrive.common` GitHub repo | The **default branch (`master`) is 1.3.9** — the Python 2 / Kodi 18 line (`xbmc.python 2.25.0`). Version **1.4.0**, which `addon.xml` requires, lives only on the **`matrix` branch** | Vendoring the default branch silently downgrades you to Python 2 code that imports plausibly and fails at runtime. Vendor from `matrix`; record the SHA in `VENDORED.md` |
| Existing users can be migrated | OAuth refresh tokens are **bound to a `client_id`**. Existing tokens were minted through the broker's registration; the new embedded `client_id` is a different client. Redeeming them fails | **Every existing user must re-authenticate. There is no way around it.** The work is making the re-auth *proactive and explained* at first launch — preserve display names and drive selections, discard tokens, mark `needs_reauth` — not an `AADSTS` error after a silent failed refresh |
| Typed InfoTag setters are a **Kodi 20+ requirement** | `setInfo` is present and functional in Kodi 22 master (`ListItem.cpp:375`) and only log-warns | Not a blocker. Deferrable cleanup phase after vendoring. But it must land atomically with `int(ms // 1000)`, or the migration turns a silent truncation into a `TypeError` on every video item |
| "Background download service" is a deferrable restored feature | It is a **~78-line loopback 302 re-signer on the critical path for playback and subtitles** | Ships in the play phase. See Reconciled Conflicts #4 |
| `allow_directory_listing` "default off unless verified loopback-bound and authenticated" | It is loopback-bound **and unauthenticated**, it is an enumerable index, and the feature it serves is documented broken upstream | Delete outright. See Reconciled Conflicts #5 |
| Bumping `xbmc.python` is needed to target Kodi 20+ | Every release 19→22 ships `<backwards-compatibility abi="3.0.0"/>`; `3.0.0` installs on all four and **`3.0.1` grants no new API** | Declare `3.0.1` anyway — its only effect is to make Kodi 19 refuse to install, which mechanically enforces a decision PROJECT.md already made |
| `GET /drives` enumerates drives | **Not a Graph v1.0 endpoint.** The reference documents only `/groups/{id}/drives`, `/sites/{id}/drives`, `/users/{id}/drives`, `/me/drives`. Current code calls `/drives`, then `/me/drives`, and swallows a 403 | Delete the bare `/drives` call. Removes a guaranteed-failing round trip per account load — latency and throttle pressure both |
| Path encoding is broken for `#`, `?`, `%`, `+`, `:` | `+` and `'` are RFC 3986 sub-delims and are **legal unencoded** in a path segment; `/ \ * < > ? : \|` are reserved in OneDrive names and cannot occur. The real problems are `#`, space and literal `%` — and **`#`/`%` are reserved on Business but legal on Personal** | `urllib.parse.quote(path, safe="/")` on the **user path only**, never the template. A Personal-only test pass cannot find this class of bug; a Business-only pass cannot either |
| `report_error` / error reporting is a feature | `remote/errorreport.py` posts tracebacks to a third-party endpoint. OAuth stack traces carry tenant names, UPNs, drive IDs and file paths | Delete the code **and** the setting. Log to `kodi.log` only |

## Maintainer Prerequisites

Non-code setup that must exist before implementation can be validated. These belong in the auth phase's prerequisite block as a **numbered checklist**, not prose; A0 blocks any real device-flow test.

1. **Register the Azure application** (one-time, maintainer only).
   - **Supported account types = "Accounts in any organizational directory (Any Microsoft Entra ID tenant - Multitenant) and personal Microsoft accounts"** → manifest `"signInAudience": "AzureADandPersonalMicrosoftAccount"`. Anything else breaks exactly one account class, and you will not notice for weeks because you only own one kind of account.
   - **`"requestedAccessTokenVersion": 2`** — mandatory when `signInAudience` is `AzureADandPersonalMicrosoftAccount`.
   - **Authentication → Advanced settings → Allow public client flows = Yes** → `"allowPublicClient": true`. **This is the single most common device-code misconfiguration.** Left at its `false` default, Entra infers a confidential client (device code performs no redirect, so there is nothing to infer from) and the token endpoint returns `AADSTS7000218: The request body must contain the following parameter: 'client_assertion' or 'client_secret'` — an error that actively misdirects toward embedding a secret. Teams have shipped a secret to "fix" it.
   - **No client secret, no certificate. Ever.** Public clients must not use them; a secret in a GPL add-on is public by definition, and its presence turns the app confidential and breaks device code.
   - Optionally register `https://login.microsoftonline.com/common/oauth2/nativeclient` as an `InstalledClient` redirect URI. Not required for device code.
   - **Verify by reading `signInAudience` and `allowPublicClient` back from the manifest**, not by trusting the portal UI. Note the caveat: once `signInAudience` is `AzureADandPersonalMicrosoftAccount`, the supported-accounts setting can no longer be changed in the UI — only via the manifest editor.
2. **Write the app registration runbook** into the repo (PROJECT.md already requires this), including the `AADSTS7000218` "if you skipped step 1c, you'll see this" note verbatim.
3. **Obtain a test account of each class** — one personal Microsoft account and one work/school account, ideally in a tenant with Conditional Access enabled. Without both, Pitfalls 1, 4 and 7 are structurally untestable.
4. **Provision a clean test environment**: a Kodi profile with **no** sibling cloud-drive add-ons installed (`plugin.googledrive`, `plugin.dropbox`, `script.module.clouddrive.common`), and a real Android TV box on Wi-Fi with a real remote. The maintainer's daily machine masks Pitfalls 13, 14, 19 and 21 simultaneously.
5. **Create the distribution GitHub repo / Pages target** before the distribution phase, served over HTTPS — `raw.githubusercontent.com` or GitHub Pages avoids Kodi's plain-HTTP repository warning.
6. **Retain a real pre-upgrade v2.3.0 profile** (`accounts.db` + `settings.xml`) as a migration test fixture. Once overwritten it cannot be recreated.

## Empirical Unknowns

Things no amount of reading resolves. Each is tagged with the phase that should answer it and the decision it unblocks.

| Unknown | Phase | Test | Decision it unblocks |
|---|---|---|---|
| **Does our own (non-first-party) `client_id` work on `/common` for both account types?** The live probe that verified `/common` used a Microsoft first-party client, which is pre-authorized in ways third-party clients are not | **Auth (first spike, before anything is built on top)** | End-to-end device-code sign-in with the maintainer's registration, once with a personal account and once with a work account | Whether `/common` is the authority at all, or whether the add-on needs a `/consumers` + `/organizations` split. The project's single highest-leverage assumption |
| **Real `@microsoft.graph.downloadUrl` lifetime, Personal vs Business.** Microsoft refuses to publish it and warns "might expire within minutes"; community reports range from minutes to ~1 hour | **Play** | Resolve a URL, then GET it with a `Range` header at T+1, +5, +15, +30, +60 min, separately on a Personal and a Business drive. Record the numbers | How bad a raw-URL fallback would be, and whether any listing/thumbnail cache TTL is safe. Does *not* gate the redirector — that ships regardless |
| **Pause-then-seek after URL expiry on Android TV** | **Play** (same phase that first achieves playback) | Play a 2h+ file on the real box, pause 20–30 min, resume, then seek forward | Confirms the redirector actually closes the expiry hole end-to-end through Kodi's curl reader. Now a confirmation test, not a decision gate (Reconciled Conflicts #4) |
| **Which exact `AADSTS` code a blocking Business tenant returns** — `65001`, `90094`, `53003`, `530035`, `7000218` or something else | **Auth** | Attempt sign-in against a tenant with third-party apps blocked and/or Conditional Access enabled | Whether the custom-`client_id` escape hatch is triggered with a precise message or a generic one. The escape hatch is worthless if the user is never told it exists |
| **Whether `allow_directory_listing` binds where it claims** | **Vendor (disclosure only)** | `netstat`/`ss` on Windows and on the Android box with the current v2.3.0 installed | Nothing in the roadmap — the feature is deleted regardless (Reconciled Conflicts #5). Answer it only to know what to tell existing users who ran the `true` default |
| **Do two Kodi sub-interpreters actually fail to exclude each other under `fcntl.lockf`?** | **Auth** (cheap, alongside the token-store work) | Two-interpreter lock test on Android; confirm `O_EXCL` excludes and `lockf` does not | Nothing — the design uses `O_EXCL` either way. Worth 20 minutes to close the inference, and it is exactly the kind of wrong assumption a later contributor reintroduces |
| **SQLite WAL reliability on Android storage (FUSE/sdcardfs)** | **Vendor / Migration** | Repeated account save/load on the box | Whether the migration can read the existing `accounts.db` reliably or needs `journal_mode=delete` as a fallback. Moot once the store is JSON, but the migration must still *read* the old DB |
| **Android TV listing performance for a 500-item folder** | **Browse** | Time it on the real box, with and without `offscreen=True` | Whether the chunk size and `$top` defaults are right, and whether `$expand=thumbnails` needs to be conditional |
| **Whether repository auto-update actually fires** | **Distribution** | Publish N+1, wait out Kodi's periodic check without pressing "Check for updates" | The entire justification for the self-hosted repo over a zip. Multi-hour latency — see Build Order |

## Recommended Build Order

One reconciled ordering. It preserves ARCHITECTURE.md's two-track parallelism where the parallelism is real, and PITFALLS.md's sequencing constraints where they bind. The project config has `parallelization: true`, so the tracks below are genuine roadmapper signal, not decoration.

**The two tracks are independent because Track V/P needs no token and no Azure registration.** It fixes roughly half the bugs listed under "Core path correctness" in PROJECT.md as pure functions over recorded JSON, which means verifiable progress on day one instead of a week of waiting on a portal.

```
  +- TRACK V/P - no auth required, start immediately -------------------+
  |  V1  VENDOR (mechanical, must land first and alone)                 |
  |      matrix branch . package rename . resources/ merge . six        |
  |      hardcoded-id fixes . skin XML paths . service.py fold .        |
  |      eval()->json . licences + VENDORED.md                          |
  |      DoD: identical behaviour, clean profile, no sibling add-ons    |
  |  P1  provider/model.py . common utils . graph/paths.py              |
  |      + fixture tests: per-segment encoding, OData quoting           |
  |  P2  extract_item() + fixtures (int durations, defensive dict       |
  |      access, video/audio/image, remoteItem, package, missing facet) |
  |  P3  graph/paging.py - iterative generator, cancellation -> []      |
  |  P4  CI: pytest . kodi-addon-checker (nexus/omega/piers) .          |
  |      layering test (no import xbmc below kodi/) .                   |
  |      greps: client_secret . eval( . script.module.clouddrive.common |
  +-------------------------------+-------------------------------------+
                                  |
  +- TRACK A - auth critical path +-------------------------------------+
  |  A0  MAINTAINER, NOT CODE: Azure app registration.                  |
  |      Blocks A2. Do it before anything else.                         |
  |  A1  auth/tokens.py . auth/store.py . O_EXCL refresh_lock           |
  |      (pure pytest with tmp_path - no Kodi, no network)              |
  |  A2  auth/device_flow.py (RFC 8628; needs A0 to test for real)      |
  |      > SPIKE: our client_id on /common, personal + work             |
  |  A3  auth/session.py TokenProvider + rotation-race recovery         |
  |  A4  kodi/dialogs.py device-code dialog (reuse pin-dialog.xml)      |
  |      + AADSTS->message map + addon.xml <disclaimer> rewrite         |
  |      > MILESTONE 1: sign in from the couch                          |
  +-------------------------------+-------------------------------------+
                                  v
   B   BROWSE - graph/client.py (timeout=, 401-retry-once, 429 +
       Retry-After via waitForAbort, absolute-URL passthrough, no
       mutable per-request state) . provider/onedrive.py (/me/drives,
       not /drives) . kodi/routes.py + listing.py (offscreen=True,
       chunked addDirectoryItems, endOfDirectory in finally) .
       entrypoint.py . search . pseudo-folders
       > MILESTONE 2: browse a folder end to end
   PL  PLAY - kodi/play.py . resolve at play time . setResolvedUrl
       exactly once . loopback 302 redirector (+ path token, dynamic
       port) . subtitle discovery through the same redirector
       > MILESTONE 3: core value delivered
       > downloadUrl-lifetime + pause-30-min-then-seek tests here
   K   KODI MODERNIZATION - typed InfoTag setters + int(ms // 1000)
       ATOMICALLY . settings.xml version="1" . delete sign-in-server,
       report_error, allow_directory_listing, port_directory_listing .
       drop Krypton visibility hacks
   M   MIGRATION - schema_version gate . preserve names + drive
       selections . discard tokens, mark needs_reauth . archive
       accounts.db.pre-v3 . clear the dead sign-in-server value .
       proactive explained re-auth prompt at first launch
   R   RESTORED SERVICES - PlayerService (resume/watched) -> ExportService
       (STRM, video only) -> slideshow -> delta sync (opt-in, default off,
       410 + Location resync, never persist a None token)
       SourceService is NOT restored - it is deleted in K
```

**Distribution (D) is deliberately not last.** PITFALLS.md's point carries: Kodi decides whether to re-read the repository index by comparing a stored checksum, and its automatic check is **periodic** — so an N→N+1 update test has **multi-hour latency**, and the maintainer (who always force-refreshes) is structurally unable to reproduce the failure users see. Stand the repository up and publish a first throwaway N→N+1 pair **as soon as the browse milestone is green**, so the waiting overlaps with the play and modernization work instead of blocking release. Ship SHA-256 (`<checksum verify="sha256">` + `<hashes>sha256</hashes>`), never MD5; use the `<dir>` schema, never the flat pre-Gotham one; and never publish a pre-release suffix on a version you want users to receive, because Kodi's Debian-style comparison sorts `2.3.0-beta` **below** `2.3.0`.

**Ordering rationale:**

- **V1 is first, mechanical, and alone.** Interleaving it with rewriting destroys the ability to answer "did vendoring break this, or did my rewrite?". The add-on must never be in a state where it has neither the external module nor a complete local copy. The package-rename decision is made *before* the first file is copied.
- **A0 is a prerequisite of the entire project and it is not code.** Put it in phase 1 as a maintainer checklist item.
- **A1 before A2.** The token store and its cross-interpreter lock are the trickiest thing to get right and the *easiest* thing to test (files and time only). Settling the concurrency design before the network protocol exists prevents it being papered over later.
- **The A2 spike gates everything downstream.** If our own `client_id` does not behave on `/common`, the authority strategy changes and every later phase inherits it.
- **The HTTP layer lands with the first Graph calls, in B.** Retrofitting `timeout=`, `Retry-After` and 401-retry into scattered call sites is the expensive version.
- **K sits after V1 and after PL,** because the `setInfo` calls live in the vendored module and because `setInfo` still works — nothing is blocked on it. Its float→int fix must be atomic with the setter migration.
- **M is its own phase, after auth exists** (you cannot write "sign in again" before sign-in exists) and **before the first distributed release**. Do not fold it into auth; it needs an acceptance pass against a real pre-upgrade profile.
- **R is last and strictly ordered by dependency:** resume/watched is downstream of export (the `dbid` recovery keys off the exported `.strm`), and delta sync is pulled in by export rather than chosen independently — so delta's CPU/RAM and 429 costs are export's costs and should be budgeted there.
- **Every phase carries an Android TV acceptance pass on real hardware with a real remote**, and the release gate requires at least one full pass on a clean profile with a Business account.

### Research Flags

Phases likely needing `/gsd-plan-phase --research-phase` during planning:

- **V1 Vendor** — not because the domain is unknown, but because the definition of done is a long, exact, verifiable checklist across six hardcoded-id sites, two licence trees, skin path resolution, a service fold and a package rename. The failure mode is "finished but silently broken on clean installs," which is exactly what deeper planning prevents.
- **A2–A4 Auth** — the highest-risk, least-testable code in the project, dependent on live Entra behaviour, with a documented gap between Microsoft's own error table and what the endpoints actually return (`invalid_grant`/`AADSTS7000014` where `bad_verification_code` is documented; `slow_down` mandated by RFC 8628 but undocumented by Microsoft). The polling loop must be written as an **allow-list**, not a deny-list.
- **M Migration** — requires reading v1.4.0's `AccountManager`/`SimpleKeyValueDb` in detail, handling mixed `repr()`/JSON rows via `ast.literal_eval` (never `eval`), and designing a one-shot `schema_version`-gated flow whose failure mode ("it lost my account") is the most damaging user-facing outcome in the project.
- **R Restored services (delta sync specifically)** — 410 + `Location` resync, the last-occurrence-wins rule, track-by-id-never-by-path, `?token=latest` baselining, and the never-persist-`None` invariant.

Phases with standard, well-documented patterns (skip research):

- **P1–P4 Track P** — pure functions with authoritative worked examples already captured (Microsoft's own encoding fixtures: `Ryan's Files` → `Ryan's%20Files`, `Break#Out` → `Break%23Out`, `estimate%s.docx` → `estimate%25s.docx`).
- **B Browse** and **PL Play** — the Graph and Kodi contracts are documented verbatim in ARCHITECTURE.md and FEATURES.md, including the exact `setResolvedUrl` and `endOfDirectory` contracts.
- **K Kodi modernization** — the typed-setter list, the `<settings version="1">` schema and the `SettingLevel` enum are all captured from Kodi source in STACK.md.
- **D Distribution** — the `<dir>` schema, zip naming (`plugin.onedrive-<version>.zip` with a single top-level `plugin.onedrive/`), and the on-disk repo layout are fully specified in STACK.md §7.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Every Kodi claim read from `xbmc/xbmc` C++ source at named release branches/tags; every Microsoft claim from Microsoft Learn; the device-code protocol additionally verified by **first-hand live HTTP probes** on 2026-08-22 (including `authorization_pending`-arrives-as-HTTP-400 and the undocumented `invalid_grant`/`AADSTS7000014` response). Kodi module availability verified by enumerating `mirrors.kodi.tv` for all three repos |
| Features | **MEDIUM-HIGH** | Protocol and API facts HIGH (Microsoft Learn + direct source read of `service/download.py`, `ui/addon.py::play()`, `service/base.py`). Category *norms* MEDIUM — only two live competitors, so the "table stakes" judgement rests on a thin sample. Forum-sourced CPU/RAM complaints are anecdotal |
| Architecture | **MEDIUM-HIGH** | Kodi and Graph mechanics read from first-party docs (HIGH). Cross-interpreter concurrency is documented behaviour plus inference (MEDIUM) — but the chosen `O_EXCL` design is correct under either process model, so the inference is not load-bearing. `clouddrive.common` internals beyond the file inventory and quoted interfaces are LOW |
| Pitfalls | **MEDIUM-HIGH** | Graph/Entra behaviour quoted verbatim from Microsoft Learn; Kodi behaviour read from the `xbmc/xbmc` tree; vendoring behaviour read from the actual v1.4.0 source with file:line citations. Evidence tagged PRIMARY / CORROBORATED / INFERRED throughout, and four brief assumptions were corrected outright |

**Overall confidence:** MEDIUM-HIGH.

A note on grading: the automated `classify-confidence` seam grades by *provider id* and rates `webfetch`/`websearch` as LOW. That grade does not fit this research pass. The elevation above is **source-based**: first-party documentation and upstream source read directly and quoted rather than paraphrased, plus first-hand protocol probes. Claims resting on forum threads, blogs or inference are capped at MEDIUM or lower and labelled inline in the source documents.

### Gaps to Address

- **The `/common` + own-`client_id` assumption is the project's load-bearing unknown.** Everything downstream inherits it. Handle by making it the first thing tested after A0, before any code is built on top.
- **Business-tenant behaviour is entirely unverified** — consent, Conditional Access, MFA, and the `#`/`%` reserved-character difference. Handle by requiring one Business account in the release acceptance matrix; a Personal-only pass is acceptable per-phase but not at release.
- **`downloadUrl` lifetime is undocumented by Microsoft and unmeasured by us.** Handle by measuring it in the play phase; the redirector makes the answer non-blocking either way.
- **`clouddrive.common` internals are only inventoried, not read line-by-line** beyond the interfaces quoted. Handle by treating the vendor phase's first mechanical commit as the read: the acceptance criterion is "behaves identically," which surfaces anything the inventory missed.
- **Recorded Graph fixtures go stale silently.** Response shapes drift between Personal and Business and over time. Handle by recording fixtures from **both** drive types, labelling them, and re-recording whenever a live response surprises you — a green suite against 2023-shaped JSON proves nothing about 2026 Graph.
- **Kodi's "does not paint until `endOfDirectory` returns" behaviour is MEDIUM confidence** and shapes whether chunked adds buy perceived responsiveness or only bounded memory. Handle in the browse phase by measuring on the real box and, if needed, adding a `DialogProgressBG` updated per page.
- **Whether `Monitor.waitForAbort` is reliable across all add-on/script instances** (Kodi issue #18191) affects clean shutdown on Android. Handle by testing "quit Kodi with a large listing in flight" as a per-phase acceptance item.

## Sources

### Primary (HIGH confidence)
- **Microsoft Learn** — `v2-oauth2-device-code` (endpoints, POST bodies, error table, `verification_uri_complete` non-support, `/common`|`/consumers`|`/organizations`), `reference-app-manifest` (`allowPublicClient`, `signInAudience`, `requestedAccessTokenVersion`), `scopes-oidc`, `refresh-tokens` (90-day lifetime, rotation, revocation), `v2-oauth2-auth-code-flow`, `reference-error-codes` (AADSTS table)
- **Microsoft Graph v1.0 reference** — `driveitem-list-children` (`Files.Read` least-privileged for personal *and* work/school), `drive-list` (no bare `/drives`), `driveitem-get-content` (preauth URL, `Range` targets the download URL), `driveitem-delta` (410 + `resyncChangesApplyDifferences`, track by id, last-occurrence-wins, `?token=latest`), `throttling` / `throttling-limits`, `addressing-driveitems` (per-segment encoding, reserved characters, Personal vs Business `#`/`%`)
- **Live protocol probes, 2026-08-22** — `POST /{common,consumers,organizations}/oauth2/v2.0/devicecode` → 200 with `expires_in=900`, `interval=5`, differing `verification_uri`; `POST /common/.../token` pending → **HTTP 400** `authorization_pending` `[70016]`; bogus `device_code` → **`invalid_grant`** `[7000014]`, not the documented `bad_verification_code`
- **Kodi C++ source (`xbmc/xbmc`)** — `addons/xbmc.python/addon.xml` @ `Matrix`/`Nexus`/`Omega`/`master`; `AddonInfo.cpp` (`MeetsVersion`); `AddonInfoBuilder.cpp` (repo zip path); `Repository.cpp` (`<dir>` schema, `checksum@verify`, `hashes`, MD5 warning, flat-schema removal); `SettingDefinitions.h` / `SettingLevel.h`; `Settings.h` / `Addon.h` / `ModuleXbmcvfs.h`; `ListItem.cpp` (`setInfo` still present at :375; 35 `GuiLock` accessors); `InfoTagVideo.h`; `tools/depends/target/python3/PYTHON3-VERSION` at release tags
- **Kodi ecosystem** — `mirrors.kodi.tv/addons/{nexus,omega,piers}/` module enumeration (absence of `msal`, `cryptography`, `pil`, `pypng`; presence of `pyqrcode`, `qrcode`, `requests` 2.31.0); `xbmc/addon-check` `versions.py` / `check_dependencies.py`; PyPI JSON API (Kodistubs 21.0.0, kodi-addon-checker 0.0.36, `msal` 1.37.0 `requires_dist`)
- **Upstream source read directly** — `cguZZman/script.module.clouddrive.common` branch `matrix` v1.4.0: `service/download.py`, `service/source.py`, `service/base.py`, `ui/addon.py` (lines 82, 424, 439, 583), `ui/dialog.py:126`, `ui/utils.py:33`, `remote/request.py:132`, `remote/oauth2.py`, `remote/signin.py`, `remote/errorreport.py`, `account.py`, `db.py`, `skins/default/1080i/pin-dialog.xml`; and `addon.xml` on **both** `master` (1.3.9 / Python 2) and `matrix` (1.4.0)
- **Standards** — RFC 8628 §3.5 (`authorization_pending`, `slow_down` +5s permanent, MUST stop polling on any other error, connection-timeout backoff); RFC 3986 (`pchar`, sub-delims)

### Secondary (MEDIUM confidence)
- Kodi official docs — `InfoTagVideo`, `xbmcplugin` (chunked `addDirectoryItems` sanctioned), `xbmcgui.Window`, Python API v20, Python libraries wiki
- Kodi wiki — Add-on:Google Drive, Cloud Drive Common Module, Features and supported formats, Subtitles
- `xbmc/xbmc#22985` — Kodi 20 `sys.path` ordering regression (fixed by PR #23244; affected builds in the wild); PRs 18345/19301 (`xbmc.translatePath` deprecated then removed); issue #18191 (`waitForAbort` reliability)
- `cguZZman/plugin.googledrive` README — advertised feature set of the closest living competitor; "Use Drive as a source" documented as not working; music STRM export documented as not working
- Microsoft troubleshooting articles — `AADSTS7000218`, consent issues, Conditional Access authentication flows
- MSAL.NET device-code-flow guidance — "Allow public client flows"; contains a **stale** `/common` constraint block citing `AADSTS90133`, superseded by the protocol reference and by our live probes

### Tertiary (LOW confidence — validate before relying on)
- Kodi forum thread 324784 — background-service CPU/RAM cost and playback stalls (anecdotal, second-hand)
- Kodi forum threads 316042 / 365620 / 370707 / 374837 — `setResolvedUrl` / `IsPlayable` semantics, InfoTag API changes
- `OneDrive/onedrive-api-docs#884` — community reports of `downloadUrl` validity (minutes to ~1 hour); **superseded in practice by our own measurement task**
- Nango blog — Microsoft OAuth `invalid_grant` on refresh-token rotation
- ARCHITECTURE.md's `SourceService`-as-seek-fix hypothesis — explicitly self-labelled LOW; **resolved as unnecessary** in Reconciled Conflicts #4

---
*Research completed: 2026-08-22*
*Ready for roadmap: yes*
