# Kodi on Modern Android: Playback Path, Writes, and Escape Hatches

**Scope:** Android 11 through 16 (and what is already visible of 17), Kodi 20 Nexus / 21 Omega / 22 Piers, `org.xbmc.kodi`.
**Purpose:** answer three questions the existing research leaves open — whether playback needs a filesystem path, whether Android can block the add-on's writes, and what to do if either is blocked.
**Relationship to existing documents:** `PITFALLS.md` Pitfalls 18 and 19 already cover the Android storage path, SQLite WAL, TLS trust and service lifecycle. Nothing here restates them. Two of their conclusions are narrowed below; one conclusion in `ARCHITECTURE.md`/`SUMMARY.md` is corrected outright.

---

## Verdict

**Q1 — Can Kodi on modern Android play a OneDrive item, and does anything need a filesystem path?**

Yes, and no. Playback is an HTTP URL handed to Kodi's own libcurl reader; **no filesystem path is involved anywhere in the media byte path.** Android's scoped-storage rules are therefore irrelevant to playback — they govern file access, and the add-on never gives Kodi a file. The loopback redirector binds a normal unprivileged TCP socket on `127.0.0.1`, which needs no Android permission on any version in scope, and the cleartext-HTTP restriction does not reach Kodi's bundled libcurl or Kodi's bundled CPython because both are native stacks that never consult the platform's network-security policy.
*Confidence: HIGH. Settled by documentation and source, except one item — see the correction immediately below.*

**The one thing that is not settled, and it is the important one:** Kodi replaces the URL it holds with the *effective* URL after following a redirect (`CCurlFile::Open`, `m_url = efurl`, present identically on Nexus, Omega and master/Piers). Every subsequent **seek** re-issues the request against the latched `*.files.1drv.com` URL, not against loopback. The redirector therefore does **not** "solve URL expiry by construction" the way `SUMMARY.md` Reconciled Conflicts #4 asserts. It covers the initial open and a reconnect-after-drop; it does not cover seeking. Detail and consequences in Q1.4.
*Confidence: HIGH that the source says this. MEDIUM that the end-to-end consequence is what it appears to be — needs the device test in §7.2, which is a five-minute check.*

**Q2 — What does the add-on write, where does it land, and can Android block it?**

Every write the add-on performs lands inside Kodi's own app-specific external directory, `/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/`. **Android cannot block an app from writing into its own app-specific directory, and never could.** Scoped storage (Android 10), the Android 11 hardening, and the Android 13/14/15 tightening all restrict *other* apps and file-manager/SAF access to that directory. The owning app has needed no permission since API 19. Neither `WRITE_EXTERNAL_STORAGE` nor `MANAGE_EXTERNAL_STORAGE` is required for anything this add-on does.
*Confidence: HIGH. Settled by Android documentation, quoted in Q2.2.*

The one real casualty is `chmod`. On Android ≤ 10 and on any path still served by the storage FUSE daemon, file mode is forced to `0664` at creation and `chmod` is a documented no-op that returns success. On Android 11+ the app's own `Android/data` directory bypasses FUSE, so mode bits are real there. The design must not depend on `0600` applying.
*Confidence: HIGH on the mechanism (AOSP source quoted in Q2.4). MEDIUM on which of the two regimes any given box is in — one line of Python on the device settles it.*

**Q3 — Escape hatches.**

None of the identified failure modes is a dead end. Ranked fallbacks in §6. The two that need a decision rather than a code guard are: what to do if the measured `downloadUrl` lifetime is short enough that PLAY-06 cannot pass (§6.3), and the VOBsub URL-shape constraint that PLAY-09 as currently written cannot satisfy (§6.4).

---

## 1. Q1 — The playback path

### 1.1 The chain, hop by hop, and where each hop runs

```
LIST TIME  (plugin invocation, Kodi Python interpreter, in-process)
  provider builds  plugin://plugin.onedrive.kn/?action=_play&driveid=D&item_id=I
  ListItem.setProperty('IsPlayable','true')
  addDirectoryItems(handle, ...)                    ── no OneDrive URL anywhere

PLAY TIME  (a NEW plugin invocation with a NEW handle)
  resolve nothing remote yet; build the loopback URL
  http://127.0.0.1:<ephemeral>/<session-token>/<driveid>/<item_driveid>/<item_id>/<name>
  xbmcplugin.setResolvedUrl(handle, True, ListItem(path=that_url))   ── exactly once

FIRST BYTE  (Kodi C++, CCurlFile → libcurl, native code)
  GET http://127.0.0.1:<port>/...        → add-on's http.server thread (Kodi Python, in-process)
                                          → Graph GET /drives/D/items/I?select=…downloadUrl
                                          → 307 Location: https://xxx.files.1drv.com/…
  libcurl follows (CURLOPT_FOLLOWLOCATION, MAXREDIRS 5)
  *.files.1drv.com serves 200/206, Kodi issues its own Range: requests
  bytes → CFileCache (64 MB memory buffer by default) → demuxer → MediaCodec
```

Everything in the first two blocks is Python inside the Kodi process. Everything from "FIRST BYTE" is Kodi's C++ and its statically linked libcurl. The redirector's Python code runs **once per HTTP connection open** — it is in the *resolution* path, not the byte path. Not one media byte passes through Python. `[VERIFIED: clouddrive/common/service/download.py, service/base.py; xbmc/filesystem/CurlFile.cpp]`

Two details worth correcting in passing:

- The upstream redirector answers with **`307`, not `302`** (`download.py:43`, `code = 307`). Functionally equivalent here — curl follows both and preserves `CURLOPT_RANGE` across either — but the project documents repeatedly say "302 redirector". Pick one word and use it in the spec so a reviewer reading the code does not think it is wrong.
- The upstream `BaseServerService.get_port()` binds `127.0.0.1:0` and reads back the kernel-assigned port, so `DownloadService` is **already** on an ephemeral port. The fixed `8586` belongs only to `SourceService`, which overrides `get_port()`. PLAY-03's "dynamically allocated port" is therefore not new work; it is the inherited behaviour. `[VERIFIED: service/base.py:41-46; service/source.py get_port override]`

### 1.2 Does anything require a filesystem path? No.

State it plainly, because it collapses most of the fear:

`xbmcplugin.setResolvedUrl()` takes a `ListItem` whose `path` may be **any string Kodi's VFS understands**. For `http://` and `https://` that is `CCurlFile`, a libcurl wrapper. Kodi opens it, wraps it in `CFileCache`, and feeds the bytes to `CDVDDemuxFFmpeg`, which feeds decoded packets to `CDVDVideoCodecAndroidMediaCodec`. MediaCodec is fed **buffers**, never a file descriptor and never a path. There is no point in the chain at which Android's storage layer, the Storage Access Framework, a `content://` URI, or a `File` object appears.

Consequences:

- Scoped storage, `MANAGE_EXTERNAL_STORAGE`, the Android 11 `Android/data` lockdown and the Android 13/14/15 tightening are all **irrelevant to playback**. They govern file access. Playback performs no file access.
- The add-on needs no storage permission for playback. Kodi's manifest happens to declare `WRITE_EXTERNAL_STORAGE` and `MANAGE_EXTERNAL_STORAGE` — those exist so Kodi can browse the user's own media libraries, and are unrelated to this add-on. `[VERIFIED: tools/android/packaging/xbmc/AndroidManifest.xml.in]`
- The only disk activity Kodi performs during playback by default is none: `filecache.memorysize` defaults to **64 MB** of RAM. Only if a user sets it to `0` does Kodi switch to `CSimpleFileCache`, which writes `special://temp/filecacheNNN.cache`. That is Kodi's write in Kodi's own directory, not the add-on's, and it is still inside app-specific external storage. `[VERIFIED: system/settings/settings.xml filecache.memorysize default 64; xbmc/filesystem/FileCache.cpp:118-145; CacheStrategy.cpp:72]`

There are exactly two places where a real path could sneak into an otherwise pure-HTTP design: **subtitles** (§1.6) and the **QR image** (§2.1, item 3). Both are handled below; neither is in the media byte path.

### 1.3 Loopback listening socket on Android 11 → 16

No Android version in scope restricts an app from binding a listening TCP socket on `127.0.0.1`.

- **Permission:** creating an `AF_INET` socket requires `android.permission.INTERNET`, which grants the process membership of the `inet` group. Kodi declares it. There is no separate "server socket" or "bind" permission on any Android version. `[VERIFIED: Kodi AndroidManifest.xml.in line 9]`
- **Port range:** binding ports ≥ 1024 is unprivileged, as on any Linux. Ports < 1024 require root. The redirector uses port `0` (kernel-assigned ephemeral, always ≥ 32768 on Linux), so this never arises. `[ASSUMED — standard POSIX/Linux semantics; Android is Linux]`
- **Android 16/17 Local Network Protections do not apply.** The new gate covers *local network* addresses — LAN peers, mDNS, SSDP — and exists to stop cross-device fingerprinting. Loopback is a separate class precisely because the traffic never leaves the device. On Android 16 the restriction is opt-in per app via `adb shell am compat enable RESTRICT_LOCAL_NETWORK <pkg>`; it becomes mandatory only for apps targeting Android 17 (API 37), gated on `ACCESS_LOCAL_NETWORK`. **Kodi master already declares `android.permission.ACCESS_LOCAL_NETWORK`**, so even in the enforced case Kodi has the declaration in place. `[CITED: developer.android.com/privacy-and-security/local-network-permission]` `[VERIFIED: Kodi AndroidManifest.xml.in line 14]`
  *The loopback exemption itself is corroborated rather than quoted from Android's own page — MEDIUM confidence. It is cheap to confirm on the box (§7.1) and the failure mode would be loud, not silent: `bind()` would raise.*
- **Doze / App Standby / background execution limits do not apply during playback.** Those defer network activity for apps the user is not using. Kodi is the foreground activity with the screen on and a wake lock held whenever video is playing. The redirector's socket lives in the same process as the player; if Android were freezing it, the player would be frozen too. `[ASSUMED — Android background-execution model; the scenario is self-contradicting]`
- **What *can* happen:** Android may kill the whole Kodi process when it is backgrounded for a long time. That is not a socket problem — it takes Kodi, the player, the redirector and the service down together. §6.5 covers what must be resumable.

Corroborating evidence that this all works in practice: Kodi's own built-in web server binds `0.0.0.0:8080` on Android and is widely used; and this exact 78-line redirector has shipped in `plugin.googledrive` / `plugin.onedrive` / `plugin.dropbox` on Android for years. Absence of "playback does not start on Android" as a dominant upstream complaint is weak but real evidence.

### 1.4 Cleartext HTTP to `127.0.0.1` — resolved, with a caveat elsewhere

**Question:** Android 9+ defaults `usesCleartextTraffic` to `false` for `targetSdk ≥ 28`. Kodi's manifest sets no `android:usesCleartextTraffic` attribute and ships no network-security-config XML. Does that block `http://127.0.0.1:PORT/...`?

**Answer: no.** Android's own documentation for `android:usesCleartextTraffic` says it outright:

> "This flag is honored on a best-effort basis because it's impossible to prevent all cleartext traffic from Android applications given the level of access provided to them. For example, there's no expectation that the `Socket` API honors this flag, because it can't determine whether its traffic is in cleartext."
>
> "When the attribute is set to `"false"`, platform components, for example, HTTP and FTP stacks, `DownloadManager`, and `MediaPlayer`, refuse the app's requests to use cleartext traffic. Third-party libraries are strongly encouraged to honor this setting as well… most network traffic from applications is handled by higher-level network stacks and components, which can honor this flag by either reading it from `ApplicationInfo.flags` or `NetworkSecurityPolicy.isCleartextTrafficPermitted()`."
>
> `[CITED: developer.android.com/guide/topics/manifest/application-element]`

The policy is **advisory and opt-in for the code that performs the I/O**. It is enforced by the platform's Java networking stack, Conscrypt, WebView, `DownloadManager` and `MediaPlayer`. Kodi's media path is none of those: it is a statically linked libcurl calling `connect()` on a raw socket, and it never queries `NetworkSecurityPolicy`. The same is true of the redirector itself, which is Python `socketserver` on raw sockets inside the same process. **Neither side of the loopback connection is subject to the policy.**

Two supporting facts. First, Android is adding an *explicit* localhost carve-out anyway: from **Android 17 (API 37)**, if no configuration is defined for localhost, an implicit configuration is applied that "allows cleartext traffic", where localhost means `localhost`, `ip6-localhost`, or a numeric address for which `InetAddress.isLoopback()` is true. `[CITED: developer.android.com/privacy-and-security/security-config]` Second, Kodi on Android routinely plays plain `http://` IPTV, PVR and UPnP streams — traffic that a policy-enforcing stack would have refused years ago.

**The caveat, and it belongs in the record:** the same "native stack, not the platform stack" property means Android's **system CA store is not used either**. Kodi sets `SSL_CERT_FILE` to `special://xbmc/system/certs/cacert.pem` on Android — a CA bundle shipped inside the APK and updated only when Kodi itself updates. Python's `ssl` module honours the same environment variable, so the add-on's Graph and token calls use Kodi's bundle too. `[VERIFIED: xbmc/platform/android/PlatformAndroid.cpp:37]` This is the mechanism behind `PITFALLS.md` Pitfall 19's TLS-trust row; it is now named precisely. A box with a wrong clock, or an old Kodi build carrying an old bundle, fails TLS to `login.microsoftonline.com` — and installing a certificate in Android's system store will not fix it.

### 1.5 The effective-URL latch — a correction to `ARCHITECTURE.md` and `SUMMARY.md`

This is the substantive finding of this document.

`CCurlFile::Open()` finishes with:

```cpp
std::string efurl = GetInfoString(CURLINFO_EFFECTIVE_URL);
if (!efurl.empty())
{
  if (m_url != efurl)
    CLog::Log(LOGDEBUG, "CCurlFile::{} - <{}> Effective URL is {}", …);
  m_url = efurl;
}
```

`[VERIFIED: xbmc/filesystem/CurlFile.cpp — master line 1238, Omega line 1174, Nexus line 1166. Identical on all three target versions.]`

`CCurlFile::Seek()` then does `SetCommonOptions(m_state)` before reconnecting, and `SetCommonOptions` ends with `easy_setopt(handle, CURLOPT_URL, m_url.c_str())`. `[VERIFIED: CurlFile.cpp master lines 1528 and 582]` Under `m_multisession` (true for http/https) it first acquires a fresh easy handle keyed on `CURL(m_url).GetHostName()` — the CDN host.

So the behaviour is:

| Event | URL actually requested | Redirector involved? |
|---|---|---|
| Initial open | loopback | **yes** — fresh signed URL |
| Connection drops, no seek yet (pause, Wi-Fi blip) | loopback | **yes** — the easy handle is re-added to the multi handle without re-setting `CURLOPT_URL`, and curl resets `state.url` from `STRING_SET_URL` on every `Curl_pretransfer` `[VERIFIED: curl lib/transfer.c Curl_pretransfer]` |
| **Any seek** | latched `*.files.1drv.com` URL | **no** |
| Any reconnect after the first seek | latched CDN URL | **no** |

**Therefore `SUMMARY.md` "Reconciled Conflicts #4" is wrong where it says:** *"the DownloadService redirector already solves expiry by construction — every Kodi re-open, on any seek, pause or network blip, hits loopback and gets a newly signed URL."* Pause and blip: yes. **Seek: no.** `ARCHITECTURE.md` §Q7 "The seek-after-expiry problem" was closer to the truth than the reconciliation that superseded it; its hypothesis about *why* upstream built a local server was wrong, but its worry was right.

**What the redirector still buys, and it is enough to keep it:**

1. No expiring URL is ever written into a directory item URL, a library row, a watched-state row, or an exported `.strm`. This alone justifies it and is unaffected by the latch.
2. Freshness at the moment of first byte, not at the moment of resolution — which matters for queued playlists and slow boxes.
3. Recovery from a dropped connection before the first seek — the long-pause-then-*resume* case.
4. A single place to enforce the per-session path token (PLAY-03) and to serve subtitles uniformly.

**What it does not buy:** survival of a seek issued after the `downloadUrl` has expired. That is precisely PLAY-06.

**Consequence for the roadmap.** PLAY-07 ("measure the real download-URL lifetime") is currently framed in `SUMMARY.md` as *"a confirmation test, not a decision gate"*. It is a decision gate again. If the measured lifetime comfortably exceeds a realistic pause (community reports cluster around an hour; Microsoft documents only "might expire within minutes"), PLAY-06 passes and nothing changes. If it is short, PLAY-06 cannot pass with a pure redirector and one of the fallbacks in §6.3 must be chosen. **PLAY-07 should be scheduled first inside Phase 6, before PLAY-02/PLAY-03 are considered complete** — it is a script, not a feature, and it can run before any playback code exists.

### 1.6 Subtitles through the redirector — an unrecorded constraint on the URL shape

`ListItem.setSubtitles([...])` becomes `subtitle:N` item properties, which `CVideoPlayer::OpenInputStream` reads back into a list and dispatches **by file extension**:

```cpp
if (URIUtils::HasExtension(filenames[i], ".idx"))
{
  if (CUtil::FindVobSubPair(filenames, filenames[i], strSubFile))
    AddSubtitleFile(filenames[i], strSubFile);
}
else if (!CUtil::IsVobSub(filenames, filenames[i]))
  AddSubtitleFile(filenames[i]);
```
`[VERIFIED: xbmc/cores/VideoPlayer/VideoPlayer.cpp:945-960]`

Two hard constraints fall out, neither currently recorded anywhere in the planning set:

1. **The subtitle URL must end in the real subtitle extension.** `URIUtils::HasExtension` on a URL evaluates `CURL::GetFileName()`, which excludes the query string. A path-style redirector URL ending `/…/Movie.en.srt` works. A query-style URL (`?action=_sub&id=…`) has no extension and Kodi will treat it as plain text of unknown type. Upstream's `build_download_url` already ends in `/{name}`, so the shape is right — but it must be stated as a requirement, not left as an accident.

2. **VOBsub `.idx`/`.sub` pairs must be two URLs that differ only in the extension.** `CUtil::FindVobSubPair` pairs them with
   `PathEquals(ReplaceExtension(idxPath, ""), ReplaceExtension(subPath, ""))` — a whole-URL comparison after stripping the extension. `[VERIFIED: xbmc/Util.cpp:2257-2280]`
   A redirector URL of the form `/…/<item_id>/<name>.idx` and `/…/<other_item_id>/<name>.sub` differs in the item id, so **the pair never matches and the VOBsub is silently dropped**. Worse, the lone `.sub` then falls into `AddSubtitleFile`, which calls `GetVobSubIdxFromSub` → `ReplaceExtension` on the same URL, producing a `.idx` URL that resolves to the `.sub` item's id — i.e. the redirector would serve the wrong bytes rather than fail.

   **PLAY-08 and PLAY-09 as written cannot both be satisfied by a per-item-id URL scheme.** Fix in §6.4.

### 1.6b The download host is not always `1drv.com` — measured, 2026-08-22

Everything above, and every other document in `.planning/research/`, names the download
host as `*.files.1drv.com`. That is right for a personal Microsoft account and **wrong for a
work/school account**. Measured live against the project's own registration:

```
item : Sing.2016.2160p.MA.WEB-DL.DDP5.1.Atmos.H.265-HHWEB.mkv  (19.9 GB)
host : x14m4-my.sharepoint.com
first one-byte Range: HTTP 206
```

A work/school account's *personal* OneDrive is backed by SharePoint, and Graph mints its
`@microsoft.graph.downloadUrl` against `<tenant>-my.sharepoint.com`. This is **not** the
"SharePoint document libraries" case that `PROJECT.md` scopes out and `AUTH-24` defers to v2 —
that one is `/sites/{id}/drives`. This is the mainline Business drive, which `PROJECT.md`
lists as a first-class tested account type alongside Personal.

Consequences:

- **Any hostname assumption breaks on Business.** Anything that allowlists, matches, logs or
  asserts on `files.1drv.com` must accept `*-my.sharepoint.com` too. The safe rule is to make
  no assumption at all: treat the `downloadUrl` as opaque, use whatever host it names, and
  never parse it.
- **§7.2's checklist step is affected.** It says to find `CCurlFile::Open - … Effective URL is
  https://...files.1drv.com/...` in `kodi.log`. On a Business account that line names
  SharePoint and the check silently finds nothing. Match on `Effective URL is` alone, then read
  the host off it.
- **The lifetime may differ between the two hosts**, which is exactly why PLAY-07 specifies
  Personal *and* Business rather than one measurement. Two hosts, two issuers, no reason to
  assume one number covers both. Do not generalise a Business result to Personal or the reverse.
- **§1.7 below still holds** — the rule is "`Range` targets the `downloadUrl` host, not
  `/content`". Only the host's name generalises, not the rule.

### 1.7 `Range` requests to the download host — what is settled and what still needs the box

Settled from Microsoft's own reference for `driveItem: get content`: the pre-authenticated URL accepts `Range` and returns `206 Partial Content`; `Range` must be appended to the `downloadUrl`, not to `/content`; no `Authorization` header is needed; the URL is valid for a limited time and "might expire within minutes". `[CITED: learn.microsoft.com/graph/api/driveitem-get-content]`

Settled from Kodi's source: curl carries `CURLOPT_RANGE` / `CURLOPT_RESUME_FROM_LARGE` across the redirect to the CDN host — these are curl options, not app-supplied headers, and are applied to whichever request curl finally issues. Kodi tolerates a `200` reply to a ranged request (`m_seekable` is switched off, so the failure degrades to "cannot seek" rather than corruption). `[VERIFIED: CurlFile.cpp SetResume / CReadState::Connect]`

**Still needs the real device** — and `ARCHITECTURE.md`'s "flag for verification" note is still correct, but the thing to measure has changed:

| Measure | Why it now matters |
|---|---|
| `downloadUrl` lifetime on Personal and on Business, at T+1/+5/+15/+30/+60 min | It is a gate on PLAY-06, not a confirmation (§1.5) |
| Whether the redirector receives a **second** `do_GET` when the user seeks | This is the single decisive observable for §1.5. If no second request arrives, the latch is real end to end |
| Whether a 20-minute pause followed by *resume without seeking* recovers | Tests the reconnect-before-first-seek path, which the source says should go back through loopback |

---

## 2. Q2 — Writes

### 2.1 Every write, with its concrete Android destination

Kodi sets `HOME` on Android to `getExternalFilesDir("")` and uses `.kodi` beneath it as the profile root; the package is `org.xbmc.kodi`. `[VERIFIED: xbmc/platform/android/activity/XBMCApp.cpp:1580-1591; version.txt APP_PACKAGE]` So:

```
special://home     = /storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/
special://profile  = …/.kodi/userdata/                (default profile = masterprofile)
special://temp     = …/.kodi/temp/                    (unless the xbmc.temp system property overrides)
addon profile      = …/.kodi/userdata/addon_data/plugin.onedrive.kn/
```

`/storage/emulated/0` and `/sdcard` are the same path by symlink. `PITFALLS.md` Pitfall 19 gives `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/` — same location, and it is correct.

| # | Write | Kodi path | Mechanism | Owner | Can Android block it? |
|---|---|---|---|---|---|
| 1 | OAuth token / account store (JSON) | `special://profile/addon_data/plugin.onedrive.kn/accounts.json` | `open()` + `os.replace()` on the translated path | add-on | No |
| 2 | Token-refresh lock | same directory, e.g. `.token.lock` | `os.open(O_CREAT\|O_EXCL)` | add-on | No |
| 3 | `qr.png` sign-in image | same directory | plain `open()` inside `pyqrcode.png()` | add-on (vendored) | **Only if the directory does not exist yet** — see §2.6 |
| 4 | Add-on settings | `special://profile/addon_data/plugin.onedrive.kn/settings.xml` | Kodi | Kodi | No |
| 5 | Runtime `<service>.service.port` value | same `settings.xml` | Kodi setting write from `ui/utils.py` | add-on via Kodi | No |
| 6 | Listing / item caches, SQLite + WAL | `…/addon_data/plugin.onedrive.kn/cache_*.db` | `sqlite3.connect()` on a raw path, `pragma journal_mode=wal` | vendored module | No, but see §2.5 |
| 7 | `kodi.log` | `special://logs` → `…/.kodi/temp/kodi.log` | Kodi | Kodi | No |
| 8 | Texture / thumbnail cache | `special://profile/Thumbnails/`, `Textures13.db` | Kodi | Kodi | No |
| 9 | Playback disk cache | `special://temp/filecacheNNN.cache` | Kodi, **only if `filecache.memorysize == 0`** | Kodi | No |
| 10 | `.strm` library export (v2) | **user-chosen destination**, may be outside the app directory | `xbmcvfs` | add-on | **Yes — this is the only one scoped storage can touch.** See §2.7 |

Items 1–9 all live inside `Android/data/org.xbmc.kodi/`. Item 10 is deferred to v2 and is the only write that ever leaves it.

### 2.2 Scoped storage — the reality check, unambiguously

**An app writing into its own `Android/data/<pkg>/files/` is not affected by scoped storage. It never has been.** The restrictions people remember are restrictions on *other* apps and on file managers.

> "On Android 4.4 (API level 19) or higher, your app doesn't need to request any storage-related permissions to access app-specific directories within external storage."
>
> "When scoped storage is enabled, apps cannot access the app-specific directories that belong to **other** apps."
>
> `[CITED: developer.android.com/training/data-storage/app-specific]`

Version by version:

| Android | What changed for `Android/data/<pkg>` | Effect on this add-on |
|---|---|---|
| 10 (API 29) | Scoped storage introduced; an app can no longer reach *other* apps' app-specific dirs | None |
| 11 (API 30) | `ACTION_OPEN_DOCUMENT_TREE` / `ACTION_OPEN_DOCUMENT` can no longer target `Android/data/` or `Android/obb/` and their subdirectories — SAF and file managers are shut out. Separately, external *private* storage begins bypassing FUSE for performance | None to writes. Materially **improves** the security posture (§2.4) |
| 12–15 | Continued tightening of third-party/file-manager access to `Android/data`; `MANAGE_EXTERNAL_STORAGE` ("All files access") does **not** grant access to `Android/data` or `Android/obb` | None |
| 16 | Local network protections (opt-in); loopback out of scope | None |
| 17 (API 37) | `ACCESS_LOCAL_NETWORK` becomes mandatory for targeting apps; implicit localhost cleartext config added | None; Kodi already declares the permission |

`[CITED: developer.android.com/about/versions/11/privacy/storage; support.google.com/googleplay/android-developer/answer/10467955]`

**No storage permission is required for anything in items 1–9.** Not `WRITE_EXTERNAL_STORAGE`, not `MANAGE_EXTERNAL_STORAGE`, not `READ_MEDIA_*`. The add-on should declare none, request none, and check for none. Kodi declaring them in its manifest is Kodi's business.

**Record this as settled so it is not re-litigated.** No requirement needs to be added to `REQUIREMENTS.md` for Android storage access. The correct number of requirements about scoped storage is zero.

### 2.3 What Android 11 *did* change, and it is in the project's favour

Since Android 11, an app's own `Android/data/<pkg>` and `Android/obb/<pkg>` bypass the storage FUSE daemon and are bind-mounted from the lower filesystem into that app's mount namespace:

> "External *private* storage (which includes `android/data` and `android/obb` directories) is bypassed by FUSE, while internal storage (such as `/data/data`…) isn't FUSE mounted."
>
> `[CITED: source.android.com/docs/core/storage/scoped]`

Combined with the SAF lockdown and the All-files-access exclusion, on **Android 11 and later** the add-on's token file is reachable only by the `org.xbmc.kodi` uid or by root. That is a materially stronger boundary than a mode bit.

**This narrows `PITFALLS.md` Pitfall 18.** Pitfall 18 justifies the urgency of removing `eval()` partly on the grounds that "on Android, `special://home` resolves under `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/`, which on older Android versions is broadly readable/writable by other apps holding storage permission. A sideloaded app on a cheap TV box is a realistic threat there in a way it isn't on Windows."

That is **true on Android ≤ 10 and false on Android 11+**. The sentence should say "on Android 10 and earlier" rather than "on older Android versions", because the reader's mental model of "older" and Android's actual cut-off are different. The conclusion — replace `eval()` with JSON — is unaffected and correct regardless; the *reason* is now mostly robustness rather than a live cross-app threat, except on the boxes in §2.6.

### 2.4 `chmod 0600` is very likely a no-op, and the design must not depend on it

Where the path is served by the storage FUSE daemon (Android 10 and earlier for `Android/data`; and any FUSE-served path on any version), AOSP's implementation is explicit:

```cpp
/* XXX: incomplete implementation on purpose.
 * chmod/chown should NEVER be implemented.*/
```

`pf_setattr` handles only `FUSE_SET_ATTR_SIZE`, `FATTR_ATIME` and `FATTR_MTIME`, then replies with a fresh `lstat` — so **`chmod()` returns success and changes nothing**. Creation mode is overridden outright:

```cpp
mode = (mode & (~0777)) | 0664;
int fd = open(child_path.c_str(), open_info.flags, mode);
```

`[VERIFIED: AOSP packages/providers/MediaProvider/jni/FuseDaemon.cpp — pf_setattr, pf_create]`

So `os.open(path, O_CREAT|O_EXCL, 0o600)` produces a `0664` file and a follow-up `os.chmod(path, 0o600)` silently does nothing. On Android 11+ the app's own external-private directory bypasses FUSE (§2.3), so on the lower ext4/f2fs the mode bits are real. Which regime a given box is in cannot be determined from documentation — but it is one line of Python on the device (§7.3).

**Design consequences:**

- `chmod` must be attempted inside `try/except` and its failure must never be fatal, never logged as an error, and never gate the write.
- **Nothing in the design may depend on `0600` actually applying.** `ARCHITECTURE.md` §Q4(b) already hedges ("`chmod 0600` where the platform supports it") and already states the honest posture ("there is no OS keychain available on Android TV from Kodi Python, so file permissions plus the fact that OneDrive tokens live on the user's own device is the realistic security posture"). That hedge is now backed by source. The load-bearing boundary on Android 11+ is the app sandbox, not the mode bits; on Android ≤ 10 there is effectively no file-level boundary at all.
- On Windows `os.chmod` is largely cosmetic too. There is no platform in scope where the mode bit is the real control. Write the code so that is obvious to the next reader.

### 2.5 `O_EXCL` does **not** carry the same exposure as SQLite WAL

`PITFALLS.md` Pitfall 19 flags SQLite WAL as flaky on Android storage stacks. That is a fair warning, and the reason is specific: WAL needs a `-shm` shared-memory file mapped with `mmap` **and** POSIX advisory byte-range locks (`fcntl` `F_SETLK`). Both are exactly the operations a FUSE layer is most likely to implement badly or not at all.

`os.open(path, O_CREAT|O_EXCL)` uses neither. It is a single atomic `create` — the simplest operation a filesystem exposes — and on the FUSE path it is handed straight through to a real `open()` on the lower filesystem with the caller's flags intact (`pf_create` passes `open_info.flags` unchanged; only the *mode* is rewritten). On Android 11+ for the app's own directory it is a plain ext4/f2fs create with no FUSE in the path at all.

**So the answer to "does the lock file have the same exposure as WAL?" is no, and the mechanism is why.** The project's decision to use `O_EXCL` for the token-refresh lock is comfortable on Android. `[VERIFIED: FuseDaemon.cpp pf_create; AOSP scoped-storage FUSE bypass]` `[Confidence: HIGH on mechanism, MEDIUM empirically — §7.4 settles it in ten seconds.]`

Two `O_EXCL` caveats that do apply, neither Android-specific:

- `O_EXCL` is unreliable over NFS and SMB. Irrelevant here: an Android Kodi profile is always local.
- A process killed while holding the lock leaves the file behind. The stale-lock breaker AUTH-14 already requires is not optional on Android, where the OS killing the whole process is a normal event (§6.5).

### 2.6 Device deviations that matter

| Device class | Android base | What is different |
|---|---|---|
| **Fire TV, Fire OS 7** (Stick 4K, Stick Lite, many still shipping) | **Android 9, API 28** | Predates scoped storage entirely. `Android/data` is readable by any app holding `WRITE_EXTERNAL_STORAGE`; storage is sdcardfs, so `chmod` is a no-op. **This is the worst case for the token file and it is a mainstream device.** `[CITED: developer.amazon.com/docs/fire-tv/fire-os-7.html]` |
| **Fire TV, Fire OS 8** | Android 10 / 11 | Android 10 units keep the old exposure; Android 11 units get the modern boundary `[CITED: developer.amazon.com/docs/fire-tv/fire-os-8.html]` |
| **Chromecast with Google TV** | Android 10 / 12 | Very little internal storage. The `.strm` export destination and any cache growth need care; nothing else differs |
| **Nvidia Shield TV** | Android 11 | Modern behaviour. Also the box most likely to have an SMB/NFS-mounted media library, which is irrelevant to this add-on |
| **Cheap generic boxes** | Frequently Android 9/10 with a spoofed "13" in Settings | Assume the *worst* of the versions the box could be, and read the API level programmatically rather than the marketing string. `xbmc.getInfoLabel('System.BuildVersion')` is Kodi's version, not Android's |
| **Google Play Kodi vs sideloaded Kodi** | — | **No difference.** Both are `org.xbmc.kodi` (`version.txt APP_PACKAGE`). Same paths, same permissions, same manifest. Only nightly/alpha builds use a different package id, and those are not a target |

The practical read: **the storage question is settled on the modern platforms and unsettled on Fire OS 7.** Since Fire OS 7 sticks are common, the honest statement in any user-facing security note is "tokens are stored in Kodi's private directory; on Android 11 and later no other app can read it, on Android 9 and 10 an app with storage permission can". That is worth one line in a README, not a code change.

### 2.7 The one write scoped storage really does constrain — deferred to v2

`.strm` library export (REST-02, v2) writes to a **user-chosen destination folder**. If the user picks anything outside `Android/data/org.xbmc.kodi/`, this becomes a genuine scoped-storage problem: `MediaProvider` rejects filenames containing `" * / : < > ? \ |`, and OneDrive names legitimately contain several of those. Kodi's own file-browser dialog will happily offer paths Kodi cannot write to on Android 11+.

Not a v1 problem. Record it so the v2 export work does not rediscover it.

---

## 3. What this changes in the existing documents

| Document / section | Change |
|---|---|
| `SUMMARY.md` → Reconciled Conflicts #4 | **Corrected.** "Solves expiry by construction — on any seek, pause or network blip" is wrong for seeks. Kodi latches the effective URL. Rewrite as: covers open and reconnect-before-first-seek; does **not** cover seek. §1.5 |
| `SUMMARY.md` → Empirical Unknowns, `downloadUrl` lifetime row | **Promoted.** "Does not gate the redirector" is still true; "confirmation test, not a decision gate" is not. It gates PLAY-06. §1.5 |
| `ARCHITECTURE.md` → Q7 "The seek-after-expiry problem" | **Partially reinstated.** The worry was correct; the `SourceService` hypothesis was not. `SourceService` stays deleted — a directory index has nothing to do with this. §1.5 |
| `ARCHITECTURE.md` → Q7 design consequence 1 ("Hand Kodi the `@microsoft.graph.downloadUrl`") | Still correct as to *which* URL is finally fetched — but note it is now Kodi that arrives there by following the redirect, not the add-on that hands it over |
| `FEATURES.md` → §3 Playback table, "Expiring URL mid-playback: Solved by construction… HIGH" | **Downgrade to partial.** Same correction as `SUMMARY.md` #4 |
| `FEATURES.md` → §4 Subtitles, "URL form: through the same loopback redirector" | **Add the constraint.** VOBsub `.idx`/`.sub` pairs must be two URLs differing only in the extension, or Kodi silently drops the pair. §1.6, §6.4 |
| `PITFALLS.md` → Pitfall 18, Android exposure sentence | **Narrow.** "older Android versions" → "Android 10 and earlier". On Android 11+ no other app can read `Android/data/org.xbmc.kodi` at all. §2.3 |
| `PITFALLS.md` → Pitfall 19, TLS trust row | **Sharpen.** The mechanism is Kodi setting `SSL_CERT_FILE` to its own bundled `cacert.pem`; Python inherits it. Installing a CA in Android's system store does not help. §1.4 |
| `PITFALLS.md` → Pitfall 19, SQLite WAL row | **Extend.** The `O_EXCL` lock does *not* share WAL's exposure — different kernel mechanism. §2.5 |
| `PITFALLS.md` → Pitfall 19, storage path row | Correct as written. Add that no storage permission is needed and that scoped storage never applied to the owning app. §2.2 |
| `PITFALLS.md` → Pitfall 19, service lifecycle row | Correct. Add that a process kill takes the redirector's socket with it, so the port setting can be stale on next start. §6.5 |

---

## 4. Requirement and phase implications

Reporting only; `ROADMAP.md` and `REQUIREMENTS.md` are not edited here.

| Requirement | Implication |
|---|---|
| **PLAY-07** (measure `downloadUrl` lifetime) | Should run **first** in Phase 6, before PLAY-02/PLAY-03 are called done. It is a standalone script needing only a token, and its result decides whether PLAY-06 is achievable with a redirector alone. §1.5 |
| **PLAY-06** (seek after a 20–30 min pause) | Now known to depend on the raw URL lifetime, not on the redirector. Add the "does the redirector log a second GET on seek?" observation to its acceptance step — it is the decisive evidence and costs nothing. §7.2 |
| **PLAY-02 / PLAY-03** | Unaffected in substance. Note in the spec that the ephemeral port is inherited behaviour (`BaseServerService.get_port()` already binds port 0), so PLAY-03 is really *one* piece of new work — the per-session path token — not two |
| **PLAY-08 / PLAY-09** | Need a URL-shape rule: subtitle URLs must end in the true extension and carry no distinguishing path component between the `.idx` and `.sub` of a VOBsub pair. As currently specified the two requirements conflict. §1.6, §6.4 |
| **AUTH-11 / AUTH-14** | Storage location and `O_EXCL` are both sound on Android; no change. Add to AUTH-14's implementation note that the stale-lock breaker must survive an OS process kill, which is routine on Android |
| **KODI-07** (nothing binds 8586, "confirmed with `netstat`/`ss` on the Android box") | The verification method needs adjusting: since Android 10, an app cannot read `/proc/net` for other uids, so a `netstat`/`ss` run *inside* an app shows nothing useful. Run it from `adb shell` (the `shell` uid retains access), or verify by attempting a connection to `127.0.0.1:8586` from the box. §7.5 |
| **Phase 1, Success Criterion 3** (`qr.png` appears under the new profile) | Two guards belong in the same commit: create the profile directory before the write, and use a unique filename per dialog invocation. §6.6 |
| **New requirements needed for Android storage** | **None.** Deliberately recorded as a non-finding so it is not re-opened |

---

## 5. Settled from documentation and source vs. needs the box

**Settled — do not re-test:**

- No filesystem path is required for playback; scoped storage is irrelevant to it. `[HIGH — Kodi source + Android docs]`
- No storage permission is required for any v1 write. `[HIGH — Android docs, quoted]`
- Cleartext policy does not reach Kodi's libcurl or Kodi's CPython. `[HIGH — Android docs, quoted]`
- Kodi replaces its held URL with the effective URL after a redirect, on Nexus, Omega and master. `[HIGH — source read on all three branches]`
- `chmod` is a no-op and creation mode is forced to `0664` on any FUSE-served path. `[HIGH — AOSP source, quoted]`
- The app's own `Android/data` bypasses FUSE from Android 11. `[HIGH — AOSP docs, quoted]`
- VOBsub pairing compares whole URLs modulo extension. `[HIGH — Kodi source]`
- Kodi's Android package is `org.xbmc.kodi` for both Play and sideloaded builds. `[HIGH — version.txt]`

**Needs the real Android TV box — the list is short and each item is cheap:**

1. Whether a seek produces a second request at the redirector (the end-to-end consequence of the latch).
2. The actual `downloadUrl` lifetime, Personal and Business.
3. Whether `chmod` applies on this box's storage regime.
4. Whether `O_EXCL` excludes correctly on this box.
5. Whether binding `127.0.0.1:0` succeeds (expected trivially yes; loud failure if not).
6. Whether Kodi's texture cache serves a stale `qr.png` on a second sign-in in one session.

**Explicitly *not* worth testing:** whether the add-on can write to its own profile directory. It can. Testing it would only produce a false sense that it was ever in doubt.

---

## 6. Escape hatches

### 6.1 If a write path is unavailable

Ranked, though the first covers essentially every real case.

1. **The directory does not exist yet.** By far the most likely cause of a failed first write, and it is not an Android restriction at all — Kodi creates `addon_data/<id>/` lazily. `xbmcvfs.mkdirs(profile_dir)` (or `os.makedirs(path, exist_ok=True)` on the translated path) before the first raw write, once, at add-on start. The vendored `db.py` already does this for its SQLite files; `pyqrcode` does not, which is why `qr.png` is the write most likely to fail.
2. **`special://profile/addon_data/<id>/` is the right root and there is no better one.** `special://home` is the same volume; `special://temp` is the same volume and is periodically cleaned; `special://userdata` is the master profile, which breaks per-profile isolation. There is no alternative root worth reaching for — if `addon_data` is unwritable, Kodi itself is broken.
3. **Kodi's internal-storage location is not addressable from Python.** Kodi falls back to `getDir()` on internal storage only when `getExternalFilesDir()` returns null, and the `xbmc.data` system property that would override it requires `setprop` at boot. Not a fallback the add-on can invoke.
4. **If the write truly fails, degrade, do not abort.** No token store means the user must sign in again — annoying, not fatal. Surface it as one sentence (ERR-01), not a traceback.

**`xbmcvfs` vs raw `open()` — the tension resolved.** `xbmcvfs.translatePath('special://…')` returns a **real OS path** on Android, exactly as on Windows and Linux; it is never a `content://` URI. So the correct pattern is: translate once through `xbmcvfs`, then use ordinary `os` calls on the result. This gives `O_EXCL`, `os.replace()` atomicity, and `sqlite3` — none of which `xbmcvfs.File` can provide — with no loss of portability, because `special://profile` never resolves to a Kodi VFS location (`smb://`, `nfs://`) on any supported platform. Use `xbmcvfs` for `mkdirs`, `exists` and `delete` where the ergonomics are better; use raw `os` for everything that needs real filesystem semantics. `[VERIFIED: the vendored module already follows exactly this split — ui/utils.py:224 translate_path → xbmcvfs.translatePath, then sqlite3 and open() on the result]`

### 6.2 If `chmod 0600` is a no-op

Nothing in the design depends on it, and after §2.4 nothing may. The realistic posture, stated for the record:

- **Android 11+:** the boundary is the app sandbox — uid isolation plus the platform's refusal to expose `Android/data` to SAF, to file managers, or to All-files-access. Strictly stronger than a mode bit.
- **Android ≤ 10 (including Fire OS 7):** there is effectively no file-level boundary. Any app with `WRITE_EXTERNAL_STORAGE` can read the token file. Mitigations that actually help there: store JSON so a malformed or hostile file cannot execute (the `eval()` removal, already required by VND-05); request the narrowest scope set so a stolen refresh token is read-only over `Files.Read` (already required by AUTH-04); and keep the refresh token the only long-lived secret on disk.
- **Windows:** `os.chmod` is largely cosmetic. Same conclusion.

Attempt the `chmod`, swallow the failure, do not log it as an error, and do not assert on it in any test.

### 6.3 If the redirector cannot keep a seek alive

This is the §1.5 problem, and the ladder is ordered by cost.

1. **Measure first (PLAY-07).** If the URL lives about an hour on both drive classes, PLAY-06's 20–30 minute pause passes and nothing further is needed. Most likely outcome. Cost: a script.
2. **Keep the redirector regardless.** Even with the latch it earns its ~80 lines — see §1.5, "what it still buys". Do not conclude from this document that the redirector should be dropped in favour of handing Kodi the raw `downloadUrl`. Doing that loses: the guarantee that no expiring URL is persisted anywhere, freshness at first byte, reconnect recovery before the first seek, and the single place where the per-session token and subtitle serving live. What it would gain is one fewer moving part. Not a good trade.
3. **Recover at the player level.** A `xbmc.Player` subclass in the service records the play position; on an unexpected `onPlayBackError` or an early `onPlayBackEnded`, it re-invokes the same `plugin://` URL with a resume offset. The user sees a one- to two-second hiccup instead of playback dying. Roughly 40 lines, no byte proxying, no architectural change. This is the right answer if the measured lifetime is short. Cost: a visible glitch and some care not to loop on a genuine failure.
4. **Byte-relay on loopback.** Fully solves it by construction — the add-on holds a live `downloadUrl`, re-signs it internally whenever it expires, and serves `206`/`Content-Range` to Kodi. This is what `PROJECT.md` rules out as "byte-proxying playback through the add-on", on the grounds of Python in the byte path on constrained ARM hardware. That objection is real but is about *throughput*, and a `shutil.copyfileobj`-style relay at 64 KB chunks is mostly kernel copying — the cost is one extra memory copy and the GIL held during the `read`/`write` pair. **Do not adopt this speculatively.** It is the option to reopen only if (1) is short and (3) proves unacceptable, and reopening it means revisiting a recorded decision, not sneaking past it.
5. **Not an option:** disabling redirect-following with Kodi's `|redirect-limit=0` URL option. Kodi would then hold a `3xx` response with no body rather than re-resolving.

### 6.4 If subtitles cannot go through the redirector as specified

The problem is §1.6: a per-item-id URL makes the `.idx` and `.sub` of a VOBsub pair differ in more than the extension, so Kodi silently drops the pair.

1. **Reshape the redirector URL** so that a play session, not an item, keys the path: `http://127.0.0.1:P/<session-token>/sub/<play-token>/<basename>.idx` and `…/<basename>.sub`, with an in-memory `(play-token, extension) → item_id` map populated at resolve time. The two URLs then differ only in the extension, `FindVobSubPair` matches, and PLAY-03's token requirement is satisfied by the same construction. Preferred — it is a naming decision, not extra machinery.
2. **Fetch subtitles to `special://temp` and hand Kodi local paths.** Subtitle files are kilobytes; the fetch happens once at resolve time and must not block first video byte. This does reintroduce a filesystem write — but into app-specific external storage, where §2.2 applies, so it is not blocked on any Android version. It also sidesteps expiry entirely, since the file is local. Use this if the URL reshaping turns out to fight the redirector's routing.
3. **Ship SRT/ASS only in v1 and drop VOBsub.** PLAY-08 explicitly names `.idx`/`.sub` pairs, so this is a requirement change, not an implementation choice — but it is an honest option if VOBsub proves disproportionate. Text subtitles have none of this problem: a single URL ending `.srt` works with no pairing logic at all.

### 6.5 If Android kills the service while backgrounded

Android kills the whole Kodi process, not the add-on's service in isolation. When it does, the player, the redirector socket and the Python interpreter all go at once. What must therefore be resumable purely from disk:

- **The token store.** Already atomic (`os.replace`) — a kill mid-write leaves either the old or the new document, never a truncated one. Verify the write really is temp-file-plus-replace and not an in-place truncate.
- **The refresh lock.** A kill while holding it leaves the lock file behind. The stale-lock breaker AUTH-14 requires is what makes the next start recover; without it the add-on is permanently wedged after one unlucky kill. Break on age, and choose the threshold longer than the worst realistic refresh round-trip on bad Wi-Fi.
- **The `<service>.service.port` setting.** Written at service start and read by the plugin when building a play URL. After a kill it holds a port nobody is listening on. The plugin must treat a connection failure to the recorded port as "service not up yet" and either wait briefly or fail with a specific message — never a bare traceback. `FEATURES.md` already flags the first-play-after-restart race; this is the same race with a worse trigger.
- **Nothing else.** No in-memory continuity may be assumed: not a cached access token beyond its own expiry check, not a delta cursor held in a variable, not the `(play-token → item_id)` map from §6.4 — which is why that map must be rebuilt on every resolve rather than treated as durable.

Waits stay on `xbmc.Monitor().waitForAbort(n)`, never `time.sleep(n)`, as Pitfall 19 already requires.

### 6.6 If `qr.png` cannot be written

**This must not be a dead end, and structurally it is not one — because the QR was never the mechanism.** Microsoft does not support `verification_uri_complete`, so the QR can only ever encode `https://microsoft.com/devicelogin`. The user reads the 8–9 character code off the screen and types it on a phone either way. The QR saves typing a short, memorable URL; nothing more. `[Established in ARCHITECTURE.md §Q4(a) and FEATURES.md §1 — restated here because it is what makes this failure mode survivable]`

Ranked fallbacks:

1. **Prevent it.** `xbmcvfs.mkdirs(profile_dir)` before `pyqrcode.create(...).png(path, scale=10)`. The upstream code does not do this, and a missing profile directory is the one realistic cause of failure. One line.
2. **Write to a unique filename per invocation** — `qr-<random>.png` — and delete it when the dialog closes. This costs nothing and pre-empts a second problem: Kodi's texture cache is keyed by path, so a second sign-in in the same Kodi session that overwrites the same `qr.png` may render the *previous* image. The upstream code writes a fixed name and deletes it in `__del__`, which is both non-deterministic timing and the wrong key. `[MEDIUM — Kodi texture caching behaviour; §7.6 settles it, and using unique names makes the question moot either way]`
3. **Degrade to text.** Catch the write failure, hide the image control, and show the verification URI and the user code as text. The dialog must already render the code at the skin's largest font (AUTH-05) and show a countdown (AUTH-06); the QR is decoration around that. The dialog should be built so the text path is the *default* layout and the image is added when available — not so the image is the layout and text is an emergency.
4. **Never abort sign-in because an image failed to render.** The QR write must be inside `try/except` with a debug log line and no user-visible error.

---

## 7. Device test checklist

Executable on the real Android TV box with a remote. Each item states what to do, what to look for, and what it decides. Total time: under an hour, excluding the URL-lifetime measurement which runs unattended.

Enable component logging first: **Settings → System → Logging → Enable component-specific logging**, tick **libcURL**. Then reproduce and read `.../.kodi/temp/kodi.log`.

### 7.1 Loopback socket binds

- Start Kodi. Open the add-on once so the service is running.
- In `kodi.log`, find `Service 'download' started in port NNNNN`.
- **Decides:** whether a Python add-on can bind `127.0.0.1:0` on this Android version. Expected yes. If the line is absent or an exception appears instead, everything in §1.3 is wrong and nothing else on this list matters.

### 7.2 Does a seek bypass the redirector? *(the decisive test)*

- Add a temporary log line at the top of the redirector's `do_GET` so every request is visible.
- Play a file over two hours. Let it run 30 seconds.
- In `kodi.log`, find `CCurlFile::Open - <...> Effective URL is https://...files.1drv.com/...`. Its presence confirms the latch mechanism is live.
- **Seek forward 10 minutes with the remote.**
- Look for a **second** `do_GET` line at the redirector.
  - **No second request** → the latch is real end to end. §1.5 stands. The redirector does not cover seeks.
  - **A second request** → Kodi re-resolved through loopback, the original position in `SUMMARY.md` #4 holds, and §1.5 is wrong. Record which, because everything about PLAY-06 and PLAY-07's priority follows from it.
- Then **pause 20 minutes without seeking**, press play, and watch for a `do_GET` and/or a `CCurlFile::CReadState::FillBuffer - Reconnect, (re)try 1` line. This is the reconnect-before-first-seek path, expected to go back through loopback.

### 7.3 Does `chmod` apply on this box?

From an add-on debug action or the Kodi Python console, on a file in the add-on profile directory:

```python
import os, stat, xbmcvfs
p = xbmcvfs.translatePath('special://profile/addon_data/plugin.onedrive.kn/') + 'perm.test'
os.makedirs(os.path.dirname(p), exist_ok=True)
fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); os.close(fd)
before = oct(stat.S_IMODE(os.stat(p).st_mode))
os.chmod(p, 0o600)
after = oct(stat.S_IMODE(os.stat(p).st_mode))
print(before, after)   # log it
os.remove(p)
```

- **`0o600 0o600`** → this box bypasses FUSE for app-private storage; mode bits are real.
- **`0o664 0o664`** → FUSE-served; `chmod` is a no-op exactly as §2.4 predicts.
- **Decides:** nothing about correctness — only what the user-facing security note should say. Record the value with the box's Android version.

### 7.4 Does `O_EXCL` exclude?

Same context, twice in a row:

```python
fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)   # expect success
try:
    fd2 = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    print('BROKEN: second O_EXCL succeeded')
except FileExistsError:
    print('OK: O_EXCL excludes')
```

- **Decides:** whether AUTH-14's lock mechanism is sound on this storage stack. Expected `OK`. If it prints `BROKEN`, the token-refresh design needs rethinking — but §2.5 says it will not.

### 7.5 Nothing binds 8586 *(KODI-07 acceptance, method corrected)*

- From a development machine: `adb shell ss -ltnp | grep 8586` — run as the `shell` uid, which retains `/proc/net` access that apps lost in Android 10. A check run *inside* an app will see nothing and prove nothing.
- Cross-check from the box itself by pointing any browser or `curl` at `http://127.0.0.1:8586/`. Connection refused is the pass.
- **Decides:** KODI-07.

### 7.6 QR image freshness and the missing-directory case

- Delete `.../addon_data/plugin.onedrive.kn/` entirely from the box.
- Trigger the sign-in dialog. It must render — either with a QR, or with text if the write failed. It must not throw.
- Cancel, then trigger it again **in the same Kodi session** so a second code is issued.
- Compare the QR shown on the second dialog against the first. If they are identical while the codes differ, Kodi is serving a cached texture and unique filenames (§6.6 item 2) are required.
- **Decides:** Phase 1 Success Criterion 3, and whether the unique-filename guard is mandatory or merely tidy.

### 7.7 `downloadUrl` lifetime *(PLAY-07 — run this first in Phase 6)*

- Resolve one `@microsoft.graph.downloadUrl` on a **Personal** drive and one on a **Business** drive. Record the wall-clock time.
- Issue `GET` with `Range: bytes=0-1023` against each at **T+1, +5, +15, +30, +60 minutes**. Record the status code at each point.
- Do this from the box if convenient, but a desktop is fine — the URL's lifetime is Microsoft's, not the client's.
- **Decides:** whether PLAY-06 is achievable with a redirector alone, and therefore which rung of §6.3 the project is standing on. Record the numbers in the repo, as PLAY-07 already requires.

### 7.8 Full-path acceptance *(rolls up into CI-06)*

- Sign in on the box with the remote; browse a Personal and a Business drive; play a video, an audio file and an image.
- Play a file over two hours; pause 20–30 minutes past the measured URL lifetime; resume; then seek forward.
- Attach a `.srt` and, separately, a VOBsub `.idx`/`.sub` pair; confirm both appear in the subtitle OSD (this is the §1.6 check in its user-visible form).
- Quit Kodi while a large listing is in flight; confirm a clean exit.

---

## 8. Assumptions log

| # | Claim | Where | Risk if wrong |
|---|---|---|---|
| A1 | Unprivileged ports ≥ 1024 are freely bindable on all Android versions in scope | §1.3 | Redirector cannot start. Loud failure at `bind()`, caught by §7.1 |
| A2 | Doze / App Standby do not affect a loopback socket in the foreground process during playback | §1.3 | Playback stalls when backgrounded. The scenario is self-contradicting; low risk |
| A3 | Loopback is exempt from Android 16/17 local network protections | §1.3 | Redirector breaks on Android 17+ targets. Corroborated but not quoted from Android's own page; Kodi already declares `ACCESS_LOCAL_NETWORK` as a hedge |
| A4 | Kodi's texture cache is keyed by path, so overwriting `qr.png` may serve a stale image | §6.6 | A user sees the wrong QR on a second sign-in. Neutralised by using unique filenames regardless |
| A5 | The reconnect-before-first-seek path really does return to the loopback URL end to end | §1.5 | The redirector covers even less than stated. Source-level reasoning through curl's `Curl_pretransfer`; §7.2 settles it |
| A6 | Community reports of an approximately one-hour `downloadUrl` lifetime are representative | §6.3 | PLAY-06 fails and §6.3 rung 3 or 4 is needed. PLAY-07 replaces this assumption with a measurement |

---

## 9. Sources

**Primary — source read this session**

- Kodi `xbmc/filesystem/CurlFile.cpp` — master, Omega and Nexus branches: `m_url = efurl` after redirect; `SetCommonOptions` → `CURLOPT_URL`; `Seek` → `SetCommonOptions` → `Connect`; `CURLOPT_FOLLOWLOCATION` / `MAXREDIRS`; `redirect-limit` URL option; `FillBuffer` reconnect path
- Kodi `xbmc/cores/VideoPlayer/VideoPlayer.cpp:945-960`, `AddSubtitleFile`; `xbmc/Util.cpp:2257-2280` `FindVobSubPair`, `2314` `GetVobSubSubFromIdx`; `xbmc/utils/URIUtils.cpp` `HasExtension` / `ReplaceExtension`
- Kodi `xbmc/platform/android/activity/XBMCApp.cpp:1547-1600` `SetupEnv` — `HOME = getExternalFilesDir("")`, `KODI_TEMP`, internal-storage fallback
- Kodi `xbmc/platform/android/PlatformAndroid.cpp:37` — `SSL_CERT_FILE` set to the bundled `cacert.pem`
- Kodi `tools/android/packaging/xbmc/AndroidManifest.xml.in` — declared permissions, no `usesCleartextTraffic`, no network-security-config; `version.txt` — `APP_PACKAGE org.xbmc.kodi`, VERSION_MAJOR 22
- Kodi `xbmc/filesystem/FileCache.cpp:118-186`, `CacheStrategy.cpp:72`, `system/settings/settings.xml` — `filecache.memorysize` default 64 MB
- AOSP `packages/providers/MediaProvider/jni/FuseDaemon.cpp` — `pf_setattr` ("chmod/chown should NEVER be implemented"), `pf_create` (`mode = (mode & ~0777) | 0664`), `parse_open_flags`
- curl `lib/transfer.c` `Curl_pretransfer` — `state.url` reset from `STRING_SET_URL` on each transfer
- `script.module.clouddrive.common` 1.4.0 (`matrix`, from `mirrors.kodi.tv/addons/omega`) — `service/download.py` (307 re-signer, URL shape), `service/base.py` (`_interface = '127.0.0.1'`, `get_port()` binds port 0), `ui/dialog.py:114-131` (`qr.png` write, `xbmcvfs.delete` in `__del__`), `db.py:42-48` (WAL, raw sqlite path), `ui/utils.py:224` (`translate_path`)

**Secondary — official documentation**

- developer.android.com/training/data-storage/app-specific — no permission for own app-specific external directory since API 19; scoped storage restricts other apps only
- developer.android.com/guide/topics/manifest/application-element — `usesCleartextTraffic` best-effort, Socket API carve-out, which components honour it
- developer.android.com/privacy-and-security/security-config — implicit localhost configuration from Android 17 (API 37)
- developer.android.com/about/versions/11/privacy/storage — SAF cannot target `Android/data` or `Android/obb`
- developer.android.com/privacy-and-security/local-network-permission and /about/versions/17/behavior-changes-17 — opt-in on 16, `ACCESS_LOCAL_NETWORK` mandatory for targetSdk 37
- source.android.com/docs/core/storage/scoped — external *private* storage bypasses FUSE
- support.google.com/googleplay/android-developer/answer/10467955 — All files access excludes `Android/data` and `Android/obb`
- developer.amazon.com/docs/fire-tv/fire-os-7.html and fire-os-8.html — Fire OS 7 = Android 9 (API 28); Fire OS 8 = Android 10/11
- learn.microsoft.com/graph/api/driveitem-get-content — 302 to a pre-authenticated URL, "might expire within minutes", `Range` targets the `downloadUrl`

**Tertiary — corroborated, not authoritative**

- Loopback treated as a class separate from "local network" in the Android 16/17 protections — consistent across vendor and browser-side write-ups of the same model, not quoted from Android's own documentation. Marked MEDIUM throughout
- Community reports of an approximately one-hour `downloadUrl` lifetime — superseded by PLAY-07's measurement

---

*Compiled 2026-08-22. The URL-latch finding (§1.5) and the VOBsub URL constraint (§1.6) are the two items that change existing decisions; everything else either confirms the current design or removes a worry from it.*
