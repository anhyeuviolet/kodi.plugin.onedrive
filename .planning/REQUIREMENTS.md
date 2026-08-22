# Requirements: OneDrive Kodi Add-on — Refactor

**Defined:** 2026-08-22
**Core Value:** Sign in from the couch with a remote, and play a file from OneDrive.

Scope note: this is a brownfield refactor. Requirements below describe the target state, not new product surface. Where the existing add-on already does something, the requirement is that it keeps working after the rewrite. Every requirement is checkable against either an automated test or a named manual acceptance step on real hardware.

## v1 Requirements

### Setup (maintainer prerequisites — not code)

- [ ] **SETUP-01**: An Azure application is registered with `signInAudience: AzureADandPersonalMicrosoftAccount` and `requestedAccessTokenVersion: 2`, verified by reading the manifest back rather than trusting the portal UI
- [ ] **SETUP-02**: `allowPublicClient: true` is set on that registration; leaving the `false` default makes the token endpoint demand a client secret
- [ ] **SETUP-03**: No client secret or certificate exists on the registration, and none appears anywhere in the repository
- [ ] **SETUP-04**: A written registration runbook lives in the repo, including the `AADSTS7000218` symptom of skipping SETUP-02
- [ ] **SETUP-05**: Two test accounts are available — one personal Microsoft account and one work/school account
- [ ] **SETUP-06**: A clean test environment exists — a Kodi profile with no sibling cloud-drive add-ons installed, plus an Android phone running Kodi and reachable over `adb`, which is the Android test device. The Android TV box is the deployment target and the design authority for the 10-foot interface, but it is not a test device: it is exercised by use, and only at release (see CI-06)

### Vendoring

- [ ] **VND-01**: `script.module.clouddrive.common` v1.4.0 is vendored into the repo from the `matrix` branch, not the `master` branch, which carries the Python 2 / Kodi 18 line
- [ ] **VND-02**: The vendored package is renamed under this add-on's namespace, with the name decided before the first file is copied
- [ ] **VND-03**: The module's `resources/` contents are merged into this add-on's existing `resources/` rather than vendored as a second importable top-level package
- [ ] **VND-04**: Every hardcoded `script.module.clouddrive.common` id lookup resolves to this add-on's own id, version, and profile directory
- [ ] **VND-05**: The vendored account store uses JSON instead of `repr()` and `eval()`
- [ ] **VND-06**: Every outbound HTTP call passes an explicit `timeout=`
- [ ] **VND-07**: The module's own `xbmc.service` extension point is folded into this add-on's `service.py`, with an explicit decision recorded about what survives
- [ ] **VND-08**: Skin XML and media are copied and every dialog construction site's path argument is updated
- [ ] **VND-09**: `VENDORED.md` records upstream URL, branch, version, commit SHA, per-subtree licence, and local modifications; both the GPL-3.0 and Apache-2.0 licence files are preserved
- [ ] **VND-10**: The add-on behaves identically after the vendor commit, verified on a clean profile with every sibling cloud-drive add-on uninstalled, with every dialog opening
- [ ] **VND-11**: The external `<import>` of `script.module.clouddrive.common` is removed from `addon.xml`

### Identity and attribution

- [ ] **ID-01**: The add-on id becomes `plugin.onedrive.kn`, and every `plugin://` reference, profile path, and internal id lookup follows it — so this is a genuinely separate add-on that can never collide with the official `plugin.onedrive` in the Kodi repository
- [ ] **ID-02**: `provider-name` in `addon.xml` names the current maintainer, and the display name distinguishes this add-on from the original in the Kodi UI
- [x] **ID-03**: `LICENSE.txt` (GPL-3.0-or-later) is retained unchanged and every existing copyright notice is preserved — the code is a derivative work and the licence requires this
- [ ] **ID-04**: A `CREDITS.md` (or a README section) states that the add-on originates from `plugin.onedrive` by Carlos Guzman (cguZZman) and bundles `script.module.clouddrive.common`, with licences named
- [ ] **ID-05**: The repository no longer belongs to the upstream fork network, and its commit history is preserved rather than squashed — squashing would destroy the attribution record while keeping the code

### Authentication

- [ ] **AUTH-01**: A user signs in by reading a code off the TV and entering it on a phone, without typing a URL, username, or password on the remote
- [ ] **AUTH-02**: The add-on ships a public `client_id` and requires no Azure setup, no server, and no token copy-paste from the user
- [ ] **AUTH-03**: Sign-in works for both a personal Microsoft account and a work/school account against the chosen authority — verified end-to-end with the project's own registration, not a first-party client
- [ ] **AUTH-04**: The requested scope set is `https://graph.microsoft.com/Files.Read offline_access openid profile`, fully qualified, with no `Files.Read.All`, no write scope, and no `.default`
- [ ] **AUTH-05**: The device-code dialog renders the code at the largest font the skin offers, legible from a sofa
- [ ] **AUTH-06**: The dialog shows a live expiry countdown and, on expiry, offers a focused "Get a new code" action
- [ ] **AUTH-07**: Cancelling sign-in with Back or Esc leaves no partially-created account behind
- [ ] **AUTH-08**: Any QR code shown encodes only the server-supplied `verification_uri`; the verification URI is never hardcoded, because it differs per authority
- [ ] **AUTH-09**: The token-polling loop is an allow-list — it continues only on `authorization_pending` and `slow_down`, and stops on anything else
- [ ] **AUTH-10**: Pending polls arriving as HTTP 400 with a JSON body are parsed as protocol responses, not treated as transport failures
- [ ] **AUTH-11**: Refresh tokens are stored as atomically-written JSON under `special://profile/addon_data/`, never in a Kodi setting
- [ ] **AUTH-12**: Every token response is written back in full; when a response omits `refresh_token`, the previous one is retained
- [ ] **AUTH-13**: An automated test proves the persisted refresh token changes across two consecutive refreshes
- [ ] **AUTH-14**: Concurrent refresh across the plugin and the service is serialised by an `os.open(..., O_CREAT|O_EXCL)` lock with a stale-lock breaker; neither `threading.Lock` nor `fcntl.lockf` is used for this
- [ ] **AUTH-15**: A refresh that loses the race and receives `invalid_grant` re-reads the store and adopts the winner's token rather than signing the user out
- [ ] **AUTH-16**: A proactive refresh runs on Kodi startup well inside the 90-day refresh-token lifetime
- [ ] **AUTH-17**: The background service never opens a sign-in dialog; only the plugin may prompt interactively
- [ ] **AUTH-18**: A tenant that blocks the app produces a specific message naming the cause and pointing at the custom `client_id` setting — not a generic failure
- [ ] **AUTH-19**: A custom `client_id` setting exists at Expert level, empty by default
- [ ] **AUTH-20**: Multiple accounts are supported, with tokens, delta tokens, and cache keys isolated per account
- [ ] **AUTH-21**: Account labels come from Graph; no account name is ever typed on a remote
- [ ] **AUTH-22**: The add-on root is the account list, with an "Add an account…" row and a per-row context menu offering re-authorise and remove
- [ ] **AUTH-23**: The `sign-in-server` setting and every code path referencing an external OAuth broker are gone

### Browsing

- [ ] **BROWSE-01**: Folders list correctly for personal and business drives, one page at a time, without buffering the whole folder
- [ ] **BROWSE-02**: Pagination is iterative, so a very large folder cannot hit a recursion limit
- [ ] **BROWSE-03**: Cancelling mid-listing returns an empty list, never `None`, and never crashes
- [ ] **BROWSE-04**: A search does not corrupt subsequent folder listings — no request-scoped state persists on the provider between calls
- [ ] **BROWSE-05**: Names containing `#`, spaces, and literal `%` resolve correctly, verified on both a Personal and a Business drive because the reserved-character sets differ
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

- [ ] **PLAY-01**: Video, audio, and image files play from both personal and business drives
- [ ] **PLAY-02**: A loopback HTTP endpoint answers each request by resolving a fresh download URL and returning a 302; Kodi is never handed a Graph URL directly
- [ ] **PLAY-03**: The redirector binds to a dynamically allocated port and requires a per-session random path token, so a guessed item id is not sufficient
- [ ] **PLAY-04**: The download URL is resolved at play time on every request and is never cached, never placed in a directory item URL, and never written into an exported `.strm`
- [ ] **PLAY-05**: `setResolvedUrl` is called exactly once per playback invocation
- [ ] **PLAY-06**: Seeking works, including after a 20–30 minute pause on real Android TV hardware
- [ ] **PLAY-07**: The real download-URL lifetime is measured separately for Personal and Business drives and the numbers are recorded
- [ ] **PLAY-08**: Same-name subtitles are discovered across Kodi's full extension set, including language suffixes and VOBsub `.idx`/`.sub` pairs, and failure is silent
- [ ] **PLAY-09**: Subtitles are served through the same redirector as media, for the same expiry reason
- [ ] **PLAY-10**: Durations reach Kodi as integers

### Kodi modernization

- [ ] **KODI-01**: `addon.xml` declares `<import addon="xbmc.python" version="3.0.1"/>`, installing on Kodi 20, 21, and 22 and being rejected by Kodi 19
- [ ] **KODI-02**: The add-on installs and runs on Kodi 20 Nexus, 21 Omega, and 22 Piers
- [ ] **KODI-03**: List items use typed InfoTag setters, and this lands in the same commit as the integer-duration fix
- [ ] **KODI-04**: A full browse-and-play `kodi.log` contains zero `is deprecated` warnings from this add-on
- [ ] **KODI-05**: `resources/settings.xml` uses the `<settings version="1">` schema with section, category, and group structure
- [ ] **KODI-06**: Krypton-era visibility conditions are gone
- [ ] **KODI-07**: The `SourceService`, its HTML index, and both the `allow_directory_listing` and `port_directory_listing` settings are deleted from the codebase
- [ ] **KODI-08**: Third-party error reporting code and the `report_error` setting are deleted; errors go to `kodi.log` only

### Release readiness

- [ ] **REL-01**: The registration hosting the embedded `client_id` is one the project can keep indefinitely — the Microsoft 365 E5 Developer tenant renews on activity, and if it lapses the `client_id` dies for every installed copy at once. Decided before anyone is told to install

### Quality and CI

- [ ] **CI-01**: Only `resources/lib/kodi/` imports `xbmc*`; an automated test enforces this
- [ ] **CI-02**: Unit tests cover item extraction, pagination, path encoding, and OData literal quoting against recorded Graph JSON
- [ ] **CI-03**: Graph fixtures are recorded from both a Personal and a Business drive and are labelled by source
- [ ] **CI-04**: CI runs the test suite plus `kodi-addon-checker` against the nexus, omega, and piers branches
- [ ] **CI-05**: CI fails on any occurrence of `client_secret`, `client_assertion`, `eval(`, or `script.module.clouddrive.common`
- [ ] **CI-06**: Every phase carries a manual acceptance pass on Windows and on Android, where Android means an Android phone running Kodi and reachable over `adb`. The phone is a valid proxy for every OS-level question — storage paths, file mode bits, `O_EXCL`, loopback binding — because those are API-level behaviours, not form-factor ones, and the phone matches the target box's Android 11/12 storage regime. It is **not** a proxy for the two things only the TV can answer: D-pad focus and 10-foot readability, and low-end box performance. Those are checked on the TV before release (CI-07), and by using it
- [ ] **CI-07**: The release gate requires at least one full acceptance pass on a clean profile using a Business account

### Error handling

- [ ] **ERR-01**: Every failure state renders as a distinct, actionable sentence on screen — there is no log, console, or keyboard available to a TV user
- [ ] **ERR-02**: No network, expired token, tenant-blocked, admin-consent-required, and rate-limited states are each distinguishable from one another
- [ ] **ERR-03**: Quitting Kodi with a large listing in flight shuts down cleanly

### Distribution

- [ ] **DIST-01**: A build produces an installable zip named `plugin.onedrive-<version>.zip` with a single top-level `plugin.onedrive/` directory
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

Cross-cutting notes. `CI-06` (per-phase manual acceptance on Windows and on an Android phone; the TV is release-only) is established in Phase 1 and inherited as a standard by every later phase; `CI-07` is the release gate and sits in the final phase. `ERR-01` to `ERR-03` land in Phase 4, the first point at which the central HTTP layer, the auth error map, and the listing error paths all exist, so the failure states can be shown to be distinguishable from one another rather than asserted piecemeal. `SETUP-01` to `SETUP-04` are the Azure registration and appear as a maintainer prerequisite block on Phase 3, not as implementation work. `PLAY-10` sits in Phase 7 rather than Phase 6 because `KODI-03` requires the float-to-int duration fix to land in the same commit as the typed InfoTag setters.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 3 | Pending |
| SETUP-02 | Phase 3 | Pending |
| SETUP-03 | Phase 3 | Pending |
| SETUP-04 | Phase 3 | Pending |
| SETUP-05 | Phase 2 | Pending |
| SETUP-06 | Phase 1 | Pending |
| VND-01 | Phase 1 | Pending |
| VND-02 | Phase 1 | Pending |
| VND-03 | Phase 1 | Pending |
| VND-04 | Phase 1 | Pending |
| VND-05 | Phase 1 | Pending |
| VND-06 | Phase 1 | Pending |
| VND-07 | Phase 1 | Pending |
| VND-08 | Phase 1 | Pending |
| VND-09 | Phase 1 | Pending |
| VND-10 | Phase 1 | Pending |
| VND-11 | Phase 1 | Pending |
| ID-01 | Phase 1 | Pending |
| ID-02 | Phase 1 | Pending |
| ID-03 | Phase 1 | Complete |
| ID-04 | Phase 1 | Pending |
| ID-05 | Phase 1 | Pending |
| AUTH-01 | Phase 3 | Pending |
| AUTH-02 | Phase 3 | Pending |
| AUTH-03 | Phase 3 | Pending |
| AUTH-04 | Phase 3 | Pending |
| AUTH-05 | Phase 3 | Pending |
| AUTH-06 | Phase 3 | Pending |
| AUTH-07 | Phase 3 | Pending |
| AUTH-08 | Phase 3 | Pending |
| AUTH-09 | Phase 3 | Pending |
| AUTH-10 | Phase 3 | Pending |
| AUTH-11 | Phase 3 | Pending |
| AUTH-12 | Phase 3 | Pending |
| AUTH-13 | Phase 3 | Pending |
| AUTH-14 | Phase 3 | Pending |
| AUTH-15 | Phase 3 | Pending |
| AUTH-16 | Phase 3 | Pending |
| AUTH-17 | Phase 3 | Pending |
| AUTH-18 | Phase 3 | Pending |
| AUTH-19 | Phase 3 | Pending |
| AUTH-20 | Phase 3 | Pending |
| AUTH-21 | Phase 3 | Pending |
| AUTH-22 | Phase 3 | Pending |
| AUTH-23 | Phase 3 | Pending |
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
| KODI-01 | Phase 1 | Pending |
| KODI-02 | Phase 1 | Pending |
| KODI-03 | Phase 7 | Pending |
| KODI-04 | Phase 7 | Pending |
| KODI-05 | Phase 7 | Pending |
| KODI-06 | Phase 7 | Pending |
| KODI-07 | Phase 7 | Pending |
| KODI-08 | Phase 7 | Pending |
| CI-01 | Phase 2 | Pending |
| CI-02 | Phase 2 | Pending |
| CI-03 | Phase 2 | Pending |
| CI-04 | Phase 2 | Pending |
| CI-05 | Phase 2 | Pending |
| CI-06 | Phase 1 | Pending |
| CI-07 | Phase 8 | Pending |
| REL-01 | Phase 8 | Pending |
| ERR-01 | Phase 4 | Pending |
| ERR-02 | Phase 4 | Pending |
| ERR-03 | Phase 4 | Pending |
| DIST-01 | Phase 5 | Pending |
| DIST-02 | Phase 5 | Pending |
| DIST-03 | Phase 5 | Pending |
| DIST-04 | Phase 5 | Pending |
| DIST-05 | Phase 5 | Pending |

**Coverage by phase:**

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1. Vendor Lift | VND-01..11, ID-01..05, KODI-01, KODI-02, SETUP-06, CI-06 | 20 |
| 2. Pure Core and CI Harness | CI-01..05, BROWSE-02, BROWSE-03, BROWSE-04, BROWSE-07, BROWSE-16, SETUP-05 | 11 |
| 3. Authentication | AUTH-01..23, SETUP-01..04 | 27 |
| 4. Browse | BROWSE-01, BROWSE-05, BROWSE-06, BROWSE-08..14, ERR-01..03 | 13 |
| 5. Distribution | DIST-01..05 | 5 |
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
