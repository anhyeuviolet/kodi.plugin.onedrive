# Feature Research

**Domain:** Kodi cloud-storage media add-on (OneDrive / Microsoft Graph), Android-TV-first
**Researched:** 2026-08-22
**Confidence:** MEDIUM-HIGH (protocol and API facts HIGH from Microsoft Learn + direct source inspection; category norms MEDIUM from a thin, largely abandoned competitor set)

---

## Headline Finding — Read This First

**The loopback HTTP redirector is on the critical path for playback and cannot be deferred.**

PROJECT.md lists "Background download service" under *Restored features (after core works)*. Direct inspection of `script.module.clouddrive.common` shows that is not what that component actually does. `clouddrive/common/service/download.py` is a 78-line loopback HTTP handler whose entire job is to answer `do_GET` by resolving a **fresh** `@microsoft.graph.downloadUrl` and returning a `302` with a `location` header. `CloudDriveAddon.play()` never hands Kodi a Graph URL — it calls `DownloadServiceUtil.build_download_url(...)` and passes `http://127.0.0.1:<port>/...` to `setResolvedUrl`, and does the same for every subtitle in `setSubtitles`.

That indirection exists because Microsoft states pre-authenticated download URLs "are valid for a limited time... they might expire within minutes" and refuses to publish the lifetime. A URL baked into `setResolvedUrl` dies the moment Kodi's HTTP source re-opens the connection — after a long pause, a far seek, or a network blip mid-movie. The loopback redirector makes every re-open resolve a new signed URL.

**Consequence for the roadmap:** either the *play* phase ships a minimal loopback redirect endpoint (recommended — it is ~80 lines and has no relationship to background downloading), or the *play* phase must own an explicit, tested decision to hand Kodi the raw `downloadUrl` and accept mid-playback failures. Do not let this be discovered during the play phase.

**Two separate things share the name "the HTTP server" and must be judged separately:**

| Component | What it is | Verdict |
|---|---|---|
| `DownloadService` (302 redirector) | Loopback endpoint that re-signs a URL per request | **Table stakes infrastructure** — required by playback |
| `SourceService` (`allow_directory_listing`, port 8586) | Loopback HTML *index* of the whole drive, on by default | **Anti-feature** — delete it |

---

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any of these makes the add-on feel broken, not minimal.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Device-code sign-in, zero typing of secrets** | Every TV-class OAuth client (YouTube, Netflix, Plex, the sibling Google Drive add-on) works this way. Typing a Microsoft password on a D-pad is a non-starter | MEDIUM | RFC 8628. Needs `offline_access` scope or no refresh token is issued |
| **QR code beside the code** | Kodi wiki's own Google Drive instructions read "scan and follow the QR code" — the category already set this expectation | MEDIUM | Proven in-family via a `WindowXMLDialog` + `setImage`. See §1 for the pyqrcode/pypng packaging trap |
| **Live polling feedback + working Cancel** | A frozen "waiting" screen with a dead remote is the single worst 10-foot failure | LOW | Poll on a worker; `iscanceled()` on the dialog; Back/Esc must abort cleanly |
| **Explicit "code expired → get a new one"** | 15-minute `expires_in` guarantees users will hit this while hunting for their phone | LOW | Depends on device-code sign-in |
| **Silent token refresh** | Users must not re-authorise every hour. `expires_in` on the access token is 3599s | MEDIUM | Single-flight refresh; concurrent service + plugin processes both need it |
| **Multiple accounts** | Both category incumbents advertise "Unlimited accounts" as a headline bullet; Personal + Work is the normal household case | MEDIUM | Account label must come from `/me` (`displayName` / `userPrincipalName`), never a typed nickname |
| **Drive/account picker at the root** | With >1 account the root listing is the only remote-friendly switch point | LOW | Depends on multiple accounts |
| **Folder browsing with pagination** | Table stakes for any file browser | MEDIUM | `$top` ≤ 999, default 200, `@odata.nextLink` |
| **Video / audio / image playback** | The product | MEDIUM | Depends on the loopback redirector |
| **Seek within a stream** | Non-negotiable for movies. Users will not accept "start over to skip the intro" | LOW (given redirector) | `Range:` on the `downloadUrl` returns `206 Partial Content` — verified in Graph docs |
| **Automatic same-name subtitle pickup** | The category's advertised behaviour; users name their `.srt` after the video and expect it to just work | LOW | Depends on browsing + play |
| **Manual subtitle enable/disable at playback** | Kodi's own OSD gives this free once `setSubtitles` is populated | LOW | Do not reinvent |
| **Thumbnails / poster art in listings** | A grid of identical generic icons is unusable on a TV | MEDIUM | `$expand=thumbnails` is an extra cost — see §5 |
| **Search across a drive** | Cheaper than navigating 8 folder levels with a D-pad | MEDIUM | Graph `search(q=...)`; escape `'` in the OData literal |
| **Actionable, distinct error states** | "Error" on a TV with no keyboard and no log access is a dead end | MEDIUM | See §8 — eight distinct states |
| **Empty-folder state** | An empty list looks identical to a silent failure | LOW | Distinct message per cause |
| **Remove / re-authorise an account** | Sign-in *will* break (password change, revoked consent, MFA policy); recovery must be reachable from the couch | LOW | Depends on multiple accounts |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Actually working sign-in in 2026** | Every incumbent in this category is broken or abandoned (upstream last pushed 2023-01-21; the Heroku broker is dead). Working auth alone is the differentiator | — | This is the Core Value, already in PROJECT.md |
| **No broker, no server, no Azure setup** | rclone-style embedded public `client_id`. Competitors either need a dead third-party broker or per-user app registration | MEDIUM | Depends on device-code sign-in |
| **Custom `client_id` escape hatch** | The only survivable answer when a tenant blocks the shipped app. Nobody else in the category offers this | LOW | Hidden advanced setting; depends on sign-in |
| **STRM library export** | Turns files into a real Kodi library: posters, NFO scraping, watched state, resume, Up Next. This is the difference between "a file browser" and "a media library" | HIGH | Advertised by the Google Drive sibling; **video only** — Kodi does not support `.strm` in the music library |
| **Resume / watched-state sync** | Stop on the TV, resume on the tablet | MEDIUM | Architecturally *downstream of export* — `play()` recovers `dbid`/`dbtype` via `find_exported_video_in_library`, so resume without export only works for the in-session case |
| **Delta-based change sync** | Keeps the exported library fresh without rescanning the whole drive | HIGH | `@odata.deltaLink`; the documented source of the category's CPU/RAM complaints |
| **Server-side sort that survives pagination** | Graph `$orderby` gives correct ordering across pages; Kodi's own sort methods only reorder the page you loaded | LOW | Genuinely better than what incumbents do |
| **Photo slideshow with auto-refresh** | Niche but beloved; a live camera-roll frame | MEDIUM | Depends on browsing images |
| **Pseudo-folders (Recent, Shared with me, Camera Roll)** | Removes deep D-pad navigation for the two most common intents | LOW | Cheap; already implemented |
| **Self-hosted Kodi repo for updates** | One-time URL entry vs. re-navigating a file manager per release | LOW | Distribution, not a runtime feature |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Local HTTP directory-listing server on 8586, default ON** | Lets Kodi (or anything) mount the drive as a "source"; sounds like power-user polish | Binds `127.0.0.1` (verified in `service/base.py`: `_interface = '127.0.0.1'`) but has **no authentication of any kind** — no token, no password anywhere in `base.py`. On **Android every installed app shares loopback**, so any app on the TV box can enumerate and download the entire OneDrive with no credentials. It is an *index*, so it is enumerable — unlike the redirector. It also proxies to other cloud add-ons' ports. And the sibling add-on's own README already marks "Use Drive as a source" as **not currently working**. Dead feature, live attack surface, on by default | **Delete `SourceService` and the `allow_directory_listing` / `port_directory_listing` settings.** Keep only the `302` redirector, and add a per-session random path token to that so item IDs are not the only secret |
| **Proxying media bytes through the local server** | "Then we control the stream, add caching, retries" | Turns a passive redirect into a full HTTP proxy on a 2 GB Android box: Python GIL in the byte path, doubled memory, broken `Range` semantics, and Kodi's own well-tuned curl cache bypassed | Keep the `302`. Let Kodi's HTTP source talk to `*.files.1drv.com` directly and do its own ranged reads |
| **Eagerly draining every `nextLink` page before rendering** | "Show the whole folder so sorting works" | A 5,000-item folder = 25 serialised round trips before the first pixel, then 5,000 texture fetches. This is the reported "slow listing / unresponsive UI" failure mode. It also caps out on recursion depth in the current code | `$top=200`, render each page as it arrives via `addDirectoryItems()` in chunks, and use `$orderby` for correctness instead of buffering |
| **Background delta polling enabled by default** | "Keep the library fresh automatically" | Kodi forum reports against the Google Drive sibling specifically cite CPU/RAM from the change-watching service. It is also the most likely source of Graph `429`s, and throttled requests still count against the quota | Default **off**. Enable only when the user has actually created an export. Serialise, honour `Retry-After`, back off |
| **Built-in error reporting to a third-party endpoint** | Helps the maintainer debug | `remote/errorreport.py` phones home on exception. Stack traces from an OAuth client can carry tenant names, UPNs, drive IDs, file paths. Silent exfiltration in a privacy-sensitive add-on | Log to `kodi.log` only. If telemetry is ever wanted: opt-in, scrubbed, and disclosed |
| **Storing tokens in `settings.xml`** | It is the path of least resistance in Kodi | Plain text, rendered in the Settings UI, and swept up in every log/config dump users post on forums | Store in the add-on `profile` dir with restrictive permissions, outside the settings tree |
| **A second auth flow (loopback browser redirect / PKCE-in-browser)** | "Desktop users would prefer a browser" | Doubles the auth surface — the highest-risk, least-testable part of the project — for a secondary platform. Already ruled Out of Scope in PROJECT.md | Device code on both platforms. Windows users can click `microsoft.com/devicelogin` on the same machine |
| **Manual account nicknames typed on the TV** | "Let me label my accounts" | On-screen keyboard entry per account; the exact interaction the project exists to avoid | Label from `/me` `displayName` + `userPrincipalName`. Renaming is a desktop-only nicety at best |
| **STRM export of music** | Symmetry with video | Kodi's music library does not support `.strm`. The sibling add-on ships it and documents it as not working — it produces files that do nothing | Video export only. Music stays plugin-browsable |
| **Bundling a subtitle *search* service (OpenSubtitles etc.)** | "Complete the subtitle story" | Duplicates a4kSubtitles / OpenSubtitles add-ons, adds a second API credential and a second rate limit | Discover subtitles *stored beside the file* only. Kodi's subtitle add-on ecosystem handles the rest |
| **Custom skin views / custom player controls** | "Make it look nice" | Breaks under every third-party skin, and re-implements what `setContent()` + Kodi's OSD give free | `setContent('videos'|'musicvideos'|'images')` and let the user's skin decide |
| **Offline download-for-later into a managed store** | "Watch on a flight" | Kodi has no library semantics for a plugin-managed offline copy; you inherit a storage manager, an eviction policy, and a sync engine | A plain "Download to…" context action writing to a user-chosen folder (already exists and is enough) |
| **SharePoint document libraries as a first-class target** | "It's in the API anyway" | Multiplies the permission, consent and throttling matrix; already Out of Scope in PROJECT.md | Keep the code path, do not test or support it |

---

## Behaviour Specifications

### §1 — Sign-in UX on a 10-foot interface

**Hard constraint discovered:** Microsoft **does not support `verification_uri_complete`** (stated explicitly in the Entra device-code reference). Google returns it; Microsoft does not. Therefore a QR code **cannot** carry the user code — it can only encode `https://microsoft.com/devicelogin`. The user still has to read a 9-character code off the TV and type it on their phone.

This inverts the usual design instinct. Do not build the screen around the QR. **Build it around the code**, with the QR as the URL shortcut.

**What good looks like:**

| Element | Recommendation | Rationale |
|---|---|---|
| Dialog type | Custom `xbmcgui.WindowXMLDialog` | `Dialog().ok()` and `textviewer()` cannot render images and cannot update while polling. Proven in-family: `pin-dialog.xml` already does exactly this (image control `1001`, textbox `1002`, cancel button `1003`) |
| The code | Dedicated `<control type="label">`, **largest font the skin offers**, letter-spaced, mixed-case avoided | The existing dialog renders instructions and code together in a `font12_title` textbox — too small to read from a sofa. This is the single highest-value UX fix |
| QR | Left panel, ≥340×340 at 1080p, encoding only `verification_uri` | Saves typing a URL, which is the part a phone user would otherwise fat-finger |
| Instructions | Three short lines, not a paragraph. "1. Scan the code or go to microsoft.com/devicelogin  2. Enter **ABCD-EFGH**  3. Sign in" | `message` from Graph is a prose blob; localise your own instead |
| Progress feedback | Countdown of *remaining validity* ("Expires in 12:04"), not a fake percent bar | The only honest signal — the client cannot know how far along the user is |
| Polling cadence | Honour the returned `interval`; never poll faster. Do not busy-wait on the UI thread | MS documents `authorization_pending` → "repeat after at least `interval` seconds" |
| Cancel | Button **and** Back/Esc via `onAction`. Must stop the poll thread and leave **no partial account** | A half-written account is worse than no account on a device with no file manager |
| On success | Close, resolve `/me`, show "Signed in as <displayName>", and land the user directly in that drive's root | Do not dump them back into a settings tree |
| On `expired_token` | Replace the dialog body with "That code expired." and a **focused** "Get a new code" button | With a 15-min window and a phone in another room, this will fire often. The default focus must be the recovery action |
| On `authorization_declined` | Close, plain message, no retry loop | Distinguish from expiry — different user intent |
| Multiple accounts | Before the flow, if any account exists, show "Add another account". After success, if the resolved `userPrincipalName` matches an existing account, offer **Replace / Cancel** rather than silently creating a duplicate | Duplicate accounts are unremovable-feeling on a remote |
| Personal-account warning | One line: "You may be asked to sign in twice." | MS documents that `/common` and `/consumers` re-prompt to transfer auth state, because the device cannot access cookies. Work/school accounts do not. Users read the second prompt as a failure |

**QR packaging trap:** `script.module.pyqrcode` (1.2.1) and `script.module.qrcode` (6.1.0) are both present in the **nexus, omega and piers** repos — verified by HTTP 200 against `mirrors.kodi.tv`. But `script.module.pil` and `script.module.pypng` are **404 in all three**. `script.module.qrcode` renders via PIL; `pyqrcode.png()` needs pypng. The existing code calls `pyqrcode.create(...).png(path, scale=10)`, which means the dependency it needs is not installable from the official repo. **Vendor a pure-Python QR→PNG writer** (pypng is ~1 file, zlib-only) rather than declaring an unresolvable `<import>`.

**Degradation:** if QR generation fails for any reason, still show the dialog with the code and URL. A missing QR is cosmetic; a failed dialog is a blocked sign-in.

### §2 — Multi-account support

**Verdict: table stakes, not a differentiator.** Both surviving competitors lead with "Unlimited accounts" as bullet #1, and the realistic household case is one Personal drive plus one Work drive. Shipping single-account would be a visible regression from v2.3.0.

**How to surface it (remote-first):**

- **The add-on root is the account/drive list.** Not a settings screen. `plugin://plugin.onedrive/` → one row per drive, labelled `<displayName> — <drive type>`, with a trailing "Add an account…" row. This is the entire switcher; no modal, no separate menu.
- **Context menu (long-press / `c` / menu button) per account row:** *Re-authorise*, *Remove account*. Two items, no submenu.
- **Never a text-entry step.** Labels derive from Graph.
- **Per-account state must be isolated:** tokens, delta change tokens, and cache keys all keyed by account, or removing one account corrupts another.
- **A broken account must still render.** Show the row with a warning label ("Sign-in expired — press OK to fix") rather than hiding it or failing the whole root listing. If one account 401s, the other must still browse.

### §3 — Playback

**Recommended architecture (confirmed correct by the incumbent, and by Graph docs):**

```
Kodi player → http://127.0.0.1:<port>/<token>/<driveid>/<itemid>/<name>
                → add-on resolves a FRESH @microsoft.graph.downloadUrl
                → HTTP 302 Location: https://xxx.files.1drv.com/...
                → Kodi's curl follows, issues its own Range: requests
                → *.files.1drv.com returns 206 Partial Content
```

| Question | Answer | Confidence |
|---|---|---|
| Direct URL or proxy? | **Neither — redirect.** A 302 re-signer on loopback. Not a byte proxy | HIGH |
| Why not the direct URL in `setResolvedUrl`? | MS: pre-authenticated URLs "might expire within minutes", lifetime undisclosed and unguaranteed. Kodi re-opens the source on far seeks, long pauses and network recovery, and would reuse the dead URL | HIGH |
| Does seek work? | Yes. Graph documents appending `Range: bytes=a-b` **to the `downloadUrl`, not to `/content`**, returning `206` + `Content-Range`. If the range can't be served it may be ignored and `200` with the full body returned — so the client must tolerate a `200` reply to a ranged request | HIGH |
| Expiring URL mid-playback | Solved by construction: every Kodi re-open hits loopback and gets a new signature. No token-refresh logic in the play path at all | HIGH |
| Bandwidth / quality on Android TV | **There is nothing to choose.** OneDrive is file storage, not a transcoder — one file, one bitrate, no renditions, no ABR, no HLS. All "quality" behaviour is really *decode capability*: hardware decode of the container/codec as-stored | HIGH |
| What actually needs doing for Android TV | Set `mimetype` on the ListItem so Kodi picks the right demuxer; populate `addStreamInfo('video', ...)` from Graph's `video` facet (width/height/bitrate/duration) so the skin and the player make correct decisions before the first byte; pass an **integer** duration | MEDIUM |
| Cache/buffering | Do **not** ship an `advancedsettings.xml` override. A remote 302 to a CDN is exactly the case Kodi's default HTTP cache is tuned for; per-add-on cache meddling is the classic Kodi buffering cargo-cult | MEDIUM |
| `inputstream.adaptive` | **Not applicable.** There is no manifest. Progressive HTTP only | HIGH |

**Also required in the play path:** `setResolvedUrl` only works from the plugin's *play* invocation with a valid handle — do not attempt it from a service or a `-1` handle. And ensure the redirector endpoint is reachable *before* resolving, or the first play after a Kodi restart races the service start.

### §4 — Subtitles

**Expected behaviour (this is the category's advertised feature):** when a video is played, look for subtitle files **in the same folder, with the same base name**, and attach them via `ListItem.setSubtitles([...])` so they appear in Kodi's normal subtitle OSD. No user action. No settings dive.

| Aspect | Recommendation |
|---|---|
| Match rule | `<video-basename>*.<subtitle-ext>` — must accept a language suffix (`Movie.en.srt`, `Movie.forced.srt`), not exact-basename-only |
| Extensions to accept | Kodi supports: **SRT, ASS/SSA, SUB (MicroDVD/SubViewer), IDX+SUB (VOBsub), SMI, MPsub, JACOsub, MicroDVD, OGM, PJS, RT, VPlayer, AQTitle, CC**. `.vtt` is **not** in Kodi's documented list — do not advertise it |
| Real bug to fix | The sibling README documents matching `.str` — a typo for `.srt`. Match the full supported set, case-insensitively |
| VOBsub pairs | `.idx` and `.sub` must both be attached, or the subtitle silently does nothing |
| URL form | Each subtitle URL goes through the **same loopback redirector** as the media, for the same expiry reason |
| Cost control | Subtitle discovery is an extra `/children` call per play. It must be behind the existing setting, must not block the first byte of video, and must fail silently — a subtitle lookup timeout must never abort playback |
| Explicitly not ours | Downloading subtitles from OpenSubtitles. That is a4kSubtitles' job |

### §5 — Browsing

**Sort / filter:**

- Graph `/children` supports `$orderby` (`name`, `size`, `lastModifiedDateTime`) plus `$select`, `$top`, `$skipToken`. Use **server-side** `$orderby` and persist the user's choice per content type.
- **Do not rely on `xbmcplugin.addSortMethod()` while paginating.** Kodi sorts only what it has been handed; with `nextLink` paging that is a sorted *page*, not a sorted folder — silently wrong, and users will report it as data loss. Only register Kodi sort methods when the entire folder is in memory.
- `$orderby` is **not** available on `search()` or `delta`. Say so in the UI (search results are relevance-ordered) rather than offering a sort that does nothing.
- "Filter" on a remote means one thing: **hide non-media files**. Do this server-side and per-content-type. It must **not** leak across calls — the existing class-level `_extra_parameters` mutation does exactly that, hiding folders after any search.
- Folders before files, always. On a D-pad, hunting for a folder in a mixed alphabetical list is the worst case.

**Thumbnails / art:**

- `driveItem` returns **no thumbnail by default**; `$expand=thumbnails` is a real cost per page. Request the *smallest* useful size, not `large`.
- Only expand thumbnails for image and video content types. For audio and folders, use static icons.
- Every remote thumbnail URL becomes a texture download + cache write on the client. On a 2 GB Android box a 1,000-item image folder is the memory event, not the JSON.
- Thumbnail URLs from Graph are themselves short-lived — if a listing is cached longer than the thumbnail URL lives, art silently 404s. Either don't cache listings past thumbnail validity, or route art through the redirector too (extra complexity; probably not worth it for v1).
- Set `setContent()` per content type so the user's skin offers appropriate views and Kodi's own art handling kicks in.

**Very large folders on constrained Android TV hardware:**

| Do | Don't |
|---|---|
| `$top=200` (default) and render **each page as it arrives** | Drain all `nextLink` pages before calling `endOfDirectory` |
| `xbmcplugin.addDirectoryItems()` in chunks — Kodi docs explicitly state large lists benefit over repeated `addDirectoryItem()` | One `addDirectoryItem()` per file in a Python loop |
| Minimal `$select` — id, name, size, file/folder facet, video/audio/image facet, lastModified | Fetch the full driveItem with every facet |
| Offer an explicit trailing "Next page →" item and let the user opt in to more | Recurse to fetch pages (the current code has a recursion-depth ceiling) |
| Check `cancel_operation()` between pages and return `[]` — never `None` — on abort | Return `None` into `items.extend(...)` |
| Keep the `DialogProgressBG` honest: "Loaded 400 of ~?" | A percent bar when total count is unknown |

**Realistic ceiling to design for:** a 10,000-file camera roll. 50 round trips + 10,000 thumbnails is not survivable eagerly, and is fine lazily.

### §6 — Library integration (STRM export)

**Verdict: differentiator, and a strong one — but not table stakes.**

- **Not table stakes** because the browse-and-play path is fully usable without it, and the deferral in PROJECT.md is sound.
- **A real differentiator** because it changes the product category. STRM export is what promotes a cloud folder into the Kodi video library: scraped metadata, posters and fanart, watched flags, resume points, "Recently added", Up Next, and library access from every Kodi client in the house. The incumbent advertises it prominently and it is the most-cited reason people install these add-ons rather than just using a network share.

**Design notes:**
- **Video only.** Kodi's music library does not support `.strm`. The sibling ships music export and documents it as non-functional — do not repeat that.
- Exported `.strm` files must contain the **plugin URL**, not the loopback URL — the loopback port is not stable across restarts and the file must survive re-installs.
- Export creates a hard dependency on delta change sync to stay fresh, which creates the CPU/RAM and Graph-`429` exposure. Ship export with sync **opt-in and off by default**.
- **Resume/watched sync is downstream of export**, not a peer of it: `play()` recovers `dbid`/`dbtype` via `find_exported_video_in_library` on the exported `.strm`. Planning resume as an independent later feature will produce something that only works within a single session.

### §7 — Anti-features (see the table above)

The explicit assessment requested on the port-8586 directory-listing server:

**Delete it. Do not restore it, do not default it off, do not gate it behind a warning.**

Evidence:
1. **It is unauthenticated.** `service/base.py` contains no token, password or authorisation check of any kind. It binds `127.0.0.1` and serves whatever reaches the socket.
2. **Loopback is not a security boundary on Android.** Every app installed on the TV box can reach `127.0.0.1:8586`. On a shared Windows machine, every local process and user session can.
3. **It is an index, so it is enumerable.** The user's entire OneDrive tree — names, structure, and download links — is browsable with no credentials. This is categorically worse than the redirector, whose URLs are keyed on high-entropy Graph item IDs and cannot be listed.
4. **It is on by default** (`allow_directory_listing = true`), so the exposure exists on every install regardless of whether the user wanted the feature.
5. **The feature it enables is already dead.** The sibling add-on's own README marks "Use Drive as a source" as *not currently working due to API changes*. You would be restoring an exploit surface to support a broken feature.
6. **It has no Android TV use case.** Its purpose is mounting the drive as a Kodi *source* — a file-manager workflow, i.e. precisely the interaction the project's own constraints rule out.

**What to keep instead:** the `DownloadService` 302 redirector, hardened with a per-session random path token so that a guessed item ID is not sufficient, and with the port allocated dynamically rather than fixed.

### §8 — Required error and empty states

Every one of these must be a distinct, readable, *actionable* on-screen message. On a TV there is no log, no console, and no keyboard.

| State | Trigger | What the user sees | Recovery offered | Complexity |
|---|---|---|---|---|
| **No network** | Socket/DNS failure before any HTTP | "Can't reach OneDrive. Check this device's internet connection." | Retry | LOW |
| **Graph reachable, service degraded** | `5xx` (non-503) or repeated timeouts | "OneDrive isn't responding right now." | Retry | LOW |
| **Token refresh rejected** | `invalid_grant` on refresh (password change, consent revoked, session revoked, MFA policy change) | "Sign-in for **<account>** expired. Sign in again to continue." | **Launch device-code flow inline** — do not send them to settings | MEDIUM |
| **Access token expired (normal)** | `401` on a Graph call | *Nothing.* Silent refresh and retry once | — | MEDIUM |
| **Tenant blocked the app** | `AADSTS7000218`, or Conditional Access rejecting the *authentication flow* (Microsoft's own guidance recommends blocking device code flow, so this is realistic) | "Your organisation has blocked this sign-in method or this app. A work admin must approve it, or you can enter your own Application ID in Advanced settings." | Point at the custom `client_id` setting; link the docs page | MEDIUM |
| **Admin consent required** | `AADSTS65001` — user or admin hasn't consented, or tenant-level user consent is disabled | "Your work account needs an administrator to approve OneDrive access for this app." + the exact app name/ID to hand the admin | Show the client ID so it can be forwarded verbatim | MEDIUM |
| **Device code expired** | `expired_token` after 15 min | "That code expired." | **Focused** "Get a new code" | LOW |
| **User declined** | `authorization_declined` | "Sign-in was cancelled." | Close, no retry loop | LOW |
| **Rate limited by Graph** | `429` (or `503`) with `Retry-After` | Foreground: "OneDrive is busy — retrying in Ns." Background: silent, no dialog | Honour `Retry-After` exactly (throttled requests still count against quota); exponential backoff if the header is absent | MEDIUM |
| **Item gone** | `404` on play or on a `delta` link | Play: "This file is no longer in OneDrive." Delta: silently reset the change token and re-baseline | — | LOW |
| **Drive enumeration partially blocked** | `403` on `/drives` (SharePoint-restricted tenant) | Show whatever drives *did* resolve; never fail the whole root | — | LOW (already handled) |
| **Empty folder** | `value: []` | "This folder is empty." | — | LOW |
| **Empty after media filter** | Folder has files, none playable for this content type | "No videos here." (content-type-specific) + "Show all files" | Distinguishing this from a true empty folder prevents "the add-on lost my files" reports | LOW |
| **No search results** | `search(q=...)` empty | "No results for '<query>'." | Search again | LOW |
| **No accounts yet** | Fresh install | The root list *is* the empty state: a single "Add an account…" row | — | LOW |

**Cross-cutting rules:** never surface a raw stack trace or an `AADSTS` code as the whole message (include the code as a secondary line for forum posts). Never use a modal that steals focus during background service work. Every error message must fit on one TV screen at skin default font size.

---

## Feature Dependencies

```
Device-code sign-in (+ offline_access)
    ├──requires──> Embedded public client_id
    ├──requires──> Custom WindowXMLDialog  ──requires──> vendored QR→PNG writer
    ├──requires──> Secure token storage (profile dir, not settings.xml)
    │                   └──requires──> Silent refresh (single-flight)
    └──enables───> Multiple accounts
                        ├──enables──> Account/drive root listing (the switcher)
                        └──enables──> Remove / re-authorise account

Multiple accounts ──requires──> Per-account isolation of tokens + delta tokens + cache keys

Folder browsing ──requires──> Silent refresh
    ├──requires──> Chunked addDirectoryItems + page-at-a-time rendering
    ├──enables───> Search
    ├──enables───> Thumbnails/art  ──conflicts──> long-lived listing cache
    │                                              (thumbnail URLs expire first)
    └──enables───> Server-side $orderby sort
                        └──conflicts──> xbmcplugin.addSortMethod under pagination

Playback ──REQUIRES──> Loopback 302 redirector   <-- NOT deferrable
    ├──requires──> Folder browsing (to reach an item)
    ├──enables───> Seek (Range → 206 on the CDN URL)
    └──enables───> Subtitle attachment (same redirector, same expiry reason)

Subtitle auto-discovery ──requires──> Folder browsing (sibling listing) + Playback

STRM export ──requires──> Folder browsing
    ├──requires──> Stable plugin:// URLs in the .strm payload
    ├──enables───> Resume / watched-state sync   <-- downstream, not a peer
    └──pulls-in──> Delta change sync ──requires──> 429 backoff discipline
                                     ──risks────> the category's CPU/RAM complaints

Slideshow ──requires──> Folder browsing (images) [+ delta sync for auto-refresh]

SourceService directory listing (8586) ──conflicts──> every security goal in PROJECT.md
```

### Dependency Notes

- **Playback requires the loopback redirector.** The single most important ordering fact in this document. See the Headline Finding.
- **Subtitles require the redirector too**, for the same URL-expiry reason — so subtitles cannot precede it either.
- **Multiple accounts requires per-account isolation before it requires a switcher UI.** If tokens, delta tokens and cache keys are not namespaced from day one, adding a second account later corrupts the first.
- **Resume/watched sync is downstream of STRM export**, because the library lookup that recovers `dbid`/`dbtype` keys off the exported `.strm`. Scheduling resume as an independent phase yields something that only works in-session.
- **Delta sync is pulled in by export, not chosen independently.** Its cost (CPU, RAM, `429`s) is therefore export's cost. Budget it there.
- **Server-side `$orderby` conflicts with `addSortMethod` under pagination.** Pick one per screen; mixing them produces silently wrong ordering.
- **Thumbnails conflict with a long listing cache**, because thumbnail URLs expire before a listing cache would. Cache TTL must be ≤ thumbnail URL validity, or art breaks on cache hits.
- **`offline_access` gates everything.** Without it Graph issues no refresh token and the add-on re-prompts hourly, which on a TV reads as total failure.
- **QR generation depends on a vendored PNG writer**, because neither `script.module.pil` nor `script.module.pypng` exists in the nexus/omega/piers repos.

---

## MVP Definition

### Launch With (v1) — "sign in from the couch and play a file"

- [ ] **Device-code sign-in dialog** (custom `WindowXMLDialog`, big code, QR, countdown, working Cancel) — the Core Value; nothing else is verifiable without it
- [ ] **Embedded public `client_id` + `offline_access`** — zero-config is the differentiator
- [ ] **Secure token storage + single-flight silent refresh** — without it, sign-in is a demo not a product
- [ ] **Multiple accounts with per-account isolation** — retrofitting isolation later is a rewrite
- [ ] **Account/drive root listing as the switcher** — the only remote-friendly switch point
- [ ] **Folder browsing, page-at-a-time, chunked `addDirectoryItems`** — the browse path
- [ ] **Loopback 302 redirector** — required by play; ~80 lines; do not defer
- [ ] **Video / audio / image playback with seek** — the product
- [ ] **Same-name subtitle auto-discovery** (full extension set, VOBsub pairs) — advertised category behaviour, cheap given browse+play
- [ ] **Thumbnails for image and video listings** — a TV grid without art is unusable
- [ ] **The full error/empty state set from §8** — on a TV, an unexplained failure is unrecoverable
- [ ] **Custom `client_id` advanced setting** — the only survivable answer to a blocking tenant
- [ ] **Delete `SourceService` / `allow_directory_listing` / `port_directory_listing`** — removing an unauthenticated index is v1 work, not cleanup

### Add After Validation (v1.x)

- [ ] **Search** — trigger: users report D-pad navigation fatigue in deep trees. Cheap once browse is stable
- [ ] **Server-side `$orderby` sort** — trigger: any folder large enough that default ordering is wrong
- [ ] **Pseudo-folders (Recent, Shared with me, Camera Roll)** — trigger: browse is stable; these are near-free
- [ ] **"Download to…" context action** — trigger: first user request; do not build a download *manager*
- [ ] **STRM export (video only)** — trigger: browse+play verified on both platforms. The category's biggest differentiator, and the biggest chunk of work
- [ ] **Delta change sync, opt-in, default off** — trigger: export exists and someone has an export defined
- [ ] **Resume / watched-state sync** — trigger: export exists (hard dependency)
- [ ] **Slideshow** — trigger: image browsing verified

### Future Consideration (v2+)

- [ ] **Slideshow auto-refresh** — defer: needs delta sync running continuously, the exact thing that generates the category's CPU/RAM complaints
- [ ] **Redirector path-token hardening + dynamic port** — defer only if v1 keeps the fixed port; otherwise fold into v1
- [ ] **SharePoint document libraries as a supported target** — defer: already Out of Scope; multiplies the consent and throttling matrix
- [ ] **Additional localisations** — defer: already Out of Scope
- [ ] **Opt-in, scrubbed telemetry** — defer: only if maintenance load actually demands it, and never silently

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Device-code sign-in dialog (code-first, QR secondary) | HIGH | MEDIUM | P1 |
| Embedded public `client_id` + `offline_access` | HIGH | LOW | P1 |
| Secure token storage + single-flight refresh | HIGH | MEDIUM | P1 |
| Loopback 302 redirector | HIGH | LOW | P1 |
| Video/audio/image playback with seek | HIGH | MEDIUM | P1 |
| Folder browsing, paged + chunked | HIGH | MEDIUM | P1 |
| Multiple accounts + per-account isolation | HIGH | MEDIUM | P1 |
| Account/drive root listing (switcher) | HIGH | LOW | P1 |
| Error / empty state set (§8) | HIGH | MEDIUM | P1 |
| Delete `SourceService` (8586) | HIGH (security) | LOW | P1 |
| Custom `client_id` escape hatch | MEDIUM | LOW | P1 |
| Same-name subtitle auto-discovery | HIGH | LOW | P1 |
| Thumbnails for image/video listings | MEDIUM | MEDIUM | P1 |
| "Code expired → get a new code" recovery | MEDIUM | LOW | P1 |
| Remove / re-authorise account | MEDIUM | LOW | P2 |
| Search across a drive | MEDIUM | MEDIUM | P2 |
| Server-side `$orderby` sort | MEDIUM | LOW | P2 |
| Pseudo-folders (Recent / Shared / Camera Roll) | MEDIUM | LOW | P2 |
| STRM export (video only) | HIGH | HIGH | P2 |
| Resume / watched-state sync | MEDIUM | MEDIUM | P2 |
| Delta change sync (opt-in, default off) | MEDIUM | HIGH | P2 |
| "Download to…" context action | LOW | LOW | P2 |
| Slideshow | LOW | MEDIUM | P3 |
| Slideshow auto-refresh | LOW | MEDIUM | P3 |
| Redirector path-token + dynamic port | MEDIUM (security) | LOW | P2 |
| Music STRM export | NONE (non-functional in Kodi) | MEDIUM | **Never** |
| Local directory-listing HTTP server | NEGATIVE | LOW | **Never** |
| Byte-proxy playback | NEGATIVE | HIGH | **Never** |
| Bundled subtitle search service | LOW | HIGH | **Never** |
| Second (browser-redirect) auth flow | LOW | HIGH | **Never** |
| Third-party error reporting | NEGATIVE | LOW | **Never** |

---

## Competitor Feature Analysis

| Feature | plugin.googledrive (cguZZman) | plugin.onedrive v2.3.0 (this, pre-refactor) | Our Approach |
|---------|-------------------------------|---------------------------------------------|--------------|
| Sign-in | QR + code via third-party broker; "unlimited accounts" | Same broker (`drive-login.herokuapp.com`, **dead**) | Native RFC 8628 device code against Microsoft directly. No broker, no server, tokens never leave the device |
| QR code | `pyqrcode` → PNG → `WindowXMLDialog` image control | Same (inherited) | Same mechanism, but **vendor** the PNG writer (pypng/PIL are not in the Kodi repo) and make the *code* the visual focus, not the QR |
| Multi-account | Headline feature: "Unlimited accounts" | Inherited from common module | Table stakes. Root listing is the switcher; labels from `/me`; per-account isolation from day one |
| Playback | Loopback 302 redirector → provider's signed CDN URL | Same (inherited) | Keep the redirector. Add a per-session path token and a dynamic port |
| Seek | Delegated to the provider CDN | Same | Same — Graph `downloadUrl` supports `Range` → `206`, verified |
| Subtitles | Auto-assign when a same-name file exists (README says `.str`) | Same | Full Kodi extension set, language suffixes, VOBsub `.idx`+`.sub` pairs, non-blocking, fail-silent |
| Library export | `.strm` for video; music export documented as **not working** | Same | Video only. Never ship music export |
| Change sync | Background service; forum reports cite CPU/RAM cost | Delta via `@odata.deltaLink` | Opt-in, default off, gated on an export existing, `Retry-After`-disciplined |
| Drive as a source | Documented as **not currently working** | `allow_directory_listing` on by default, port 8586, **unauthenticated** | **Removed entirely** |
| Slideshow | Yes, with auto-refresh | Yes | Restore late, auto-refresh later still |
| Error reporting | `errorreport.py` phones home | Same, behind `report_error` | Local logging only |
| Maintenance | Upstream last pushed **2023-01-21** | Broken sign-in since Heroku free dynos ended Nov 2022 | Self-contained: vendored common module, no external broker, self-hosted Kodi repo for updates |

---

## Confidence Notes

| Claim | Confidence | Basis |
|---|---|---|
| `verification_uri_complete` unsupported by Microsoft; `expires_in` = 15 min; polling error set | **HIGH** | learn.microsoft.com `v2-oauth2-device-code`, states it explicitly |
| `downloadUrl` expires "within minutes", undisclosed lifetime; `Range` → `206` supported on the CDN URL only | **HIGH** | learn.microsoft.com `driveitem-get-content` |
| Existing add-on plays via a loopback **302 redirector**, not a proxy or a direct URL | **HIGH** | Direct source read of `service/download.py` and `ui/addon.py::play()` |
| Directory-listing server is loopback-bound but **unauthenticated** | **MEDIUM-HIGH** | Direct source read of `service/base.py` (`_interface = '127.0.0.1'`, no auth token present). Not runtime-verified |
| `script.module.pil` / `script.module.pypng` absent from nexus/omega/piers; `pyqrcode`/`qrcode` present | **HIGH** | HTTP status probes against `mirrors.kodi.tv` |
| Graph `/children`: 200 default, `$top` ≤ 999, `$orderby` supported | **MEDIUM-HIGH** | Graph `driveitem-list-children` reference |
| `429` + `Retry-After` is authoritative; throttled requests still count | **MEDIUM** | Graph throttling guidance |
| Multi-account is a category headline feature | **MEDIUM** | Sibling README + Kodi wiki; only two live competitors, so a thin sample |
| Background sync is the observed CPU/RAM complaint | **MEDIUM** | Kodi forum thread reports, second-hand |
| Kodi external subtitle format list | **MEDIUM** | Kodi wiki "Features and supported formats" |

**Gaps not resolved:**
- Real-world `downloadUrl` lifetime for Personal vs Business drives (Microsoft refuses to state it; community reports range from minutes to ~1 hour). Worth a one-off empirical measurement during the play phase, since it determines how bad the direct-URL fallback would be.
- Whether Kodi's HTTP source re-issues the *original* plugin URL or the *resolved* URL after a mid-playback reconnect. The redirector makes this moot, which is another argument for keeping it.
- Whether any Entra Conditional Access "authentication flows" policy is common enough in small Business tenants to matter in practice.

---

## Sources

- Microsoft Learn — [OAuth 2.0 device authorization grant](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code) (HIGH)
- Microsoft Learn — [Download driveItem content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0) (HIGH)
- Microsoft Learn — [List the contents of a folder](https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0) (MEDIUM-HIGH)
- Microsoft Learn — [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) and [service-specific limits](https://learn.microsoft.com/en-us/graph/throttling-limits) (MEDIUM)
- Microsoft Learn — [AADSTS7000218 troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/entra/entra-id/app-integration/confidential-client-application-authentication-error-aadsts7000218), [consent issues](https://learn.microsoft.com/en-us/troubleshoot/entra/entra-id/app-integration/troubleshoot-consent-issues), [Conditional Access authentication flows](https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-authentication-flows) (MEDIUM)
- Direct source inspection — [`cguZZman/script.module.clouddrive.common`](https://github.com/cguZZman/script.module.clouddrive.common) branch `matrix`: `service/download.py`, `service/source.py`, `service/base.py`, `ui/addon.py`, `ui/dialog.py`, `remote/signin.py`, `resources/skins/default/1080i/pin-dialog.xml` (HIGH for behaviour, MEDIUM for security posture)
- [`cguZZman/plugin.googledrive` README](https://github.com/cguZZman/plugin.googledrive) — advertised feature set of the closest living competitor (MEDIUM)
- Kodi wiki — [Add-on:Google Drive](https://kodi.wiki/view/Add-on:Google_Drive), [Add-on:Cloud Drive Common Module](https://kodi.wiki/view/Add-on:Cloud_Drive_Common_Module), [Features and supported formats](https://kodi.wiki/view/Features_and_supported_formats), [Subtitles](https://kodi.wiki/view/Subtitles) (MEDIUM)
- Kodi Python API — [`xbmcplugin`](https://xbmc.github.io/docs.kodi.tv/master/kodi-base/d1/d32/group__python__xbmcplugin.html) (`addDirectoryItems` batching guidance), [`xbmcgui.Window`](https://alwinesch.github.io/group__python__xbmcgui__window.html) (MEDIUM)
- Kodi repo availability probes — `mirrors.kodi.tv/addons/{nexus,omega,piers}/script.module.{pyqrcode,qrcode,pypng,pil}/` (HIGH)
- [Kodi forum: Google Drive for KODI](https://forum.kodi.tv/showthread.php?tid=324784) — user reports of background-service CPU/RAM cost and playback stalls (LOW-MEDIUM, anecdotal)
- [RFC 8628 device flow explainers](https://curity.io/resources/learn/oauth-device-flow/) and [Google's limited-input device guidance](https://developers.google.com/identity/protocols/oauth2/limited-input-device) — QR-on-TV conventions (MEDIUM)
- OneDrive API docs issue — [downloadUrl validity](https://github.com/OneDrive/onedrive-api-docs/issues/884) (LOW-MEDIUM, community)

---
*Feature research for: Kodi cloud-storage media add-on (OneDrive), Android-TV-first*
*Researched: 2026-08-22*
