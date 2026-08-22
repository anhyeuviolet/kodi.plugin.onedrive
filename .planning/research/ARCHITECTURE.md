# Architecture Research

**Domain:** Kodi 20+ cloud-storage add-on (`plugin.onedrive`) — self-contained, in-process OAuth device-code flow, Microsoft Graph backend
**Researched:** 2026-08-22
**Confidence:** MEDIUM-HIGH on Kodi and Graph API mechanics (read directly from first-party docs); MEDIUM on cross-interpreter concurrency (documented behaviour + inference, needs a device test); LOW on `clouddrive.common` internals beyond the file inventory and the interfaces quoted below.

---

## Executive Answer

The target architecture is **not** "vendor `clouddrive.common` and patch it." For the core path (auth → browse → play), essentially none of that module survives as running code — its OAuth layer is being replaced by decision, its HTTP client is entangled with the OAuth layer and the dead sign-in broker, and its 41 KB `ui/addon.py` god class is the thing that makes the current codebase unreadable. What "vendoring" actually buys you is a **place to park the deferred subsystems** (export, source, download, player services) so the external dependency can be dropped in one commit without losing those features.

So: **vendor everything once, mechanically, into a quarantined `resources/lib/vendor/` tree; then build the core path fresh in `resources/lib/` and delete from `vendor/` as each subsystem is replaced or restored.**

The second structural decision that drives everything else: **no module below the Kodi boundary may `import xbmc*`.** Token handling, Graph HTTP, pagination, and Graph-JSON→item mapping become plain Python, unit-testable with recorded fixtures. That single rule turns the eight listed "core path correctness" bugs in `PROJECT.md` from *manual-acceptance-only* into *CI-catchable*.

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Kodi process (single OS process)                 │
│  ┌────────────────────────────┐   ┌────────────────────────────────┐ │
│  │ sub-interpreter A (thread) │   │ sub-interpreter B (thread)     │ │
│  │  entrypoint.py             │   │  service.py                    │ │
│  │  plugin:// invocation      │   │  xbmc.service, start="login"   │ │
│  │  FOREGROUND · interactive  │   │  BACKGROUND · never interactive│ │
│  └─────────────┬──────────────┘   └──────────────┬─────────────────┘ │
│                │                                  │                   │
│   shared only via: xbmcgui.Window(10000) properties  +  files on disk │
└────────────────┼──────────────────────────────────┼───────────────────┘
                 │                                  │
╔════════════════▼══════════════════════════════════▼═══════════════════╗
║  KODI BOUNDARY  — the only layer allowed to import xbmc*               ║
║  resources/lib/kodi/                                                   ║
║  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐  ║
║  │ routes   │ │ listing  │ │ dialogs  │ │ settings │ │ shared      │  ║
║  │ dispatch │ │ Item→LI  │ │ devicecd │ │ + strings│ │ Window(1e4) │  ║
║  └────┬─────┘ └────▲─────┘ └────▲─────┘ └──────────┘ └──────┬──────┘  ║
╚═══════┼════════════┼════════════┼══════════════════════════╤┼═════════╝
        │            │            │                          ││
┌───────▼────────────┴────────────┼──────────────────────────┼┼─────────┐
│  DOMAIN — pure Python, zero xbmc imports, 100% unit-testable││          │
│  ┌──────────────────────────────┴───────────────────────┐  ││          │
│  │ provider/onedrive.py   OneDriveProvider              │  ││          │
│  │   Graph JSON  →  Item / Drive  (mapping is pure)     │  ││          │
│  └────────────────────────┬─────────────────────────────┘  ││          │
│  ┌────────────────────────▼─────────────────────────────┐  ││          │
│  │ graph/  client.py · paging.py · paths.py · errors.py │  ││          │
│  │   authenticated request, @odata.nextLink iteration,  │  ││          │
│  │   URL encoding, 429/Retry-After, 401→refresh-once    │  ││          │
│  └────────────────────────┬─────────────────────────────┘  ││          │
│  ┌────────────────────────▼─────────────────────────────┐  ││          │
│  │ auth/  session.py (TokenProvider)  ← the ONLY caller │◄─┘│          │
│  │        device_flow.py    store.py    tokens.py       │◄──┘          │
│  └────────────────────────┬─────────────────────────────┘             │
└───────────────────────────┼───────────────────────────────────────────┘
                            │
              ┌─────────────┴────────────────┐
              ▼                              ▼
   login.microsoftonline.com       graph.microsoft.com/v1.0
   /{tenant}/oauth2/v2.0/          → 302 / @microsoft.graph.downloadUrl
   devicecode · token                        │
                                             ▼
                                 *.files.1drv.com  (preauth, expires in minutes)

┌───────────────────────────────────────────────────────────────────────┐
│  resources/lib/vendor/clouddrive/  — QUARANTINE (deferred features)    │
│  export · source · download · player services, reached only through   │
│  a thin adapter. Deleted file-by-file as each is restored or dropped. │
└───────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Owns | Must not know about |
|-----------|------|---------------------|
| `entrypoint.py` | Parse `sys.argv`, hand `(handle, params)` to `routes`. ~10 lines. | Graph, auth, Kodi widgets |
| `service.py` | Start background loops with an abort-aware sleep. ~20 lines. | Interactive dialogs (hard rule) |
| `kodi/routes.py` | `action` → handler dispatch table; guarantees exactly one terminating call per invocation | Graph URLs, token internals |
| `kodi/listing.py` | `Item` → `xbmcgui.ListItem` via typed InfoTag setters; chunked `addDirectoryItems` | HTTP, JSON shapes |
| `kodi/dialogs.py` | Device-code dialog, progress, notifications, error surfaces | OAuth protocol details |
| `kodi/shared.py` | `Window(10000)` property cache + the cross-interpreter file mutex | What is being cached |
| `kodi/settings.py` | `xbmcaddon.Addon()` handle, localized strings, `xbmcvfs.translatePath` paths | Everything else |
| `provider/onedrive.py` | OneDrive semantics: drives, pseudo-folders, search, subtitles, `_extract_item` | Kodi, tokens, sockets |
| `graph/client.py` | One authenticated HTTP call + retry policy | OneDrive concepts, Kodi |
| `graph/paging.py` | `@odata.nextLink` iteration as a generator | Item shapes |
| `graph/paths.py` | URL construction, percent-encoding, OData literal quoting | HTTP |
| `auth/session.py` | `get_access_token()` — **the only place a refresh ever happens** | Graph, Kodi UI |
| `auth/device_flow.py` | RFC 8628 against Entra: `start()`, `poll()`, `refresh()` | Disk, Kodi, Graph |
| `auth/store.py` | Atomic JSON persistence + locking | OAuth protocol |
| `vendor/clouddrive/` | Deferred subsystems, frozen | Anything in the new tree (adapter-only contact) |

---

## Recommended Project Structure

```
plugin.onedrive/
├── addon.xml                       # xbmc.python 3.0.0; NO clouddrive.common import
├── entrypoint.py                   # plugin:// bootstrap (thin)
├── service.py                      # xbmc.service bootstrap (thin)
├── LICENSE.txt                     # GPL-3.0-or-later
├── NOTICE.md                       # attribution for vendored clouddrive.common code
└── resources/
    ├── settings.xml                # Kodi 19+ version="1" schema
    ├── language/
    └── lib/
        ├── __init__.py
        ├── kodi/                   # ── the ONLY package allowed to import xbmc*
        │   ├── settings.py         #    Addon handle, strings, profile paths
        │   ├── log.py
        │   ├── shared.py           #    Window(10000) cache + O_EXCL file mutex
        │   ├── dialogs.py          #    device-code dialog, progress, notify
        │   ├── listing.py          #    Item -> ListItem (typed InfoTags)
        │   ├── play.py             #    resolve -> setResolvedUrl
        │   └── routes.py           #    action dispatch table
        ├── auth/                   # ── pure
        │   ├── tokens.py           #    TokenSet + expiry math
        │   ├── device_flow.py      #    RFC 8628 / Entra
        │   ├── store.py            #    atomic JSON persistence
        │   └── session.py          #    TokenProvider facade
        ├── graph/                  # ── pure
        │   ├── errors.py
        │   ├── paths.py
        │   ├── client.py
        │   └── paging.py
        ├── provider/               # ── pure
        │   ├── model.py            #    Item, Drive dataclasses
        │   └── onedrive.py
        └── vendor/                 # ── quarantine, deleted as it is replaced
            ├── README.md           #    provenance, upstream commit, licence
            └── clouddrive/common/…
tests/
├── fixtures/graph/                 # recorded Graph JSON
├── test_extract_item.py
├── test_paging.py
├── test_paths.py
├── test_token_store.py
└── test_layering.py                # asserts no xbmc import below kodi/
```

### Structure Rationale

- **`kodi/` as a named boundary, not a convention.** Add a CI test that walks `auth/`, `graph/`, `provider/` and fails on any `import xbmc`. This is a five-line test that keeps the whole design honest for the life of the project, and it is what makes fixture-based testing of `_extract_item` possible without stubbing Kodi.
- **`auth/` split four ways, not one `oauth.py`.** Device-code protocol, token value object, persistence, and refresh-orchestration have genuinely different reasons to change (protocol vs. filesystem vs. concurrency). Collapsing them is exactly how the upstream `remote/oauth2.py` ended up with a refresh path that has no locking at all.
- **`graph/` separate from `provider/`.** `graph/client.py` should be usable to call any Graph endpoint. `provider/onedrive.py` should contain zero `urllib` and zero header construction. This is the seam that lets you test drive-listing logic against a fake client.
- **`vendor/` at `resources/lib/vendor/`, not at the repo root.** Under `resources/lib/` it is inside the package tree Kodi already puts on `sys.path`, and it is unambiguously *not yours*. A repo-root `clouddrive/` package would compete with the add-on's own top-level namespace and read like first-party code.
- **`tests/` outside `resources/`.** Ships in git, must be excluded from the release zip by the build script.

---

## Q1 — Kodi 20+ add-on conventions

### Plugin / service split

Both entry points are declared in `addon.xml` and both are invoked by Kodi, but they are **not** separate OS processes:

```xml
<extension point="xbmc.python.pluginsource" library="entrypoint.py">
  <provides>video audio image</provides>
</extension>
<extension point="xbmc.service" library="service.py" />
```

Kodi's `CPythonInvoker` runs each invocation in its own **CPython sub-interpreter on its own thread inside the single Kodi process**. Practical consequences, which matter enormously for Q5:

- Module globals, singletons, and `threading.Lock` objects are **not** shared between the plugin and the service. Every plugin invocation also starts from a cold `sys.modules`.
- `xbmcgui.Window(10000)` properties **are** shared, because the backing object is C++.
- Files on disk are shared, but they are shared *within one process*, which breaks a common locking assumption (see Q5).
- The service is long-lived; the plugin invocation is measured in hundreds of milliseconds and must not block on anything the user cannot see.

**Hard rule:** the service must never open an interactive dialog. It starts at `start="login"`, potentially before a user is present. It may *refresh* tokens; it may never *initiate* device-code sign-in.

### Routing: hand-rolled, not `script.module.routing`

Recommendation: **keep hand-rolled query-parameter dispatch.** `script.module.routing` (tamland) is a good library — `@plugin.route("/folder/<path:p>")` with `url_for()` is genuinely nicer than string matching — but three things rule it out here:

1. It is another external `script.module.*` dependency, in a project whose stated goal is removing external dependencies. Vendoring it is possible (~150 lines) but buys little.
2. It is path-based. Your existing URLs are query-based (`?action=open_folder&driveid=…&path=…`).
3. **Plugin URLs are a persistent compatibility surface.** Kodi writes them into the video/music library, into watched-state rows, and — for this add-on specifically — into exported `.strm` files on the user's disk. Changing the URL shape silently breaks every previously exported library entry. `_rename_action()` in the current `addon.py` already exists precisely to keep old action names working; that constraint does not go away.

What to build instead — a dispatch table with an explicit terminator contract:

```python
# resources/lib/kodi/routes.py
_ROUTES = {}

def route(*actions):
    def deco(fn):
        for a in actions:
            _ROUTES[a] = fn
        return fn
    return deco

# legacy names kept as aliases, not translated at call time
@route('_list_folder', 'open_folder')
def list_folder(ctx): ...

@route('_play', 'play')
def play(ctx): ...

def dispatch(handle, params):
    action = params.get('action', '_list_drives')
    handler = _ROUTES.get(action)
    if handler is None:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    handler(Context(handle, params))
```

Directory handlers own `endOfDirectory`; playback handlers own `setResolvedUrl`. Enforce that they never mix (see Q7).

### Directory items with typed InfoTag setters

Kodi 20 Nexus introduced the typed setter API and deprecated most of `ListItem.setInfo()`. Verified against the official `InfoTagVideo` reference: `setDuration`, `setPlot`, `setTitle`, `setMediaType`, `setGenres`, `setCast`, `setResumePoint`, `setUniqueIDs`, `setDbId`, `setYear`, `setSeason`, `setEpisode`, `setPremiered`, `setDateAdded`, `setPath`, `setFilenameAndPath` are all **v20** additions. `setVideoAssetTitle` is v21. `setOriginalLanguage` and `setAvailableFanart` are v22 — do not use them if you target 20.

**`setDuration` is documented as `integer - Duration in seconds`.** This is exactly the `PROJECT.md` bug "pass integer durations to Kodi, not floats": Graph returns `video.duration` in **milliseconds**, and the current `_extract_item` divides by 1000 producing a float.

```python
# resources/lib/kodi/listing.py
def to_list_item(item):
    li = xbmcgui.ListItem(label=item.name, offscreen=True)
    li.setArt({'thumb': item.thumbnail, 'icon': item.thumbnail})

    if item.kind == 'video':
        tag = li.getVideoInfoTag()
        tag.setMediaType('video')
        tag.setTitle(item.name)
        if item.duration_ms is not None:
            tag.setDuration(int(round(item.duration_ms / 1000)))   # int seconds
        if item.date_added:
            tag.setDateAdded(item.date_added)
        li.setProperty('IsPlayable', 'true')
    elif item.kind == 'audio':
        tag = li.getMusicInfoTag()
        tag.setMediaType('song')
        tag.setTitle(item.name)
        if item.duration_ms is not None:
            tag.setDuration(int(round(item.duration_ms / 1000)))
        li.setProperty('IsPlayable', 'true')
    elif item.kind == 'image':
        tag = li.getPictureInfoTag()
        tag.setResolution(item.width, item.height)
    return li
```

Two details worth internalising:

- **`offscreen=True`** on every `ListItem` you build in a plugin. It skips the GUI-thread lock acquisition; on a low-powered Android TV box listing a few hundred files this is a measurable win and there is no downside for plugin-constructed items.
- **`IsPlayable`** is what makes Kodi call back into the plugin so `setResolvedUrl` can answer. Set it only on items whose handler actually calls `setResolvedUrl`; setting it on a folder or on a leaf handler that does not resolve leaves Kodi waiting.

### Where `endOfDirectory` belongs

Exactly one call per directory invocation, in a `finally`, owned by the route handler and nowhere else:

```python
def list_folder(ctx):
    ok = False
    try:
        xbmcplugin.setContent(ctx.handle, 'videos')
        _add_items_chunked(ctx)
        ok = True
    except GraphError as e:
        dialogs.error(e)
    finally:
        xbmcplugin.endOfDirectory(ctx.handle, succeeded=ok, cacheToDisc=False)
```

- `succeeded=False` makes Kodi **navigate back** instead of displaying an empty folder — the right behaviour for an auth failure or a network error, and much clearer than a blank screen.
- `cacheToDisc=False` for cloud listings; Kodi's on-disk directory cache will otherwise serve a stale listing after files change remotely.
- `updateListing=True` only when you are *replacing* the current level (e.g. re-listing after a search) rather than descending into a child. Getting this wrong corrupts the back-navigation stack.

This directly fixes two `PROJECT.md` bugs at once: `get_folder_items()` returning `None` on cancellation currently causes `items.extend(None)` to raise inside the framework, which means `endOfDirectory` is never reached and Kodi sits on a spinner until timeout. Return `[]`, and terminate in `finally`.

---

## Q2 — Vendoring strategy

### Layout and import paths

Kodi places the add-on's own root directory on `sys.path` before running `entrypoint.py` or `service.py`. Given `resources/__init__.py` and `resources/lib/__init__.py` already exist, everything imports as an ordinary package:

```python
from resources.lib.provider.onedrive import OneDriveProvider
from resources.lib.vendor.clouddrive.common.service.export import ExportService
```

**No `sys.path` manipulation is needed or wanted.** Every directory in the vendored tree needs an `__init__.py` (the upstream tree already has them).

### Collisions with other add-ons

Not a real risk, for two independent reasons:

1. Each invocation gets its own sub-interpreter with its own `sys.modules`, so two add-ons that both define `resources.lib.utils` never see each other.
2. Nesting under `resources/lib/vendor/` means the importable name is `resources.lib.vendor.clouddrive.common.*`, which cannot be reached by anything outside this add-on's root.

There **is** a related trap worth knowing about: Kodi 20 regressed `sys.path` ordering so that system `site-packages` came *before* the add-on directory and its `script.module.*` dependencies ([xbmc/xbmc#22985](https://github.com/xbmc/xbmc/issues/22985), fixed by PR #23244). A system-installed `requests`/`urllib3` could shadow a bundled one. Vendoring under your own package path is immune to this — which is an underrated argument for using stdlib `urllib.request` plus vendored code rather than declaring `script.module.requests`.

### Licensing

`script.module.clouddrive.common` is **GPL-3.0-or-later**, identical to `plugin.onedrive`. Copying its source into this repo is therefore licence-compatible with zero analysis and zero relicensing. The obligations are ordinary GPL attribution:

1. Keep the per-file GPL headers and copyright notices intact on every copied file.
2. Keep `LICENSE.txt` (GPL-3.0 text) at the repo root — already present.
3. **Mark modified files as changed, with a date.** GPL-3.0 §5(a). Practically: a one-line comment at the top of each edited vendored file, plus a `NOTICE.md` recording upstream repo URL, branch, and the exact commit you copied from.
4. `clouddrive/common/cache/LICENSE` (11.5 KB) is a **nested third-party licence** — `cache.py` is itself vendored code from somewhere else. If you keep that file, keep its licence text verbatim in the same directory. If you drop `cache.py`, drop the licence with it.
5. Upstream's `addon.xml` declares `script.module.dateutil` and `script.module.pyqrcode`. Those stay separate Kodi add-ons with their own licences; you are not vendoring them by vendoring clouddrive.common. Decide each on its own merits (see the note on `pyqrcode` under Q4).

There is no "GPL-2 into GPL-3" problem here at all — both sides are GPL-3.0-or-later. The only thing that would create a licensing question is pulling in a *different* upstream later; note it in `vendor/README.md` so the next person checks.

### The vendoring commit sequence

Do this as **two mechanical commits, before any rewriting**, so the diff stays reviewable:

1. **Copy verbatim.** Whole upstream tree → `resources/lib/vendor/clouddrive/`. Rewrite only `from clouddrive.common…` → `from resources.lib.vendor.clouddrive.common…`. Drop `<import addon="script.module.clouddrive.common"/>` from `addon.xml`. Add `NOTICE.md` and `vendor/README.md`. **The add-on must still work identically after this commit** (modulo the already-dead broker). If it doesn't, stop.
2. **Delete the provably unreachable.** `remote/signin.py`, `remote/errorreport.py`, `html.py`, the `pt_br` strings, the Eclipse project files, upstream's own `service.py`/`addon.xml`/`icon.png`.

Then rewriting begins, and each new-code phase ends by deleting the vendored module it replaced.

---

## Q3 — What to keep from `script.module.clouddrive.common`

Inventory taken from the upstream `matrix` branch tree (sizes are bytes of source).

| Subsystem | Upstream file(s) | Size | Verdict | Why |
|-----------|------------------|------|---------|-----|
| **HTTP client** | `remote/request.py` | 9.7 K | **REWRITE** | Entangled with `oauth2.py` and `errorreport.py`. Needs 429/`Retry-After` handling, generator-based paging, and per-call params (the class-level `_extra_parameters` bug lives at this seam). ~200 lines of new `graph/client.py` replaces it. |
| **OAuth base** | `remote/oauth2.py` | 5.1 K | **REWRITE — steal two ideas** | Replaced by decision. Worth keeping: the token record shape `{access_token, refresh_token, expires_in, date}` and the **600-second early-refresh margin** in `prepare_request()`. Worth discarding: everything else, and specifically the fact that it refreshes with **no locking at all**. |
| **Sign-in broker client** | `remote/signin.py` | 3.4 K | **DROP** | This *is* the dead Heroku dependency. Deleting it is the point of the milestone. |
| **Provider base** | `remote/provider.py` | 3.8 K | **REWRITE (shrink hard)** | 13 methods; `create_pin` / `fetch_tokens_info` / `refresh_access_tokens` / `_signin` all die with the broker. What remains — `configure`, change-token persistence, `cancel_operation` — is better expressed as **composition** (`OneDriveProvider(client, store)`) than as a template-method base class with one subclass. |
| **Account / drive store** | `account.py` + `db.py` (`SimpleKeyValueDb`) | 9.1 K | **REWRITE (simplify)** | SQLite for a handful of accounts is over-engineered, and it makes cross-interpreter locking harder than a single JSON file with `os.replace()`. Drop the `accounts.cfg` migration path entirely — every stored token it could migrate was issued by the dead broker and is worthless. |
| **Cache** | `cache/cache.py` + nested `LICENSE` | 5.1 K | **DROP for core; reconsider later** | Third-party vendored code with its own licence. A response cache masks correctness bugs during a rewrite. Reintroduce deliberately after browsing is verified, wired to the existing `cache-expiration-time` setting. |
| **Exceptions** | `exception.py` | 2.7 K | **KEEP (trim)** | Small, typed, already consumed by `onedrive.py` (`RequestException`, `ExceptionUtils.extract_exception`). Port the ~6 classes that are actually raised. |
| **Utils** | `utils.py` | 5.2 K | **KEEP (trim)** | `Utils.get_safe_value` / `Utils.default` / `get_extension` are used on nearly every line of `_extract_item`. Port ~10 functions into `provider/model.py` or a small `common.py`. Pure, trivially testable. |
| **UI base class** | `ui/addon.py` | **41.5 K** | **REWRITE — this is the main event** | One class holding routing, listing, playback, settings, account setup, drive selection, search UI, and slideshow. It is the reason the current 300-line repo is unreadable. Split into `routes.py` + `listing.py` + `play.py` + `accounts.py`. Expect this to be the single largest phase. |
| **Dialogs + skins** | `ui/dialog.py` + `skins/default/1080i/*.xml` | 18.8 K | **PARTIAL** | `pin-dialog.xml` is structurally close to what a device-code dialog needs (large code display, instruction text, cancel) — **keep the skin XML, rewrite the controller.** `export-*-dialog.xml` moves to the quarantine with export. |
| **Logger** | `ui/logger.py` | 1.6 K | **REWRITE (trivial)** | ~20 lines wrapping `xbmc.log`. Rewriting is faster than reviewing. |
| **Kodi utils** | `ui/utils.py` | 12.7 K | **REWRITE (trim)** | Holds `KodiUtils.lock` and misc helpers. Port only what the core path touches; the rest goes with the features that use it. |
| **Error reporting** | `remote/errorreport.py` | 3.4 K | **DROP** | Ships tracebacks to a third-party endpoint that is very likely as dead as the broker. Delete the code *and* the `report_error` setting. |
| **HTML listing** | `html.py` | 8.7 K | **DROP for now** | Pairs with `SourceService`. Comes back only if the HTTP listener comes back. |
| **DownloadService** | `service/download.py` + `service/base.py` | 8.7 K | **DEFER (quarantine)** | Small. Restore after core works, as-is. |
| **SourceService** | `service/source.py` | **18.9 K** | **DEFER, default OFF, audit before shipping** | This is the port-8586 HTTP listener. It must not be re-enabled until loopback binding and authentication are verified. See the Q7 note — it may also be the seek-after-expiry fix, which raises its priority. |
| **ExportService** | `service/export.py` + `export.py` | **35.1 K** | **DEFER (quarantine)** | Largest single file in the tree. Pure quarantine; touch nothing. |
| **PlayerService** | `service/player.py` | 7.6 K | **DEFER — rewrite when restored** | Resume/watched sync. ~200 lines; by the time you restore it, rewriting against the new `GraphClient` will be cheaper than adapting it. |
| **Service runner** | `service/utils.py` | 1.6 K | **REWRITE (trivial)** | `ServiceUtil.run([...])` thread launcher. Replace with an `xbmc.Monitor().waitForAbort()` loop so Kodi shuts down promptly. |

**Net for the core milestone:** roughly **8 KB** of vendored source survives as running code (`exception.py` + `utils.py` fragments + one skin XML). About **73 KB** goes into quarantine for later restoration. About **32 KB** is deleted outright. Everything on the core path is new.

That is the honest shape of this decision, and it should inform phase sizing: **"vendor the module" is a small mechanical phase; "replace `ui/addon.py`" is a large one.**

---

## Q4 — Where the auth layer belongs

Four components, one direction of dependency, no cycles. Each interface below is the contract a phase must satisfy.

### (a) Device-code flow + token lifecycle — `auth/device_flow.py`

Knows the Entra protocol. Knows nothing about disk, Kodi, or Graph.

```python
@dataclass(frozen=True)
class DeviceChallenge:
    device_code: str
    user_code: str
    verification_uri: str
    message: str
    expires_at: float      # monotonic-safe absolute deadline
    interval: int          # seconds between polls

class DeviceFlow:
    def __init__(self, client_id: str, tenant: str, scopes: Sequence[str],
                 http: HttpFn): ...

    def start(self) -> DeviceChallenge:
        """POST /{tenant}/oauth2/v2.0/devicecode"""

    def poll(self, ch: DeviceChallenge,
             sleep: Callable[[float], bool]) -> TokenSet:
        """POST /{tenant}/oauth2/v2.0/token until success or terminal error.
           `sleep(seconds) -> aborted` is injected so Kodi's Monitor can
           cancel it, and so tests can run instantly."""

    def refresh(self, refresh_token: str) -> TokenSet:
        """Same token endpoint, grant_type=refresh_token."""
```

Protocol facts this module encodes, verified against Microsoft's reference:

- Endpoints: `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode` and `.../token`. `tenant` ∈ `common` | `consumers` | `organizations` | GUID. For an add-on serving both Personal and Business, **`common`**.
- Token request: `grant_type=urn:ietf:params:oauth:grant-type:device_code`, plus `client_id` and `device_code`.
- Response carries `interval` — **poll at that rate, not a hard-coded 5s**. Default `expires_in` is 15 minutes.
- Polling errors and the required client action:
  | Error | Action |
  |---|---|
  | `authorization_pending` | wait ≥ `interval`, retry |
  | `authorization_declined` | stop, revert to unauthenticated |
  | `bad_verification_code` | stop, you sent a wrong `device_code` |
  | `expired_token` | stop, `expires_in` exceeded |
- **`offline_access` must be in `scope`** or you get no `refresh_token` and the add-on is useless after an hour. Recommended scope set: `offline_access Files.Read Files.Read.All User.Read`.
- **`verification_uri_complete` is explicitly not supported by Microsoft**, even though RFC 8628 lists it. You cannot render a one-tap QR code that pre-fills the user code — the QR can only carry the plain `verification_uri` (`https://microsoft.com/devicelogin`) and the user still types the 8-9 character code. This is worth knowing before designing the dialog; it also means `pyqrcode` (already an upstream dependency) buys real UX value on a TV and is worth keeping deliberately rather than dropping with `signin.py`.
- The Azure app registration must have **`allowPublicClient: true`** ("Allow public client flows" → Yes). Without it the token endpoint returns `AADSTS7000218` demanding a `client_secret`, *even for a device-code request*. Put this in the maintainer's registration doc as a numbered step, because the error message actively misleads you toward adding a secret.

### (b) Token storage — `auth/store.py`

Knows the filesystem. Knows nothing about OAuth.

```python
class TokenStore:
    def __init__(self, profile_dir: str): ...
    def load(self) -> TokenSet | None: ...
    def save(self, t: TokenSet) -> None:      # write temp + os.replace (atomic)
    def clear(self) -> None: ...
    @contextmanager
    def refresh_lock(self, timeout: float = 30.0): ...
```

Path: `xbmcvfs.translatePath('special://profile/addon_data/plugin.onedrive/')`. Note that `translatePath` **moved from `xbmc` to `xbmcvfs` in Kodi 19** — a Kodi-20-migration item in its own right. Resolve the path once in `kodi/settings.py` and inject it, so `TokenStore` itself stays Kodi-free and unit-testable with `tmp_path`.

Store the tokens as a single JSON document, `chmod 0600` where the platform supports it. There is no OS keychain available on Android TV from Kodi Python, so file permissions plus the fact that OneDrive tokens live on the user's own device is the realistic security posture — matching the `PROJECT.md` constraint "OAuth tokens stay on the device."

### (c) Authenticated Graph HTTP client — `graph/client.py`

Depends on a `TokenProvider`. Knows nothing about OneDrive.

```python
class GraphClient:
    def __init__(self, tokens: TokenProvider,
                 base_url: str = 'https://graph.microsoft.com/v1.0'): ...

    def request(self, method: str, url: str, *,
                params: dict | None = None,
                headers: dict | None = None,
                json_body: dict | None = None) -> dict:
        """Absolute URLs pass through untouched (needed for @odata.nextLink);
           relative paths are joined onto base_url.
           - 401 once  -> tokens.get_access_token(force_refresh=True), retry once
           - 429 / 503 -> honour Retry-After, bounded retries
           - 4xx/5xx   -> raise GraphError(status, code, message)"""

    def get_json(self, url, **params) -> dict: ...
```

Every request builds its headers fresh from `params` passed *in*. Nothing is stored on `self` that varies per call — this is the structural fix for the class-level `_extra_parameters` mutation bug, and it should be enforced by making the client hold no mutable request state at all.

### (d) The provider — `provider/onedrive.py`

```python
class OneDriveProvider:
    def __init__(self, client: GraphClient): ...
    def get_drives(self) -> list[Drive]: ...
    def list_folder(self, drive_id, *, path=None, item_id=None) -> Iterator[Item]:
    def get_item(self, drive_id, *, path=None, item_id=None) -> Item: ...
    def search(self, drive_id, query: str) -> Iterator[Item]: ...
    def get_subtitles(self, drive_id, item: Item) -> list[str]: ...
    def resolve_download_url(self, drive_id, item_id) -> str: ...
    def changes(self, drive_id, token: str | None) -> tuple[list[Item], str]: ...

def extract_item(raw: dict) -> Item | None:
    """PURE. dict -> Item. This is the function the fixture tests target."""
```

### The interface between (a)+(b) and everything else — `auth/session.py`

`TokenProvider` is the **only** type the rest of the codebase ever sees. It is deliberately a one-method interface:

```python
class TokenProvider(Protocol):
    def get_access_token(self, *, force_refresh: bool = False) -> str: ...
```

Two implementations:

- `InteractiveTokenProvider` — used by the **plugin**. If no tokens exist, or refresh fails permanently, it may raise `NeedsSignIn`, which the route layer turns into the device-code dialog.
- `SilentTokenProvider` — used by the **service**. Identical refresh logic, but `NeedsSignIn` becomes a log line and a one-shot notification, never a dialog. This is the code-level expression of the "service is never interactive" rule.

Dependency direction, strictly one way and cycle-free:

```
routes → provider → graph.client → auth.session → auth.device_flow
                                                 → auth.store
routes → kodi.listing (Item → ListItem)
routes → kodi.dialogs → auth.device_flow   (sign-in flow only)
```

`auth.device_flow` and `auth.store` never import each other. `auth.session` is the only thing that imports both.

---

## Q5 — Token refresh under concurrency

### The correction that changes the design

The framing "the plugin process and the background service process" is not quite right, and the difference matters. They are **two CPython sub-interpreters on two threads inside one Kodi OS process**. That has three concrete consequences:

| Mechanism | Shared between plugin and service? | Verdict |
|---|---|---|
| `threading.Lock`, module globals, singletons | **No** — separate interpreters, separate module objects | Useless here |
| `xbmcgui.Window(10000)` properties | **Yes** — C++-backed string map | Good cache/signal, **not** a mutex |
| Files on disk | Yes | Source of truth |
| `fcntl.lockf` / POSIX record locks | **No** — record locks are *per process*; two sub-interpreters of the same process do not exclude each other | **Trap. Silently does nothing.** |
| `flock(2)` | Yes (per open-file-description) | Works on Linux/Android, **absent on Windows** |
| `os.open(path, O_CREAT \| O_EXCL)` | Yes, atomic, cross-platform | **Use this** |

The `fcntl.lockf` line is the important one. It is the obvious thing to reach for, it will pass a naive two-terminal test, and it will not protect you at all inside Kodi on Linux or Android.

### Recommended design: window cache + O_EXCL mutex + double-checked read

```python
# auth/session.py  (Kodi-specific bits injected, not imported)
SKEW = 300  # refresh 5 min early; upstream used 600 and that is also fine

def get_access_token(self, *, force_refresh=False) -> str:
    # 1. FAST PATH — no lock, no disk. Shared across interpreters.
    if not force_refresh:
        tok, exp = self._cache.get()           # Window(10000) properties
        if tok and exp - time.time() > SKEW:
            return tok

    # 2. SLOW PATH — serialise every refresher in this Kodi install.
    with self._store.refresh_lock(timeout=30):
        # 3. DOUBLE-CHECK inside the lock. Someone may have refreshed
        #    while we were blocked. This is what actually prevents the
        #    refresh-token race.
        t = self._store.load()
        if t and t.expires_at - time.time() > SKEW and not force_refresh:
            self._cache.put(t.access_token, t.expires_at)
            return t.access_token
        if t is None:
            raise NeedsSignIn()

        # 4. Refresh, PERSIST FIRST, then publish.
        try:
            new = self._flow.refresh(t.refresh_token)
        except OAuthError as e:
            if e.error == 'invalid_grant':
                # 5. Rotation-race recovery, see below.
                current = self._store.load()
                if current and current.refresh_token != t.refresh_token:
                    self._cache.put(current.access_token, current.expires_at)
                    return current.access_token
                self._store.clear()
                raise NeedsSignIn() from e
            raise
        self._store.save(new)                  # durable BEFORE use
        self._cache.put(new.access_token, new.expires_at)
        return new.access_token
```

The lock itself:

```python
@contextmanager
def refresh_lock(self, timeout=30.0):
    deadline = time.time() + timeout
    fd = None
    while fd is None:
        try:
            fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            # stale-lock breaker: a crashed interpreter leaves the file behind
            try:
                if time.time() - os.path.getmtime(self._lock_path) > 60:
                    os.unlink(self._lock_path)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                raise TimeoutError('token refresh lock')
            if self._sleep(0.2):     # Monitor.waitForAbort — Kodi shutdown wins
                raise Aborted()
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        try: os.unlink(self._lock_path)
        except OSError: pass
```

`self._sleep` is `xbmc.Monitor().waitForAbort` in production and `time.sleep`-returning-`False` in tests. Never busy-wait with `time.sleep` inside Kodi — it delays shutdown and, on Android, gets the add-on blamed for ANRs.

### The refresh-token rotation risk, specifically

Microsoft Entra rotates refresh tokens: a successful refresh returns a **new** `refresh_token` and the old one stops working. If the plugin and the service both POST the same `refresh_token`, one wins and the loser receives `invalid_grant` — which, taken at face value, signs the user out. On a TV, at the exact moment they pressed play. This is the failure mode most likely to make this add-on feel broken after it otherwise works.

Four layered mitigations, in order of importance:

1. **Serialise refreshes** with the mutex above. This alone removes the common case.
2. **Double-check inside the lock.** Waiting on the lock almost always means someone else just refreshed for you.
3. **Do not treat `invalid_grant` as terminal on first sight.** Re-read the store; if the persisted refresh token now differs from the one you sent, you lost a benign race — adopt the winner's tokens and continue. Only clear the store and prompt re-auth when `invalid_grant` comes back for the token that is *still* the persisted one.
4. **Persist before use.** Write the new token set to disk with `os.replace()` *before* returning the access token. A crash between "Microsoft rotated the token" and "we wrote it down" strands the user permanently; the window for that must be as close to zero as you can make it.

Additionally: **cache expiry aggressively, not lazily.** With a 300–600 s skew and a 3599 s access-token lifetime, a normal browsing session performs at most one refresh per hour and virtually never contends.

### What goes in the Window property, and what does not

`Window(10000)` properties are readable by **every add-on and skin in the Kodi install**. Therefore:

- **Cache:** access token + absolute expiry. Short-lived, already leaves the device on every request. Namespace the keys (`plugin.onedrive.at`, `plugin.onedrive.at_exp`).
- **Never cache:** the refresh token. It is a long-lived bearer credential for the user's entire OneDrive; putting it in a globally-readable string map is a genuine downgrade over a `0600` file.
- Clear both on sign-out via `clearProperty`.

If that exposure is unacceptable, the fallback is to skip the window cache entirely and read the JSON file every time — it is under 2 KB and a directory listing performs one read. That costs almost nothing and removes the shared-surface question. Worth offering as a setting only if it turns out to matter; otherwise pick one and document the trade-off.

---

## Q6 — Pagination and streaming

### The generator stack

Three layers, each independently testable:

```python
# graph/paging.py  — PURE
def iter_pages(client, url, params=None):
    """Yield each page dict. Follows @odata.nextLink iteratively."""
    while url:
        page = client.get_json(url, params=params)
        params = None            # nextLink already carries every query param
        yield page
        url = page.get('@odata.nextLink')

def iter_values(client, url, params=None):
    for page in iter_pages(client, url, params):
        for raw in page.get('value') or []:     # never index blindly
            yield raw
```

```python
# provider/onedrive.py  — PURE
def list_folder(self, drive_id, *, path=None, item_id=None):
    url = paths.children_url(drive_id, path=path, item_id=item_id)
    for raw in iter_values(self._client, url, dict(SELECT_FIELDS)):
        item = extract_item(raw)
        if item is not None:
            yield item
```

```python
# kodi/routes.py  — the only layer that knows about handles
CHUNK = 200

def _add_items_chunked(ctx, items):
    monitor = xbmc.Monitor()
    batch = []
    for item in items:
        batch.append((build_url(item), listing.to_list_item(item), item.is_folder))
        if len(batch) >= CHUNK:
            xbmcplugin.addDirectoryItems(ctx.handle, batch)
            batch.clear()
            if monitor.abortRequested():
                break                       # partial listing, NEVER None
    if batch:
        xbmcplugin.addDirectoryItems(ctx.handle, batch)
```

### What this does and does not buy you

`addDirectoryItems` is explicitly documented as chunk-friendly: *"large lists benefit over using the standard `addDirectoryItem()`, and you may call this more than once to add items in chunks."* So chunked adding is sanctioned, and it gives you:

- **Bounded memory** — never more than `CHUNK` `ListItem`s plus the current Graph page alive at once. Matters on Android TV boxes with 1–2 GB RAM listing a 10,000-file folder.
- **Early abort** — you stop making Graph requests the moment the user backs out, instead of paging a whole camera roll into the void.
- **No recursion ceiling** — this is the `PROJECT.md` item "convert recursive pagination to an iterative loop," and the generator form removes the ceiling by construction rather than by discipline.

Be honest about what it does **not** buy: **Kodi does not paint the directory until `endOfDirectory` returns.** Items added in chunk 1 are not visible while chunk 5 is being fetched. If a folder takes eight seconds, the user stares at a spinner for eight seconds regardless. If you want feedback on large folders, that is a separate mechanism — `xbmcgui.DialogProgressBG` updated per page, cancellable via `Monitor`.

### Paging rules that are easy to get wrong

1. **Follow `@odata.nextLink` verbatim.** It is an opaque absolute URL that already encodes `$select`, `$filter`, `$top`, and a skip token. Re-appending your own params to it is a real and common bug — hence `params = None` after the first iteration, and hence `GraphClient.request` must pass absolute URLs through without re-joining the base.
2. **`$top` is a hint.** Graph may return fewer items than requested and may page even when you asked for everything. Never infer "last page" from page size; the *only* end-of-collection signal is the absence of `@odata.nextLink`.
3. **Never build your own `$skip` paging.** It is not stable under concurrent modification.
4. **Cancellation returns `[]`, never `None`.** Together with the `finally: endOfDirectory(...)` contract from Q1, this closes the `items.extend(None)` crash permanently.
5. **Delta paging is a different shape.** `changes()` follows `@odata.nextLink` the same way but terminates on `@odata.deltaLink`, which is the token you persist. Same generator, different terminal key — worth a distinct function rather than a flag.

---

## Q7 — Data flow for playback

### The path a Graph item takes to the screen

```
1. LIST TIME
   provider.list_folder() ──► Item ──► listing.to_list_item()
                                       li.setProperty('IsPlayable','true')
                                       url = plugin://plugin.onedrive/
                                              ?action=_play&driveid=D&item_id=I
   xbmcplugin.addDirectoryItems(handle, [(url, li, False)])
   ── NO downloadUrl anywhere in this URL ──

2. USER PRESSES PLAY
   Kodi re-invokes the plugin at that plugin:// url, with a NEW handle

3. RESOLVE TIME  (kodi/play.py)
   tokens.get_access_token()
   GET /drives/D/items/I?select=id,name,size,file,@microsoft.graph.downloadUrl
   ──► 200 { "@microsoft.graph.downloadUrl": "https://…files.1drv.com/…" }
   li = xbmcgui.ListItem(path=download_url, offscreen=True)
   li.setSubtitles([sub_url, …])          # resolved in the same invocation
   xbmcplugin.setResolvedUrl(handle, True, li)      ← exactly once

4. PLAYBACK
   Kodi's curl reader GETs the preauth URL directly.
   No Authorization header. Range requests go to THIS url.
```

### `@microsoft.graph.downloadUrl` — the facts that constrain the design

Straight from the Microsoft reference for `driveItem: get content`:

- `GET /drives/{d}/items/{i}/content` returns **HTTP 302** with a `Location` header pointing at the same value as `@microsoft.graph.downloadUrl`.
- *"Preauthenticated download URLs are valid for a limited time. Use them immediately, as they might expire within minutes. You don't need to include an `Authorization` header when you access the download URL."*
- *"To download a partial range of bytes from the file, your app can use the `Range` header… You must append the `Range` header to the actual `@microsoft.graph.downloadUrl` URL and **not** to the request for `/content`."*

Three design consequences:

1. **Hand Kodi the `@microsoft.graph.downloadUrl`, not the `/content` endpoint.** Kodi's player seeks by issuing `Range` requests; Microsoft documents that `Range` belongs on the download URL. Handing Kodi `/content` also means Kodi must carry your bearer token through a 302, which is both fragile and a token-leak surface.
2. **Resolve at play time, never at list time.** An `expires within minutes` URL must not be embedded into a directory item URL, because Kodi *persists plugin URLs* — into the video library, into watched-state rows, and into exported `.strm` files on the user's disk. A `.strm` containing a `1drv.com` URL is dead by the time anyone opens it. `.strm` files must contain `plugin://plugin.onedrive/?action=_play&…`, which re-resolves every time.
3. **Do not cache the resolved URL** — not in the window, not on disk, not for "the next 30 seconds."

### `setResolvedUrl` timing

- **Exactly one call per playback invocation**, and it must happen. On any failure — auth, 404, network — call `setResolvedUrl(handle, False, xbmcgui.ListItem())`. Skipping it leaves Kodi on the busy dialog until it times out, which reads to the user as a freeze.
- **Never mix.** A single invocation either builds a directory (`addDirectoryItems` + `endOfDirectory`) or resolves playback (`setResolvedUrl`). Doing both, or neither, is the single most common cause of "my plugin won't play" threads.
- The `ListItem` you pass **inherits metadata from the directory item it was launched from**, so in practice you only need to set the path (and subtitles). Re-setting the full InfoTag here is wasted work.
- The `handle` for the playback invocation is a *different* integer from the listing invocation. Never stash a handle in a module global — with per-invocation sub-interpreters it would not survive anyway, but under the same-interpreter service it would be silently wrong.

### The seek-after-expiry problem — flag for verification

If the user pauses for twenty minutes and then seeks, Kodi's reader reconnects with a `Range` request against a URL that has since expired, and gets a 403. Kodi has no mechanism to ask the plugin to re-resolve mid-playback.

**Hypothesis (unverified, MEDIUM confidence):** this is a substantial part of why upstream built `SourceService` — a local HTTP server that Kodi plays *from*, which can re-resolve the preauth URL per range request. If true, `SourceService` is not merely a "share to other devices" nicety; it is the correctness fix for long-pause seeking, and its restore priority is higher than the "restored features" ordering in `PROJECT.md` implies.

**This needs a real device test before it drives any decision.** Play a large file on Android TV, pause 20–30 minutes, then seek forward. If it fails, `SourceService` (or a minimal loopback re-resolving proxy written fresh) moves up the roadmap. If it succeeds — Microsoft may issue longer-lived URLs in practice than the docs promise — the whole question goes away and `SourceService` stays deferred and off. Cheap test, large architectural consequence: **schedule it early, in the same phase that first achieves playback.**

---

## Q8 — Suggested build order

Authentication gates everything, but not everything is downstream of it. Two independent tracks converge at Layer 5.

```
      ┌─ TRACK P (pure, no auth, start immediately) ─────────────────┐
      │  P0  vendor commit (mechanical) + repo hygiene               │
      │  P1  provider/model.py, common utils, graph/paths.py         │
      │      + fixture tests: percent-encoding, OData quoting        │
      │  P2  extract_item()  + fixture tests (int durations,          │
      │      defensive dict access, video/audio/image mapping)       │
      │  P3  graph/paging.py + tests with a fake client              │
      │  P4  CI: pytest + kodi-addon-checker + the no-xbmc-import    │
      │      layering test                                           │
      └───────────────────────────────┬──────────────────────────────┘
                                      │
      ┌─ TRACK A (auth critical path) ┼──────────────────────────────┐
      │  A0  ⚠ MAINTAINER TASK: Azure app registration               │
      │      (allowPublicClient=true, scopes, multi-tenant+personal) │
      │      Blocks A2. Not code. Do it first.                       │
      │  A1  auth/tokens.py + auth/store.py + refresh_lock           │
      │      (pure pytest with tmp_path — no Kodi needed)            │
      │  A2  auth/device_flow.py  (needs A0 to test for real)        │
      │  A3  auth/session.py TokenProvider (A1 + A2)                 │
      │  A4  kodi/dialogs.py device-code dialog (reuse pin-dialog)   │
      │      ▶ FIRST USER-VISIBLE MILESTONE: sign-in succeeds        │
      └───────────────────────────────┬──────────────────────────────┘
                                      ▼
      5   graph/client.py             (A3; 401-retry, 429, absolute URLs)
      6   provider/onedrive.py        (5 + P2 + P3) — drives, folders
      7   kodi/routes.py + listing.py + entrypoint.py
          ▶ SECOND MILESTONE: browse a folder end to end
      8   kodi/play.py + setResolvedUrl
          ▶ THIRD MILESTONE: core value delivered
          ▶ RUN THE PAUSE-20-MIN-THEN-SEEK TEST HERE
      9   subtitles · search · pseudo-folders (recent / sharedWithMe)
     10   settings.xml v1 schema; delete sign-in-server + report_error
     11   service.py rewrite: Monitor loop, SilentTokenProvider,
          background refresh only
     12   build zip + self-hosted GitHub Kodi repo
     ── core milestone ends here ──
     13+  restore from vendor/, one per phase, deleting as you go:
          PlayerService (resume/watched) → DownloadService →
          ExportService (STRM) → slideshow → SourceService (audit first)
```

### Ordering rationale

- **A0 is a prerequisite of the whole project and it is not code.** The Azure registration must exist, with `allowPublicClient: true`, before device-code flow can be tested against anything real. Put it in phase 1 as a maintainer checklist item, not buried in an implementation phase. `AADSTS7000218` misdirects you toward adding a client secret, so getting this right early saves a confusing day.
- **Track P needs no auth and fixes half the listed bugs.** `extract_item`, path encoding, OData quoting, and pagination are pure functions over recorded JSON. They can be built and tested before a single token exists, which means the project produces verifiable progress on day one instead of waiting on Azure.
- **A1 before A2.** The token store and its cross-interpreter lock are the trickiest part to get right and the easiest part to test (it is just files and time). Building it before the network protocol means the concurrency design is settled before it can be papered over.
- **The vendor commit (P0) must be mechanical and land first.** If it is interleaved with rewriting, the diff becomes unreviewable and you lose the ability to answer "did vendoring break this, or did my rewrite?".
- **Do not delete the `addon.xml` import before the vendor commit, and do not vendor piecemeal.** The add-on should never be in a state where it neither has the external module nor a complete local copy.
- **Layer 7 is the big one.** Replacing 41 KB of `ui/addon.py` is where the schedule risk lives. Size the phase accordingly, and resist the urge to restore export or slideshow inside it.
- **Layer 10 (settings schema) can float.** The legacy schema still loads on Kodi 20+, so it is not a hard blocker — but it must land before the first `kodi-addon-checker` green run and before any real install test on Kodi 22.
- **Layer 11 is deliberately late.** The service does nothing useful until browsing works, and starting it early risks the exact failure this design forbids: an auth dialog at Kodi startup.
- **`SourceService` is last and conditional.** It carries the `allow_directory_listing` / port 8586 security concern from `PROJECT.md`. Unless the seek test in phase 8 promotes it, it stays off by default and ships only after a verified loopback-bound, authenticated audit.

---

## Anti-Patterns

### 1. Embedding the resolved download URL in a directory item URL

**What people do:** call `?select=@microsoft.graph.downloadUrl` at list time and put the `1drv.com` URL straight into the item.
**Why it's wrong:** the URL expires within minutes, and Kodi persists plugin URLs into the library, into watched-state rows, and into exported `.strm` files. Every export is dead on arrival.
**Instead:** directory URLs carry `driveid` + `item_id` only. Resolve inside the playback handler, every time.

### 2. Mutable request state on a shared object

**What people do:** `self._extra_parameters['filter'] = 'file ne null'` on a class-level dict (the live bug in `onedrive.py:167`).
**Why it's wrong:** the filter leaks into every subsequent listing, silently hiding folders after any search — a bug that looks like a Graph problem and is not.
**Instead:** `GraphClient` holds **no** mutable per-request state. Params are arguments, always.

### 3. Refreshing tokens without a cross-interpreter lock

**What people do:** what `remote/oauth2.py` does — check `time.time() > date + expires_in - 600`, refresh, carry on.
**Why it's wrong:** Entra rotates refresh tokens. Two racing refreshes mean one gets `invalid_grant` and the user is signed out mid-playback.
**Instead:** window-cache fast path, `O_EXCL` mutex, double-checked read inside the lock, `invalid_grant` rotation-race recovery.

### 4. Using `fcntl.lockf` for that lock

**What people do:** reach for POSIX record locks, since this is "two processes."
**Why it's wrong:** it is not two processes. Record locks are per-process and do not exclude two sub-interpreters of the same Kodi process on Linux or Android. It will appear to work in a two-terminal test and protect nothing in production.
**Instead:** `os.open(path, O_CREAT | O_EXCL)` with a stale-lock breaker. Atomic everywhere, including Windows.

### 5. Returning `None` from a listing function

**What people do:** `return None` on user cancellation (the current `get_folder_items()` / `search()`).
**Why it's wrong:** the caller does `items.extend(None)`, raises, and `endOfDirectory` is never reached — Kodi spins until timeout.
**Instead:** return `[]`; call `endOfDirectory` in a `finally`; pass `succeeded=False` on error so Kodi navigates back.

### 6. Recursive `@odata.nextLink` following

**What people do:** `process_files()` calls itself per page.
**Why it's wrong:** a large camera roll hits the recursion limit, and the whole result set is buffered before anything is displayed.
**Instead:** a `while url:` generator. Constant stack, bounded memory, cancellable between pages.

### 7. Re-appending query params to `@odata.nextLink`

**What people do:** pass the same `params` dict on every page.
**Why it's wrong:** `nextLink` is opaque and already contains `$select`/`$filter`/`$top`/skip-token. Duplicating them produces 400s or silently wrong pages.
**Instead:** send params on the first request only.

### 8. `import xbmc` inside parsing or protocol code

**What people do:** log with `xbmc.log`, read a setting, or resolve a path from inside `_extract_item`.
**Why it's wrong:** it makes the pure logic untestable without stubbing all of Kodi — which is precisely why this repo has zero tests today despite `_extract_item` being trivially testable.
**Instead:** inject a logger and a settings object. Enforce with a CI layering test that greps `auth/`, `graph/`, `provider/` for `import xbmc`.

### 9. Storing the refresh token in a Window property

**What people do:** cache the whole token set in `Window(10000)` for convenience.
**Why it's wrong:** those properties are readable by every add-on and skin installed. The refresh token is a long-lived bearer credential for the user's entire OneDrive.
**Instead:** access token + expiry only, namespaced; refresh token stays in the `0600` file.

### 10. `sys.path.append` to reach vendored code

**What people do:** `sys.path.append(os.path.join(addon_path, 'lib'))`.
**Why it's wrong:** unnecessary (Kodi already puts the add-on root on `sys.path`) and it re-opens the shadowing class of bug that xbmc#22985 caused.
**Instead:** ordinary package imports with `__init__.py` everywhere.

### 11. Interactive dialogs from the service

**What people do:** call `get_access_token()` from a service loop and let it raise into a sign-in dialog.
**Why it's wrong:** the service starts at `start="login"`, potentially before a user exists. A device-code dialog at Kodi startup is a bug report waiting to happen.
**Instead:** two `TokenProvider` implementations. `SilentTokenProvider` logs and notifies; it never prompts.

---

## Scaling Considerations

The relevant axis is **drive size and device class**, not user count — this is single-user software.

| Scale | Adjustments |
|-------|-------------|
| Folder < 200 items, desktop | Nothing. Single page, one `addDirectoryItems`, instant. |
| Folder 200–5,000 items | Chunked `addDirectoryItems` at 200; `offscreen=True` on every `ListItem`; `DialogProgressBG` for feedback. |
| Folder > 5,000 (camera roll) | Bounded generator is now load-bearing for memory. Consider `$top=999` to cut round-trips, and a hard cap with a "show more" pseudo-item rather than paging 30 seconds of nothing. |
| Android TV, 1–2 GB RAM | Memory is the binding constraint, not CPU. Never materialise a full listing. Never hold decoded thumbnails. |
| Library export over a whole drive | Delta queries, not full walks. Persist `@odata.deltaLink`; handle `resyncRequired` by clearing the token and re-baselining. |

### First bottlenecks, in the order you will actually hit them

1. **Graph round-trip latency on large folders.** Fix by requesting only the fields you map (`$select`) and raising `$top`, not by caching.
2. **Memory on Android TV.** Fix with the generator + chunk pipeline. This is why it is in the design from day one rather than added later.
3. **Throttling (HTTP 429).** Graph throttles per-app and per-user. `GraphClient` must honour `Retry-After` from the start; retrofitting it after the export service starts hammering delta queries is painful.
4. **Preauth URL expiry during long playback.** See the Q7 flag. Verify before designing around it.

---

## Integration Points

### External Services

| Service | Integration Pattern | Gotchas |
|---------|---------------------|---------|
| `login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode` | POST form, `client_id` + `scope` | `expires_in` defaults to 15 min; `verification_uri_complete` is **not** supported by Microsoft, so no one-tap QR |
| `…/oauth2/v2.0/token` (device grant) | poll at the returned `interval` | `authorization_pending` is normal, not an error; app must have `allowPublicClient: true` or you get `AADSTS7000218` |
| `…/oauth2/v2.0/token` (refresh) | POST `grant_type=refresh_token` | Refresh tokens **rotate**; `invalid_grant` may mean "you lost a race", not "user revoked" |
| `graph.microsoft.com/v1.0` | Bearer, JSON, `@odata.nextLink` paging | `$top` is a hint; nextLink is absolute and opaque; 429 carries `Retry-After` |
| `*.files.1drv.com` (preauth download) | plain GET, **no** `Authorization` header | expires "within minutes"; `Range` must target this URL, not `/content` |
| Kodi core | `xbmcplugin` handle per invocation | handle differs between listing and playback invocations; never cache it |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `entrypoint.py` ↔ `routes` | direct call, `(handle, params)` | entry point holds no logic |
| `routes` ↔ `provider` | direct call, returns `Iterator[Item]` | routes never sees Graph JSON |
| `provider` ↔ `graph.client` | constructor injection | provider never builds headers or touches `urllib` |
| `graph.client` ↔ `auth.session` | `TokenProvider` protocol, one method | client never sees a refresh token |
| `auth.session` ↔ `auth.store` | direct + `refresh_lock()` context manager | the only holder of the mutex |
| `auth.session` ↔ `auth.device_flow` | direct call | `device_flow` is stateless and Kodi-free |
| plugin interpreter ↔ service interpreter | `Window(10000)` properties + token file + `O_EXCL` lock | **no shared Python objects — ever** |
| new code ↔ `vendor/clouddrive/` | one adapter module per deferred service | vendored code must not import new modules |

---

## Confidence and Verification Notes

| Claim | Confidence | Basis |
|---|---|---|
| InfoTagVideo v20 setter list; `setDuration` takes int seconds | HIGH | Read directly from the official Kodi `InfoTagVideo` reference |
| `xbmcplugin` signatures; chunked `addDirectoryItems` is sanctioned | HIGH | Official Kodi `xbmcplugin` reference |
| `xbmc.python` is at 3.0.2 on master; 3.0.0 is a *minimum*, so it installs on 20/21/22 | HIGH | Read from `xbmc/addons/xbmc.python/addon.xml` on master |
| downloadUrl is preauth, "might expire within minutes", `Range` targets it not `/content` | HIGH | Quoted verbatim from Microsoft Graph `driveItem: get content` |
| Device-code endpoints, params, four polling errors, `offline_access` requirement, no `verification_uri_complete` | HIGH | Quoted from Microsoft's OAuth 2.0 device authorization grant reference |
| `allowPublicClient: true` required or `AADSTS7000218` | MEDIUM-HIGH | Microsoft troubleshooting article + corroborating reports |
| `clouddrive.common` file inventory and sizes; GPL-3.0-or-later | HIGH | Read from the GitHub tree API and the repo's own metadata |
| `Provider` / `OAuth2` interfaces and the 600 s refresh margin | MEDIUM | Read from upstream source, summarised rather than quoted in full |
| Plugin and service are sub-interpreters in one process, not separate OS processes | MEDIUM-HIGH | Kodi `CPythonInvoker` behaviour, corroborated by Kodi/LibreELEC issue reports |
| `fcntl.lockf` will not exclude two sub-interpreters of one process | MEDIUM | POSIX record-lock semantics applied to the above. **Verify with a two-interpreter test on Android before relying on it** — the design uses `O_EXCL` regardless, so a wrong inference here costs nothing |
| Refresh-token rotation causes `invalid_grant` on concurrent use | MEDIUM-HIGH | General OAuth rotation semantics + Microsoft-specific `invalid_grant` writeups; Microsoft does not publish an explicit grace-period guarantee, so assume none |
| `SourceService` exists partly to fix seek-after-expiry | **LOW — hypothesis** | Inference from the expiry docs + what a local re-resolving proxy would fix. Explicitly flagged for a device test in phase 8 |
| Kodi does not render the directory until `endOfDirectory` returns | MEDIUM | Consistent with the documented callback contract; no doc states it in those words |

**Note on confidence tiers:** `gsd-tools query classify-confidence` returns `LOW` for the `webfetch` and `websearch` providers because they are generic fetchers. The elevation to HIGH above is source-based, not provider-based: those claims come from directly reading first-party documentation (learn.microsoft.com, xbmc.github.io official Kodi docs, `raw.githubusercontent.com` on the actual upstream repos), and the specific wording is quoted rather than paraphrased. Claims resting on forum threads, third-party blogs, or inference are capped at MEDIUM or lower and labelled as such.

---

## Sources

**Official Kodi documentation**
- [Kodi Documentation: InfoTagVideo](https://xbmc.github.io/docs.kodi.tv/master/kodi-base/d9/dc2/group__python___info_tag_video.html)
- [Kodi Development: Library - xbmcplugin](https://xbmc.github.io/docs.kodi.tv/master/kodi-dev-kit/group__python__xbmcplugin.html)
- [Kodi Development: Python API v20](https://alwinesch.github.io/python_v20.html)
- [xbmc/addons/xbmc.python/addon.xml (master)](https://github.com/xbmc/xbmc/blob/master/addons/xbmc.python/addon.xml)
- [Python libraries - Official Kodi Wiki](https://kodi.wiki/view/Python_libraries)
- [Kodi 20 Regression: Python sys.path incorrect (xbmc/xbmc#22985)](https://github.com/xbmc/xbmc/issues/22985)
- [Kodi Documentation: CPythonInvoker Class Reference](https://xbmc.github.io/docs.kodi.tv/master/kodi-base/db/d58/class_c_python_invoker.html)

**Official Microsoft documentation**
- [Download driveItem content - Microsoft Graph v1.0](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0)
- [OAuth 2.0 device authorization grant - Microsoft identity platform](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code)
- [Invalid Client Error AADSTS7000218 When Authenticating to Microsoft Entra ID](https://learn.microsoft.com/en-us/troubleshoot/entra/entra-id/app-integration/confidential-client-application-authentication-error-aadsts7000218)
- [RFC 8628 — OAuth 2.0 Device Authorization Grant](https://tools.ietf.org/html/rfc8628)

**Upstream source (read directly)**
- [cguZZman/script.module.clouddrive.common](https://github.com/cguZZman/script.module.clouddrive.common) — GPL-3.0-or-later
- [`clouddrive/common/remote/provider.py`](https://github.com/cguZZman/script.module.clouddrive.common/blob/matrix/clouddrive/common/remote/provider.py)
- [`clouddrive/common/remote/oauth2.py`](https://github.com/cguZZman/script.module.clouddrive.common/blob/matrix/clouddrive/common/remote/oauth2.py)
- [`clouddrive/common/account.py`](https://github.com/cguZZman/script.module.clouddrive.common/blob/matrix/clouddrive/common/account.py)

**Secondary (MEDIUM/LOW — used only where labelled)**
- [tamland/kodi-plugin-routing](https://github.com/tamland/kodi-plugin-routing)
- [Kodi forum: Still Confused about setResolvedUrl, IsPlayable & IsFolder for ListItems](https://forum.kodi.tv/showthread.php?tid=316042)
- [Kodi forum: Proper use of xbmcplugin.setResolvedUrl](https://forum.kodi.tv/showthread.php?tid=365620)
- [Kodi forum: [Nexus] API changes to VideoStreamDetail and InfoTagVideo APIs](https://forum.kodi.tv/showthread.php?tid=370707)
- [Kodi forum: Import python module in kodi addon](https://forum.kodi.tv/showthread.php?tid=374837)
- [Nango: Microsoft OAuth refresh token invalid_grant](https://nango.dev/blog/microsoft-oauth-refresh-token-invalid-grant/)
- [Kodi 21.0 "Omega" release notes](https://kodi.tv/article/kodi-21-0-omega-release/)

---
*Architecture research for: Kodi 20+ self-contained OneDrive cloud-drive add-on*
*Researched: 2026-08-22*
