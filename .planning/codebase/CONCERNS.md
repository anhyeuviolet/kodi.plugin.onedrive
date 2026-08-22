# Codebase Concerns

**Analysis Date:** 2026-08-22

## Tech Debt

**Mutable class-level state shared across calls:**
- Issue: `_extra_parameters` is a class attribute dict on `OneDrive`, and `search()` mutates it in place (`self._extra_parameters['filter'] = 'file ne null'`). The filter is never removed, so every later `get_folder_items()` / `get_item()` call in the same process silently inherits `filter=file ne null` and hides folders.
- Files: `resources/lib/provider/onedrive.py` (lines 28, 180-181, 85, 95, 200, 210)
- Impact: After a single search, folder listings are wrong until Kodi restarts the plugin process. Long-lived services (`service.py`) are most affected.
- Fix approach: Build a local copy per call — `params = dict(self._extra_parameters)` — and never mutate the class attribute.

**Duplicated entry points:**
- Issue: `entrypoint.py` and the `__main__` block at the bottom of `resources/lib/addon.py` both instantiate and route `OneDriveAddon`. Only `entrypoint.py` is registered in `addon.xml`.
- Files: `entrypoint.py`, `resources/lib/addon.py` (lines 66-67), `addon.xml` (line 6)
- Impact: Two places to keep in sync; dead code confuses maintainers.
- Fix approach: Delete the `__main__` block in `resources/lib/addon.py`.

**Implicit `urllib.parse` import:**
- Issue: Both modules do `import urllib` but call `urllib.parse.urlencode` / `urllib.parse.quote`. In CPython this only works because some other module already imported `urllib.parse`.
- Files: `resources/lib/addon.py` (lines 20, 43, 48), `resources/lib/provider/onedrive.py` (lines 24, 179, 189)
- Impact: `AttributeError: module 'urllib' has no attribute 'parse'` if the dependency chain ever stops importing it.
- Fix approach: Use `import urllib.parse` explicitly.

**Legacy settings format:**
- Issue: `resources/settings.xml` uses the pre-Kodi-19 `<settings><category>` schema with no `version="1"` attribute and relies on `window(home).property(iskrypton)` visibility hacks for Kodi Krypton (v17, EOL).
- Files: `resources/settings.xml`
- Impact: Kodi shims the old format today, but the shim is deprecated; settings may stop rendering in future Kodi releases.
- Fix approach: Migrate to the Kodi 19+ settings format (`<settings version="1"><section><category><group>`), drop Krypton-era visibility conditions.

**Hardcoded subtitle extension list:**
- Issue: Subtitle detection is a literal tuple inside the method.
- Files: `resources/lib/provider/onedrive.py` (line 193)
- Impact: Adding formats requires a code change; the list is not shared with the common module's own subtitle handling.
- Fix approach: Move to a module-level constant or source it from `clouddrive.common`.

## Known Bugs

**`items.extend(None)` on cancelled pagination:**
- Symptoms: `TypeError: 'NoneType' object is not iterable` when the user cancels/aborts during a multi-page folder listing.
- Files: `resources/lib/provider/onedrive.py` (lines 114-118)
- Trigger: `process_files` recurses for `@odata.nextLink`; the recursive call can hit `if self.cancel_operation(): return` (lines 116-117) and return `None`, which line 118 then passes to `items.extend()`.
- Workaround: None. Avoid cancelling during large listings.
- Fix: Capture the recursive result, and `return items` early when it is `None`.

**Callers receive `None` instead of a list on cancellation:**
- Symptoms: Downstream code iterating the result of `get_folder_items()` / `search()` crashes or silently shows nothing.
- Files: `resources/lib/provider/onedrive.py` (lines 96-97, 182-183)
- Trigger: `cancel_operation()` returns true mid-request.
- Fix: Return `[]` rather than bare `return`.

**Unescaped path interpolation into Graph URLs:**
- Symptoms: Malformed requests or wrong-item resolution for certain names.
- Files: `resources/lib/provider/onedrive.py` (lines 89-95, 204-210)
- Trigger: `path` is concatenated straight into the request URL with no percent-encoding, and the `root:<path>:` addressing form is built by naive string surgery. Folder/file names containing `#`, `?`, `%`, `+`, or `:` break it.
- Fix: Percent-encode each path segment with `urllib.parse.quote`.

**Unescaped single quotes in search queries:**
- Symptoms: Searches containing `'` fail with a Graph 400.
- Files: `resources/lib/provider/onedrive.py` (line 179) vs. (line 189)
- Trigger: `search()` inserts the user query into an OData `search(q='...')` literal after `urllib.parse.quote` only. A single quote terminates the OData string. `get_subtitles()` does handle this (`.replace("'","''")`), `search()` does not — an inconsistency showing the escape was known and missed.
- Fix: Apply `.replace("'", "''")` before quoting, matching line 189.

**Float durations passed to Kodi:**
- Symptoms: Type errors or inconsistent duration display depending on Kodi version.
- Files: `resources/lib/provider/onedrive.py` (lines 145, 152)
- Trigger: `duration` is computed with `/ 1000` (true division in Python 3), yielding a float, while Kodi InfoTag duration setters expect an integer. Kodi 20+ typed setters are strict.
- Fix: Use `int(... // 1000)`.

**Unguarded dictionary access on API responses:**
- Symptoms: `KeyError` traceback instead of a handled error.
- Files: `resources/lib/provider/onedrive.py` (lines 43, 50-55, 63-69, 102, 125)
- Trigger: `f['id']`, `me['id']`, `me['displayName']`, `drive['id']`, `drive['driveType']`, `response['value']`, `files['value']` are indexed directly while every other field goes through `Utils.get_safe_value`. Any Graph response shape change or error payload crashes.
- Fix: Route through `Utils.get_safe_value` and validate `value` presence.

## Security Considerations

**Third-party OAuth broker as default sign-in server:**
- Risk: All OAuth token exchange is proxied through an external service, so that host sees authorization codes and refresh tokens for the user's full OneDrive/SharePoint account.
- Files: `resources/settings.xml` (setting `sign-in-server`), `addon.xml` (disclaimer block)
- Current mitigation: The disclaimer discloses the design and points users at `https://github.com/cguZZman/drive-login` to self-host; the server URL is user-overridable.
- Recommendations: Move to PKCE with a public client so no broker holds secrets; at minimum, surface the broker host prominently at sign-in time.

**Default sign-in server host is a dead Heroku app:**
- Risk: `https://drive-login.herokuapp.com` — Heroku terminated free dynos in November 2022. The hostname is either unresolvable or, worse, re-registrable by a third party who would then receive OAuth traffic from every default install.
- Files: `resources/settings.xml` (setting `sign-in-server`)
- Current mitigation: None.
- Recommendations: Verify who controls that hostname today; repoint the default to a live, controlled host and ship it as a forced settings migration, not just a new default value (existing installs keep the stored old value).

**Local HTTP directory-listing server enabled by default:**
- Risk: `allow_directory_listing` defaults to `true` on port `8586`, binding a listener that serves drive content. Authentication and bind-address behaviour live in `script.module.clouddrive.common`, not in this repo, and are unverified.
- Files: `resources/settings.xml` (settings `allow_directory_listing`, `port_directory_listing`), `service.py` (`SourceService`)
- Current mitigation: The setting can be disabled manually.
- Recommendations: Confirm the listener binds to loopback and requires a token; default to off otherwise.

**Error reporting toggle with undocumented destination:**
- Risk: `report_error` ships error payloads somewhere unspecified in this repo; payloads may include drive/file names or tokens.
- Files: `resources/settings.xml` (setting `report_error`)
- Current mitigation: Defaults to `false`.
- Recommendations: Document the endpoint and the scrubbing applied before offering the toggle.

## Performance Bottlenecks

**Recursive, fully-buffered pagination:**
- Problem: Every page of a folder listing is accumulated into one in-memory list, and paging is done by recursion rather than a loop.
- Files: `resources/lib/provider/onedrive.py` (lines 100-119)
- Cause: `process_files` calls itself per `@odata.nextLink` and `extend`s the child result.
- Improvement path: Convert to a `while nextLink:` loop and stream via `on_items_page_completed` instead of retaining all items; this also removes the recursion-depth ceiling on very large drives.

**Double drive enumeration on every account load:**
- Problem: `get_drives` always issues `/drives` and then `/me/drives`, deduplicating client-side.
- Files: `resources/lib/provider/onedrive.py` (lines 45-71)
- Cause: `/drives` is only meaningful for business/SharePoint accounts but is attempted unconditionally; personal accounts pay a guaranteed failing round-trip (403 swallowed at lines 57-60).
- Improvement path: Skip `/drives` for known-personal accounts, or cache the 403 result per account.

**Subtitle search on every item fetch:**
- Problem: `get_item(find_subtitles=True)` issues an extra Graph search per played item and filters client-side across all results.
- Files: `resources/lib/provider/onedrive.py` (lines 186-195, 213-216)
- Cause: No server-side extension filter on the search.
- Improvement path: Constrain the query server-side, or cache results per parent folder.

## Fragile Areas

**Provider to common-module coupling:**
- Files: `resources/lib/provider/onedrive.py`, `resources/lib/addon.py`, `service.py`
- Why fragile: Nearly all behaviour (routing, auth, caching, services, UI) lives in `script.module.clouddrive.common`, which is not in this repo. This add-on supplies only ~300 lines of provider glue and overrides methods whose contracts are defined externally.
- Safe modification: Read the installed `script.module.clouddrive.common` source before changing any overridden method signature (`get_folder_items`, `process_files`, `changes`, `on_exception`, `get_custom_drive_folders`, `_rename_action`).
- Test coverage: None.

**Unpinned upper bound on the shared module:**
- Files: `addon.xml` (`script.module.clouddrive.common` version `1.4.0`)
- Why fragile: Kodi's `<import version=...>` is a minimum, not a pin. A future 2.x of the common module with changed base-class contracts would silently satisfy the requirement and break at runtime.
- Safe modification: Test against the exact common-module version shipped in the target Kodi repo before releasing.

**Change-token / delta sync:**
- Files: `resources/lib/provider/onedrive.py` (lines 219-229)
- Why fragile: `changes()` persists whatever `extra_info['change_token']` ended up as — including `None` when the delta response lacked `@odata.deltaLink` (which happens whenever `process_files` returns early on cancellation), silently resetting sync state. `on_exception` also clears the token on any 404, including transient ones.
- Safe modification: Only persist a non-`None` token; distinguish a `resyncRequired` response from a generic 404.

**Personal-account-only custom folders:**
- Files: `resources/lib/addon.py` (lines 36-55)
- Why fragile: Behaviour branches on `drive['type']` string literals (`personal`, `documentLibrary`) matched against Graph's `driveType`; a new or unexpected drive type silently degrades the menu with no warning.

## Scaling Limits

**Folder listing size:**
- Current capacity: Bounded by available memory and Python's recursion limit (default 1000 frames, i.e. ~1000 Graph pages).
- Limit: Very large folders exhaust memory or raise `RecursionError`.
- Scaling path: Iterative pagination plus streaming callbacks (see Performance Bottlenecks).

## Dependencies at Risk

**`script.module.clouddrive.common` 1.4.0:**
- Risk: Single upstream author; the add-on is inert without it. The latest commit in this repo is dated 2023-01-21, suggesting the family of add-ons is unmaintained.
- Impact: Total loss of function if the module is dropped from the Kodi repo or breaks on a new Kodi release.
- Migration plan: Vendor or fork the common module, or reimplement the needed surface in-repo.

**`xbmc.python` 3.0.0 (Kodi 19 Matrix):**
- Risk: Targets a Kodi API generation several major versions behind current Kodi. Kodi 21/22 compatibility is unverified — no CI proves it.
- Impact: The add-on may fail to load or hit deprecated-API removals on modern Kodi.
- Migration plan: Bump `xbmc.python`, replace deprecated InfoTag setters, retest against each target Kodi.

## Missing Critical Features

**No automated build/test/lint pipeline:**
- Problem: `.github/` contains only `ISSUE_TEMPLATE/bug_report.md` and `ISSUE_TEMPLATE/feature_request.md`; there is no `.github/workflows/` directory.
- Blocks: No Kodi add-on validation (`kodi-addon-checker`), no syntax check, no release automation. Regressions reach users directly.

**No dependency or development environment manifest:**
- Problem: No `requirements.txt`, `pyproject.toml`, or documented local dev setup; only IDE files (`.project`, `.pydevproject`) are committed.
- Blocks: Contributors cannot reproduce a working environment or run the add-on outside Kodi.

**Limited localization:**
- Problem: Only `resources/language/resource.language.en_gb/strings.po` and `resources/language/resource.language.he_il/strings.po` exist for a globally distributed add-on.
- Blocks: Non-English/Hebrew users see untranslated strings.

## Test Coverage Gaps

**Everything — there are no tests in the repository:**
- What's not tested: All of `resources/lib/provider/onedrive.py` and `resources/lib/addon.py`. No test files, no test runner config, no fixtures.
- Files: `resources/lib/provider/onedrive.py`, `resources/lib/addon.py`, `service.py`, `entrypoint.py`
- Risk: The response-parsing logic in `_extract_item` and `process_files` is pure and highly testable, yet every one of the bugs listed above would have been caught by a handful of unit tests against recorded Graph JSON.
- Priority: High — start with `_extract_item`, `process_files` pagination, and the path-building branches in `get_folder_items` / `get_item`, using recorded Graph responses and a stubbed `Provider.get`.

**Kodi-version compatibility untested:**
- What's not tested: Behaviour on Kodi 20/21/22; the code declares `xbmc.python` 3.0.0 (Kodi 19).
- Files: `addon.xml`, `resources/settings.xml`
- Risk: Silent breakage for most current users.
- Priority: High.

**Business / SharePoint code paths untested:**
- What's not tested: The `documentLibrary` and `business` branches in `get_drive_type_name` and `get_custom_drive_folders`, and the 403-swallowing path in `get_drives`.
- Files: `resources/lib/provider/onedrive.py` (lines 45-80), `resources/lib/addon.py` (lines 36-55)
- Risk: Regressions only surface for business account holders, who are a minority of reporters.
- Priority: Medium.

---

*Concerns audit: 2026-08-22*
