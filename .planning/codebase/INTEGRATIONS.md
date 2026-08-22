# External Integrations

**Analysis Date:** 2026-08-22

## APIs & External Services

**Cloud storage (primary):**
- Microsoft Graph API v1.0 - The single upstream data source. Base URL returned by `OneDrive._get_api_url()` in `resources/lib/provider/onedrive.py`: `https://graph.microsoft.com/v1.0`
  - SDK/Client: none. Raw REST calls via the inherited `Provider.get()` from `script.module.clouddrive.common`.
  - Auth: OAuth 2.0 bearer tokens passed as `access_tokens` into `get_account()` / `get_drives()`; no env var, tokens live in the clouddrive account store.
  - Endpoints used (all in `resources/lib/provider/onedrive.py`):
    - `GET /me/` - account identity (`get_account`)
    - `GET /drives`, `GET /me/drives` - drive enumeration (`get_drives`); a 403 on `/drives` is tolerated and only `/me/drives` is used
    - `GET /drives/{driveId}/items/{itemId}` and `/children` - item and folder listing (`get_item`, `get_folder_items`)
    - `GET /drives/{driveId}/root:{path}:/children` - path-addressed listing
    - `GET /drives/{driveId}/sharedWithMe`, `GET /drives/{driveId}/recent` - special views
    - `GET /drives/{driveId}/search(q='...')` - search and subtitle discovery (`search`, `get_subtitles`)
    - `GET /drives/{driveId}/root/delta?token=latest` - change tracking (`changes`)
  - Query parameters: `expand=thumbnails` (`_extra_parameters`), `filter=file ne null` during search.
  - Paging: follows `@odata.nextLink`; delta cursor read from `@odata.deltaLink` in `process_files`.
  - Direct download: pre-signed URL taken from `@microsoft.graph.downloadUrl` in `_extract_item`, consumed by `DownloadService` / `PlayerService`.

**Special personal-drive paths** (`resources/lib/addon.py`, `get_custom_drive_folders`): `special/photos`, `special/cameraroll`, `special/music`, plus `recent` and `sharedWithMe`. `sharedWithMe` is suppressed for `documentLibrary` (SharePoint) drives.

**Drive types supported** (`get_drive_type_name`): `personal` (OneDrive Personal), `business` (OneDrive for Business), `documentLibrary` (SharePoint Document Library).

## Data Storage

**Databases:**
- None in this repository. Any caching/state (accounts, change tokens, item cache) is owned by `script.module.clouddrive.common`. Change tokens are read/written through `get_change_token()` / `persist_change_token()` in `resources/lib/provider/onedrive.py`.
- Cache lifetime is user-controlled via the `cache-expiration-time` setting and can be flushed by `RunPlugin(plugin://plugin.onedrive/?action=_clear_cache)` (`resources/settings.xml`).

**File Storage:**
- Remote files stay on OneDrive and are streamed. Local writes are limited to Kodi library `.strm` export performed by `ExportService` (`service.py`), controlled by `clean_folder`, `no_extension_strm`, `hide_export_progress`.

**Caching:**
- In-module cache from the clouddrive common library; no external cache service.

## Authentication & Identity

**Auth Provider:**
- Microsoft identity platform via OAuth 2.0, brokered by an external sign-in server.
  - Implementation: the add-on never handles user credentials. The browser-based OAuth flow is delegated to the server configured by the `sign-in-server` setting in `resources/settings.xml`, default `https://drive-login.herokuapp.com`.
  - The broker is user-replaceable; its source is published at `https://github.com/cguZZman/drive-login` per the `<disclaimer>` in `addon.xml`.
  - The Kodi service extension is declared with `start="login"` in `addon.xml`, so `service.py` starts at the login stage.
  - Token acquisition/refresh and account persistence are handled by the clouddrive common `_account_manager`, used in `resources/lib/addon.py` (`get_by_driveid('drive', driveid)`).
  - Multiple personal and business accounts are supported concurrently.

## Monitoring & Observability

**Error Tracking:**
- Opt-in remote error reporting via the `report_error` setting (default `false`) in `resources/settings.xml`; the reporting transport lives in `script.module.clouddrive.common`.

**Logs:**
- Kodi log (`xbmc.log`) through the common module's logging helpers. No structured logging or third-party log service.

## CI/CD & Deployment

**Hosting:**
- Distributed via the official Kodi add-on repository (`https://addons.kodi.tv/show/plugin.onedrive`); source of record `https://github.com/cguZZman/plugin.onedrive`.

**CI Pipeline:**
- None. `.github/` holds only `ISSUE_TEMPLATE/bug_report.md` and `ISSUE_TEMPLATE/feature_request.md`.

## Environment Configuration

**Required env vars:**
- None. Configuration is entirely Kodi add-on settings (`resources/settings.xml`).

**Secrets location:**
- No secrets are stored in the repository. OAuth client credentials live on the external sign-in server; user access/refresh tokens live in the Kodi user profile managed by `script.module.clouddrive.common`.

## Webhooks & Callbacks

**Incoming:**
- OAuth redirect callback is received by the external sign-in server, not by this add-on.
- Local HTTP listener for directory listing / streaming, enabled by `allow_directory_listing` on port `port_directory_listing` (default `8586`), served by `SourceService` (`service.py`).

**Outgoing:**
- None. Change detection is pull-based polling of the Graph delta endpoint in `OneDrive.changes()` rather than push notifications/subscriptions.

**Kodi-internal callbacks** (`resources/settings.xml`, `resources/lib/addon.py`):
- `plugin://plugin.onedrive/?action=_clear_cache`
- `plugin://plugin.onedrive/?action=_open_common_settings`
- `plugin://plugin.onedrive/?action=_slideshow` (context menu, built with `urllib.parse.urlencode`)

---

*Integration audit: 2026-08-22*
