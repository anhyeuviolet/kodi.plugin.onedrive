# Vendored code

This add-on carries a copy of the Cloud Drive Common Module inside its own source tree instead of
depending on it as a separate Kodi add-on. This file is the record of that copy: where it came
from, what licence each part is under, what was deliberately left behind, what was changed
locally, and every way the add-on's behaviour now differs from the original.

It exists so that a future upstream diff, a future licence question and a future "was that already
broken?" all start from a written fact rather than from a guess. If you change anything under
`resources/lib/vendor/`, add a row here in the same commit.

## Upstream

| Field | Value |
|---|---|
| Repository | `https://github.com/cguZZman/script.module.clouddrive.common` |
| Branch | `matrix` |
| Version | `1.4.0` |
| Commit | `df68e9a589a6faef2b3228f7520e77729bc05d9b` |
| Commit date | 2023-01-21 |
| Commit subject | `Kodi 20 fix` |
| Licence | GPL-3.0-or-later |
| Vendored to | `resources/lib/vendor/clouddrive_common/` |

The copy is pinned to that commit, not to the branch. It was taken by checking out the commit and
comparing every copied file against the upstream blob **by git object id**, so "verbatim" is a
measured property of the bytes rather than a claim about the copy command. All 38 copied files
matched.

Upstream has exactly two branches, `krypton` and `matrix`, with `HEAD` on `matrix`. **There is no
`master` branch any longer.** This matters because `raw.githubusercontent.com` still serves content
for that dead ref, and what it serves is the 1.3.9 Python 2 line. Anyone re-deriving this copy from
a URL naming `master` will get the wrong code and it will look plausible. Re-derive from the commit
id above and from nothing else.

The vendored package path `resources/lib/vendor/clouddrive_common/` is fixed. Every import in the
tree is anchored to it, so moving or renaming the directory means rewriting all of them.
The upstream layout `clouddrive/common/X` collapses to `clouddrive_common/X`: the intermediate
level carried nothing, and upstream's `clouddrive/__init__.py` is not copied because
`clouddrive/common/__init__.py` becomes the vendored package's own marker.
`resources/lib/vendor/__init__.py` has no upstream counterpart and is a new, empty file.

**On the repository-wide sweep for the old module id.** The acceptance conditions for this work
ask for zero repository-wide occurrences of the upstream module's add-on id and zero occurrences of
the dynamic-evaluation construct. Read literally that is unsatisfiable, and always was: this file
and `CREDITS.md` are *required* to name the upstream module verbatim, and the test file is required
to name the construct it forbids. The operative form is therefore **zero occurrences outside the
record and planning paths**, which is exactly what the `source_scan` helper in
`tests/test_vendor_gates.py` implements — it reads every tracked text file except `.planning/`,
`tests/`, and the four documents `VENDORED.md`, `CREDITS.md`, `COVERAGE.md` and `README.md`. The
runnable form of both conditions is `test_no_hardcoded_module_id` and `test_no_eval` in that file.
Those two tests, not a bare `grep` over the whole checkout, are what "zero hits" means here.

## Licences

The whole combined work is **GPL-3.0-or-later**. The root `LICENSE.txt` is the licence for it.

| Subtree | Licence | Where the notice lives |
|---|---|---|
| This add-on's own code | GPL-3.0-or-later | Per-file headers, © 2017 Carlos Guzman (cguZZman) |
| `resources/lib/vendor/clouddrive_common/**` | GPL-3.0-or-later | Per-file headers, © 2017 Carlos Guzman (cguZZman) |
| `resources/lib/vendor/clouddrive_common/cache/LICENSE` | Apache-2.0 boilerplate — **provenance unresolved**, see below | The file itself, preserved verbatim in place |
| `resources/lib/vendor/pyqrcode/**` | BSD-3-Clause, © 2013 Michael Nooner | `resources/lib/vendor/pyqrcode/LICENSE.md` |
| `resources/lib/vendor/pyqrcode/png.py` | MIT, © 2006 Johann C. Rocholl and others | The file's own header, kept intact |

**One `LICENSE.txt`, not two.** Upstream's `LICENSE.txt` is byte-identical to this repository's
(sha256 `0b383d5a63da644f628d99c33976ea6487ed89aaa59f0b3257992deac1171e6b`), so a second copy would
have added nothing. It was deliberately not copied. Recorded here so a later reader does not
conclude that a licence file went missing during the lift.

**The Apache-2.0 file beside the cache module.** `clouddrive_common/cache/LICENSE` is unmodified
Apache-2.0 boilerplate. Its `[yyyy] [name of copyright owner]` placeholder was never filled in, so
it names nobody and grants nothing to anyone in particular. The file next to it, `cache/cache.py`,
carries a GPL-3.0 header naming the module's own author. Those two facts contradict each other and
**this record does not resolve the contradiction** — it states it. The file is preserved verbatim
and in place rather than deleted, because deleting it or asserting what it covers would settle the
question by assertion. It travels with the `cache/` subtree: if that subtree is dropped in a later
cleanup, this file goes with it.

Every vendored file that this repository has edited keeps its original copyright header. No header
was rewritten, replaced or re-attributed. `test_gpl_headers_intact` in `tests/test_vendor_gates.py`
enforces that, and holds the BSD and MIT files to their own upstream notices rather than excusing
them from carrying one.

## Excluded from the copy

Upstream files that were deliberately not copied, and why.

| Excluded | Reason |
|---|---|
| `resources/__init__.py` | Copying it creates a second importable top-level `resources` package and makes every import ambiguous. The failure shows up on some machines only, and Kodi 20's `sys.path` ordering makes shadowing bugs of this class worse |
| `resources/settings.xml` | It declares only the two directory-listing settings this add-on already declares, and the module reads them *unqualified* against the calling add-on — so the module's own file was never the live one for this add-on |
| `resources/language/resource.language.pt_br/strings.po` | This add-on ships no Brazilian Portuguese; additional localizations are out of scope |
| `addon.xml` | This add-on has its own manifest |
| `service.py` | Its entire executable content is out of scope — see **Service extension point** below |
| `icon.png` | This add-on has its own |
| `LICENSE.txt` | Byte-identical to this repository's; see **Licences** above |
| `README.md`, `.project`, `.pydevproject`, `.settings/`, `.gitignore` | Upstream repository and IDE metadata |

From the QR encoder add-on zip, `addon.xml` and `icon.png` were likewise not copied: they are Kodi
add-on wrapper metadata and mean nothing inside this add-on.

## Local modifications

One row per modified vendored file. This is the table a future upstream diff starts from, which is
why it is a table and not prose.

| File | Change | Why |
|---|---|---|
| 21 files under `clouddrive_common/` | 98 import statements repointed from the upstream dotted prefix to `resources.lib.vendor.clouddrive_common` | The module now lives inside this add-on. The rewrite is anchored on a line-start `from … import` prefix, which an add-on-id literal can never match; a bare substring replacement is forbidden here because the old module id *contains* the old package name and rewriting it produces a string that still parses and fails only at runtime on a clean profile |
| `clouddrive_common/utils.py` | Deleted `Utils.get_fqn` and `Utils.get_class` — one contiguous 12-line block, 150 → 138 lines | Neither had a caller anywhere in the tree, and together they were the only string-based import mechanism in it. With them gone, a text sweep over import statements is a complete proof of a rename rather than an approximate one |
| `clouddrive_common/ui/utils.py` | `KodiUtils.common_addon_id` set to `None` | The root of the identity change. The accessor already had a `None` branch that constructs `xbmcaddon.Addon()` with no argument, so the "common add-on" and this add-on become **one object** rather than two that happen to agree. `get_common_addon()` and `get_common_addon_path()` follow from it with no edit of their own, and with them all three dialog skin lookups |
| `clouddrive_common/ui/addon.py` | `self._common_addon_id` reads `KodiUtils.common_addon_id` instead of the old literal | Same change, second site. The four settings reads it feeds follow with no edit |
| `clouddrive_common/service/export.py` | `self._common_addon_id` reads `KodiUtils.common_addon_id` instead of the old literal | Same change, third site |
| `clouddrive_common/ui/dialog.py` | QR image profile lookup is `get_addon_info("profile")` instead of `get_addon_info("profile", <old id>)` | The QR image must be written into *this* add-on's profile directory. Plus the two write guards in the row below |
| `clouddrive_common/ui/dialog.py` | **QR write guard 1:** `KodiUtils.mkdirs(profile_path)` immediately before the encoder writes. **QR write guard 2:** the image filename is now `os.path.join(profile_path, "qr-%s.png" % uuid.uuid4().hex)` — shape `qr-<32 lowercase hex>.png` — replacing the fixed `qr.png`; `import uuid` added | Two edits upstream does not have, so a future upstream diff will show them. Guard 1: a brand-new add-on id means a brand-new `addon_data` path that may not exist on first sign-in, and the write would otherwise raise before the dialog renders — upstream never needed it because its profile always already existed. Guard 2: Kodi's texture cache is keyed by path, so one fixed name lets a second sign-in inside a single session render the *previous* image against the *new* code — a dialog that looks right showing a code that will not authorise. The existing teardown deletion in `__del__` already targets `self._image_path` and follows the new name with no edit |
| `clouddrive_common/remote/errorreport.py` | Version lookup is `get_addon_info('version')` instead of naming the old module | Reports this add-on's version, not a version it no longer carries |
| `clouddrive_common/remote/signin.py` | The User-Agent's third field is this add-on's own version | Same reason |
| `clouddrive_common/ui/dialog.py` | The QR encoder import became `import resources.lib.vendor.pyqrcode as pyqrcode`, still function-local inside `onInit` | The encoder is bundled now. Keeping the import function-local means the dialog constructs and its skin loads even if the encoder is unavailable; it is deliberately **not** wrapped in a handler, so a failure surfaces rather than degrading silently |
| `pyqrcode/__init__.py`, `pyqrcode/builder.py` | Five internal self-imports rewritten to `from . import …`, and two Python-2 compatibility `try`/`except ImportError` blocks reduced to their Python 3 branch | Absolute self-imports such as `import pyqrcode.tables` resolve to nothing once the package has a parent; and `try: import png` could only ever bind a *top-level* `png` — absent here, or somebody else's module if present. `tables.py`, `png.py` and `LICENSE.md` were not touched at all |
| `clouddrive_common/ui/utils.py` | `KodiUtils.to_datetime` parses with `datetime.datetime.fromisoformat` after `re.sub(r'(\.\d{6})\d+', r'\1', s)`, replacing `dateutil.parser.parse`; `import datetime` and `import re` replace `import dateutil.parser` in the same function-local position | Removes the last dependency this add-on did not carry. The substitution truncates a seven-or-more-digit fractional-seconds field, which SharePoint emits, and is a literal no-op for six digits or fewer. It is kept even though CPython 3.11.9 already tolerates those inputs, because Kodi Nexus ships 3.11.2 and that build was not available to check. The surrounding bare handler that returns `None` on failure is unchanged |
| `clouddrive_common/db.py` | Three reads: `eval(row[…])` → `json.loads(row[…])`. Two writes: `repr(value)` → `json.dumps(value)`. `import json` added | The key-value store backs the account store that holds OAuth refresh tokens. Reading it with `eval` turns a file on disk into running code. There is deliberately **no** compatibility read path and no fallback evaluator: a new add-on id means no database in the old format can exist, and a fallback would restore the exact hole being closed |
| `clouddrive_common/cache/cache.py` | One read and two writes converted the same way; `import json` added | Same reasoning, for the item, children and page caches |
| `clouddrive_common/service/source.py` | `content_value = Utils.str(cached_page['content'].getvalue())` — the cached response body is decoded at the write site | The page cache stored `bytes`, a shape JSON cannot carry. It is coerced where it is produced rather than special-cased in the serializer, which is the exact inverse of what the read path already does with `Utils.encode`. Every body written is HTML or a JSON string, so the decode is total |
| `clouddrive_common/remote/request.py` | `Request.HTTP_TIMEOUT_SECONDS = 30`, passed as `urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT_SECONDS)` | The one outbound HTTP call in the tree could previously block forever. **The value is unmeasured** — 15 to 30 seconds is a recommended range, not a measurement of this add-on on a real network, and nothing in this repository can tell a correct 30 from a wrong one. One value serves both the metadata path and the chunked download path because the timeout applies per socket operation, not to a whole transfer: it bounds how long a single `read` may block, so a large download never trips it as long as bytes keep arriving |

Two things that are edits to *this repository's* own files rather than to vendored ones, recorded
here because they belong to the same change: `addon.xml` now declares exactly one import,
`xbmc.python` 3.0.1; and `.project` line 6 no longer references the module, leaving `<projects>`
empty.

## Service extension point

The module's own manifest declared `<extension point="xbmc.service" library="service.py" start="login" />`,
and the entire executable content of that file was `ServiceUtil.run([SourceService(None, SourceRedirector)])`
— the `SourceRedirector` variant of `SourceService`, which is the unauthenticated directory-listing
server. That subsystem is out of scope by decision and is deleted outright in a later cleanup, so
**nothing survives the fold**: this add-on's own `service.py` gains nothing from the module's, and
the module's `service.py` was not copied. This is written down so that a later reader can tell
"considered and discarded" from "overlooked".

Separately, and not to be confused with the above: this repository's own `service.py` constructs
`SourceService(OneDrive)` — a different construction, with a provider — alongside the download,
export and player services. That instance survives this change unchanged, because the contract of
this change is preserved behaviour. It is deleted in the same later cleanup.

## Recorded behaviour deviations

The contract of the vendor lift was identical behaviour, so every departure from it is listed here
with its reasoning. There are four.

**1. Sign-in, account listing, browsing and playback do not work.** The sign-in flow calls a
third-party broker that has been offline since November 2022. This is inherited, not caused by the
lift — the original add-on has the same problem — and it is why a fresh profile shows an empty
account list and nothing beyond it can be exercised. Sign-in is replaced by a device-code flow in
the next stage of work.

**2. `allow_directory_listing` now defaults to `false` instead of `true`.** The gated service binds
a loopback port and serves an enumerable index of the entire drive, with no authorisation check
anywhere in the server base class. On Android every installed application can reach loopback. The
module's own upstream documents the feature as not working. And because this add-on ships under a
new id, no user has a stored `true` that would override the new default, so the flip is complete
rather than partial. The subsystem is deleted outright in a later cleanup; until then this is a
deliberate default change and not a regression.

**3. The settings row that opened the separate common-settings add-on is gone**, together with the
string that labelled it. After bundling there is no separate add-on to open, so the row could only
have errored or looped back into these same settings.

**4. A dialog smoke action exists at `plugin://plugin.onedrive.kn/?action=_dialog_smoke`.** It is
the `_dialog_smoke` method on `OneDriveAddon` in `resources/lib/addon.py`. It constructs each of
the three `WindowXMLDialog` subclasses with dummy arguments, shows and closes them, and logs the
resolved skin path, the profile path and both QR image paths. It exists because the QR dialog is
unreachable by clicking while deviation 1 holds, and because asserting that the skin XML files were
copied proves the copy but not the path argument. It performs no network call and touches no
credential. **It is a debug affordance and is scheduled for removal, or for a debug-only gate,
before release** — an undocumented one becomes permanent by default, which is why it is written
down here rather than only in the code.

Two further things that are not deviations but will surprise a reader of a fresh profile.

First, an **undeclared setting appears in the settings file on first service start**. The service
base class binds its socket, discovers the port, and writes it back as `<name>.service.port` —
once for each of the four services (`download`, `source`, `export`, `player`). None of those four
keys is declared in `resources/settings.xml`. That is upstream behaviour, unchanged.

Second, the tree carries a **third-party traceback reporter**, `clouddrive_common/remote/errorreport.py`,
which posts a stack trace to the same broker as the sign-in flow. It is gated on the `report_error`
setting, which is declared `default="false"`, so it is off unless a user turns it on. It is a known
liability, carried in unchanged because the contract here was preservation, and it is deleted in
the later cleanup.

Finally, one number worth having written down: the HTTP retry loop's worst-case wall time is the
number of tries multiplied by the timeout, plus the injected waits between attempts. At the request
class's defaults (`tries=4`, `delay=5`, `backoff=2`) that is `4 × 30 + 5 + 10 + 20 = 155 seconds`.
It is recorded rather than bounded; routing the wait through Kodi's abort-aware sleep is later work.
