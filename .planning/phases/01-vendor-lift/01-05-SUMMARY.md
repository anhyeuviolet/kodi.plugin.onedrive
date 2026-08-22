---
phase: 01-vendor-lift
plan: 05
subsystem: vendoring
tags: [addon-id, kodi, profile, skins, pyqrcode, licences, iso8601, manifest, uuid, texture-cache]

# Dependency graph
requires:
  - "01-04 — the vendored tree whose imports already point inside this add-on, and whose eight id literals were deliberately left correct"
  - "01-02 — tests/test_vendor_gates.py, the instrument that proves no literal survived"
provides:
  - "A tree with no add-on-id literal for the upstream module anywhere outside .planning/ and tests/"
  - "KodiUtils.common_addon_id = None — the single change that redirects the common-addon and common-addon-path accessors, and with them all three dialog skin lookups, to this add-on"
  - "resources/lib/vendor/pyqrcode/ — the QR encoder at 1.2.1+matrix.4 with BSD-3-Clause and MIT notices, importable under its new parent package"
  - "A standard-library ISO-8601 parse with the fractional-seconds field truncated before parsing"
  - "addon.xml declaring exactly one import, xbmc.python 3.0.1 — the add-on now installs with nothing else present"
  - "FOREIGN_NOTICES in the gate suite — the per-file copyright expectation that lets BSD and MIT source ship without being re-attributed"
affects: [01-06, 01-07, phase-03-auth, phase-07-cleanup]

# Tech tracking
tech-stack:
  added:
    - "pyqrcode 1.2.1+matrix.4 (BSD-3-Clause) with pypng bundled inside it (MIT), vendored from the Kodi omega add-on zip"
  patterns:
    - "One attribute, not eight call sites: setting the id to None makes the accessor's existing None branch do the work, so five of the eight sites need no edit at all"
    - "Per-invocation filenames where a cache is keyed by path — the stale-render question is made moot rather than measured"
    - "Truncate before parsing rather than catching after: a bare handler that returns None turns a parse the input could satisfy into a silently missing field"
    - "A licence gate names the notice each file must carry rather than one notice for all files; adding a row is a stricter demand, never an escape hatch"

key-files:
  created:
    - resources/lib/vendor/pyqrcode/__init__.py
    - resources/lib/vendor/pyqrcode/builder.py
    - resources/lib/vendor/pyqrcode/tables.py
    - resources/lib/vendor/pyqrcode/png.py
    - resources/lib/vendor/pyqrcode/LICENSE.md
  modified:
    - resources/lib/vendor/clouddrive_common/ui/utils.py
    - resources/lib/vendor/clouddrive_common/ui/addon.py
    - resources/lib/vendor/clouddrive_common/ui/dialog.py
    - resources/lib/vendor/clouddrive_common/service/export.py
    - resources/lib/vendor/clouddrive_common/remote/errorreport.py
    - resources/lib/vendor/clouddrive_common/remote/signin.py
    - addon.xml
    - .project
    - tests/test_vendor_gates.py

key-decisions:
  - "The common-addon id is None rather than this add-on's own id literal: None makes the two objects one object, where a literal would make them two objects that happen to agree and would break again at the next rename"
  - "The Eclipse .project reference is deleted rather than repointed — the module is inside this repository now, so there is no sibling project to name"
  - "__init__.py's Python 2 import fallback is dropped: it imports urlparse, which has not existed since Python 2 and which this add-on cannot ship; Kodi 20+ is Python 3 only"
  - "builder.py's try/except around `import png` is collapsed to the relative branch — the try branch can only ever resolve to a top-level module that is either absent or somebody else's"
  - "test_gpl_headers_intact is made licence-aware rather than the encoder being GPL-stamped; stamping is the re-attribution that test's own closing assertion forbids"
  - "The manifest import is deleted in the same commit that vendors the encoder and replaces the date parser, because the module declared three imports and pulled both of those in transitively"

patterns-established:
  - "Vendored third-party code is held to its own upstream notice by an explicit per-file map, so a licence gate never forces re-attribution to make itself green"
  - "A write into addon_data creates its directory first: a new add-on id means the path may not exist, and that is the one realistic cause of the write failing"

requirements-completed: [VND-04, VND-08, VND-11]

coverage:
  - id: D1
    description: "No add-on-id literal for the upstream module survives outside the planning record and the gate file that must name what it forbids"
    requirement: VND-04
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_no_hardcoded_module_id"
        status: pass
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_no_legacy_package_prefix"
        status: pass
    human_judgment: false
  - id: D2
    description: "The common-addon id attribute is None, so no Kodi Addon is constructed from a literal id anywhere in the vendored tree"
    requirement: VND-04
    verification:
      - kind: unit
        ref: "grep for common_addon_id = None in ui/utils.py; the six literal sites are gone by D1"
        status: pass
    human_judgment: false
  - id: D3
    description: "All three dialog XMLs and all seven textures resolve under this add-on's own skin tree, with no edit to any of the three construction sites"
    requirement: VND-04
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_skin_assets_present"
        status: pass
    human_judgment: false
  - id: D4
    description: "The QR image write creates its profile directory first and uses a per-invocation filename"
    requirement: VND-04
    verification:
      - kind: unit
        ref: "ui/dialog.py: KodiUtils.mkdirs(profile_path) precedes the write; the name is qr-<uuid4hex>.png"
        status: pass
    human_judgment: false
  - id: D5
    description: "addon.xml declares exactly one import and it is xbmc.python at 3.0.1, asserted by parsing the manifest rather than grepping it"
    requirement: VND-11
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_addon_xml_imports"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every top-level import in the add-on tree is standard library, an xbmc module, or rooted at this add-on's own package"
    requirement: VND-11
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_vendor_tree_self_contained"
        status: pass
    human_judgment: false
  - id: D7
    description: "Both encoder licences are present and intact — BSD-3-Clause in LICENSE.md and the MIT header inside png.py"
    requirement: VND-08
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_licences_present"
        status: pass
    human_judgment: false
  - id: D8
    description: "The vendored encoder imports and constructs under its new parent package and produces a real PNG"
    requirement: VND-08
    verification:
      - kind: unit
        ref: "pyqrcode.create(...).png(BytesIO(), scale=10) -> 591 bytes with the PNG magic; .svg and .text also exercised"
        status: pass
    human_judgment: false
  - id: D9
    description: "The ISO-8601 parse handles Graph's shapes through the standard library and still returns None on failure"
    requirement: VND-08
    verification:
      - kind: unit
        ref: "probe over Z-suffixed, offset-suffixed, 0/3/6/7/9-fractional-digit, malformed, empty and None inputs"
        status: pass
    human_judgment: false
  - id: D10
    description: "The tree still compiles after every edit — the only check that catches an edit which ate a character"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_tree_compiles"
        status: pass
    human_judgment: false
  - id: D11
    description: "The add-on actually runs with nothing else installed — every id lookup resolving to this add-on on a genuinely clean profile"
    requirement: VND-04
    verification:
      - kind: manual
        ref: "01-07 acceptance pass on a clean profile"
        status: deferred
    human_judgment: true
    rationale: "Every one of the eight sites keeps resolving on any machine with a sibling cloud-drive add-on installed. The repository can prove the literals are gone; only a clean profile can prove nothing else was resolving them."

# Metrics
duration: 20min
completed: 2026-08-22
status: complete
---

# Phase 1 Plan 05: Cut the Last Three Cords Summary

**The add-on stops depending on anything it does not carry: one attribute set to `None` redirects every add-on lookup, and with it all three dialog skin paths, to this add-on; the QR encoder is bundled with both its licences; the date parse becomes standard library; and the manifest drops to a single import.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-22T21:20:00+07:00
- **Completed:** 2026-08-22T21:40:00+07:00
- **Tasks:** 2 of 2
- **Files:** 5 created, 9 modified

## Task Commits

1. **Task 1: resolve every hardcoded module-id lookup** — `2b37f9dfc97c68c454cb040686a80bb9cc37e3e5` (fix) — exactly the six files the plan names, no others, no deletions
2. **Task 1 follow-on: the ninth site 01-04 carried forward** — `f364ab18f584247b8709009f7ac630fde8574203` (chore) — `.project`
3. **Task 2: bundle the encoder, swap the parser, cut the manifest** — `5a6e112989502da8b72b49b29af586fac25f1e0a` (feat) — 8 files
4. **Task 2 follow-on: make the header gate licence-aware** — `b6d8b330aeb8af801fe229520ff9fbb136a39030` (test) — `tests/test_vendor_gates.py`

`git show --name-only --format= 2b37f9dfc97c68c454cb040686a80bb9cc37e3e5` was re-run after all four
commits and still lists exactly the six files, as the plan's self-relative assertion requires.

## The eight id sites and what each became — for VENDORED.md

The plan is precise that there are eight sites, not six: six carry the literal, and two more pass
the same value from an attribute. Five of the eight needed no edit of their own.

| # | Site | Was | Is | Edited? |
|---|---|---|---|---|
| 1 | `ui/utils.py:33` `KodiUtils.common_addon_id` | the upstream add-on id literal | `None` | **yes** — the root change |
| 2 | `ui/utils.py` `get_common_addon()` | `Addon(<literal>)` | `Addon()` via the accessor's existing `None` branch | no — follows from 1 |
| 3 | `ui/utils.py` `get_common_addon_path()` | the module's `path` info key | this add-on's `path` | no — follows from 1 |
| 4 | `ui/addon.py:82` `self._common_addon_id` | the literal | `KodiUtils.common_addon_id` | **yes** |
| 5 | `ui/addon.py:675/676/679/680` settings reads | passed the literal | pass `None` | no — follows from 4 |
| 6 | `service/export.py:40` `self._common_addon_id` | the literal | `KodiUtils.common_addon_id` | **yes** |
| 7 | `ui/dialog.py:126` QR image profile path | `get_addon_info("profile", <literal>)` | `get_addon_info("profile")` | **yes**, plus two guards |
| 8 | `remote/errorreport.py:70` version lookup | `get_addon_info('version', <literal>)` | `get_addon_info('version')` | **yes** |
| — | `remote/signin.py:32` User-Agent | third field was the module's version | this add-on's own version | **yes** |
| — | `.project:6` Eclipse project reference | the literal | deleted; `<projects>` is empty | **yes** (ninth site, see deviations) |
| — | `addon.xml:5` manifest import | declared the module | deleted in Task 2 | **yes** |

`ui/addon.py:84` (`_common_addon_version`) now reads this add-on's own version, which is what feeds
the User-Agent's third field and the exception report's version triple. One of the two settings at
site 5 (`report_error_invite`) is declared in no settings file at all and therefore already returned
an empty string; it is left exactly as it was, because this phase preserves behaviour and Phase 7
deletes the subsystem under KODI-08.

### Why `None` and not this add-on's own id literal

`None` makes the common add-on and this add-on **one object**. Writing this add-on's id would make
them two objects that happen to agree — correct today, and wrong again the next time the id changes.
The accessor already had the `None` branch; the plan's insight is that nothing needed writing, only
deleting.

This is also what makes the merged skin tree live. All three dialogs — `QRDialogProgress`,
`ExportScheduleDialog`, `ExportMainDialog` — take their script-path argument from
`KodiUtils.get_common_addon_path()`, so **none of the three construction sites was edited** and all
three now load `pin-dialog.xml`, `export-schedule-dialog.xml` and `export-main-dialog.xml` from this
add-on's own `resources/skins/default/`.

## The two QR-image write guards — for VENDORED.md's local-modification table

Both are in `ui/dialog.py`, in `QRDialogProgress.onInit`, in the same edit as site 7.

**Guard 1 — create the profile directory before writing.** The profile path is translated into a
local, then `KodiUtils.mkdirs(profile_path)` (which is `xbmcvfs.mkdirs`) runs immediately before the
encoder writes. Upstream never needed this because its profile directory always already existed; a
brand-new add-on id means a brand-new `addon_data` path that may not exist on first sign-in, and the
write would otherwise raise before the dialog renders. A traceback in the acceptance log is a
phase-gate failure under 01-07's criteria.

**Guard 2 — a per-invocation filename.** The exact shape produced is:

```
qr-<32 lowercase hex characters>.png        e.g. qr-3f2a...c81d.png
```

built as `os.path.join(profile_path, "qr-%s.png" % uuid.uuid4().hex)`, replacing the fixed `qr.png`.
Kodi's texture cache is keyed by path, so a second sign-in within one Kodi session that overwrote a
single fixed name can render the *previous* image against the *new* code — a dialog that looks like
it is working while showing a code that will not authorise. The existing teardown deletion in
`__del__` already targets `self._image_path` and therefore follows the new name with no edit.
`import uuid` was added to the module's import block.

**No swallow-and-degrade path was added** around the write, as the plan directs. A text-only
fallback is Phase 3's job under AUTH-05/AUTH-06; here an unexpected write failure must still surface
as a traceback, because the acceptance log is the phase's evidence.

## The QR encoder, precisely — for VENDORED.md

- **Source:** `https://mirrors.kodi.tv/addons/omega/script.module.pyqrcode/script.module.pyqrcode-1.2.1+matrix.4.zip`
- **Redirects to:** `https://www.mirrorservice.org/sites/mirrors.xbmc.org/addons/omega/script.module.pyqrcode/script.module.pyqrcode-1.2.1+matrix.4.zip` (the mirror answers the canonical URL with a 302; a plain `curl` without `-L` reports `302` and a zero-byte body)
- **Version:** `1.2.1+matrix.4`, add-on id `script.module.pyqrcode`, provider Michael Nooner
- **Zip sha256:** `3bd98699099b531ba8175a3822536927eeaac111d7cb9d12e1f0ed707b020899` (66,542 bytes)
- **Upstream source of the code:** `https://github.com/mnooner256/pyqrcode`, licence declared BSD-3-Clause in the zip's own `addon.xml`
- **Mapping:** `script.module.pyqrcode/lib/pyqrcode/*` → `resources/lib/vendor/pyqrcode/*`; `script.module.pyqrcode/LICENSE.md` → `resources/lib/vendor/pyqrcode/LICENSE.md`
- **Not copied:** `addon.xml` and `icon.png` — Kodi add-on wrapper metadata, meaningless inside this add-on

Taken from the Kodi add-on zip rather than PyPI or a source archive because that zip is the exact
build this add-on was tested against **and** it is the only distribution that bundles the PNG
writer, which exists as no separate Kodi module in any repository branch.

| Vendored file | Bytes | sha256 | Byte-identical to the zip? |
|---|---:|---|---|
| `__init__.py` | 32,727 | `781d7ba4aef8a83ca3932a52ea07b4c83f145f8b6f33ca9605fd1c161897bc2a` | no — 3 rewrites |
| `builder.py` | 57,948 | `bc4f6d4ccffc2d59b40babf7ba6ff3ed8aeb33a92197b72086a872b1479cc4ca` | no — 2 rewrites |
| `tables.py` | 31,446 | `20983a11ec5dc81fd74629d9ba6f3a9a737d8a410cce390b4e10bf5c2dbef588` | **yes** |
| `png.py` | 81,765 | `9f70a9033f0f7f4412719c7a51cad9043c0187dfe09698b3c1b04ebb859d17df` | **yes** |
| `LICENSE.md` | 1,503 | `0d2437a10d8ef93c488d49b0a09068c56bc1543e8ee9393bcbba15d172a031f9` | **yes** |

All five are LF-only, exactly as the zip ships them, and were staged with
`git -c core.autocrlf=false add` so the blobs match the zip's bytes — the same procedure 01-04
established for the vendored tree.

### Every internal import rewritten inside the encoder — for VENDORED.md

Five edits across two files. `tables.py`, `png.py` and `LICENSE.md` were not touched at all.

| File | Line | Was | Is | Why |
|---|---:|---|---|---|
| `__init__.py` | 46 | `import pyqrcode.tables` | `from . import tables` | absolute self-import; resolves to nothing under a parent package |
| `__init__.py` | 47 | `import pyqrcode.builder as builder` | `from . import builder` | same |
| `__init__.py` | 382–387 | a `try: # Python 2` block importing `urlparse`/`urllib.pathname2url` with a Python 3 `except ImportError` fallback | the two Python 3 imports only | see deviation 2 |
| `builder.py` | 33 | `import pyqrcode.tables as tables` | `from . import tables` | absolute self-import |
| `builder.py` | 1266–1269 | `try: import png / except ImportError: from . import png` | `from . import png` | the try branch can only ever bind a *top-level* `png` — absent here, or somebody else's module if present |

The `from . import tables` form is not merely equivalent to the original in `__init__.py`, it is the
same mechanism written down: importing a submodule binds it as an attribute of the parent package,
and inside `pyqrcode/__init__.py` the package namespace *is* the module globals, which is why the
original's bare `tables.modes` references worked at all.

`__init__.py` and `builder.py` also contain `from __future__ import ...` lines; those are left
untouched and are inert on Python 3.

The dialog's function-local import became
`import resources.lib.vendor.pyqrcode as pyqrcode` and stays function-local, inside `onInit` — the
dialog constructs and its skin loads without the encoder. It is **not** guarded, and the QR is not
skippable, as the plan directs.

## The date parse — for VENDORED.md

`KodiUtils.to_datetime` in `ui/utils.py` was five lines calling `dateutil.parser.parse`. It is now:

```python
s = re.sub(r'(\.\d{6})\d+', r'\1', s)
return datetime.datetime.fromisoformat(s)
```

still inside the original bare handler that returns `None` on failure, with `import datetime` and
`import re` replacing `import dateutil.parser` in the same function-local position.

**The exact form of the truncation** is `re.sub(r'(\.\d{6})\d+', r'\1', s)` — it fires only on seven
or more fractional digits and is a literal no-op for every value with six or fewer, which is why it
is not redundant with the handler. A six-line comment in the code states that reason so a later
reader does not remove it as dead weight.

Behaviour was probed rather than reasoned about. Both call sites feed it Graph's
`lastModifiedDateTime` (`resources/lib/provider/onedrive.py:131`), reaching
`ui/addon.py:396` and `service/source.py:241`:

| Input | Result |
|---|---|
| `2026-08-22T10:11:12Z` | `2026-08-22 10:11:12+00:00` |
| `2026-08-22T10:11:12.123Z` | `2026-08-22 10:11:12.123000+00:00` |
| `2026-08-22T10:11:12.1234567Z` (seven digits) | `2026-08-22 10:11:12.123456+00:00` |
| `2026-08-22T10:11:12.123456789Z` (nine digits) | `2026-08-22 10:11:12.123456+00:00` |
| `2026-08-22T10:11:12+07:00` | `2026-08-22 10:11:12+07:00` |
| `'not a date'`, `''`, `None` | `None` — the pre-existing failure behaviour, unchanged |

**As the plan asks, recorded as an assumption rather than an observation:** the seven-digit
SharePoint case was **not observed directly**; it is carried from research. Two honest notes on top
of that. First, the truncation is harmless if it never occurs. Second, and worth recording because
it slightly weakens the stated motivation: on the CPython **3.11.9** available here,
`datetime.fromisoformat` *already* accepts and truncates seven and nine fractional digits, so on
that build the substitution is redundant. The plan's premise — "the parser accepts only three or six
fractional digits" — describes the pre-3.11 parser. Whether Kodi Nexus's **3.11.2** is equally
permissive was not verified, no 3.11.2 interpreter being available, so the truncation is kept: it
costs one regex on a metadata field and removes the question.

## The manifest

`addon.xml` went from two `<import>` elements to one:

```xml
<requires>
    <import addon="xbmc.python" version="3.0.1" />
</requires>
```

This deletion landed only after the encoder was vendored and the date parser replaced, in the same
commit, because the module declared **three** imports, not one: itself, plus the QR encoder and the
date parser transitively. Dropping its import drops those two from the installed set, which is why
all three had to move together. Deleting it earlier would have left the add-on with neither the
external module nor a working local copy.

## Gate movement

Full suite before this plan: **10 failed, 12 passed**. After: **5 failed, 17 passed**.

| Gate | Before | After Task 1 | After Task 2 | Final |
|---|---|---|---|---|
| `test_no_hardcoded_module_id` | red | red (`.project`, `addon.xml` only) | **green** | green |
| `test_no_legacy_package_prefix` | red | red (same two) | **green** | green |
| `test_addon_xml_imports` | red | red | **green** | green |
| `test_vendor_tree_self_contained` | red | red | **green** | green |
| `test_licences_present` | red | red | **green** | green |
| `test_gpl_headers_intact` | green | green | **red** | **green** (deviation 3) |
| `test_skin_assets_present`, `test_tree_compiles`, `test_no_unanchored_rename_damage` | green | green | green | green |

The five still red are all owned by later plans and none is this plan's:

| Gate | Owner |
|---|---|
| `test_no_eval` — three `eval(` sites at `cache/cache.py:66`, `db.py:59`, `db.py:66` | 01-06 |
| `test_all_http_calls_have_timeout` — `remote/request.py:132` | 01-06 |
| `test_vendored_sha_recorded`, `test_vendored_md_sections`, `test_credits_content` | 01-07 |

## Decisions Made

1. **`common_addon_id = None`, not this add-on's id.** Recorded above: `None` makes the two Addon
   objects one object; a literal makes them two that happen to agree, and re-breaks on the next
   rename.
2. **The Eclipse `<project>` reference is deleted, not repointed.** The module lives inside this
   repository now, so there is no sibling workspace project to name. `<projects>` is left empty and
   `.project` still parses as XML.
3. **The encoder came from the Kodi add-on zip, and both licences travel with it.** BSD-3-Clause in
   `LICENSE.md` (Copyright (c) 2013 Michael Nooner) and the MIT header inside `png.py` (Copyright
   (C) 2006 Johann C. Rocholl and others) — that in-file header *is* the notice and was kept intact.
4. **`builder.py`'s `import png` try-branch is removed, not kept as a fallback.** Keeping it would
   mean the encoder silently prefers a top-level `png` module belonging to some other add-on if one
   is ever importable — the same class of shadowing bug the whole vendor lift exists to remove.
5. **The header gate is corrected rather than the encoder re-stamped.** Detailed as deviation 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] The ninth id site the plan does not name: `.project`**

- **Found during:** Task 1, in the post-edit gate run
- **Issue:** `.project` line 6 read `<project>script.module.clouddrive.common</project>`. It is
  this repository's own Eclipse project file, has no suffix and so counts as text under the gate's
  `_is_text`, and is a live hit in both `test_no_legacy_package_prefix` and
  `test_no_hardcoded_module_id`. The plan names eight Python sites plus the manifest; this is a
  ninth, and both gates stay red without it. 01-04's summary carried it forward explicitly.
- **Fix:** The `<project>` element is deleted, leaving `<projects>` empty. Deleting rather than
  repointing is correct: the module is inside this repository now, so it is not a referenced
  project any more.
- **Files modified:** `.project`
- **Verification:** `ET.parse('.project')` succeeds and `<projects>` has zero children; both gates
  then report only `addon.xml:5`, which Task 2 owns.
- **Committed in:** `f364ab1` — deliberately a separate commit, so the plan's acceptance criterion
  that Task 1's commit lists **exactly** the six named files stays literally true.

---

**2. [Rule 3 — Blocking] The encoder's Python 2 fallback imports a module that cannot ship**

- **Found during:** Task 2, in the extracted-file import audit
- **Issue:** `pyqrcode/__init__.py` lines 382–387 contain a `try: # Python 2` block importing
  `from urlparse import urljoin` and `from urllib import pathname2url`, with the Python 3 forms in
  the `except ImportError`. `urlparse` is not a standard-library module on any Python 3, so
  `test_vendor_tree_self_contained` reads it — correctly — as an unshipped dependency and fails.
  The plan says to rewrite self-imports and "leave every other import alone", but leaving this one
  leaves the plan's own acceptance criterion unsatisfiable.
- **Fix:** The `try`/`except` is collapsed to the two Python 3 imports. Kodi 20+ is Python 3 only
  (the manifest's `xbmc.python 3.0.1` floor is exactly that decision), so the Python 2 branch was
  unreachable dead code. It sits inside `QRCode.show()`, a debugging helper that opens a web
  browser and which this add-on never calls.
- **Files modified:** `resources/lib/vendor/pyqrcode/__init__.py`
- **Verification:** `test_vendor_tree_self_contained` green; the encoder imports, and
  `pyqrcode.create(...).png(...)` produces a 591-byte file with the PNG magic number.
- **Committed in:** `5a6e112`; recorded in the rewrite table above so 01-07 carries it.

---

**3. [Rule 1 — Bug] The copyright-header gate cannot be satisfied by BSD or MIT source without
re-attributing it**

- **Found during:** Task 2, immediately after the encoder was staged
- **Issue:** `test_gpl_headers_intact` asserts `'GNU General Public License'` appears in the first
  25 lines of **every** non-empty tracked `.py`. This plan lands four files that are BSD-3-Clause
  and MIT. The gate flipped red on all four.
- **Root cause, established rather than guessed:** 01-02's own summary contains both halves of the
  contradiction. Its line 131 records `test_gpl_headers_intact` as needing to "stay green through
  01-04's copy and 01-06's edits" — 01-05 is not mentioned — while line 152 records that
  `pyqrcode/LICENSE.md` and `png.py` (BSD-3-Clause, MIT) arrive **with 01-05**. The gate was
  written before the tree it now guards contained non-GPL source.
- **Why not the obvious fix:** adding a GPL banner to Michael Nooner's BSD code is licence
  misattribution, and it is specifically what the same test's own closing assertion — "the upstream
  copyright notice must be preserved, not re-attributed" — exists to prevent. The gate would have
  been made green by committing the exact wrong the gate is for.
- **Fix:** the check is made licence-aware, not weaker. A module-level `FOREIGN_NOTICES` map (beside
  the existing exclusion sets, with the file's own "lives here and nowhere else" discipline) names
  the one exact phrase each foreign file must carry — `Michael Nooner` for the three encoder files,
  `Johann C. Rocholl` for `png.py` — and every other checked file still must carry the GPL phrase.
  **No file is excused from carrying a notice**; only which notice is expected changes. An added
  orphan assertion fails if a row stops naming real checked source, which is the way a per-file
  expectation would otherwise quietly stop checking a file.
- **Non-vacuity proved by mutation, not by reading:** replacing `Michael Nooner` with
  `Somebody Else` in `tables.py` makes the gate fail; restoring it makes it pass.
- **Files modified:** `tests/test_vendor_gates.py`
- **Committed in:** `b6d8b33` — a separate commit from the vendoring, because a semantic change to
  the gate suite should not hide inside a 5,400-line vendoring diff. `5a6e112`'s message states
  that the gate is red at that boundary and why, so nobody bisecting reads it as a real regression.
- **Note for 01-06:** 01-04 recorded that neither 01-05 nor 01-06 edits `tests/test_vendor_gates.py`.
  That is now false for 01-05. 01-06 touches `test_no_eval` and `test_all_http_calls_have_timeout`,
  which are far from `test_gpl_headers_intact` and `FOREIGN_NOTICES`, so no conflict is expected —
  but 01-06 should rebase on `b6d8b33` rather than on `8a883d0`.

---

### Precondition note

Task 2's precondition — "mirrors.kodi.tv is reachable and the pyqrcode add-on zip for the omega
branch downloads with an HTTP 200" — was checked read-only and **met**, with one wrinkle worth
recording: the directory index returns `200` directly, but the zip URL returns **`302`** to
`www.mirrorservice.org` and only returns `200` when the redirect is followed. `curl` without `-L`
reports a 302 and a zero-byte body, which reads like a failure and is not one.

### Standing note

`.planning/config.json` was modified-but-uncommitted on arrival — orchestrator bookkeeping, not this
plan's doing — and was deliberately kept out of all four commits, as 01-02 through 01-04 did.

---

**Total deviations:** 3 auto-fixed (2 × Rule 3 — blocking, 1 × Rule 1 — bug).
**Impact on plan:** None on scope. Every acceptance criterion in both tasks passes as written, with
one ordering caveat recorded below.

## Issues Encountered

- **Task 1's acceptance criteria cannot all hold at Task 1's own commit boundary.** They require
  `test_no_hardcoded_module_id` and `test_no_legacy_package_prefix` to exit 0, but `addon.xml:5`
  carries the literal and Task 2 owns deleting it — by the plan's own explicit reasoning, since
  deleting it before the encoder is vendored would leave the add-on with neither the module nor a
  working local copy. Both gates were confirmed at the Task 1 boundary to report **exactly**
  `.project:6` and `addon.xml:5` and nothing else, proving every Python site was closed, and both
  went green at the end of Task 2. Nothing was changed to work around this; it is a plan-internal
  ordering artefact and is recorded rather than papered over.
- **Heredocs remain blocked in this environment.** Every edit was applied by a script written to the
  scratch directory carrying its own assertions — each replacement must match exactly once, line
  endings are checked before and after, and nothing is written if any assertion fails. This is why
  the CRLF/LF split (CRLF for this repository's files, LF for the encoder's) held without incident.

## User Setup Required

None. No package-manager dependency was installed. The encoder was vendored from a pinned Kodi
add-on zip whose sha256 is recorded above, and the date parser was replaced by the standard library.

## Carry-forward for later plans

- **01-06** should rebase on `b6d8b33`. Its three `eval(` sites are `cache/cache.py:66`, `db.py:59`
  and `db.py:66`; its HTTP call site is `remote/request.py:132`. `FOREIGN_NOTICES` now exists at the
  top of the gate file — if 01-06 adds any file under `resources/lib/vendor/pyqrcode/` it must add a
  row, and the orphan assertion will complain if a row stops matching.
- **01-07's VENDORED.md** takes from this summary: the eight-site table, the two QR write guards
  with the exact `qr-<uuid4hex>.png` shape, the pyqrcode zip URL, its `1.2.1+matrix.4` version and
  `3bd98699…` sha256, the five-row internal-import rewrite table, the per-file sha256 table, and the
  exact truncation `re.sub(r'(\.\d{6})\d+', r'\1', s)`. It should also record `errorreport.py` as a
  **carried liability** — edited only to drop an add-on-id argument, no reporting path extended or
  wired, gating setting already off, deleted in Phase 7 under KODI-08 — so a later reader can tell
  "considered and carried" from "overlooked".
- **01-07's CREDITS.md** needs both new attributions: pyqrcode, BSD-3-Clause, Copyright (c) 2013
  Michael Nooner; pypng, MIT, Copyright (C) 2006 Johann C. Rocholl, with portions (C) 2009 David
  Jones and (C) 2006 Nicko van Someren.
- **01-07's acceptance pass** is what actually closes D11 and the third success criterion: the
  repository can prove the literals are gone, but only a clean profile with no sibling cloud-drive
  add-on installed can prove nothing else was quietly satisfying them. The QR dialog is the first
  thing a user sees and now writes to a directory it creates itself.
- **Phase 3** reuses `QRDialogProgress` for device-code sign-in and owns the text-only fallback
  under AUTH-05/AUTH-06 that this phase deliberately did not add.

## Threat Flags

None. No file created or modified here introduces network surface, an auth path, a file-access
pattern or a schema change that the plan's threat register does not already cover. The one new
write — the QR image — is `T-1-12` and is mitigated as the register specifies.

## Backstopped truth

The plan carries one truth marked `verification: backstop`: Kodi resolves a dialog skin under the
current skin id before falling back to the default skin directory, and only the default fallback
tree is shipped, so **a user skin literally named `default` would shadow it**. This is recorded, not
guarded, in this phase — exactly as the plan specifies. Nothing here changes that exposure; the
three dialogs previously resolved against the module's `default` tree and now resolve against this
add-on's, with the same shadowing rule applying to both.

## Known Stubs

None. No hardcoded empty value, placeholder string or unwired data source was introduced. Every
file created or modified is live code on a path the add-on executes.

## Next Phase Readiness

- `addon.xml` declares exactly one import. Every top-level import in the tree is standard library,
  an `xbmc` module, or rooted at `resources` — asserted by AST walk over every tracked `.py` under
  `resources/` plus the two entry scripts, past its ≥20-import non-vacuity guard.
- Nothing in the tree can be made to work by installing something else. That was the phase's
  success criterion and it is now structurally true rather than argued.
- The add-on is no longer installable-only-by-luck: before this plan every id lookup resolved on any
  machine with a sibling cloud-drive add-on present, and the same tree on a clean profile raised
  "Unknown addon id". Both halves are now the same.

## Self-Check: PASSED

- `resources/lib/vendor/pyqrcode/{__init__,builder,tables,png}.py` and `LICENSE.md` — all found
- `addon.xml`, `.project` — found, both parse as XML
- `2b37f9d`, `f364ab1`, `5a6e112`, `b6d8b33` — all present in git history
- `git show --name-only --format= 2b37f9d…` still lists exactly the six files the plan names
- No tracked file was deleted by any of the four commits (`git diff --diff-filter=D` empty across
  the whole range `8a883d0..b6d8b33`)
- `python -m compileall -q resources/ entrypoint.py service.py` exits 0
- No untracked file left behind; working tree clean apart from the pre-existing
  `.planning/config.json`
- Full suite: 17 passed, 5 failed — every failure owned by 01-06 or 01-07, none by this plan

---
*Phase: 01-vendor-lift*
*Completed: 2026-08-22*
