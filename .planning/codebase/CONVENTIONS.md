# Coding Conventions

**Analysis Date:** 2026-08-22

## Naming Patterns

**Files:**
- Lowercase, single word, no separators: `entrypoint.py`, `service.py`, `resources/lib/addon.py`, `resources/lib/provider/onedrive.py`
- Package dirs mirror module role: `resources/lib/` (library code), `resources/lib/provider/` (remote provider impl)
- Every package dir carries an empty `__init__.py`: `resources/__init__.py`, `resources/lib/__init__.py`, `resources/lib/provider/__init__.py`

**Classes:**
- `PascalCase`, named after the provider or the Kodi role they fulfill: `OneDrive` (`resources/lib/provider/onedrive.py`), `OneDriveAddon` (`resources/lib/addon.py`)
- One public class per module.

**Functions/Methods:**
- `snake_case` throughout: `get_folder_items`, `get_drive_type_name`, `process_files`
- Leading underscore marks internal/protected members: `_extract_item`, `_get_api_url`, `_get_request_headers` (`resources/lib/provider/onedrive.py`), `_rename_action` (`resources/lib/addon.py`)
- Public methods on `OneDrive` implement the `clouddrive.common.remote.provider.Provider` contract — override, do not rename.

**Variables:**
- `snake_case` locals: `item_driveid`, `drives_id_list`, `parent_reference`, `next_files`
- Short loop vars for raw API payload entries: `f` for a file dict, `ex` / `httpex` for exceptions.

**Class attributes:**
- Underscore-prefixed class-level state: `_provider`, `_action` (`resources/lib/addon.py`), `_extra_parameters` (`resources/lib/provider/onedrive.py`)
- Inherited attributes from the common module keep their names: `self._driveid`, `self._addon`, `self._common_addon`, `self._addon_params`, `self._content_type`, `self._account_manager`, `self._addon_url`

**Dict keys (internal item model):**
- `snake_case` for the add-on's normalized model: `name_extension`, `last_modified_date`, `drive_id`, `download_info`
- Microsoft Graph `camelCase` keys are only read, never propagated: `displayName`, `driveType`, `lastModifiedDateTime`, `@microsoft.graph.downloadUrl`

## Code Style

**Formatting:**
- No formatter or linter configured. No `.editorconfig`, `setup.cfg`, `pyproject.toml`, `.flake8`, or pre-commit config exists.
- 4-space indent. No trailing-newline enforcement (`service.py` ends without one).
- Long lines are accepted; URL-building strings routinely exceed 120 chars (`get_subtitles` in `resources/lib/provider/onedrive.py`).
- Spaces around `=` in keyword arguments is the local habit (`parameters = self._extra_parameters`, `source_mode = False`) — contrary to PEP 8 but consistent here.
- Dict literals often put a space before the colon (`'id' : f['id']`). Match the surrounding block rather than reformatting.

**Linting:**
- None. Avoid lint-driven mass reformatting; it would swamp the diff of a 346-line codebase.

**License header:**
- **Required on every `.py` file.** Copy the exact 19-line GPL-3.0 banner from `entrypoint.py` verbatim (including the "Cloud Drive Common Module for Kodi is distributed..." line) at the very top of any new module, before imports.

## Import Organization

**Order observed** (`resources/lib/addon.py`, `resources/lib/provider/onedrive.py`):
1. Standard library (`import urllib`)
2. `clouddrive.common.*` shared-module imports
3. Local `resources.lib.*` imports
4. Stdlib `from` imports may trail the group (`from urllib.error import HTTPError` sits last in `resources/lib/provider/onedrive.py`) — grouping is loose; keep new imports near their kin.

**Python 3 only:**
- Targets `xbmc.python` 3.0.0 (`addon.xml`). Use `urllib.parse.urlencode`, `urllib.parse.quote`, `from urllib.error import HTTPError`.
- `.pydevproject` still declares `python 2.7` — stale IDE metadata, ignore it.

**No path aliases.** Absolute imports rooted at the add-on directory only.

## Error Handling

**Patterns:**
- Wrap optional/permission-sensitive API calls in `try/except RequestException`, unwrap the underlying HTTP error, and re-raise unless it is the tolerated status:
  ```python
  except RequestException as ex:
      httpex = ExceptionUtils.extract_exception(ex, HTTPError)
      if not httpex or httpex.code != 403:
          raise ex
  ```
  (`get_drives`, `resources/lib/provider/onedrive.py`) — a 403 on `/drives` is expected for personal accounts, so it falls through to `/me/drives`.
- Async/streamed failures use an `on_exception(self, request, e)` callback passed via `request_params={'on_exception': self.on_exception}` (`changes()`), which resets the delta token on HTTP 404 instead of raising.
- Raise bare `Exception('SomeCode')` with a symbolic string code for domain errors surfaced to the common UI layer: `raise Exception('NoAccountInfo')` (`get_account`).
- Never swallow exceptions silently; every `except` either re-raises or performs a documented recovery.

**Defensive access is preferred over try/except:**
- `Utils.get_safe_value(dict, key, default)` for every optional Graph field — do not use `dict[key]` unless the Graph schema guarantees it (`id`, `value`, `driveType`).
- `Utils.default(value, fallback)` for None-coalescing; `item_driveid = Utils.default(item_driveid, self._driveid)` opens nearly every provider method.
- Membership tests as feature detection: `if 'folder' in f:`, `if 'video' in f:`, `'deleted': 'deleted' in f`.

**Cancellation:**
- After any potentially long remote call, check and bail: `if self.cancel_operation(): return` (`get_folder_items`, `search`, `process_files`).

## Logging

**Framework:** None used directly in this repo — no `xbmc.log`, `print`, or `logging` calls anywhere. Logging is delegated to `clouddrive.common`.

**Pattern:** If logging is needed, use the common module's logger rather than `print` or `xbmc.log` directly.

## Comments

**When to Comment:**
- The codebase is comment-free apart from license headers. Logic is expected to be self-evident from method names.
- Add a comment only for non-obvious protocol quirks (why a 403 is tolerated, why `root:path:` addressing is used) — those are currently undocumented and are the right place for the first comments.

**Docstrings:** None present. No docstring convention to follow.

## Function Design

**Size:** Small-to-medium. `_extract_item` (~50 lines) is the largest and is a flat mapping function — acceptable. Keep transformation logic in one place rather than splitting field-by-field.

**Parameters:**
- Keyword arguments with defaults are the norm; provider entry points accept `item_driveid=None, item_id=None, path=None` plus optional flags (`include_download_info=False`, `find_subtitles=False`) and callbacks (`on_items_page_completed=None`, `on_before_add_item=None`).
- Callbacks are invoked guarded: `if on_before_add_item: on_before_add_item(item)`.

**Return Values:**
- Return plain `dict` / `list` structures matching the normalized item model produced by `_extract_item`; no custom classes.
- Bare `return` (implicit `None`) signals "cancelled" or "not applicable" (e.g. `get_item` for `sharedWithMe` / `recent`).

**Pagination:**
- Follow `@odata.nextLink` recursively and `items.extend(...)` the recursion result (`process_files`).
- Persist `@odata.deltaLink` into the caller-supplied `extra_info` dict, then call `self.persist_change_token(...)` in `changes()`.

## Module Design

**Exports:** No `__all__`, no barrel files. All `__init__.py` files are intentionally empty.

**Entry points:**
- Plugin: `entrypoint.py` → `OneDriveAddon().route()` (declared in `addon.xml` as `xbmc.python.pluginsource`)
- Service: `service.py` → `ServiceUtil.run([...])` guarded by `if __name__ == '__main__':` (declared as `xbmc.service`, `start="login"`)
- `resources/lib/addon.py` also carries an `if __name__ == '__main__':` block for direct invocation.

**Extension pattern:**
- This repo is a thin provider shim over `script.module.clouddrive.common` (>= 1.4.0). New behavior belongs in the shared module unless it is OneDrive/Graph-specific.
- `OneDriveAddon` subclasses `CloudDriveAddon` and overrides only `get_provider`, `get_custom_drive_folders`, `_rename_action`.
- `OneDrive` subclasses `Provider` and implements the Graph-specific surface.

## Localization

- User-facing strings never appear as literals. Use `self._addon.getLocalizedString(32007)` for add-on strings and `self._common_addon.getLocalizedString(32053)` for shared-module strings (`resources/lib/addon.py`).
- Add new strings to `resources/language/resource.language.en_gb/strings.po`, and mirror in `resources/language/resource.language.he_il/strings.po`.

## Versioning

- Bump `version` on the `<addon>` element and append a `<news>` entry in `addon.xml` for each release.

---

*Convention analysis: 2026-08-22*
