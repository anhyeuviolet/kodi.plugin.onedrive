# Technology Stack

**Analysis Date:** 2026-08-22

## Languages

**Primary:**
- Python 3 - All add-on logic: `entrypoint.py`, `service.py`, `resources/lib/addon.py`, `resources/lib/provider/onedrive.py`

**Secondary:**
- XML - Kodi add-on manifest and settings: `addon.xml`, `resources/settings.xml`
- GNU gettext PO - Localized strings: `resources/language/resource.language.en_gb/strings.po`, `resources/language/resource.language.he_il/strings.po`

## Runtime

**Environment:**
- Kodi `xbmc.python` 3.0.0 (Kodi 19 Matrix / 20 Nexus), declared in `addon.xml` `<requires>`
- CPython 3 (embedded in Kodi). Code uses `urllib.parse` / `urllib.error`, so Python 2 is not supported.

**Package Manager:**
- Kodi add-on repository (`https://addons.kodi.tv/show/plugin.onedrive`) — dependency resolution is done by Kodi via `<import>` entries in `addon.xml`.
- No `pip` / `requirements.txt`. Lockfile: not applicable to Kodi packaging.

## Frameworks

**Core:**
- Kodi Add-on API (`xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcaddon`) - Plugin + service runtime. Two extension points in `addon.xml`:
  - `xbmc.python.pluginsource` → `entrypoint.py` (provides `image audio video`)
  - `xbmc.service` (`start="login"`) → `service.py`
- `script.module.clouddrive.common` 1.4.0 - Shared cloud-drive framework this add-on specializes. Supplies `CloudDriveAddon` base UI class, `Provider` base remote class, account management, OAuth handling, caching, and the background services.

**Testing:**
- Not detected. No test files, test runner, or CI test workflow present. `.github/` contains only issue templates (`.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`).

**Build/Dev:**
- Eclipse PyDev project files: `.project`, `.pydevproject` (the latter still declares `python 2.7` as the interpreter grammar — stale relative to the Python 3 code).
- No build step — the repository is the shippable add-on directory.

## Key Dependencies

**Critical:**
- `script.module.clouddrive.common` 1.4.0 - Nearly all behavior comes from here. Imported in:
  - `resources/lib/addon.py`: `clouddrive.common.ui.addon.CloudDriveAddon`, `clouddrive.common.utils.Utils`
  - `resources/lib/provider/onedrive.py`: `clouddrive.common.remote.provider.Provider`, `clouddrive.common.exception.RequestException`, `ExceptionUtils`
  - `service.py`: `clouddrive.common.service.download.DownloadService`, `.source.SourceService`, `.export.ExportService`, `.player.PlayerService`, `.utils.ServiceUtil`
- `xbmc.python` 3.0.0 - Host runtime ABI.

**Infrastructure:**
- Python stdlib `urllib` (`urllib.parse.urlencode`, `urllib.parse.quote`, `urllib.error.HTTPError`) - URL building and HTTP error classification in `resources/lib/addon.py` and `resources/lib/provider/onedrive.py`. No `requests`; HTTP transport lives in the clouddrive common module.

## Configuration

**Environment:**
- No environment variables and no `.env` file. All configuration is Kodi add-on settings defined in `resources/settings.xml`, stored by Kodi in the user profile.
- Key settings:
  - `sign-in-server` (default `https://drive-login.herokuapp.com`) - external OAuth 2.0 broker
  - `cache-expiration-time` (default 5)
  - `allow_directory_listing` / `port_directory_listing` (default 8586) - local HTTP listing
  - `set_subtitle`, `resume_playing`, `save_resume_watched`, `ask_resume`
  - `clean_folder`, `no_extension_strm`, `hide_export_progress` (library export)
  - `slideshow_refresh_interval` (5), `slideshow_recursive`
  - `report_error` (default false)
- OAuth tokens/accounts are persisted by the clouddrive common account manager (accessed via `self._account_manager` in `resources/lib/addon.py`), not by files in this repo.

**Build:**
- `addon.xml` is the only packaging manifest: id `plugin.onedrive`, version `2.3.0`, license `GPL-3.0-or-later`, assets `icon.png` / `fanart.jpg`.
- `.gitignore` excludes `/.settings/`, `/.idea/`, `/env/`, `*.pyc`, `*.pyo`.

## Platform Requirements

**Development:**
- A Kodi 19+ installation to run the add-on; `script.module.clouddrive.common` 1.4.0 must be installed alongside.
- `<platform>all</platform>` in `addon.xml` — no OS-specific code.

**Production:**
- Distributed through the official Kodi add-on repository; installed into Kodi's `addons/plugin.onedrive` directory.
- Requires outbound HTTPS to Microsoft Graph and to the configured sign-in server.

---

*Stack analysis: 2026-08-22*
