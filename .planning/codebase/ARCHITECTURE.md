<!-- refreshed: 2026-08-22 -->
# Architecture

**Analysis Date:** 2026-08-22

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     Kodi Add-on Runtime                      │
├──────────────────────────────┬──────────────────────────────┤
│  Plugin entry (UI/routing)   │  Service entry (background)  │
│      `entrypoint.py`         │        `service.py`          │
└──────────────┬───────────────┴──────────────┬───────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│  OneDriveAddon               │  │  DownloadService /           │
│  (CloudDriveAddon subclass)  │  │  SourceService /             │
│  `resources/lib/addon.py`    │  │  ExportService /             │
│                              │  │  PlayerService               │
│                              │  │  (from clouddrive.common)    │
└──────────────┬───────────────┘  └──────────────┬───────────────┘
               │                                  │
               └───────────────┬──────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  OneDrive provider (Provider subclass)                       │
│  `resources/lib/provider/onedrive.py`                        │
│  Maps Microsoft Graph JSON to common item dicts              │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  script.module.clouddrive.common (external Kodi module 1.4+) │
│  HTTP, OAuth 2.0, account manager, cache, UI, services       │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Microsoft Graph API `https://graph.microsoft.com/v1.0`      │
│  + Sign-in Server (OAuth broker, configurable in settings)   │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Plugin entry point | Instantiate `OneDriveAddon` and dispatch the Kodi plugin URL | `entrypoint.py` |
| Service entry point | Start the four long-running background services | `service.py` |
| `OneDriveAddon` | Kodi UI behavior: custom drive folders, action name remapping | `resources/lib/addon.py` |
| `OneDrive` provider | All Microsoft Graph calls and item normalization | `resources/lib/provider/onedrive.py` |
| Add-on manifest | Declares Kodi extension points, dependencies, metadata | `addon.xml` |
| Settings schema | User-visible settings (playback, export, slideshow, sign-in server) | `resources/settings.xml` |
| Localized strings | UI labels referenced by numeric msgctxt IDs | `resources/language/resource.language.en_gb/strings.po` |

## Pattern Overview

**Overall:** Thin provider plug-in over a shared framework (Template Method / Strategy).

**Key Characteristics:**
- Nearly all generic behavior (auth, HTTP, caching, listing UI, export, playback) lives in the external `script.module.clouddrive.common` module; this repo supplies only the OneDrive-specific specialization.
- Two independent Kodi extension points share the same provider class: `xbmc.python.pluginsource` (`entrypoint.py`) and `xbmc.service` (`service.py`).
- Subclassing is the extension mechanism: `OneDriveAddon(CloudDriveAddon)` and `OneDrive(Provider)` override hook methods rather than composing.
- The provider is effectively stateless per invocation aside from `self._driveid` and a persisted delta change token.

## Layers

**Entry layer:**
- Purpose: Kodi-invoked process bootstraps.
- Location: `entrypoint.py`, `service.py`
- Contains: Module-level instantiation and a single call (`route()` / `ServiceUtil.run(...)`).
- Depends on: Addon layer, provider layer, `clouddrive.common.service.*`
- Used by: Kodi core, via the extension points declared in `addon.xml`.

**Addon (UI) layer:**
- Purpose: Presentation decisions specific to OneDrive — which pseudo-folders to show per drive type and content type.
- Location: `resources/lib/addon.py`
- Contains: `OneDriveAddon` with `get_provider()`, `get_custom_drive_folders()`, `_rename_action()`.
- Depends on: `clouddrive.common.ui.addon.CloudDriveAddon`, `clouddrive.common.utils.Utils`, `OneDrive`.
- Used by: `entrypoint.py`.

**Provider (remote) layer:**
- Purpose: Talk to Microsoft Graph and translate responses into the framework's item schema.
- Location: `resources/lib/provider/onedrive.py`
- Contains: `OneDrive(Provider)` — `get_account`, `get_drives`, `get_drive_type_name`, `get_folder_items`, `get_item`, `search`, `get_subtitles`, `changes`, `process_files`, `_extract_item`, `on_exception`.
- Depends on: `clouddrive.common.remote.provider.Provider`, `clouddrive.common.exception`, `clouddrive.common.utils.Utils`.
- Used by: Addon layer and all four background services.

**Framework layer (external, not in this repo):**
- Purpose: HTTP with token refresh, account/drive persistence, caching, Kodi list rendering, HTTP directory-listing server, `.strm` export.
- Location: Kodi add-on `script.module.clouddrive.common` version `1.4.0` or newer, declared in `addon.xml`.

## Data Flow

### Primary Request Path (browse a folder)

1. Kodi invokes `plugin://plugin.onedrive/?action=...&driveid=...&path=...` and runs `OneDriveAddon().route()` (`entrypoint.py:20`).
2. `CloudDriveAddon.route()` parses params and calls the `_rename_action()` hook, which maps legacy actions (`open_folder` to `_list_folder`, `open_drive` to `_list_drive`) (`resources/lib/addon.py:55`).
3. The framework resolves the account/drive and calls `OneDrive.get_folder_items()` (`resources/lib/provider/onedrive.py:76`).
4. The provider builds a Graph path (`/drives/{driveid}/root:{path}:/children`, or the `sharedWithMe` / `recent` collections) and `self.get(...)` performs the authenticated call.
5. `process_files()` walks `@odata.nextLink` pages recursively and calls `_extract_item()` per entry (`resources/lib/provider/onedrive.py:94`).
6. Normalized item dicts (`id`, `name`, `folder` / `video` / `audio` / `image`, `thumbnail`, `download_info`) return to the framework, which renders Kodi list items.

### Drive root listing

1. `get_drives()` calls `/drives`, tolerating HTTP 403 (SharePoint-restricted tenants) via `ExceptionUtils.extract_exception` (`resources/lib/provider/onedrive.py:44`).
2. It then calls `/me/drives` and merges by drive id, de-duplicating against the first result set.
3. `get_custom_drive_folders()` appends pseudo-folders: `special/photos` and `special/cameraroll` for images, `special/music` for audio (personal drives only), plus `recent` for all and `sharedWithMe` for non-`documentLibrary` drives (`resources/lib/addon.py:34`).

### Background change detection (export / library sync)

1. `service.py` starts `ExportService(OneDrive)` alongside download, source, and player services.
2. `OneDrive.changes()` calls the persisted delta link, or `/drives/{driveid}/root/delta?token=latest` on first run (`resources/lib/provider/onedrive.py:219`).
3. `process_files()` extracts `@odata.deltaLink` into `extra_info['change_token']`, which is saved via `persist_change_token()`.
4. `on_exception()` resets the token to `None` on HTTP 404 so the next run re-baselines from scratch.

**State Management:**
- `self._driveid` is set by the framework per invocation.
- The delta change token is persisted by the framework (`persist_change_token` / `get_change_token`).
- Accounts and drives live in `self._account_manager` (framework-owned), queried via `get_by_driveid('drive', driveid)`.
- `self._extra_parameters` is a class-level dict; `search()` mutates it in place.

## Key Abstractions

**Provider:**
- Purpose: A cloud storage backend expressed as a fixed set of methods the framework calls.
- Examples: `resources/lib/provider/onedrive.py`
- Pattern: Template Method — the base class owns HTTP/auth; the subclass implements `_get_api_url`, `_get_request_headers`, and the item operations.

**Normalized item dict:**
- Purpose: Provider-agnostic media entry consumed by list rendering, export, and playback.
- Examples: `_extract_item()` at `resources/lib/provider/onedrive.py:117`
- Pattern: Plain dict with optional typed sub-dicts (`folder`, `video`, `audio`, `image`, `subtitles`, `download_info`); durations are normalized from milliseconds to seconds.

**Addon UI hook:**
- Purpose: Inject provider-specific folders and action names into the shared UI.
- Examples: `get_custom_drive_folders()`, `_rename_action()` in `resources/lib/addon.py`
- Pattern: Overridden hook methods on `CloudDriveAddon`.

## Entry Points

**Plugin source:**
- Location: `entrypoint.py`, declared `library="entrypoint.py"` in `addon.xml`
- Triggers: Any `plugin://plugin.onedrive/...` URL from Kodi; provides `image audio video` content.
- Responsibilities: Construct `OneDriveAddon` and route the request.

**Service:**
- Location: `service.py`, declared `<extension point="xbmc.service" start="login" />`
- Triggers: Kodi startup, at the login stage.
- Responsibilities: Run `DownloadService`, `SourceService`, `ExportService`, `PlayerService`, each parameterized with the `OneDrive` class.

**Module-run fallback:**
- Location: `resources/lib/addon.py:65` — `if __name__ == '__main__': OneDriveAddon().route()` allows running the addon module directly.

## Architectural Constraints

- **Runtime:** Python 3 only (`xbmc.python` 3.0.0), meaning Kodi 19 Matrix and newer. `urllib.parse` / `urllib.error` usage is Python-3 specific; the branch name `matrix` reflects this.
- **Hard external dependency:** Nothing runs without `script.module.clouddrive.common` 1.4.0 or newer. That module is not vendored here, so this repo cannot be executed, imported, or type-checked standalone.
- **Threading:** Four services run concurrently in the Kodi service process via `ServiceUtil.run` (`service.py:26`); each service receives the `OneDrive` class and constructs its own instance, so provider instances are not shared across threads.
- **Shared mutable class state:** `OneDrive._extra_parameters` is a class attribute mutated by `search()`, so changes leak across calls and instances.
- **Circular imports:** None. Import direction is strictly `entrypoint`/`service` to `addon` to `provider` to `clouddrive.common`.
- **Auth indirection:** OAuth 2.0 runs through an external Sign-in Server whose URL is a user setting (`sign-in-server` in `resources/settings.xml`); no client secret is stored in this repo.
- **Localization coupling:** Some labels resolve against the add-on's own strings (`self._addon`), others against the shared module's strings (`self._common_addon`); the two id spaces are independent.

## Anti-Patterns

### Mutating class-level `_extra_parameters`

**What happens:** `search()` does `self._extra_parameters['filter'] = 'file ne null'` on a dict defined at class scope (`resources/lib/provider/onedrive.py:167`).
**Why it's wrong:** The filter persists for every later `get_folder_items()` / `get_item()` call, silently hiding folders from listings after any search.
**Do this instead:** Build a per-call copy: `params = dict(self._extra_parameters); params['filter'] = ...` and pass `params` to `self.get`.

### String-concatenated Graph paths duplicated across methods

**What happens:** URLs are assembled by concatenation (`'/drives/'+item_driveid+'/items/' + item_id + '/children'`) and the `root:`/`:` path wrapping logic appears verbatim in both `get_folder_items()` and `get_item()` (`resources/lib/provider/onedrive.py:80`, `resources/lib/provider/onedrive.py:196`).
**Why it's wrong:** Unescaped ids and paths break on special characters, and the duplicated wrapping logic drifts when one copy is fixed.
**Do this instead:** Extract a single `_build_drive_path(driveid, path, item_id)` helper and quote segments with `urllib.parse.quote`, as `search()` and `get_subtitles()` already do.

### Magic path strings shared across layers

**What happens:** The literals `'sharedWithMe'` and `'recent'` are compared or produced in `resources/lib/addon.py:50` and in both `get_folder_items()` and `get_item()` in `resources/lib/provider/onedrive.py`.
**Why it's wrong:** Adding or renaming a pseudo-folder requires coordinated edits in unrelated files with no shared definition.
**Do this instead:** Define module-level constants in `resources/lib/provider/onedrive.py` and import them into the addon layer.

### Bare `Exception` for domain failures

**What happens:** `get_account()` raises `Exception('NoAccountInfo')` when `/me/` returns nothing (`resources/lib/provider/onedrive.py:33`).
**Why it's wrong:** Callers cannot distinguish this from an unrelated crash, so it cannot be handled selectively.
**Do this instead:** Raise a typed exception from `clouddrive.common.exception`, consistent with how `RequestException` is consumed elsewhere in the same file.

## Error Handling

**Strategy:** Let framework exceptions propagate; intercept only where a specific HTTP status has a meaningful recovery.

**Patterns:**
- Unwrap wrapped errors with `ExceptionUtils.extract_exception(ex, HTTPError)` before inspecting `.code` (`resources/lib/provider/onedrive.py:45`).
- Tolerate HTTP 403 on `/drives` and fall through to `/me/drives`.
- Pass an `on_exception` callback through `request_params` so `changes()` can reset a stale delta token on HTTP 404.
- Read all API fields defensively via `Utils.get_safe_value(obj, key, default)` and `Utils.default(...)` rather than direct indexing.
- Check `self.cancel_operation()` between pagination pages and return early when the user aborts.

## Cross-Cutting Concerns

**Logging:** No direct logging in this repo; delegated to `clouddrive.common`. Error reporting is opt-in via the `report_error` setting in `resources/settings.xml`.
**Validation:** None explicit — `Utils.get_safe_value` / `Utils.default` supply fallbacks instead of validating shapes.
**Authentication:** OAuth 2.0 access tokens are managed by the framework; `_get_request_headers()` returns `None` (no custom headers) and `_get_api_url()` pins the Graph v1.0 base URL.
**Localization:** All user-facing text is a numeric string id resolved via `self._addon.getLocalizedString()` or `self._common_addon.getLocalizedString()`.
**Caching:** Controlled by the `cache-expiration-time` setting; implemented entirely in the framework.

---

*Architecture analysis: 2026-08-22*
