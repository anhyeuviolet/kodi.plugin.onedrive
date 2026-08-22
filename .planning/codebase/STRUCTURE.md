# Codebase Structure

**Analysis Date:** 2026-08-22

## Directory Layout

```
plugin.onedrive/
├── addon.xml                                  # Kodi manifest: id, version, deps, extension points
├── entrypoint.py                              # Plugin entry point (xbmc.python.pluginsource)
├── service.py                                 # Background service entry point (xbmc.service)
├── icon.png                                   # Add-on icon asset
├── fanart.jpg                                 # Add-on fanart asset
├── LICENSE.txt                                # GPL-3.0-or-later
├── README.md                                  # Feature overview
├── .project / .pydevproject                   # Eclipse/PyDev IDE project files
├── .github/
│   └── ISSUE_TEMPLATE/                        # bug_report.md, feature_request.md
└── resources/
    ├── __init__.py
    ├── settings.xml                           # User settings schema (Kodi settings UI)
    ├── language/
    │   ├── resource.language.en_gb/strings.po # English UI strings
    │   └── resource.language.he_il/strings.po # Hebrew UI strings
    └── lib/
        ├── __init__.py
        ├── addon.py                           # OneDriveAddon (CloudDriveAddon subclass)
        └── provider/
            ├── __init__.py
            └── onedrive.py                    # OneDrive (Provider subclass), Graph API calls
```

Total Python source: 7 files, ~296 lines (3 are empty `__init__.py` package markers).

## Directory Purposes

**Repository root:**
- Purpose: Kodi add-on package root — this directory is what ships to the user as `plugin.onedrive`.
- Contains: Manifest, both entry-point scripts, image assets, license, README.
- Key files: `addon.xml`, `entrypoint.py`, `service.py`

**`resources/`:**
- Purpose: Kodi's conventional home for everything that is not the manifest or entry scripts.
- Contains: Settings schema, translations, Python package tree.
- Key files: `resources/settings.xml`

**`resources/lib/`:**
- Purpose: The add-on's Python package.
- Contains: The UI/addon layer.
- Key files: `resources/lib/addon.py`

**`resources/lib/provider/`:**
- Purpose: Backend implementations against remote APIs.
- Contains: One module per cloud provider (currently only OneDrive).
- Key files: `resources/lib/provider/onedrive.py`

**`resources/language/`:**
- Purpose: Kodi gettext translations, one directory per locale.
- Contains: `resource.language.<lang>_<country>/strings.po`
- Key files: `resources/language/resource.language.en_gb/strings.po` (source of truth for string ids)

**`.github/ISSUE_TEMPLATE/`:**
- Purpose: GitHub issue templates.
- Contains: `bug_report.md`, `feature_request.md`

## Key File Locations

**Entry Points:**
- `entrypoint.py`: Plugin URL handler — builds `OneDriveAddon` and calls `route()`.
- `service.py`: Starts `DownloadService`, `SourceService`, `ExportService`, `PlayerService` with the `OneDrive` class.
- `resources/lib/addon.py:65`: `__main__` guard allowing the addon module to be run directly.

**Configuration:**
- `addon.xml`: Add-on id `plugin.onedrive`, version, `xbmc.python` 3.0.0 and `script.module.clouddrive.common` 1.4.0 requirements, extension points, metadata, disclaimer.
- `resources/settings.xml`: Three setting categories — general (subtitles, resume, export, directory-listing port, slideshow), advanced (`sign-in-server`, `cache-expiration-time`, clear cache, open common settings), and error reporting.
- `.gitignore`: Ignores `/.settings/`, `/.idea/`, `/env/`, `*.pyc`, `*.pyo`.

**Core Logic:**
- `resources/lib/addon.py`: `OneDriveAddon` — `get_provider()`, `get_custom_drive_folders()`, `_rename_action()`.
- `resources/lib/provider/onedrive.py`: `OneDrive` — all Microsoft Graph requests and item normalization.

**Testing:**
- None. There is no test directory, test file, or test runner configuration in the repository.

## Naming Conventions

**Files:**
- Python modules: lowercase, no separators — `addon.py`, `onedrive.py`, `entrypoint.py`, `service.py`.
- Provider modules are named after the service they wrap: `provider/onedrive.py` defines `OneDrive`.
- Kodi-mandated names must not change: `addon.xml`, `resources/settings.xml`, `icon.png`, `fanart.jpg`.

**Directories:**
- lowercase single words — `resources`, `lib`, `provider`, `language`.
- Language directories follow the Kodi pattern `resource.language.<lang>_<country>` (lowercase), e.g. `resource.language.en_gb`.

**Code:**
- Classes: `PascalCase` — `OneDriveAddon`, `OneDrive`.
- Methods and variables: `snake_case` — `get_folder_items`, `item_driveid`, `include_download_info`.
- Non-public members: single leading underscore — `_provider`, `_extra_parameters`, `_extract_item`, `_rename_action`.
- Kodi plugin actions passed in URLs are `snake_case` with a leading underscore for internal ones — `_list_folder`, `_slideshow`, `_clear_cache`, `_open_common_settings`.
- Localized strings are referenced by numeric id (`32000`+) via `getLocalizedString`, never by literal text.
- Every source file starts with the GPL-3.0 header block copied from `entrypoint.py`.

## Where to Add New Code

**New OneDrive API operation (listing, metadata, search):**
- Implementation: add a method to `OneDrive` in `resources/lib/provider/onedrive.py`.
- Item shaping: extend `_extract_item()` in the same file so all callers get the new fields.

**New pseudo-folder or UI entry in a drive:**
- Implementation: extend `get_custom_drive_folders()` in `resources/lib/addon.py`.
- Handling: add the corresponding path branch to `get_folder_items()` and `get_item()` in `resources/lib/provider/onedrive.py`.
- Label: add a `msgctxt` entry to `resources/language/resource.language.en_gb/strings.po` and mirror it in `resource.language.he_il/strings.po`.

**New user setting:**
- Schema: add a `<setting>` to the appropriate `<category>` in `resources/settings.xml`.
- Label: add the numeric string to every `strings.po`.

**New background service:**
- Register it in the `ServiceUtil.run([...])` list in `service.py`, passing the `OneDrive` class (not an instance).

**New cloud provider (if ever generalized):**
- Implementation: new module under `resources/lib/provider/`, subclassing `clouddrive.common.remote.provider.Provider`.

**Shared helpers:**
- Prefer `clouddrive.common.utils.Utils` (`get_safe_value`, `default`, `str`, `get_extension`, `remove_extension`) before writing a new helper. There is no local utils module.

**Tests:**
- No location established. Any test suite would need to stub `clouddrive.common`, since that package is not vendored in this repo.

## Special Directories

**`resources/language/`:**
- Purpose: Locale `.po` files.
- Generated: No — hand-edited; upstream Kodi translations sync via Transifex.
- Committed: Yes.

**`.github/`:**
- Purpose: GitHub metadata and issue templates.
- Generated: No.
- Committed: Yes.

**`.planning/`:**
- Purpose: GSD planning artifacts, including this document under `.planning/codebase/`.
- Generated: Yes, by GSD commands.
- Committed: Yes.

**`.settings/`, `.idea/`, `env/`:**
- Purpose: IDE state and local virtualenv.
- Generated: Yes.
- Committed: No — listed in `.gitignore`. Note `.project` and `.pydevproject` (PyDev) are committed.

**External dependency (not a directory here):**
- `script.module.clouddrive.common` is installed by Kodi as a separate add-on. It is not vendored, so its source is not browsable from this repository.

---

*Structure analysis: 2026-08-22*
