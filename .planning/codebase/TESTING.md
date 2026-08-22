# Testing Patterns

**Analysis Date:** 2026-08-22

## Test Framework

**Runner:**
- **None.** No test framework is configured or vendored.
- No `pytest.ini`, `tox.ini`, `setup.cfg`, `pyproject.toml`, `noxfile.py`, or `conftest.py` exists in the repository.
- No `requirements-dev.txt` or any dependency manifest beyond `addon.xml`'s `<requires>` block.

**Assertion Library:** Not applicable.

**Run Commands:** None defined. There is no `make`, `npm`, or script-based task runner.

## Test File Organization

**Location:** No test files exist. `find . -name "test_*.py" -o -name "*_test.py"` returns nothing.

**Full Python inventory (346 lines total):**
- `entrypoint.py` (21)
- `service.py` (29)
- `resources/lib/addon.py` (68)
- `resources/lib/provider/onedrive.py` (228)
- `resources/__init__.py`, `resources/lib/__init__.py`, `resources/lib/provider/__init__.py` (empty)

**If tests are added, the recommended layout** (no precedent in-repo, so this is a proposal):
```
tests/
├── conftest.py                  # xbmc/xbmcaddon + clouddrive.common stubs
├── test_onedrive_provider.py    # covers resources/lib/provider/onedrive.py
└── fixtures/
    └── graph/                   # captured Microsoft Graph JSON responses
```
Keep `tests/` out of the packaged add-on (Kodi ships the repo tree as-is; exclude it in the release zip).

## Test Structure

No in-repo pattern exists. Suggested shape, matching the codebase's plain-dict style:

```python
def test_extract_item_maps_video_duration_to_seconds():
    provider = OneDrive()
    item = provider._extract_item({
        'id': 'abc',
        'name': 'movie.mkv',
        'video': {'width': 1920, 'height': 1080, 'duration': 5000},
    })
    assert item['video']['duration'] == 5
    assert item['name_extension'] == 'mkv'
```

## Mocking

**Framework:** None in use.

**What must be stubbed to test anything here:**
- Kodi's built-in modules — `xbmc`, `xbmcaddon`, `xbmcgui`, `xbmcplugin`, `xbmcvfs`. These exist only inside the Kodi runtime and are not pip-installable from this repo; inject fakes into `sys.modules` before importing add-on code.
- `script.module.clouddrive.common` — the `clouddrive.common.*` package is an external Kodi add-on dependency (`addon.xml` requires version `1.4.0`) and is **not vendored here**. `Provider`, `CloudDriveAddon`, `Utils`, `RequestException`, `ExceptionUtils`, `ServiceUtil`, and the four services in `service.py` all come from it.
- HTTP to Microsoft Graph — stub `OneDrive.get(...)` (inherited from `Provider`) rather than patching a socket layer; every remote call in `resources/lib/provider/onedrive.py` funnels through it.

**What NOT to mock:**
- `_extract_item` and `process_files` — these are pure dict transformations over Graph payloads and are the highest-value real code to exercise directly.
- `get_drive_type_name` — pure string mapping, test as-is.

## Fixtures and Factories

**Test Data:** None present. Capture real Microsoft Graph v1.0 responses (`/me/`, `/drives`, `/me/drives`, `/drives/{id}/root/children`, `/drives/{id}/root/delta`) as JSON fixtures, scrubbing account ids, `displayName`, and any `@microsoft.graph.downloadUrl` (those are pre-signed URLs).

## Coverage

**Requirements:** None enforced. No coverage tooling configured.

**Current coverage: 0%.** Every code path is unverified.

## Test Types

**Unit Tests:** Not present. Best candidates, in priority order:
1. `_extract_item` (`resources/lib/provider/onedrive.py`) — folder/video/audio/image/thumbnail branches, ms→s duration division, `remoteItem` unwrapping, `deleted` flag.
2. Path addressing in `get_folder_items` and `get_item` — `/` → `root`, leading-slash paths → `root:/a/b:`, and the `sharedWithMe` / `recent` special cases.
3. `get_drives` 403 fallback from `/drives` to `/me/drives` and the `drives_id_list` de-duplication.
4. `process_files` pagination via `@odata.nextLink` and `change_token` extraction from `@odata.deltaLink`.
5. `get_subtitles` extension filter (`srt`, `idx`, `sub`, `sbv`, `ass`, `ssa`, `smi`) and the `'` → `''` quote escaping in the search query.
6. `OneDriveAddon.get_custom_drive_folders` (`resources/lib/addon.py`) — personal vs business vs `documentLibrary` folder sets.
7. `OneDriveAddon._rename_action` action-name mapping.

**Integration Tests:** Not present. Would require a live OneDrive account and OAuth 2.0 tokens obtained through the external sign-in server (`https://github.com/cguZZman/drive-login`, configured under Settings / Advanced / Sign-in Server). Not automatable in CI without a dedicated test tenant.

**E2E Tests:** Not used. Verification is manual: install the add-on in Kodi, sign in, and exercise browse / search / slideshow / export-to-library / source-mode flows.

## CI

**Status:** No CI. `.github/` contains only `ISSUE_TEMPLATE/bug_report.md` and `ISSUE_TEMPLATE/feature_request.md` — there is no `.github/workflows/` directory.

**Minimum viable gate if CI is introduced:** a Python 3 syntax/compile check (`python -m compileall`) plus an XML well-formedness check on `addon.xml` and `resources/settings.xml`, since a malformed `addon.xml` breaks installation for all users.

## Common Patterns

**Async Testing:** Not applicable — no `async`/`await` in the codebase. Concurrency lives in `clouddrive.common.service.*` (`DownloadService`, `SourceService`, `ExportService`, `PlayerService` wired in `service.py`), outside this repo.

**Error Testing:** Assert the re-raise behavior of the `RequestException` / `HTTPError` unwrapping in `get_drives` (403 tolerated, all other codes re-raised) and that `on_exception` clears the change token via `persist_change_token(None)` on HTTP 404.

---

*Testing analysis: 2026-08-22*
