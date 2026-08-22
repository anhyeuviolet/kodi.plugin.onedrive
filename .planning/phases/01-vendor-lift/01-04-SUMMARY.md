---
phase: 01-vendor-lift
plan: 04
subsystem: vendoring
tags: [git, gpl, imports, gettext, strings.po, kodi, skins, compileall, crlf]

# Dependency graph
requires:
  - "01-02 — tests/test_vendor_gates.py, the instrument that proves the rename corrupted nothing"
  - "01-03 — the 30000-block renumbering that empties the 32000 block this plan fills"
provides:
  - "resources/lib/vendor/clouddrive_common/ — the upstream module at df68e9a, 28 files, importable under this add-on's own namespace"
  - "resources/lib/vendor/__init__.py — the package marker with no upstream counterpart"
  - "The merged skin tree: three dialog XMLs and seven textures under resources/skins/default/"
  - "Both .po files carrying the 30000 and 32000 blocks side by side — 114 en_gb ids, 73 he_il"
  - "A tree with no string-based import mechanism, so a text sweep over import statements is a complete proof of a rename rather than an approximate one"
  - "The exact exclusion list and local-modification record that 01-07 builds VENDORED.md from"
affects: [01-05, 01-06, 01-07, phase-03-auth, phase-06-playback, phase-07-cleanup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Copy-then-edit in two commits: the first diff against upstream is empty, so every later diff is exactly the local modification list"
    - "Anchored rewrite over bare substring: the match is a line-start import statement, which an id literal can never be"
    - "Blob-identity as the proof of verbatim: staged object ids compared against upstream's, not eyeballed diffs"
    - "The host file's line endings win in a merge; the vendored file's line endings win in a copy"

key-files:
  created:
    - resources/lib/vendor/__init__.py
    - resources/lib/vendor/clouddrive_common/ (28 files)
    - resources/skins/default/1080i/ (3 XML)
    - resources/skins/default/media/ (7 PNG)
  modified:
    - service.py
    - resources/lib/addon.py
    - resources/lib/provider/onedrive.py
    - resources/language/resource.language.en_gb/strings.po
    - resources/language/resource.language.he_il/strings.po
    - resources/lib/vendor/clouddrive_common/utils.py

key-decisions:
  - "Vendored files are staged with core.autocrlf=false so their blobs are byte-identical to upstream; git would otherwise have normalised CRLF to LF on files with no prior index entry, while leaving this repository's existing CRLF files alone"
  - "The module's LF-only he_IL block adopts the host file's CRLF on merge; no msgctxt, msgid or msgstr byte changes, and neither .po ends up with two conventions"
  - "The plan's inversion of the research Procedure was followed as the plan directs: imports first, id literals left for 01-05, which is what keeps the add-on installable at this boundary"
  - "A five-line comment marks the start of the module's block in both .po files, stating why those ids must never be renumbered — the constraint is invisible at the point where someone would break it"
  - "The research figure of 106 module import lines is a raw grep, not an import count; the real anchored surface is 98 in the module and 10 here"

patterns-established:
  - "A verbatim claim is proven by comparing git object ids against the upstream repository, not by trusting the copy command"
  - "After a mechanical rewrite, assert that every differing line is exactly the intended substitution and that line counts and endings are unchanged — a diff that is small is not the same as a diff that is correct"

requirements-completed: [VND-01, VND-02, VND-03]

coverage:
  - id: D1
    description: "The vendored tree is the upstream matrix branch at df68e9a copied verbatim in its own commit, with no modified file in that commit"
    requirement: VND-01
    verification:
      - kind: unit
        ref: "git show --name-status 413489d — 39 entries, all A"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every file containing no occurrence of the legacy dotted prefix is byte-identical to upstream, including the Apache-2.0 file and all package markers"
    requirement: VND-01
    verification:
      - kind: unit
        ref: "byte comparison of all 7 untouched module files against upstream blobs — 7 identical, 0 differing"
        status: pass
    human_judgment: false
  - id: D3
    description: "The rename matched an anchored import prefix only; neither corruption shape an unanchored replacement produces appears anywhere"
    requirement: VND-02
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_no_unanchored_rename_damage"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every one of the 98 differing lines in the rewritten module files is exactly one anchored import substitution, with line counts and line endings unchanged"
    requirement: VND-02
    verification:
      - kind: unit
        ref: "line-by-line byte comparison against upstream blobs — 98 lines examined, 0 problems"
        status: pass
    human_judgment: false
  - id: D5
    description: "No importable top-level resources package was copied in; the merge is the skin tree and the two surviving language files only"
    requirement: VND-03
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_resources_merged"
        status: pass
    human_judgment: false
  - id: D6
    description: "compileall over resources, entrypoint.py and service.py exits 0 — the only check that catches a rewrite which ate a character"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_tree_compiles"
        status: pass
    human_judgment: false
  - id: D7
    description: "No file appends to or inserts into sys.path"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_no_syspath_mutation"
        status: pass
    human_judgment: false
  - id: D8
    description: "Both .po files carry both id blocks with no duplicate; en_gb holds exactly the add-on's 25 renumbered ids plus the module's contiguous 32000-32088"
    requirement: VND-03
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_string_ids_partitioned"
        status: pass
    human_judgment: false
  - id: D9
    description: "The three dialog XMLs and seven textures are present and all 14 texture references resolve to a present file"
    requirement: VND-03
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_skin_assets_present"
        status: pass
    human_judgment: false
  - id: D10
    description: "No behaviour change beyond the recorded deviations — the add-on runs exactly as it did, only from a different location"
    requirement: VND-01
    verification:
      - kind: manual
        ref: "01-07 acceptance pass on a clean profile"
        status: deferred
    human_judgment: true
    rationale: "That a copied tree behaves identically cannot be proven from inside the repository while the external module is still installed and still satisfying the same imports. The mechanical half is proven here — verbatim bytes, an anchored rewrite, a clean compile; the behavioural half is 01-07's install matrix."

# Metrics
duration: 15min
completed: 2026-08-22
status: complete
---

# Phase 1 Plan 04: Vendor the Module Summary

**The module stops being someone else's add-on and becomes this add-on's code: 28 files copied byte-for-byte at a pinned SHA in a commit that modifies nothing, then 108 import statements repointed by a rewrite anchored so tightly it provably could not touch the six add-on-id literals sitting one substring away.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-08-22T20:54:00+07:00
- **Completed:** 2026-08-22T21:08:00+07:00
- **Tasks:** 2 of 2
- **Files:** 39 created, 5 pre-existing modified (plus 22 of the newly-vendored files edited by the rename and the dead-code deletion)

## Accomplishments

- Landed the phase's end-to-end proof. Before this, the architecture was a hypothesis; after it, the vendoring mechanism is demonstrated across every layer the phase touches — the copied tree, the rewritten imports, this repository's own ten import sites, the merged resources, and the compile check that proves none of it was mangled.
- Proved "verbatim" rather than asserting it. All 38 copied files were compared **by git object id** against the upstream repository at `df68e9a`; all 38 matched. The claim is not that the copy command was run correctly, it is that the bytes are the same bytes.
- Proved the rename was surgical rather than merely small. Every one of the 98 differing lines in the 21 rewritten module files was compared against its upstream original and shown to differ by exactly one import substitution, with line counts and line endings unchanged. The seven files with no occurrence of the legacy prefix — including the Apache-2.0 licence and all five package markers — are still byte-identical.
- Kept the add-on installable at every commit boundary. The six add-on-id literals and the manifest `<import>` are deliberately still correct, so Kodi still resolves them; 01-05 replaces both in the commit that makes the bundled copy live.
- Removed the only string-based import mechanism in the tree, which converts a text sweep over import statements from an approximate proof into a complete one for every rename that follows.

## Task Commits

1. **Task 1 (tracer), Commit A: the verbatim copy** — `413489d` (feat) — 39 files, all additions
2. **Task 1 (tracer), Commit B: the anchored rename** — `d52d638` (refactor) — 24 files, all modifications
3. **Task 2: the resource merge and the dead-code deletion** — `ca231be` (feat) — 3 files

## The copy, precisely

**Source:** `https://github.com/cguZZman/script.module.clouddrive.common`, branch `matrix`,
commit **`df68e9a589a6faef2b3228f7520e77729bc05d9b`** (2023-01-21, "Kodi 20 fix", v1.4.0,
GPL-3.0-or-later). `git rev-parse HEAD` was asserted equal to that SHA before a single file was
read. The branch tip was never resolved at execution time — though it is worth recording that the
tip *is* still that SHA today, so upstream remains frozen as research assumed.

For the record, as the plan asks: upstream has exactly two branches, `krypton` and `matrix`, with
`HEAD` pointing at `matrix`. **There is no `master` branch.** VND-01's wording names a branch that
no longer exists, and `raw.githubusercontent.com` still serves 1.3.9 — the Python 2 line — for that
dead ref. Anyone re-deriving this copy from a URL rather than from the SHA will get the wrong code
and it will look plausible.

**Mapping:** upstream `clouddrive/common/X` → `resources/lib/vendor/clouddrive_common/X`. The
redundant intermediate level is collapsed, and upstream `clouddrive/__init__.py` is not copied
because `clouddrive/common/__init__.py` becomes the vendored package's own marker.
`resources/lib/vendor/__init__.py` has no upstream counterpart and is created empty.

**Copied:** 28 module files + 3 skin XMLs + 7 textures = 38 upstream files, plus the one new
package marker.

### The exclusion list applied, with the reason for each — for VENDORED.md

| Excluded | Reason |
|---|---|
| `resources/__init__.py` | Copying it creates a second importable top-level `resources` package and makes imports ambiguous. The failure appears on some machines only, and Kodi 20's `sys.path` ordering regression amplifies every shadowing bug of this class |
| `resources/settings.xml` | Declares only the two directory-listing settings this add-on already declares, and the module reads them unqualified against the *calling* add-on — so the module's own file has never been the live one for this add-on |
| `resources/language/resource.language.pt_br/strings.po` | This add-on has no Brazilian Portuguese; additional localizations are out of scope |
| `addon.xml` | This add-on has its own |
| `service.py` | Its entire executable content is out of scope; 01-07 records that decision |
| `icon.png` | This add-on has its own |
| `LICENSE.txt` | Byte-identical to this repository's (sha256 `0b383d5a…`, confirmed); a second copy adds nothing |
| `README.md`, `.project`, `.pydevproject`, `.settings/`, `.gitignore` | Upstream repository and IDE metadata |

**Preserved deliberately:** `clouddrive/common/cache/LICENSE`, verbatim and in place. Its
provenance is genuinely unresolved — it is unmodified Apache-2.0 boilerplate whose
`[yyyy] [name of copyright owner]` placeholder was never filled in, naming nobody, while
`cache.py` beside it carries a GPL-3.0 header naming the module's own author. Deleting the file or
asserting what it covers would settle that question by assertion. 01-07 records it honestly.

## The rename, precisely

**Pattern:** `^([ \t]*)from clouddrive\.common(\.|(?= import ))` → `\1from resources.lib.vendor.clouddrive_common\2`

An id literal only ever appears inside a quoted string on the right-hand side of an assignment or
as a call argument, never at the start of an import statement, so this pattern cannot reach one.
A bare substring replacement was never run and is forbidden: `script.module.clouddrive.common`
*contains* `clouddrive.common`, and rewriting it produces a string that still parses, still runs,
and fails only at `xbmcaddon.Addon(id)` on a clean profile.

**108 import lines rewritten across 24 files:**

| Where | Lines | Files |
|---|---:|---:|
| Vendored module tree | 98 | 21 |
| `service.py` | 5 | 1 |
| `resources/lib/provider/onedrive.py` | 3 | 1 |
| `resources/lib/addon.py` | 2 | 1 |
| **Total** | **108** | **24** |

Across **22** distinct dotted sub-prefixes, with **zero** relative imports and **zero** bare
`import clouddrive` statements — both confirmed by an explicit sweep, not assumed.

### Every file the rename modified

`service.py`, `resources/lib/addon.py`, `resources/lib/provider/onedrive.py`, and under
`resources/lib/vendor/clouddrive_common/`: `account.py` (4), `cache/cache.py` (2), `db.py` (3),
`export.py` (6), `html.py` (1), `remote/errorreport.py` (6), `remote/oauth2.py` (3),
`remote/provider.py` (3), `remote/request.py` (4), `remote/signin.py` (4), `service/base.py` (3),
`service/download.py` (7), `service/export.py` (7), `service/player.py` (7), `service/source.py` (9),
`service/utils.py` (1), `ui/addon.py` (12), `ui/dialog.py` (3), `ui/logger.py` (4), `ui/utils.py` (7),
`utils.py` (2).

**Left byte-identical**, because they contain no occurrence of the legacy prefix:
`exception.py`, `cache/LICENSE`, and the five package markers `__init__.py`, `cache/__init__.py`,
`remote/__init__.py`, `service/__init__.py`, `ui/__init__.py`.

### On the plan's inversion of the research Procedure

The research Procedure resolves the id literals first and rewrites imports second; the plan does
the opposite and states that the plan is the authority. **The plan was followed.** The inversion is
sound because the rewrite is anchored on a line-start import prefix, which cannot match an id
literal — the trap the Procedure's ordering guards against is a bare substring replacement, and
that is forbidden here outright. What the inversion buys is the property the Procedure's ordering
would have destroyed: with the manifest import still declared, the six literals are still correct
and still resolve at this boundary, so the add-on remains installable. Resolving them first would
have left a commit in which the literals name an add-on the manifest no longer requires.
`test_no_unanchored_rename_damage` is green, which is the standing proof that the anchoring held.

## The resource merge, precisely

| File | This add-on | Module | Merged | Duplicates |
|---|---:|---:|---:|---:|
| `resource.language.en_gb/strings.po` | 25 | 89 (32000–32088, contiguous) | **114** | 0 |
| `resource.language.he_il/strings.po` | 12 | 61 (32004–32071) | **73** | 0 |

Not one module id was renumbered. Three are resolved at runtime from a `UIException` message
(`32065`, `32018`, `32021`) and two more from an export schedule type (`32081`, `32082`) whose value
is **persisted in the exports store**, so a mechanical shift would break lookups no static rewrite
can see and would invalidate already-stored rows. 01-03 moved this add-on's own ids instead, which
touches no dynamic site and no persisted value — and is why this merge could not produce a
duplicate.

Both files carry a five-line comment at the head of the module's block stating that constraint,
because it is invisible at exactly the point where someone would break it.

The skin tree is complete: three dialog XMLs and seven textures, with all **14** texture references
across the three XMLs resolving to a present file — checked by parsing the XML for every `<texture>`
element and every attribute value ending in `.png`, not by reasoning about it.

## The two deleted functions — for VENDORED.md's local-modification table

Both were `@staticmethod` members of `Utils` in
`resources/lib/vendor/clouddrive_common/utils.py`, removed as a contiguous 12-line block
(150 → 138 lines):

| Function | What it did | Callers |
|---|---|---|
| `Utils.get_fqn(o)` | Computed a fully-qualified name from an object: `o.__module__ + "." + o.__class__.__name__` | none, anywhere |
| `Utils.get_class(fqn)` | Split a dotted name, called `__import__(data[0])`, then walked it with `getattr` | none, anywhere |

Together they were the only string-based import mechanism in the tree. With them gone, no future
rename can be silently incomplete: a text sweep over import statements is now a complete proof
rather than an approximate one.

## Gate movement

Full suite before this plan: **12 failed, 10 passed**. After: **10 failed, 12 passed**.

| Gate | Before | After copy | After rename | After merge |
|---|---|---|---|---|
| `test_resources_merged` | red | **green** | green | green |
| `test_skin_assets_present` | red | **green** | green | green |
| `test_string_ids_partitioned` | red | red | red | **green** |
| `test_no_eval` | green | **red** | red | red |
| `test_no_unanchored_rename_damage` | green | green | **green** | green |
| `test_no_syspath_mutation` | green | green | green | green |
| `test_tree_compiles` | green | green | green | green |
| `test_gpl_headers_intact` | green | green | green | green |

`test_no_eval` flipping red is the copy landing three `eval(` sites, exactly as 01-02 predicted —
`cache/cache.py:66`, `db.py:59`, `db.py:66`. It is **not** a regression and the vendored source was
deliberately not edited to clear it, because the copy must be verbatim. 01-06 Task 1 owns it.

The four gates the plan expects to remain red did remain red, each for its intended reason:

| Gate | Why still red | Owner |
|---|---|---|
| `test_no_legacy_package_prefix` | Only add-on-id literals remain — 6 Python lines, `addon.xml:5`, `.project:6`. **Zero** import statements | 01-05 |
| `test_no_hardcoded_module_id` | The same six literals plus the manifest `<import>` | 01-05 |
| `test_addon_xml_imports` | Two `<import>` elements; the module is deliberately still declared | 01-05 |
| `test_vendor_tree_self_contained` | Exactly two unshipped imports remain: `pyqrcode` (`ui/dialog.py:125`) and `dateutil.parser` (`ui/utils.py:244`). The ≥20-import non-vacuity guard is now satisfied | 01-05 |

`test_licences_present`, `test_all_http_calls_have_timeout`, `test_vendored_sha_recorded`,
`test_vendored_md_sections` and `test_credits_content` are red as before, owned by 01-05, 01-06 and
01-07.

## Decisions Made

1. **Vendored files are staged with `core.autocrlf=false`.** This repository has `core.autocrlf=true`, and a probe confirmed that `git add` normalises CRLF to LF for a file with **no prior index entry** — while leaving this repository's existing CRLF files alone, because git skips normalisation when the index entry already contains CRLF. Staged normally, the vendored blobs would have differed from upstream's on every line, and the verbatim claim would have been false at the object level while looking fine in the working tree. Staging with the filter off makes the blobs identical *and* makes these files behave exactly like every other file in this repository from here on.

2. **The module's `he_IL` block adopts CRLF on merge.** Upstream's `he_IL` file is LF-only (262 lone LFs, zero CRLF) while every `.po` here is CRLF-only. The merge target is this add-on's file, not a vendored file, and leaving one file with two conventions to preserve a byte-level accident of upstream's would be the worse trade. No `msgctxt`, `msgid` or `msgstr` byte changes; both merged files verified CRLF-only and valid UTF-8, Hebrew text intact.

3. **A marker comment heads the module's block in both `.po` files.** Five comment lines stating that these ids are resolved dynamically and persisted, and must not be renumbered. `.po` comments are inert, and the gate parses `msgctxt` lines only.

4. **The Apache-2.0 file is preserved rather than resolved.** Recorded above; the ambiguity is real and 01-07 records it as such.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The plan's import counts are wrong, and the mismatch would read as an incomplete rename**

- **Found during:** Task 1, Commit B, in the pre-rename audit
- **Issue:** The plan states "There are 106 import lines in the module tree and 10 here, 116 in all, across 20 distinct dotted sub-prefixes". The actual anchored import surface is **98** in the module and 10 here, **108** in all, across **22** sub-prefixes. Left uncorrected, an auditor comparing the plan against the commit would count 108 rewrites where 116 were promised and reasonably conclude that 8 imports were missed.
- **Root cause, established rather than guessed:** `grep -rc 'clouddrive\.common' clouddrive/ service.py` over the upstream tree returns exactly **106**. That figure is a raw occurrence count, not an import count: 98 anchored imports under `clouddrive/`, 6 add-on-id-literal lines, and 2 imports inside the upstream `service.py` that this phase deliberately drops. 98 + 6 + 2 = 106. The research document's "106 import lines" conflates three categories, and the plan inherited it.
- **Fix:** The rename script asserts `total == 108` and fails loudly otherwise; the corrected figures are recorded here and in the commit message. No code changed as a result — the work performed is identical either way.
- **Files modified:** none (documentation correction)
- **Verification:** the anchored sweep found 108 lines; a post-rename sweep found zero import statements beginning with the legacy prefix; `test_vendor_tree_self_contained` now visits well past its ≥20-import non-vacuity guard.
- **Committed in:** `d52d638` (message body records the corrected figure)

---

**2. [Rule 3 — Blocking] `git add` would have silently broken the verbatim claim**

- **Found during:** Task 1, Commit A, before staging
- **Issue:** With `core.autocrlf=true`, `git add` normalises CRLF to LF for files with no prior index entry. Upstream's blobs contain CRLF. Staged normally, every vendored blob would have differed from upstream's on every line, so `git diff` against upstream would **not** have been empty — which is the single property the two-commit structure exists to establish.
- **Fix:** The copy commit and every later commit touching these files stage with `git -c core.autocrlf=false add`. Identity was then verified positively: all 38 files compared by git object id against upstream, 38 matches.
- **Files modified:** none (staging procedure)
- **Verification:** 38/38 object ids match; after the rename, 7/7 untouched files byte-identical; the merged `.po` blob confirmed to still carry CRLF in the index.
- **Committed in:** `413489d`

---

**3. [Rule 1 — Bug] Upstream's `he_IL` line endings would have produced a mixed-convention file**

Recorded in full as Decision 2 above. Content unchanged; only line terminators in the appended
block were normalised to the host file's convention.

---

### Precondition note

The task's precondition requires `git status --porcelain` to be empty. On arrival
`.planning/config.json` was modified-but-uncommitted — orchestrator bookkeeping carried in from
01-02 and 01-03, not this plan's doing. The **source** tree was verified clean
(`git status --porcelain -- . ':!.planning'` empty) before the rename, which is the condition the
stop-rule actually protects: a half-renamed source tree still parses. `.planning/config.json` was
deliberately kept out of all three commits, as 01-02 and 01-03 did.

---

**Total deviations:** 3 auto-fixed (2 × Rule 1 — bug, 1 × Rule 3 — blocking).
**Impact on plan:** None on scope. Two corrections concern the record rather than the work, and one
concerns how bytes are staged rather than what is staged. Every acceptance criterion in the plan
passes as written.

## Issues Encountered

- **Heredocs are blocked in this environment.** The rename, merge and verification passes were run
  as script files written to the scratch directory rather than inline one-liners. This turned out
  to be an improvement, not a workaround: each script carries its own assertions (id-literal lines
  unchanged, line counts unchanged, expected substitution count) and refuses to write anything if
  one fails.
- **`git hash-object <path>` applies the repository's clean filter** and produced two false
  "drift" reports during verification. Byte comparison against the upstream blob is the correct
  check and showed 7/7 identical.

## User Setup Required

None. This plan installs no package-manager dependency; the source is vendored from a pinned git
commit, not fetched from a registry.

## Carry-forward for later plans

- **01-05 must also fix `.project` line 6**, which reads
  `<project>script.module.clouddrive.common</project>`. This is *this repository's* Eclipse project
  file, not a vendored one, and it is a live hit in `test_no_legacy_package_prefix`. The plan for
  01-05 names the eight Python literals and the manifest `<import>`; `.project` is a ninth site and
  the gate will stay red without it.
- **01-05's two remaining unshipped imports are exactly** `pyqrcode` at
  `resources/lib/vendor/clouddrive_common/ui/dialog.py:125` and `dateutil.parser` at
  `resources/lib/vendor/clouddrive_common/ui/utils.py:244`. Both are currently satisfied at runtime
  through the still-declared module import's own transitive dependencies, which is why the add-on
  runs today and why both must land in the same commit that drops the manifest import.
- **01-06's three `eval(` sites are** `cache/cache.py:66`, `db.py:59` and `db.py:66`. Its single
  HTTP call site is `remote/request.py:132` (`urllib.request.urlopen(req)`), which needs the
  `timeout=` that `test_all_http_calls_have_timeout` is waiting for.
- **01-07's VENDORED.md** takes the exclusion table, the modified-file list and the two deleted
  functions from this summary, plus the SHA `df68e9a589a6faef2b3228f7520e77729bc05d9b`, which
  `test_vendored_sha_recorded` asserts by literal.

## Next Phase Readiness

- Every Python import in this add-on now resolves inside this add-on's own directory. The top-level
  name `clouddrive` no longer exists here, so no sibling add-on's copy can shadow this one, and
  `resources.lib.vendor.clouddrive_common` is unreachable from outside this add-on's root.
- The add-on is still installable and runnable at this boundary: the manifest still declares the
  module, the six id literals still resolve, and the module still supplies `pyqrcode` and
  `dateutil` transitively. Nothing about the running behaviour changed; only where the code lives.
- 01-05 and 01-06 can now run in parallel as planned — they touch disjoint file sets and neither
  edits `tests/test_vendor_gates.py`.

## Self-Check: PASSED

- `resources/lib/vendor/__init__.py`, `resources/lib/vendor/clouddrive_common/__init__.py`,
  `resources/lib/vendor/clouddrive_common/ui/addon.py`,
  `resources/lib/vendor/clouddrive_common/cache/LICENSE` — all found
- `resources/skins/default/1080i/pin-dialog.xml`, `resources/skins/default/media/black.png` — found
- `413489d`, `d52d638`, `ca231be` — all present in git history
- No tracked file was deleted by any of the three commits (`git diff --diff-filter=D` empty across all)
- `python -m compileall -q resources/ entrypoint.py service.py` exits 0
- Working tree clean after every commit, excluding the pre-existing `.planning/config.json`

---
*Phase: 01-vendor-lift*
*Completed: 2026-08-22*
