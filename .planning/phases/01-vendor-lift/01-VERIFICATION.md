---
phase: 01-vendor-lift
verified: 2026-08-23T00:21:11Z
status: gaps_found
score: 16/18 must-haves verified
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "Kodi 19 mechanically refuses to install the add-on; Kodi 20, 21 and 22 install it and load both the plugin and service entry points"
    reason: "Narrowed by owner decision on 2026-08-23. This add-on targets one device, a TCL television running Android TV 12; the Windows leg and the four-version install matrix are not pursued. Recorded as unmet — not satisfied — in ROADMAP.md success criterion 2, in REQUIREMENTS.md KODI-02, and in 01-07-SUMMARY.md. The Windows leg was stopped mid-run by decision, not by failure"
    accepted_by: "Kenny Nguyen"
    accepted_at: "2026-08-23T00:00:00Z"
gaps:
  - truth: "The vendoring record makes every vendored component re-derivable from a fixed point"
    status: partial
    reason: "Complete and independently reproducible for the Cloud Drive common module. Absent for the second vendored component, the QR encoder. VENDORED.md identifies its source only as 'the QR encoder add-on zip' — no add-on id, no URL, no version, no checksum. CREDITS.md names the GitHub project `mnooner256/pyqrcode`, but the copy was NOT taken from there; it was taken from a Kodi add-on zip, and a reader following CREDITS.md would re-derive different bytes. 01-05-SUMMARY.md line 519 explicitly handed these facts forward to 01-07 for inclusion in VENDORED.md; they did not land. This is the concrete reason VND-09 is correctly left unchecked"
    artifacts:
      - path: "VENDORED.md"
        issue: "No Upstream entry for `resources/lib/vendor/pyqrcode/`. Zero occurrences of `script.module.pyqrcode`, `mirrors.kodi.tv`, `1.2.1+matrix.4`, or the zip sha256"
    missing:
      - "An Upstream row for the QR encoder in VENDORED.md: add-on id `script.module.pyqrcode`, version `1.2.1+matrix.4`, URL `https://mirrors.kodi.tv/addons/omega/script.module.pyqrcode/script.module.pyqrcode-1.2.1+matrix.4.zip`, zip sha256 `3bd98699099b531ba8175a3822536927eeaac111d7cb9d12e1f0ed707b020899` (66,542 bytes), the `script.module.pyqrcode/lib/pyqrcode/* -> resources/lib/vendor/pyqrcode/*` mapping, and the statement that `addon.xml` and `icon.png` were not copied"
      - "The per-file sha256 table from 01-05-SUMMARY.md (all five values re-verified as still current during this verification)"
      - "A note in CREDITS.md that the GitHub project is the code's origin but not the copy's source"
  - truth: "VENDORED.md's local-modification table is accurate at the granularity it claims (one row per file)"
    status: partial
    reason: "No unrecorded modification exists — that was checked exhaustively and is clean. Two counts in the table are wrong, and the table is described in its own preamble as 'the table a future upstream diff starts from', so a wrong count sends that diff looking for changes that are not there"
    artifacts:
      - path: "VENDORED.md"
        issue: "db.py row says 'Three reads ... Two writes'. db.py has TWO reads and TWO writes; the third read is in cache/cache.py, which has its own row. The figure 3 is the phase-wide read total misfiled under one file. 01-06-SUMMARY.md states it correctly ('three eval( reads and four repr( writes')"
      - path: "VENDORED.md"
        issue: "pyqrcode row says 'Five internal self-imports rewritten ... and two Python-2 compatibility try/except blocks reduced' — double counting. Verified against the zip: THREE self-imports rewritten (__init__.py x2, builder.py x1) plus two try/except reductions = five EDITS total. 01-05-SUMMARY.md states it correctly ('Five edits across two files')"
    missing:
      - "Correct the db.py row to 'Two reads ... Two writes'"
      - "Correct the pyqrcode row to 'Three internal self-imports rewritten ... and two Python-2 compatibility try/except ImportError blocks reduced — five edits across two files'"
  - truth: "REQUIREMENTS.md checkbox state does not assert more than the evidence supports"
    status: partial
    reason: "Two checked requirements carry no caveat while the SUMMARY that closed them states an explicit limitation. KODI-02 was given an inline narrowing note; KODI-01 and SETUP-06 were not, and REQUIREMENTS.md is the file every later phase reads"
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "KODI-01 is `[x]` / Complete, unqualified. Its Kodi-19-refusal half rests solely on an unobserved run on an unverified profile (`D:/KodiPortable/kodi-19.5/portable_data/kodi.log`), and its 'installs on 20, 21 and 22' half has controlled evidence only for 21.3 on Android. 01-07-SUMMARY.md says so and flags it for the owner to decide; REQUIREMENTS.md is silent"
      - path: ".planning/REQUIREMENTS.md"
        issue: "SETUP-06 is `[x]` / Complete and its text still demands 'an Android phone running Kodi and reachable over adb'. No phone was ever connected; AVD `kodi_api30` (Android 11 / API 30) stood in, recorded as an approved substitution in 01-01-SUMMARY.md deviation 1"
    missing:
      - "Add an inline caveat to KODI-01 in the same style as KODI-02, naming the uncontrolled Kodi 19 log and the single controlled install (21.3 / Android)"
      - "Add an inline note to SETUP-06 that the Android instrument is an emulator, not a phone, with the limits 01-01-SUMMARY.md records"
  - truth: "ROADMAP.md carries no premise the phase has already disproved"
    status: partial
    reason: "01-07 measured the sign-in broker alive and corrected VENDORED.md and README.md on that measurement. The ROADMAP parenthetical was not corrected, so the roadmap still hands the disproved premise forward — the exact failure mode 01-07 caught once already"
    artifacts:
      - path: ".planning/ROADMAP.md"
        issue: "Phase 1 success criterion 3 reads '(modulo the already-dead broker)'. The broker is not dead: measured 2026-08-22, `GET /ip` and `POST /pin` both answered 200 and the add-on began polling. VENDORED.md deviation 1 and README.md were rewritten; this line was not"
    missing:
      - "Rewrite the parenthetical in ROADMAP.md Phase 1 success criterion 3 to match the measurement"
deferred:
  - truth: "First acceptance run on the TCL Android TV 12 (API 31): D-pad focus order, ten-foot readability, real GPU and codec behaviour, low-end performance, and whether the vendor ROM restricts shell access to Android/data"
    addressed_in: "Phase 3"
    evidence: "Phase 3 success criterion 6: 'First run on the real target device... the same checklist the Android emulator ran in Phase 1 is repeated on it... This is the first time the add-on runs on the hardware it is written for'"
  - truth: "The dialog smoke action is removed or placed behind a debug-only gate"
    addressed_in: "Phase 7 / release"
    evidence: "Recorded in VENDORED.md deviation 4 as 'scheduled for removal, or for a debug-only gate, before release', which is the condition VND-10's prohibition attaches to it"
  - truth: "The unauthenticated directory-listing server, the third-party error reporter and the report_error setting are deleted"
    addressed_in: "Phase 7"
    evidence: "Phase 7 success criterion 4 and requirements KODI-07, KODI-08"
  - truth: "Packaging excludes .gitignore, .project and .pydevproject and produces a directory named after the add-on id"
    addressed_in: "Phase 5"
    evidence: "Phase 5 success criterion 1: 'A build produces plugin.onedrive-<version>.zip containing exactly one top-level plugin.onedrive/ directory'"
human_verification:
  - test: "Open https://github.com/anhyeuviolet/kodi.plugin.onedrive in a browser while signed in and confirm the repository header shows no 'forked from cguZZman/plugin.onedrive' line"
    expected: "No fork-network banner. ID-05's history half is already verified mechanically: 163 commits, upstream root commits `2482723 Create README.md` and `872108b Initial version` still present, nothing squashed"
    why_human: "The repository is private. `curl https://api.github.com/repos/anhyeuviolet/kodi.plugin.onedrive` returns 404 for an unauthenticated caller, and no `gh` CLI is installed, so fork-network membership cannot be read from this shell"
  - test: "Decide KODI-01: either accept the harvested Kodi 19.5 log as sufficient evidence of the refusal, or install the zip once on Kodi 19 under an observed run on a verified-clean profile"
    expected: "A recorded decision. If accepted, KODI-01 keeps its checkbox with the caveat added. If re-run, `CAddonInstallJob[plugin.onedrive.kn]: The dependency on xbmc.python version 3.0.1 could not be satisfied.` appears under observation"
    why_human: "01-07-SUMMARY.md explicitly escalates this: 'It is flagged here for the owner to decide.' The log content was re-verified during this verification and is exactly as quoted, but the run was unobserved and the profile unverified, which no amount of re-reading the file can fix"
  - test: "Measure Request.HTTP_TIMEOUT_SECONDS = 30 under a throttled connection resembling marginal Android TV Wi-Fi"
    expected: "Either a measurement that supports 30, or a corrected value"
    why_human: "Deliberately deferred and must remain unpassed. No network throttling was applied in 01-06 or 01-07, on any platform. The value's entire justification is a condition no run has been near. It must not be reported as validated"
  - test: "On the TCL Android TV 12, confirm whether the vendor ROM permits shell access to /sdcard/Android/data/org.xbmc.kodi/"
    expected: "An answer either way, recorded"
    why_human: "Deliberately deferred and must remain unpassed. Unanswerable on the instruments used — the emulator is an AOSP image with no vendor storage policy. Resolves the first time the add-on runs on the TCL"
  - test: "On the TCL Android TV 12, check D-pad focus order through all three dialogs, ten-foot readability of the QR code, real GPU and codec behaviour, and responsiveness on the low-end SoC"
    expected: "Recorded observations, or defects raised"
    why_human: "The one filled acceptance row ran on AVD kodi_api30, Android 11 / API 30, software-rendered through SwiftShader — one API level below the target and a different form factor. 01-07-SUMMARY.md claims none of these and says so. Deferred to Phase 3 by decision"
---

# Phase 1: Vendor Lift Verification Report

**Phase Goal:** The add-on carries its own complete, renamed copy of the common module, ships under its own identity, and depends on nothing outside `xbmc.python`, behaving exactly as it did before.
**Verified:** 2026-08-23T00:21:11Z
**Status:** gaps_found — four record-accuracy gaps, no functional blocker
**Re-verification:** No — initial verification

---

## Verdict in one paragraph

The phase goal is achieved and the load-bearing claims survive adversarial checking. The verbatim-copy proof is not a claim, it is a measured fact: upstream was cloned at `df68e9a` during this verification and all 38 copied blobs are byte-identical by git object id. Every subsequent modification to the vendored tree was diffed and every one is accounted for in `VENDORED.md`; nothing was smuggled in. The QR encoder's zip was re-downloaded and its sha256, byte count, three untouched files and two modified files all match the record exactly. The 22/22 suite was re-run in this verifier's own process, the two gates the user flagged were read line by line and neither was weakened, `kodi-addon-checker` was re-run against a freshly staged artefact and reproduced the claimed zero-ERROR result verbatim, and the archived acceptance log was re-greped and every quoted line is real. The gaps are all in the *record*, not the code: the QR encoder's provenance never made it from a plan SUMMARY into `VENDORED.md`, two counts in the modification table are wrong, and two REQUIREMENTS.md checkboxes assert more than their own SUMMARYs do.

---

## Goal Achievement

### Observable Truths

Merged from ROADMAP.md Phase 1 success criteria (the contract) and the `must_haves.truths` of all seven plans.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No `script.module.clouddrive.common` id literal and no `eval(`/`exec(` survive in shipped source; `addon.xml` declares no `<import>` other than `xbmc.python` | VERIFIED | `git grep` over all tracked files excluding `.planning/` and `tests/`: the only `script.module.clouddrive.common` hits are the four attribution-required documents; the only `eval(` hit anywhere is inside VENDORED.md prose describing its removal. `addon.xml` has exactly one `<import addon="xbmc.python" version="3.0.1"/>` |
| 2 | Kodi 19 mechanically refuses; Kodi 20, 21 and 22 install and load both entry points | PASSED (override) | Override: narrowed by owner decision 2026-08-23 — one target device, matrix not pursued — accepted by Kenny Nguyen. Recorded as **unmet, not satisfied** in ROADMAP SC2, REQUIREMENTS.md KODI-02 and 01-07-SUMMARY.md. Nothing became true by being descoped |
| 3 | On a clean profile the add-on installs, both entry points load, and every dialog opens — including the one that writes the QR image | VERIFIED | Re-greped `D:/KodiPortable/_logs/android-acceptance/kodi-android-acceptance.log` (146,341 B, matches claim): `CPythonInvoker(0, …/plugin.onedrive.kn/service.py)` and `CPythonInvoker(2, …/plugin.onedrive.kn/entrypoint.py)`; `pin-dialog.xml` x2, `export-schedule-dialog.xml`, `export-main-dialog.xml` all loaded from `…/addons/plugin.onedrive.kn/resources/skins/default/1080i/`; `grep -c Traceback` = **0**; `grep -ci 'unknown addon'` = **0** |
| 4 | `VENDORED.md` records the module's upstream URL, `matrix` branch, version 1.4.0, commit SHA, per-subtree licence and local modifications; GPL-3.0 and Apache-2.0 files both survive | VERIFIED | All four values present. `git ls-remote` upstream confirms `matrix` is HEAD and that only `krypton` and `matrix` exist — the "there is no `master` branch any longer" warning is true. `LICENSE.txt` blob `818433ec` == upstream `818433ec`; pinned sha256 matches the live file. `cache/LICENSE` contains "Apache License" |
| 5 | Every vendored component is re-derivable from a fixed point recorded in the shipped record | **FAILED** | Module: fully reproducible, re-derived during this verification. QR encoder: `VENDORED.md` says only "the QR encoder add-on zip" — zero occurrences of `script.module.pyqrcode`, `mirrors.kodi.tv`, `1.2.1+matrix.4` or the zip sha256. See Gap 1 |
| 6 | Manual acceptance pass on Android over `adb` on a clean profile | VERIFIED | Profile deletion quoted and verified absent before the run; whole pass in one session; log, 14 screenshots, dialog capture set and `record.json` all present on disk at the recorded paths |
| 7 | The vendored tree is upstream `matrix` at `df68e9a589a6faef2b3228f7520e77729bc05d9b` copied verbatim, in its own commit, before any edit | VERIFIED | **Independently reproduced.** Cloned upstream, checked out `df68e9a`, compared every path added by commit `413489d` by git object id: **38 match, 0 mismatch, 0 missing**. The 39th path, `resources/lib/vendor/__init__.py`, is zero bytes and has no upstream counterpart, exactly as recorded. "All 38 copied files matched" is arithmetically exact |
| 8 | Every modification to the vendored tree since the verbatim commit is recorded in `VENDORED.md` | VERIFIED | `git diff 413489d HEAD` over `resources/lib/vendor` and `resources/skins`: 21 modified files + 5 added (pyqrcode). The 10 files covered only by the blanket import row have **0** non-import changed lines each. The 11 named files' non-import diffs were printed in full and each matches its row. No opportunistic fix was smuggled into the tree. *(Two counts inside the table are wrong — Gap 2 — but no change is unrecorded)* |
| 9 | No dynamic code execution anywhere; both stores round-trip through JSON with no compatibility evaluator | VERIFIED | `db.py` 2 reads + 2 writes and `cache/cache.py` 1 read + 2 writes all converted; no fallback path added. `test_store_json_roundtrip` asserts double round-trip idempotence on three real payload shapes and asserts the two shapes that do *not* survive (tuple, non-string key) rather than assuming them |
| 10 | Exactly one dependency; the vendored tree imports nothing outside stdlib, `xbmc*` and this add-on's own root | VERIFIED | `test_vendor_tree_self_contained` walks the AST of every `.py` under `resources/` plus both root scripts, visiting 98+ import statements against a `sys.stdlib_module_names` allow-list, with a `visited >= 20` non-vacuity guard. No `sys.path` mutation anywhere |
| 11 | Every outbound HTTP call carries an explicit timeout from a named constant | VERIFIED | Independent sweep for `urlopen`/`urlretrieve`/`http.client`/`HTTPConnection`/`requests`: exactly one outbound call site in the tree, `remote/request.py:151`, `urlopen(req, timeout=self.HTTP_TIMEOUT_SECONDS)`. `service/base.py:42`'s socket is a listener, correctly outside the sweep. *(The value 30 is unmeasured — human item 3)* |
| 12 | The licence-header gate was made licence-aware without being weakened | VERIFIED | Read `b6d8b33` in full. `FOREIGN_NOTICES` **excuses nothing** — it swaps the expected phrase for the file's own upstream notice, so each of the four pyqrcode files must name Michael Nooner or Johann C. Rocholl, and an orphan check fails if a row stops naming real checked source. Independently: of 43 tracked `.py`, 27 carry Carlos Guzman's notice, 4 are the pyqrcode files, 9 are zero-byte package markers, 3 are `.planning/research` probes. Nothing is unchecked |
| 13 | String ids are partitioned, with no duplicate `msgctxt` in any `.po` | VERIFIED | Computed independently: `en_gb` = 114 ids, 114 unique — 25 in the 30000 block, 89 contiguous 32000–32088. `he_il` = 73 unique, 12 in the 30000 block, all within the partition. `30012` absent, `32012` present with the module's own string "Yes! Count me in". 0 unresolved `settings.xml` label references. The gate uses **exact set equality** for `en_gb`, not a subset test |
| 14 | The `test_string_ids_partitioned` contradiction was resolved by correction, not by relaxation | VERIFIED | The original form was genuinely unsatisfiable: `32012` lies inside the 32000–32088 block the same assertion demands be complete. The gate now asserts `30012 not in en_gb` and `32012 in en_gb`, both with inline comments naming the contradiction, and the deletion of the settings row it labelled is gated **separately** by `test_directory_listing_default_off`'s `_open_common_settings` check. Nothing was dropped |
| 15 | All eight add-on-id lookups resolve to this add-on; skin paths and the QR image land under `plugin.onedrive.kn` | VERIFIED | `KodiUtils.common_addon_id = None` at `ui/utils.py:36`, so `get_addon(None)` constructs `xbmcaddon.Addon()` with no argument and the two objects become one. Confirmed on device: `dialog scriptPath` and both QR paths resolve under `plugin.onedrive.kn` |
| 16 | Two openings of the QR dialog in one session write two different image paths | VERIFIED (behavioural) | Behaviour-dependent truth — presence of `uuid4()` cannot prove it. Exercised on the device and re-read from the archived log: `qr-c463cfb25f0141cb91248111ac54bbca.png` and `qr-7bf7aac6207c4719aa443c97fa520fd9.png`, both `exists: True`, both under this add-on's id |
| 17 | The licence is GPL-3.0-or-later and nothing in the tree contradicts it | VERIFIED | `addon.xml` `<license>GPL-3.0-or-later</license>`; `LICENSE.txt` byte-identical to upstream and sha-pinned; every non-empty shipped `.py` carries its own notice; the two added components are BSD-3-Clause and MIT, both GPL-3 compatible and both keeping their own notices. The Apache-2.0 ambiguity beside `cache/` is stated as unresolved rather than resolved by guess, in both VENDORED.md and CREDITS.md |
| 18 | The repository left the upstream fork network with its commit history preserved | UNCERTAIN | History half **verified**: 163 commits (>= the 113 floor), upstream root commits `2482723` and `872108b` still present, nothing squashed. Fork-network half **unverifiable from this shell** — the repository is private and the GitHub API returns 404 unauthenticated. See human item 1 |

**Score:** 16/18 truths verified (15 VERIFIED + 1 PASSED (override)); 1 FAILED; 1 UNCERTAIN; 0 present-but-behaviour-unverified.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `resources/lib/vendor/clouddrive_common/**` | 28 upstream files, imports repointed | VERIFIED | 38/38 blobs byte-identical at the verbatim commit; 21 later modified, all recorded |
| `resources/lib/vendor/__init__.py` | New empty package marker | VERIFIED | 0 bytes at `413489d` and today |
| `resources/lib/vendor/clouddrive_common/cache/LICENSE` | Apache-2.0 preserved verbatim in place | VERIFIED | Blob identical to upstream; contains "Apache License" |
| `resources/lib/vendor/pyqrcode/**` | QR encoder with both licences | VERIFIED (bytes) / **INCOMPLETE (record)** | All five files' sha256 and byte counts match the record; zip re-downloaded, sha256 `3bd98699…` and 66,542 B reproduced; `tables.py`, `png.py`, `LICENSE.md` byte-identical to the zip. But the provenance is absent from VENDORED.md — Gap 1 |
| `tests/test_vendor_gates.py` | 22 assertions, no Kodi import | VERIFIED | 22 collected, 22 passed in 0.36 s in this verifier's process. Imports only `ast`, `compileall`, `functools`, `hashlib`, `json`, `re`, `subprocess`, `sys`, `xml.etree`, `pathlib` |
| `addon.xml` | New identity, one import, no `start` attribute | VERIFIED | `id="plugin.onedrive.kn"`, `name="OneDrive KN"`, `provider-name="Kenny Nguyen"`, `version="1.0.0"`, one `<import>`, `<extension point="xbmc.service" library="service.py" />` with the schema-invalid `start` gone |
| `resources/settings.xml` | Listing off, one repointed `plugin://`, no common-settings row | VERIFIED | `allow_directory_listing default="false"`; the surviving `plugin://plugin.onedrive.kn/?action=_clear_cache`; `_open_common_settings` row deleted |
| `resources/language/**/strings.po` | Renumbered, merged, no duplicates | VERIFIED | See truth 13 |
| `resources/skins/default/**` | 3 dialog XMLs + 7 textures, all references resolving | VERIFIED | All present and byte-identical to upstream; every texture reference resolves; empty texture values treated as failures by the gate |
| `VENDORED.md` | Six sections, module provenance, licences, exclusions, modifications, service decision, deviations | VERIFIED (module) / **PARTIAL** | All six headings present and substantive, not a stub. Two count errors (Gap 2) and no QR-encoder provenance (Gap 1) |
| `CREDITS.md` | Four attributions with licences named | VERIFIED | `plugin.onedrive`/Carlos Guzman/GPL-3.0, the module, PyQRCode/Michael Nooner/BSD-3-Clause, pypng/Johann C. Rocholl/MIT, plus the Apache-2.0 ambiguity |
| `README.md` | Accurate description and attribution | VERIFIED | Accurate, including the corrected broker status and the honest "Early" framing |
| `resources/lib/addon.py` | `_dialog_smoke` present and reachable | VERIFIED | Method at line 77; reachable through the base class's `getattr(self, self._action)` at `ui/addon.py:700`; imports are all method-local so removal is one contiguous block |
| `.planning/phases/01-vendor-lift/COVERAGE.md` | Reasoned no-external-API declaration | VERIFIED | Present, reasoned, names Phase 3 for re-evaluation; not copied to the shippable root |

---

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `service.py` | `vendor/clouddrive_common/service/*` | Five root service imports repointed | WIRED | All five resolve; `compileall` exit 0 |
| `resources/lib/provider/onedrive.py` | `vendor/clouddrive_common/remote/provider.py` | Subclassed provider base | WIRED | Import present and anchored |
| `ui/dialog.py` | `resources/skins/default/1080i/pin-dialog.xml` | scriptPath through `get_common_addon_path()` | WIRED — **observed** | Log shows the skin loading from `…/addons/plugin.onedrive.kn/resources/skins/default/1080i/`. File existence alone could never have proved this |
| `ui/dialog.py` | `vendor/pyqrcode/__init__.py` | Function-local import inside `onInit` | WIRED | `import resources.lib.vendor.pyqrcode as pyqrcode`; deliberately unguarded so failure surfaces |
| `remote/signin.py` | `addon.xml` | User-Agent built from this add-on's own version | WIRED | `get_addon_info('version')`, no module id |
| `account.py` | `db.py` | Account dicts persisted through `SimpleKeyValueDb` | WIRED | JSON on both sides |
| `settings.xml` labels | `strings.po` | Every `label=` resolves in the owning add-on's file | WIRED | 22 rows, 0 unresolved — computed independently |
| `resources/lib/addon.py` | `ui/dialog.py` | Smoke action constructs all three dialog classes | WIRED — **observed** | All three rendered and closed on device; screenshots archived |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| QR dialog | `self._image_path` | `uuid4()` per invocation, written under `get_addon_info("profile")` | Yes — two distinct files on disk, both `exists: True` | FLOWING |
| Plugin root | account list | `AccountManager` over the JSON key-value store | Yes — renders one `Add an account...` row on an empty store, which is the correct result | FLOWING |
| Settings screen | 22 label ids | Merged `en_gb` catalogue | Yes — every row resolved statically and read correctly on screen | FLOWING |
| `request.py` | `HTTP_TIMEOUT_SECONDS` | Named class constant | Yes structurally; **the value itself is unmeasured** | FLOWING (value unvalidated — human item 3) |

---

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|---|---|---|---|
| Gate suite is genuinely green | `python -m pytest tests/test_vendor_gates.py -q` | `22 passed, 3 warnings in 0.36s` | PASS |
| Gate suite collects 22 ids | `pytest --collect-only -q` | `22 tests collected` | PASS |
| Whole tree compiles | (via `test_tree_compiles`) | exit 0 | PASS |
| Verbatim copy is byte-exact | clone upstream `df68e9a`, compare 38 blobs by object id | `match=38 mismatch=0 missing=0` | PASS |
| Upstream branch facts | `git ls-remote https://github.com/cguZZman/script.module.clouddrive.common` | HEAD = `matrix` = `df68e9a…`; only `krypton` and `matrix` exist | PASS |
| QR encoder zip is the recorded one | `curl -L … && sha256sum` | `3bd98699099b531ba8175a3822536927eeaac111d7cb9d12e1f0ed707b020899`, 66,542 B | PASS |
| Untouched encoder files really untouched | sha256 vs the zip | `tables.py`, `png.py`, `LICENSE.md` all IDENTICAL | PASS |
| Encoder edits are exactly the recorded ones | `diff` vs the zip | 3 self-import rewrites + 2 try/except reductions, nothing else | PASS |
| Shipped artefact passes the checker | `python -m kodi_addon_checker plugin.onedrive.kn --branch=omega` on a fresh `git archive` staging | `Addon id matches folder name`, `Valid XML file found`, `PO files are valid`, **`We found no problems and 2 warnings`** | PASS — reproduces 01-07's Run 3 verbatim |
| Acceptance log claims | re-grep of the archived log | 0 Traceback, 0 unknown-addon, 2 distinct QR paths, 3 skins from own dir, source service **not** started | PASS |
| Kodi 19 refusal log claims | re-grep of `kodi-19.5/portable_data/kodi.log` | 3 `plugin.onedrive.kn` lines, 0 `entrypoint.py`, `xbmc.python v3.0.0` | PASS (content real; run uncontrolled) |
| Working tree clean | `git status --porcelain` | empty | PASS |

No probes are declared by this phase (`scripts/*/tests/probe-*.sh` does not exist); Step 7c is N/A.

---

### Requirements Coverage

All 20 Phase 1 requirement IDs accounted for. The set claimed `requirements-completed` across the seven SUMMARYs is exactly the set checked `[x]` in REQUIREMENTS.md — 14 IDs, no drift in either direction.

| Requirement | Source Plan | Status | Evidence |
|---|---|---|---|
| VND-01 | 01-04 | SATISFIED | 38/38 blobs byte-identical to `matrix`@`df68e9a`, independently reproduced |
| VND-02 | 01-04 | SATISFIED | `resources/lib/vendor/clouddrive_common/`, name fixed before the copy |
| VND-03 | 01-04 | SATISFIED | Skins and two `.po` files merged; no second importable `resources` package; `pt_br` excluded |
| VND-04 | 01-05 | SATISFIED | `common_addon_id = None`; no add-on-id literal survives; verified on device |
| VND-05 | 01-06 | SATISFIED | 3 reads + 4 writes converted; no fallback evaluator |
| VND-06 | 01-06 | SATISFIED | Sole outbound call carries `timeout=` from a named constant |
| VND-07 | 01-07 | **PENDING** (correctly) | Decision recorded in VENDORED.md naming `SourceService` and `SourceRedirector`; nothing survives the fold. Left open pending the Phase 7 deletion |
| VND-08 | 01-05 | SATISFIED | All three dialog skins resolve through the common-addon path accessor — observed |
| VND-09 | 01-07 | **PENDING** (correctly) | Module provenance complete; **QR encoder provenance absent** — Gap 1 is the concrete reason |
| VND-10 | 01-07 | **PENDING** (correctly) | Clean-profile + every-dialog-opening half verified on Android; the "identically" half is supported by construction (verbatim copy + exhaustive modification table, both re-verified) but was never run comparatively |
| VND-11 | 01-05 | SATISFIED | One `<import>` |
| ID-01 | 01-03 | SATISFIED | `plugin.onedrive.kn` everywhere; both `plugin://` literals rewritten in the identity commit `a2c6db2` (backstop truth verified in git) |
| ID-02 | 01-03 | SATISFIED | `OneDrive KN` / `Kenny Nguyen`; distinguishable in the add-on browser |
| ID-03 | 01-02 | SATISFIED | LICENSE.txt blob-identical to upstream and sha-pinned; every notice preserved |
| ID-04 | 01-07 | **PENDING** (conservative) | CREDITS.md is substantively complete and the gate is green. Only defect: it names the GitHub project as the QR encoder's origin without noting the copy came from a Kodi zip — folded into Gap 1 |
| ID-05 | 01-01 | SATISFIED (history) / **HUMAN** (fork network) | 163 commits, upstream roots present, nothing squashed. Fork-network status unreadable — private repo |
| KODI-01 | 01-03 | **OVERCLAIMED** | Checked unqualified. Kodi-19-refusal half rests on an unobserved run; 20/22 install evidence likewise. Gap 3 |
| KODI-02 | — | DESCOPED | Narrowed by decision, left unchecked with an inline note. Correct behaviour |
| SETUP-06 | 01-01 | **OVERCLAIMED (minor)** | Checked unqualified while its text demands a phone; an emulator stood in. Gap 3 |
| CI-06 | 01-07 | PARTIAL (correctly) | Android leg filled; Windows leg dropped by decision. **Its requirement text now contradicts the corrected ROADMAP** — see Note below |

**Note on CI-06.** As written, CI-06 mandates a per-phase acceptance pass "on Windows and on Android", and states the Android TV box "is **not** a test device: it is exercised by use, and only at release". Both clauses now contradict the owner's 2026-08-23 directive and the corrected ROADMAP, which names the TCL Android TV 12 as the *primary* acceptance device from Phase 3 onward. This is flagged as a contradiction to be resolved by the pending rewrite, **not** treated as a Phase 1 failure.

**Orphaned requirements:** none. Every ID mapped to Phase 1 in REQUIREMENTS.md appears in at least one plan's `requirements` field.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | `TODO` / `FIXME` / `XXX` / `TBD` / `HACK` in shipped source | — | **Zero.** Nothing to gate on |
| `vendor/pyqrcode/__init__.py` | 251 | "not yet implemented" | INFO | Upstream docstring about ECI encoding, arriving in a byte-identical vendored file. Not a stub introduced here |
| `vendor/clouddrive_common/remote/oauth2.py` | 70 | `re.search("^\/", path)` — invalid escape sequence | INFO | Inherited upstream defect. Emits a `DeprecationWarning` on 3.11 and a `SyntaxWarning` at *error* level on Kodi 22. One-character fix, correctly deferred to the next time the tree is touched |
| `vendor/clouddrive_common/ui/addon.py` | 700 | `getattr(self, self._action)` — arbitrary method dispatch from a URL parameter | INFO | Pre-existing upstream routing design, unchanged by this phase and out of its scope. Worth carrying into the Phase 4 error-handling work |
| `resources/lib/addon.py` | 77 | `_dialog_smoke` debug affordance reachable in a shipped build | INFO | **Not a stub** — a complete implementation, documented in VENDORED.md deviation 4 and scheduled for removal, which is exactly the condition VND-10's prohibition attaches. Correctly handled |

---

### Prohibitions

`must_haves.prohibitions` were declared across all seven plans (14 total, all `status: resolved`). Routed per verification tier.

| Plan | Prohibition (abridged) | Tier | Disposition |
|---|---|---|---|
| 01-02 | MUST NOT remove, alter or re-attribute any upstream copyright notice or licence file | test | **Enforced and green.** `test_license_unmodified` (sha256 pin) + `test_gpl_headers_intact` (per-file notice + Carlos Guzman assertion). Independently re-verified |
| 01-02 | MUST NOT weaken a gate to make it pass | judgment | **Held.** Both mid-phase gate changes were read in full. The licence change is strictly stricter per file and adds an orphan check; the string change corrects an unsatisfiable assertion and moves the dropped half to a separate gate. Flagged non-authoritative LLM-judge verdict — human review recommended |
| 01-03 | MUST NOT ship with the unauthenticated directory listing enabled by default | test | **Enforced and green.** `test_directory_listing_default_off`; confirmed on device (`Service 'source' started` count = 0) |
| 01-03 | MUST NOT present this add-on as the original OneDrive by Carlos Guzman | judgment | Held — distinct name, distinct provider, both gated |
| 01-03 | MUST NOT read or write the original add-on's profile or settings | judgment | Held — new id throughout; both `plugin://` literals rewritten in the identity commit; profile paths observed under `plugin.onedrive.kn` |
| 01-04 | MUST NOT drop or rewrite a single upstream notice at copy time | test | **Enforced and green**, and independently proven by 38/38 blob identity |
| 01-04 | MUST NOT ship a modified vendored file without recording it in VENDORED.md | judgment | **Held in substance** — no unrecorded modification exists. Two counts inside the record are wrong (Gap 2) |
| 01-04 | MUST NOT introduce a behaviour change beyond the recorded deviations | judgment | Held — exhaustive diff shows no opportunistic fix |
| 01-05 | MUST NOT leave any of the eight id lookups resolving elsewhere | test | **Enforced and green** (`test_no_hardcoded_module_id`, `test_addon_id_everywhere`), confirmed on device |
| 01-05 | MUST NOT enable third-party error reporting by default or extend it | judgment | Held — `report_error default="false"`; only edit is a version lookup |
| 01-05, 01-06 | MUST NOT omit this plan's own edits from the record | judgment | **01-06's edits: held.** **01-05's: partially breached** — the QR encoder rows landed but its provenance did not. Gap 1 |
| 01-06 | MUST NOT add a compatibility read path that evaluates a legacy value | test | **Enforced and green** (`test_no_eval`); no fallback exists |
| 01-06 | MUST NOT move a credential-shaped value into a setting or a log line | judgment | Held — store untouched in that respect; the supplementary log was redacted before archiving |
| 01-07 | MUST NOT leave the smoke action unrecorded and unscheduled | test | **Enforced and green** (`test_vendored_md_sections` + `_dialog_smoke` occurrences) |
| 01-07 | MUST NOT describe this add-on as original work or omit any of the four attributions | test | **Enforced and green** (`test_credits_content`, 11 required strings) |
| 01-07 | MUST NOT sign off the acceptance pass over a known unrecorded departure | judgment | **Actively honoured** — 01-07 discovered the "broker is dead" premise was false while confirming the deviations rather than assuming them, and corrected the record before signing |
| 01-07 | MUST NOT assert a provenance the evidence does not support | judgment | **Honoured for the Apache-2.0 file** — the contradiction is stated, not resolved by guess. This is the strongest single instance of discipline in the phase |

Judgment-tier prohibitions carry a non-authoritative verdict; none is silently passed.

---

## Gaps Summary

Four gaps. None blocks the phase goal; all four are in the written record rather than the code, and all four are cheap.

**Gap 1 — the QR encoder's provenance never left the planning directory.** `01-05-SUMMARY.md` line 519 spells out what `VENDORED.md` must carry for the second vendored component: the zip URL, `1.2.1+matrix.4`, the `3bd98699…` sha256 and the per-file hash table. None of it landed. What `VENDORED.md` says instead is "the QR encoder add-on zip", which names no artefact. `CREDITS.md` compounds it by naming `github.com/mnooner256/pyqrcode` as the origin — true of the code, false of the copy, and a reader who re-derives from there gets different bytes. The facts are *right*; I re-downloaded the zip, reproduced the sha256 and byte count, and confirmed all five per-file hashes still current. They are simply in a planning SUMMARY instead of the shipped record, which is the one file that survives a `.planning` archive. This is the concrete, nameable reason VND-09 stays unchecked, and it is one paragraph of work.

**Gap 2 — two counts in the local-modification table are wrong.** The `db.py` row claims three reads; there are two, and the third is in `cache/cache.py`, which has its own row. The `pyqrcode` row claims five self-imports *plus* two try/except reductions; there are three self-imports plus two reductions, five edits in total. Both SUMMARYs state their versions correctly (`01-06` "three `eval(` reads and four `repr(` writes"; `01-05` "Five edits across two files") — the errors were introduced in the paraphrase. The table's own preamble calls it "the table a future upstream diff starts from", so a wrong count sends that diff hunting for a change that does not exist. Nothing is *unrecorded*, which is the property that actually matters, and that was checked exhaustively.

**Gap 3 — two checkboxes assert more than their own SUMMARYs do.** KODI-02 was given an inline narrowing note and is a model of how to do this. KODI-01 was not: it is `[x]` and "Complete" with no caveat, while `01-07-SUMMARY.md` states plainly that the Kodi-19-refusal half "was never exercised under a controlled, observed run" and escalates the decision to the owner. Its other half, "installing on Kodi 20, 21, and 22", has controlled evidence only for 21.3 on Android. SETUP-06 is the same shape in miniature: checked, while its text still requires "an Android phone running Kodi and reachable over `adb`" and no phone was ever connected. In both cases the SUMMARY is honest and REQUIREMENTS.md is silent — and REQUIREMENTS.md is what the next seven phases read.

**Gap 4 — the ROADMAP still carries a premise this phase disproved.** Phase 1 success criterion 3 reads "(modulo the already-dead broker)". `01-07` measured the broker answering `200`, issuing a code and being polled, and rewrote `VENDORED.md` deviation 1 and `README.md` on that measurement — correctly identifying that leaving it would make it "the premise every later phase reasoned from". The ROADMAP line was missed. One sentence.

**What is not a gap, and was checked hard.** The verbatim-copy proof is real and reproducible from scratch. The "no eval anywhere" claim is real. The "exactly one dependency" claim is real, and so is the stronger claim underneath it that the tree imports nothing it does not ship. The licence-header gate was made *stricter*, not looser, and no file is excused. The `test_string_ids_partitioned` rewrite corrected a genuinely unsatisfiable assertion and moved the dropped half to a separate gate rather than dropping it. The 22/22 is real, reproduced here. The `kodi-addon-checker` zero-ERROR result is real, reproduced here on a fresh staging. The acceptance log says what the SUMMARY says it says, line for line. And the licence position is sound: GPL-3.0-or-later throughout, verbatim GPL-3.0-or-later code © Carlos Guzman preserved with every notice intact, two GPL-compatible components added with their own notices kept, and the one genuinely ambiguous artefact left recorded as ambiguous.

`01-07-SUMMARY.md` is unusually disciplined about its own limits — it labels the harvested Windows logs uncontrolled, refuses to promote them, flags its own KODI-01 gap, and lists two claims that must remain unpassed. The gaps above are what escaped that discipline, and they are all one edit away.

---

_Verified: 2026-08-23T00:21:11Z_
_Verifier: Claude (gsd-verifier)_
