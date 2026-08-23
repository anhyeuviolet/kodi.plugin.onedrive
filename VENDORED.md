# Vendored code

This add-on carries copies of two other projects inside its own source tree instead of depending on
them as separate Kodi add-ons: the Cloud Drive Common Module, and the QR encoder that draws the
sign-in code. This file is the record of both copies: where each came from, what licence each part
is under, what was deliberately left behind, what was changed locally, and every way the add-on's
behaviour now differs from the original.

It exists so that a future upstream diff, a future licence question and a future "was that already
broken?" all start from a written fact rather than from a guess. If you change anything under
`resources/lib/vendor/` or `resources/skins/`, add a row here in the same commit. **Deleting a
vendored file counts as changing it**, and it is the one difference a diff cannot explain on its
own, because the file is simply absent on one side.

## Upstream: the Cloud Drive Common Module

| Field | Value |
|---|---|
| Repository | `https://github.com/cguZZman/script.module.clouddrive.common` |
| Branch | `matrix` |
| Version | `1.4.0` |
| Commit | `df68e9a589a6faef2b3228f7520e77729bc05d9b` |
| Commit date | 2023-01-21 |
| Commit subject | `Kodi 20 fix` |
| Licence | GPL-3.0-or-later |
| Vendored to | `resources/lib/vendor/clouddrive_common/` (the Python package) and `resources/skins/default/` (the dialog skins) |

The copy is pinned to that commit, not to the branch. It was taken by checking out the commit and
comparing every copied file against the upstream blob **by git object id**, so "verbatim" is a
measured property of the bytes rather than a claim about the copy command. All 38 copied files
matched.

**Ten of those 38 are not under `resources/lib/vendor/`.** The module's three dialog skins and their
seven textures were merged into this add-on's own skin directory, because that is where Kodi looks
for them:

| Vendored from the module | Vendored to |
|---|---|
| the `pin-dialog`, `export-main-dialog` and `export-schedule-dialog` skins | `resources/skins/default/1080i/` |
| `black.png`, `white.png`, `dialog-bg.png`, `dialogbutton-fo.png`, `dialogbutton-nofo.png`, `radio-button-off.png`, `radio-button-on.png` | `resources/skins/default/media/` |

Nothing under `resources/skins/` predates the lift — the whole directory arrived with it. It is
recorded here because the sentence above about `resources/lib/vendor/` reads, on its own, as though
the vendored surface stopped at that path; it never did, and a modification to a skin is as much a
divergence from upstream as a modification to a module.

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
record paths**, which is exactly what the `source_scan` helper implements — it reads every tracked
text file except `tests/` and the documents in its `EXCLUDED_DOCS` set. The planning record was
named there too until it was untracked; the sweep reads the git index, so nothing changed about
which bytes it covers.
The runnable form of both conditions is `test_no_hardcoded_module_id` and `test_no_eval` in
`tests/test_vendor_gates.py`. Those two tests, not a bare `grep` over the whole checkout, are what
"zero hits" means here.

Two corrections to the paragraph above, both measured against the tree rather than carried forward:
the helper now lives in `tests/gatelib.py`, which both gate files read, and `EXCLUDED_DOCS` holds
five names, not four — `VENDORED.md`, `CREDITS.md`, `COVERAGE.md`, `README.md` and
`docs/AZURE-REGISTRATION.md`. **`COVERAGE.md` has never existed in this repository.** It has been in
the exclusion set since the gates were first written and excludes nothing; it is left in place and
named here rather than quietly dropped, because an exclusion for a file that is not there is a
different thing from an exclusion that is doing work, and the next person to read that set should
not have to discover the difference. The exclusions that *are* doing work are paid for by positive
assertions: `test_the_replaced_flow_is_named_in_the_two_excluded_documents` reads this file and
`README.md` by name, and the runbook has its own assertion in the vendor gate file.

## The QR encoder

The second vendored component draws the QR code shown during sign-in. It was **not** taken from the
project's own source repository; it was taken from a published Kodi add-on zip, and that zip — not
the repository — is the fixed point this copy is re-derivable from.

| Field | Value |
|---|---|
| Add-on id | `script.module.pyqrcode` |
| Version | `1.2.1+matrix.4` |
| Zip | `https://mirrors.kodi.tv/addons/omega/script.module.pyqrcode/script.module.pyqrcode-1.2.1+matrix.4.zip` |
| Zip sha256 | `3bd98699099b531ba8175a3822536927eeaac111d7cb9d12e1f0ed707b020899` |
| Zip size | 66,542 bytes |
| Licence | BSD-3-Clause, © 2013 Michael Nooner; the PNG writer bundled inside it is MIT, © 2006 Johann C. Rocholl and others |
| Code originates at | `https://github.com/mnooner256/pyqrcode` — the origin of the code, **not** the source of this copy |
| Vendored to | `resources/lib/vendor/pyqrcode/` |

**That URL answers with a 302, and it is not a dead link.** `mirrors.kodi.tv` redirects the canonical
address above to
`https://www.mirrorservice.org/sites/mirrors.xbmc.org/addons/omega/script.module.pyqrcode/script.module.pyqrcode-1.2.1+matrix.4.zip`.
A `curl` without `-L` therefore reports `302` and writes a zero-byte body, which looks exactly like a
URL that has rotted. Follow the redirect and check the sha256 above before concluding anything.

**Mapping.** `script.module.pyqrcode/lib/pyqrcode/*` → `resources/lib/vendor/pyqrcode/*`, and
`script.module.pyqrcode/LICENSE.md` → `resources/lib/vendor/pyqrcode/LICENSE.md`. The zip's own
`addon.xml` and `icon.png` were **not** copied: they are Kodi add-on wrapper metadata and mean
nothing inside this add-on.

**Why the zip rather than PyPI or a source archive.** That zip is the exact build this add-on was
tested against, and it is the only distribution that bundles the PNG writer, which exists as no
separate Kodi module in any repository branch. Re-deriving from the GitHub project instead will
produce different bytes.

| Vendored file | Bytes | sha256 | Byte-identical to the zip? |
|---|---:|---|---|
| `__init__.py` | 32,727 | `781d7ba4aef8a83ca3932a52ea07b4c83f145f8b6f33ca9605fd1c161897bc2a` | no — 3 edits |
| `builder.py` | 57,948 | `bc4f6d4ccffc2d59b40babf7ba6ff3ed8aeb33a92197b72086a872b1479cc4ca` | no — 2 edits |
| `tables.py` | 31,446 | `20983a11ec5dc81fd74629d9ba6f3a9a737d8a410cce390b4e10bf5c2dbef588` | **yes** |
| `png.py` | 81,765 | `9f70a9033f0f7f4412719c7a51cad9043c0187dfe09698b3c1b04ebb859d17df` | **yes** |
| `LICENSE.md` | 1,503 | `0d2437a10d8ef93c488d49b0a09068c56bc1543e8ee9393bcbba15d172a031f9` | **yes** |

All five ship LF-only, exactly as the zip does, and were staged with `git -c core.autocrlf=false add`
so the blobs match the zip's bytes — the same procedure used for the module above. The five edits are
itemised in **Local modifications** below.

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
add-on wrapper metadata and mean nothing inside this add-on. The zip is identified in full under
**The QR encoder** above.

## Local modifications

One row per modified vendored file. This is the table a future upstream diff starts from, which is
why it is a table and not prose.

The first block of rows is the vendor lift itself. The second block, under **Rewriting sign-in**, is
the work that replaced the hosted sign-in flow; it is kept separate because those rows are large and
because a reader trying to answer "what did the lift change?" and a reader trying to answer "what
did sign-in change?" are asking different questions.

| File | Change | Why |
|---|---|---|
| 21 files under `clouddrive_common/` | 98 import statements repointed from the upstream dotted prefix to `resources.lib.vendor.clouddrive_common` | The module now lives inside this add-on. The rewrite is anchored on a line-start `from … import` prefix, which an add-on-id literal can never match; a bare substring replacement is forbidden here because the old module id *contains* the old package name and rewriting it produces a string that still parses and fails only at runtime on a clean profile |
| `clouddrive_common/utils.py` | Deleted `Utils.get_fqn` and `Utils.get_class` — one contiguous 12-line block, 150 → 138 lines | Neither had a caller anywhere in the tree, and together they were the only string-based import mechanism in it. With them gone, a text sweep over import statements is a complete proof of a rename rather than an approximate one |
| `clouddrive_common/ui/utils.py` | `KodiUtils.common_addon_id` set to `None` | The root of the identity change. The accessor already had a `None` branch that constructs `xbmcaddon.Addon()` with no argument, so the "common add-on" and this add-on become **one object** rather than two that happen to agree. `get_common_addon()` and `get_common_addon_path()` follow from it with no edit of their own, and with them all three dialog skin lookups |
| `clouddrive_common/ui/addon.py` | `self._common_addon_id` reads `KodiUtils.common_addon_id` instead of the old literal | Same change, second site. The four settings reads it feeds follow with no edit |
| `clouddrive_common/service/export.py` | `self._common_addon_id` reads `KodiUtils.common_addon_id` instead of the old literal | Same change, third site |
| `clouddrive_common/ui/dialog.py` | QR image profile lookup is `get_addon_info("profile")` instead of `get_addon_info("profile", <old id>)` | The QR image must be written into *this* add-on's profile directory. Plus the two write guards in the row below |
| `clouddrive_common/ui/dialog.py` | **QR write guard 1:** `KodiUtils.mkdirs(profile_path)` immediately before the encoder writes. **QR write guard 2:** the image filename is now `os.path.join(profile_path, "qr-%s.png" % uuid.uuid4().hex)` — shape `qr-<32 lowercase hex>.png` — replacing the fixed `qr.png`; `import uuid` added | Two edits upstream does not have, so a future upstream diff will show them. Guard 1: a brand-new add-on id means a brand-new `addon_data` path that may not exist on first sign-in, and the write would otherwise raise before the dialog renders — upstream never needed it because its profile always already existed. Guard 2: Kodi's texture cache is keyed by path, so one fixed name lets a second sign-in inside a single session render the *previous* image against the *new* code — a dialog that looks right showing a code that will not authorise. The existing teardown deletion in `__del__` already targets `self._image_path` and follows the new name with no edit |
| `clouddrive_common/remote/errorreport.py` | Version lookup is `get_addon_info('version')` instead of naming the old module | Reports this add-on's version, not a version it no longer carries. **This file has since been deleted** — see **Rewriting sign-in** below |
| `clouddrive_common/remote/signin.py` | The User-Agent's third field is this add-on's own version | Same reason. **This file has since been deleted** — see **Rewriting sign-in** below |
| `clouddrive_common/ui/dialog.py` | The QR encoder import became `import resources.lib.vendor.pyqrcode as pyqrcode`, still function-local inside `onInit` | The encoder is bundled now. Keeping the import function-local means the dialog constructs and its skin loads even if the encoder is unavailable; it is deliberately **not** wrapped in a handler, so a failure surfaces rather than degrading silently |
| `pyqrcode/__init__.py`, `pyqrcode/builder.py` | Three internal self-imports rewritten to `from . import …` — `__init__.py` lines 46 and 47, `builder.py` line 33 — and two Python-2 compatibility `try`/`except ImportError` blocks reduced to their Python 3 branch: **five edits in total, across two files** | Absolute self-imports such as `import pyqrcode.tables` resolve to nothing once the package has a parent; and `try: import png` could only ever bind a *top-level* `png` — absent here, or somebody else's module if present. `tables.py`, `png.py` and `LICENSE.md` were not touched at all |
| `clouddrive_common/ui/utils.py` | `KodiUtils.to_datetime` parses with `datetime.datetime.fromisoformat` after `re.sub(r'(\.\d{6})\d+', r'\1', s)`, replacing `dateutil.parser.parse`; `import datetime` and `import re` replace `import dateutil.parser` in the same function-local position | Removes the last dependency this add-on did not carry. The substitution truncates a seven-or-more-digit fractional-seconds field, which SharePoint emits, and is a literal no-op for six digits or fewer. It is kept even though CPython 3.11.9 already tolerates those inputs, because Kodi Nexus ships 3.11.2 and that build was not available to check. The surrounding bare handler that returns `None` on failure is unchanged |
| `clouddrive_common/db.py` | Two reads: `eval(row[…])` → `json.loads(row[…])`. Two writes: `repr(value)` → `json.dumps(value)`. `import json` added. (The tree's third converted read is in `cache/cache.py`, the row below; it is not in this file) | The key-value store backs the account store that holds OAuth refresh tokens. Reading it with `eval` turns a file on disk into running code. There is deliberately **no** compatibility read path and no fallback evaluator: a new add-on id means no database in the old format can exist, and a fallback would restore the exact hole being closed |
| `clouddrive_common/cache/cache.py` | One read and two writes converted the same way; `import json` added | Same reasoning, for the item, children and page caches |
| `clouddrive_common/service/source.py` | `content_value = Utils.str(cached_page['content'].getvalue())` — the cached response body is decoded at the write site | The page cache stored `bytes`, a shape JSON cannot carry. It is coerced where it is produced rather than special-cased in the serializer, which is the exact inverse of what the read path already does with `Utils.encode`. Every body written is HTML or a JSON string, so the decode is total |
| `clouddrive_common/remote/request.py` | `Request.HTTP_TIMEOUT_SECONDS = 30`, passed as `urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT_SECONDS)` | The one outbound HTTP call in the tree could previously block forever. **The value is unmeasured** — 15 to 30 seconds is a recommended range, not a measurement of this add-on on a real network, and nothing in this repository can tell a correct 30 from a wrong one. One value serves both the metadata path and the chunked download path because the timeout applies per socket operation, not to a whole transfer: it bounds how long a single `read` may block, so a large download never trips it as long as bytes keep arriving |

| 8 files under `clouddrive_common/` | `import urllib` → `import urllib.parse`, and in `remote/request.py` → `import urllib.request`. One line each: `export.py`, `remote/oauth2.py`, `remote/provider.py`, `remote/request.py`, `service/player.py`, `service/source.py`, `ui/addon.py`, `ui/utils.py` | `import urllib` binds the package and **not** its submodules, so every `urllib.parse.…` call in these files was reaching an attribute nobody had asked for. It resolved anyway, because some other import in the same interpreter had pulled `urllib.parse` in as a side effect — an implementation detail, not a guarantee. This add-on has to run on Python 3.8 under Kodi 19–21 and 3.14 under Kodi 22, and a side effect that holds on one is not evidence about the other. `ui/dialog.py` already had the correct form and was the model. `test_urllib_submodules_are_imported_by_name` parses the tree and holds it |

Two things that are edits to *this repository's* own files rather than to vendored ones, recorded
here because they belong to the same change: `addon.xml` now declares exactly one import,
`xbmc.python` 3.0.1; and `.project` line 6 no longer references the module, leaving `<projects>`
empty.

The `urllib` row above has two counterparts in this repository's own code, changed in the same
sweep for the same reason and listed here rather than given rows of their own: `resources/lib/addon.py`
and `resources/lib/provider/onedrive.py`.

### Rewriting sign-in

The hosted sign-in flow was replaced by the OAuth 2.0 device authorization grant, spoken directly to
the identity provider. That work spans twelve vendored files, deletes two of them outright and
rewrites one skin. The protocol itself lives in `resources/lib/auth/`, which is this repository's own
code and carries no upstream counterpart; the rows below are only the vendored side.

| File | Change | Why |
|---|---|---|
| `clouddrive_common/remote/signin.py` | **Deleted — the whole file, 66 lines.** `Signin.get_addon_header`, `create_pin`, `fetch_tokens_info`, `refresh_tokens` and the two exception wrappers between them each composed an address against the hosted sign-in server and posted to it | Every method in it existed to talk to that server. Nothing survives a flow that talks to the provider directly, so there was nothing to keep and no partial file to leave. A deletion is the one divergence from upstream a diff cannot describe on its own, which is why it has a row rather than an absence |
| `clouddrive_common/remote/errorreport.py` | **Deleted — the whole file, 84 lines.** `send_report` posted a stack trace to that same server; `handle_exception` assembled the same report with the raw response body appended and sent it | Its only address source was the accessor deleted from `ui/utils.py` in the same work, so it could not have functioned afterwards even if it had been kept. It was also the one path in the tree that put an unredacted response body on the wire, and a failing token exchange answers with a body that *is* the credential. Its eight call sites in five other modules were rewritten first — see the row for them below — because deleting the module with those in place stops the export subsystem and both service listeners from importing at all |
| `clouddrive_common/remote/provider.py` | Rewritten around the new flow, 102 → 364 lines. `create_pin` → `request_device_code` and `fetch_tokens_info` → `poll_for_token`, both now delegating to `resources/lib/auth/device_code`; the `Signin` import and the `_signin` attribute removed; `refresh_access_tokens` rewritten onto `resources/lib/auth/refresh`; `get_access_tokens` and `persist_access_tokens` repointed at the per-account token store; `_post_port`, `_stop_retrying_a_settled_answer`, `_parse_body`, `_account_key`, `save_tokens`, `_lock_for`, `resolve_client_id()`, `ReauthorisationRequired`, `CLIENT_ID_SETTING` and `CLIENT_ID_PATTERN` added | This class is the seam between Kodi and the protocol, so it is where the protocol change lands. The two renames are not cosmetic: a pin issued by a third party and a device code issued by the provider are different objects with different lifetimes, and a method that keeps the old name while returning the new object is how the two get confused later. `_post_port` builds the `post(url, fields) -> (status, body)` callable that is the entire coupling between `resources/lib/auth/` and the network, which is what keeps that package free of sockets and testable without a stub library |
| `clouddrive_common/remote/request.py` | `import re` added, plus `REDACTED_FIELDS` (five names: `access_token`, `refresh_token`, `id_token`, `device_code`, `user_code`), `REDACTED_PREFIX_CHARACTERS`, `REDACTED_MARKER`, the two compiled patterns behind them, `_keep_prefix` and `get_body_for_report`. Four sites route through it: `get_url_for_report`, the request-data report and the two response-body reports | The bearer header and one query parameter were already covered; neither is where this grant puts its credentials. A token exchange sends the device code in a form body and gets three tokens back in a JSON body, and both were being concatenated into a report string that goes straight to the Kodi log — a file users paste into forum posts verbatim. A successful token response *is* the credential. All five names in both directions, because covering four is publishing the fifth. `_keep_prefix` drops a value entirely rather than keeping eight of its nine characters, which for `user_code` would be the live code with a typo |
| `clouddrive_common/ui/dialog.py` | `QRDialogProgress` gains `set_code`, `set_remaining`, `set_expired`, `reset_for_new_code`, `is_new_code_requested`, `format_remaining`, `_render_text`, `_addon_string`, `_is_secure_url`, two control ids and three string ids; `__del__` guarded with `getattr`; the `setFocus` call moved out of `update()` into `onInit`; `import urllib` became `import urllib.parse` | The dialog is driven once a second by the poll loop, so every per-tick call has to be free of side effects. `setFocus` at the end of `update()` was not: it returned focus to Cancel on every tick, so no focus set anywhere else could survive, and the expiry button would have been unreachable. `__del__` called `xbmcvfs.delete(None)` for any dialog abandoned before `onInit` ran — inside a destructor, where the interpreter discards the error and prints a note nobody reads. `_is_secure_url` refuses to encode a sign-in address that is not `https`, because a QR is a thing a person is told to point a camera at. `import urllib` never bound `urllib.parse`; it resolved only because something else had imported it first |
| `clouddrive_common/ui/addon.py` | Fourteen methods added — `_action_map`, `_released_the_handle`, `_signin_request_params`, `_acquire_tokens`, `_await_authorisation`, `_poll_once`, `_identify`, `_reauthorise_account`, `_needs_reauthorisation`, `_provider_failure`, `_failure_sentence`, `_offer_signin_again`, `_addon_string` and the `_FAILURE_STRINGS` table. `_add_account` and `list_accounts` rewritten; `route`'s dynamic dispatch replaced by the explicit mapping; `_handle_exception` rebuilt; `_remove_account` extended to the token store; `_remove_drive`, `_DEFAULT_SIGNIN_TIMEOUT`, `_ip_before_pin`, the `migrated`-account cleanup block and the address-changed heuristic all deleted. Imports: `json`, `resources.lib.auth_context`, `device_code`, `errors`, `store` and `ReauthorisationRequired` in, `ErrorReport` out | This is the file the user's sign-in actually runs through, so it absorbs most of the change. Three structural properties are worth naming because they are what the gates hold: the directory handle is released and the work re-enters as an action, so a container fetch is not left blocked for the life of a device code; there is exactly one `save_account`, last, so a cancel anywhere above it returns having written nothing; and `route` dispatches through a name-to-method table rather than `getattr(self, self._action)`, so a crafted plugin address cannot reach an arbitrary method. `_remove_drive` went because there is one drive per account by measurement, so the option was unreachable |
| `clouddrive_common/ui/utils.py` | `KodiUtils.get_signin_server` deleted. `ADDON_STRING_FLOOR = 30000` added and `KodiUtils.localize`'s boundary moved onto it from the literal `32000` | The accessor read the hosted server's address out of a setting and was the only address source the reporter and the replaced flow ever had. The boundary was correct while the only add-on ids in the tree were the module's 32000-32088; it stopped being correct when this add-on's own strings moved into the 30000 block Kodi reserves for plugins, and it failed *silently* — id 30042 went to Kodi's catalogue and came back as Kodi's 30042, so a caller got the wrong sentence rather than an error. No shipped caller passes an id in that range today, so this closes a latent fault rather than fixing a visible one |
| `clouddrive_common/export.py`, `service/download.py`, `service/export.py`, `service/player.py`, `service/source.py` | Eight `ErrorReport.handle_exception(e)` call sites — two, one, three, one and one respectively — replaced with `Logger.error(ExceptionUtils.full_stacktrace(e))`. `ExceptionUtils` added to the imports of the three files that lacked it; the `ErrorReport` import removed from all five | The logging half of what the reporter did, without the sending half or the raw response body it appended. These five modules are outside the sign-in flow entirely; they are here because deleting the reporter without them would have broken their imports outright. `service/player.py` also now logs the full stack trace where it previously logged the bare exception and then handed it to the reporter |
| `resources/skins/default/1080i/pin-dialog.xml` | Rebuilt around the code, 86 → 150 lines. A dedicated code label (control 1005, `font60`) and a second button (control 1004) added, and the layout reordered so the code is the largest thing on screen. **The font named here was superseded once the dialog was read on a television — see the `pin-dialog.xml` row under Fixed on hardware. The shape described here is unchanged; only the sizes are** | The old layout was built for a short pin beside a QR image. The device code is what a person has to read off a television and type into a phone, so it is what the layout has to serve, and the expiry path needs a second button the old skin had nowhere to put. The font names matter more than they look: Kodi falls back to `font13` **silently** when it cannot resolve one — no error, no log line — and this file shipped naming `font12_title`, which Estuary does not define. Every font it names now is defined in both Estuary fontsets |
| `clouddrive_common/ui/addon.py` (`356de0d`), `clouddrive_common/ui/utils.py` (`c3a1445`), `resources/skins/default/1080i/pin-dialog.xml` (`345999a`) | **Line endings converted from CRLF to LF across the whole of each file** | Recorded because it is invisible in review and total in a byte diff: upstream holds all three as CRLF, so **every line of all three now differs from upstream**, and a diff taken without `--ignore-cr-at-eol` shows each file as wholly rewritten and says nothing about what actually changed. It was not deliberate and nothing depends on it. It is left as it stands rather than converted back, because a conversion is itself a whole-file rewrite and doing one inside a documentation change would bury the same problem a commit deeper. Use `git diff --ignore-cr-at-eol` on these three until somebody normalises them on purpose. Upstream itself is not uniform — `remote/provider.py` and `export.py` arrived LF — so "convert everything to LF" is not the obvious repair it appears to be |

Two methods survive in the vendored tree that nothing can now reach, both left deliberately and
recorded so that a later reader does not take them for an oversight. `CloudDriveAddon._open_common_settings`
opened a separate module's settings dialog; there is no separate module, no settings row points at
it, and it is absent from the action mapping, so it is unreachable by construction rather than by
convention. `AccountManager.remove_drive` in `clouddrive_common/account.py` lost its only caller when
the per-drive removal option went. It is harmless, and it is the shape to restore if drive selection
ever comes back.

### Fixed on hardware

A third block, kept separate for the same reason the second one is: these rows answer "what did the
first real sign-in on a television find?", which is a different question again. Three of the four
are integration defects between `resources/lib/auth/` and this vendored layer — invisible to a suite
that tests each side on its own, and visible on the first run where the two met the live provider.
The fourth is not a defect of that kind at all. It is what a person sitting in front of a television
could see and no instrument in this repository could: the code was too small to read from a normal
seat. It is in this block rather than in **Rewriting sign-in** because the finding, not the file, is
what the block is organised by.

| File | Change | Why |
|---|---|---|
| `clouddrive_common/ui/addon.py` | In `_acquire_tokens`, the authorised poll payload is returned as `store.merge_token_response({}, payload)` rather than as `payload` | A provider token response is not a token blob. It carries `expires_in` and no `date`; `date` is stamped locally, it is one of the four fields `OAuth2._validate_access_tokens` requires, and `OAuth2.prepare_request` computes expiry from `date + expires_in - 600`. So the raw payload was rejected by the first request made with it — `_identify` → `provider.get_account` — and a sign-in that had actually **succeeded** reached the television as a dialog reading "Access tokens provided are not valid". Fixed at the seam rather than by persisting the token earlier: `merge_token_response` is a pure function and writes nothing, so `_add_account` and `_reauthorise_account` still assemble everything in memory and write only in their last two statements, and a cancel anywhere above still leaves no partial account behind (AUTH-07). `_await_authorisation` was the wrong site because its payload is a refusal code for one of its four outcomes, and `provider.poll_for_token` was the wrong site because it would have to re-derive which of its states are successes. Held by `test_the_signin_flow_stamps_the_token_before_returning_it` and `test_the_signin_flow_stamps_without_writing_anything`, with the contract itself pinned behaviourally in `tests/test_oauth2_tokens.py` |
| `clouddrive_common/remote/oauth2.py` | `_validate_access_tokens` rebuilt: `REQUIRED_ACCESS_TOKEN_FIELDS` and `_access_tokens_for_report` added, the four inline `'x' in access_tokens` tests replaced by a `missing` list read from that tuple, and all four parts of the `RequestException` routed through a redactor — the message through `_access_tokens_for_report`, the URL and the request data through `Request.get_body_for_report`, the headers through `Request.get_headers_for_report` | The message was `'Access tokens provided are not valid: ' + Utils.str(access_tokens)`, and it is **not log-only**: `_handle_exception` renders a `UIException`'s root exception onto line two of a Kodi dialog and `_identify` wraps every `get_account` failure in one, so a live token blob — access token, refresh token and identity token in the clear — was printed on a television. The third argument embedded `Utils.str(data)`, which for a token exchange is a form body carrying the refresh token, the device code and the client id. Field *names* are not credentials and they are the whole of the diagnosis: `date` missing means a response never went through `store.merge_token_response`. 03-09's redaction gate covered the transport's report path and could not see this one — it is a `raise`, not an assignment, and the value is a local name rather than a raw-body attribute. `_access_tokens_for_report` carries the `_for_report` suffix deliberately: it is the convention the widened gate reads to tell a redacted value from a raw one |
| `clouddrive_common/remote/request.py` | `get_headers_for_report` became a classmethod and returns non-dict input unchanged | The OAuth2 layer reports a failure before any `Request` exists to report it through, so the method had to be callable without an instance. The guard is not defensive padding: `prepare_request` calls the validator a second time with the plain strings `'refresh_access_tokens'` and `'Unknown'` in place of a URL and headers, and iterating that string as a mapping would have reported a dictionary of single characters. Nothing about the redaction itself changed — the `authorization` value is still the one replaced |
| `resources/skins/default/1080i/pin-dialog.xml` | Resized throughout, 150 → 216 lines, no control added or removed. Control `1005` (the code) `font60` → `WeatherTemp` and its box 96 → 152 high. Control `1001` (the QR) 150×150 → 280×280. Control `1002` (the body block, whose last line is the countdown) `font27` → `font37` and 926×156 → 798×364. The panel 450 → 750 high, the two buttons moved down with it, and the window origin re-centred from `top` 315 to 165. The header comment's font paragraph replaced by the measured chain described below | Read on a TCL Android TV 12 (Kodi 21.2, stock Estuary) during the 03-14 acceptance run, the code was legible but small from a normal seat — and `font60` was never "the largest font the skin offers" that AUTH-05 asks for. Estuary defines `WeatherTemp` at 120, so there was exactly 2× of headroom going unused. This is **not** the silent-substitution failure the header comment was written about: `font60` did resolve, the layout simply never reached the top. Three things came with the font. A 120px glyph in the 96-high box that control had would have clipped top and bottom, and a clipped code is worse than a small one, so the box and the panel under it grew. The QR was 150×150 on 03-06's reasoning that the provider returns no `verification_uri_complete` and the image can therefore only carry the address — that reasoning stands and is untouched, but 150 was smaller than the layout required; 280 is what the width allows once the text column keeps the address on one unwrapped line. And the body block turned out to have been **overflowing since 03-06**: at `font27` its shipped text wraps to six lines of roughly 38px against 156 of room, and the line pushed out of view is the last one, which is the countdown. The risk taken on is that `WeatherTemp` is special-purpose — a temperature on a weather pane — and is the likeliest of the chain to be absent from a third-party skin, where Kodi drops to `font13` (30px) and logs nothing. Kodi's skin XML has no fallback operator, so the mitigation is a chain recorded for a human reader in the header comment (`WeatherTemp` 120 → `font_clock` 70 → `font60` 60 → `font52_title` 52 → `font45` 45, sizes read out of Estuary's Omega `Font.xml`) and four gates in `tests/test_auth_gates.py` that hold the layout to the head of that chain and hold every box to the glyphs it must fit. Those gates prove the layout's intent; they cannot prove what rendered on a screen, which is the distinction AUTH-05's prohibition exists to protect |

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

**1. Sign-in no longer goes through a third-party server. It is now the OAuth 2.0 device
authorization grant, spoken straight to the identity provider — and a fresh profile still shows an
empty account list until someone completes a sign-in.**

What it used to do, in the past tense, because this is the modification record and erasing what was
replaced is the one thing such a record must not do: the inherited flow posted to
`drive-login.herokuapp.com`, which issued a short-lived pin, showed it in the QR dialog, and polled
`/pin/<code>` until a browser elsewhere completed the OAuth exchange on the user's behalf. That
server was long assumed dead and **it was not**. Measured on 2026-08-22 from the Android test
instrument: `GET /ip` and `POST /pin` both answered `200`, a pin was issued, the dialog rendered it,
and the add-on began polling as designed. It was removed while it still worked, and that is the
point — a third party held the exchange, saw which account was being connected, and was a single
point of failure and of trust for every user of the add-on. Liveness was never the objection.

What happens now: the add-on asks the provider for a device code, shows the code and the provider's
own verification address on the television, and polls the provider's token endpoint until the user
has finished on their own phone. The application identifier it sends is public by design, which is
what this grant is for; there is no client secret anywhere in the tree and adding one would break
the grant. The refresh token that comes back is written to a per-account file in this add-on's
profile directory at mode `0600`, never into the account record. The whole of the protocol lives in
`resources/lib/auth/`, which imports no Kodi module and opens no socket.

The empty account list on a fresh profile is unchanged and is still the correct result, for the same
reason as before: nothing is signed in, and signing in needs a human with a phone. The vendored
files this replacement touched are itemised under **Rewriting sign-in** above, including the two it
deleted outright.

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
resolved skin path, the profile path and both QR image paths. It exists because asserting that the
skin XML files were copied proves the copy but not the path argument, which is the thing that
actually breaks, and because it reaches all three dialogs without a network round trip, a live
third-party server or a human at a browser — none of which a repeatable check should depend on. It
performs no network call and touches no credential. **It is a debug affordance and is scheduled for
removal, or for a debug-only gate, before release** — an undocumented one becomes permanent by
default, which is why it is written down here rather than only in the code.

Two further things that are not deviations but will surprise a reader of a fresh profile.

First, an **undeclared setting appears in the settings file on first service start**. The service
base class binds its socket, discovers the port, and writes it back as `<name>.service.port` —
once for each of the four services that bind one (`download`, `source`, `export`, `player`). None of
those four keys is declared in `resources/settings.xml`. That is upstream behaviour, unchanged. A
fifth service now runs alongside them, the token keepalive; it binds nothing and writes no port key.

Second, the tree **used to carry a third-party traceback reporter**,
`clouddrive_common/remote/errorreport.py`, which posted a stack trace — with the raw response body
appended — to the same server as the inherited sign-in flow. It was gated on a `report_error`
setting declared `default="false"`, so it was off unless a user turned it on. Both are gone: the
module was deleted, the setting was deleted with the sign-in-server row in the settings rewrite, and
its eight call sites in five modules now log the stack trace instead of sending it. Nothing in this
add-on reports anything to anyone. The rows are under **Rewriting sign-in** above; this paragraph
survives because a reader who met the reporter in an older checkout, or in upstream, should find out
here what happened to it.

Finally, two numbers worth having written down. The transport's own retry loop has a worst-case wall
time of the number of tries multiplied by the timeout, plus the injected waits between attempts: at
the request class's defaults (`tries=4`, `delay=5`, `backoff=2`) that is
`4 × 30 + 5 + 10 + 20 = 155 seconds`. It is recorded rather than bounded; routing the wait through
Kodi's abort-aware sleep is later work. Sign-in and refresh do **not** use those defaults — they pass
a deliberately short profile (`tries=2`, `delay=5`, `backoff=1`) giving a worst case of
`2 × 30 + 5 = 65 seconds`. That is the number the refresh lock's `LIFETIME_SECONDS = 90` is set
against, and it sits twenty-five seconds clear of it. Changing either without the other is how a
lock comes to expire underneath the request still holding it.
