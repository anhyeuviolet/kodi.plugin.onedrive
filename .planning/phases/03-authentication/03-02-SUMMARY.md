---
phase: 03-authentication
plan: 02
subsystem: distribution
tags: [packaging, zip, git-index, kodi-install, dist-01, pytest]

requires:
  - phase: 01-vendor-lift
    provides: "The git-index-over-filesystem-walk convention in tests/test_vendor_gates.py (tracked_files), the non-vacuity guard convention, and the addon.xml identity this build reads"
provides:
  - "tools/build_addon_zip.py — one command produces the installable archive; importable as build(out_dir, repo=...) so a test can drive it anywhere"
  - "tests/test_build_zip.py — twelve assertions over a real built archive, including the single-top-level-directory install contract"
  - "The archive itself: plugin.onedrive.kn-<version>.zip, ready for the file-manager install on the TCL"
affects: [03-14, 05-distribution]

tech-stack:
  added: []
  patterns:
    - "The git index is the ship boundary: what is not in the index cannot reach a device"
    - "Identity is read from the manifest, never written as a literal, so the archive and addon.xml cannot disagree"
    - "An exclusion list over first path components, never an include list, so a new source directory ships by default"

key-files:
  created:
    - tools/build_addon_zip.py
    - tests/test_build_zip.py
  modified:
    - .gitignore
    - .planning/REQUIREMENTS.md

key-decisions:
  - "DIST-01 is corrected in place: the top-level directory is plugin.onedrive.kn, read from the manifest, because Kodi refuses an install whose directory disagrees with the id inside the archive"
  - "The member list comes from git ls-files -z, so an untracked scratch file, a compiled cache or the live latch-probe output under .planning/research cannot enter a build"
  - "Three exclusions only (.planning, tests, tools); .github, pytest.ini and the two Eclipse project files ship, because an exclusion list that grows by taste is one that eventually drops a source directory"
  - "/dist/ is gitignored rather than added to the exclusion list — the index is the guard, and keeping the output out of the index is what stops an archive being shipped inside the next one"

patterns-established:
  - "A build is an importable module with a repo= parameter, so its behaviour can be driven over an index the test controls rather than the repository under test"
  - "The test reads the manifest by pattern while the build reads it by XML parser: two mechanisms, so agreement means something"
  - "Proving a negative about the index is done against a throwaway repository in tmp_path, plus a companion test asserting the fixture really created the files whose absence is claimed"

requirements-completed: [DIST-01]

coverage:
  - id: D1
    description: "The archive has exactly one top-level directory and it equals the id in the manifest — the whole install-time contract"
    requirement: "DIST-01"
    verification:
      - kind: unit
        ref: "tests/test_build_zip.py::test_exactly_one_top_level_directory_and_it_is_the_manifest_id"
        status: pass
      - kind: unit
        ref: "tests/test_build_zip.py::test_the_directory_name_follows_a_different_manifest"
        status: pass
    human_judgment: false
  - id: D2
    description: "The manifest and both entry scripts are inside the archive at the paths Kodi loads them from"
    requirement: "DIST-01"
    verification:
      - kind: unit
        ref: "tests/test_build_zip.py::test_the_manifest_and_both_entry_scripts_are_present"
        status: pass
    human_judgment: false
  - id: D3
    description: "The planning record, the test suite and the build tool are absent from the archive, asserted rather than assumed, behind a member-count floor"
    requirement: "DIST-01"
    verification:
      - kind: unit
        ref: "tests/test_build_zip.py::test_the_planning_record_the_suite_and_the_tools_are_absent"
        status: pass
      - kind: unit
        ref: "tests/test_build_zip.py::test_the_archive_holds_a_real_tree"
        status: pass
    human_judgment: false
  - id: D4
    description: "The member list is drawn from the git index, not a filesystem walk — an untracked file and a compiled cache both stay out (T-03-07, T-03-09, the DIST-01 prohibition)"
    requirement: "DIST-01"
    verification:
      - kind: unit
        ref: "tests/test_build_zip.py::test_an_untracked_file_cannot_enter_the_archive"
        status: pass
      - kind: unit
        ref: "tests/test_build_zip.py::test_the_miniature_repository_would_expose_a_walk"
        status: pass
      - kind: unit
        ref: "tests/test_build_zip.py::test_no_compiled_cache_reaches_the_archive"
        status: pass
    human_judgment: false
  - id: D5
    description: "The filename carries the manifest's own version, so the two cannot disagree"
    requirement: "DIST-01"
    verification:
      - kind: unit
        ref: "tests/test_build_zip.py::test_the_filename_carries_the_manifest_version"
        status: pass
    human_judgment: false
  - id: D6
    description: "Two builds from the same index produce the same member list in the same order, and every member path is relative and forward-separated"
    requirement: "DIST-01"
    verification:
      - kind: unit
        ref: "tests/test_build_zip.py::test_two_builds_from_the_same_index_agree"
        status: pass
      - kind: unit
        ref: "tests/test_build_zip.py::test_every_member_path_is_relative_and_forward_separated"
        status: pass
    human_judgment: false
  - id: D7
    description: "The produced archive actually installs from the Kodi file manager on the TCL Android TV 12"
    requirement: "DIST-01"
    verification:
      - kind: manual
        ref: "plan 03-14, the on-device acceptance run"
        status: pending
    human_judgment: true
    rationale: "Every property that can be read off the archive is asserted here; that Kodi accepts it is a fact about Kodi on the target device and can only be established on the device"

duration: 12min
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 02: The Installable Archive Summary

**`python tools/build_addon_zip.py` now writes `plugin.onedrive.kn-1.0.0.zip` — 70 members, one top-level directory named from the manifest, drawn from the git index so nothing untracked can ride along.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-23T02:45Z
- **Completed:** 2026-08-23T02:57Z
- **Tasks:** 2 of 2
- **Files created:** 2 — one tool, one test file
- **Suite:** 76 passed, 1 skipped, 1.16s (was 64 passed, 1 skipped)

## Accomplishments

- **The phase can now reach the television.** Every wave after this one can be put on the TCL instead of the whole phase arriving on the hardware at the end. That was the reason DIST-01 was pulled out of phase 5 and into wave 1 here.
- **The install contract is one assertion.** Kodi resolves an installed add-on by matching the archive's top-level directory against the id in the manifest inside it. `test_exactly_one_top_level_directory_and_it_is_the_manifest_id` is that whole contract, and a companion test builds a throwaway repository declaring `plugin.other.id` and asserts the directory follows it — so the name is provably read, not written.
- **The ship boundary is the git index.** `git ls-files -z`, null-separated for the same reason `tests/test_vendor_gates.py` does it. A filesystem walk would ship `__pycache__` built by whichever Python ran on the build host (3.11 here; Kodi 19–21 run 3.8 and Kodi 22 runs 3.14) and, worse, the latch-probe output under `.planning/research/` that holds live measurement data. Neither is in the index, so neither can be in an archive.
- **The negative is proven against a repository the test owns.** Proving an untracked file stays out means creating one, and creating one inside the working tree under test is how a test leaves debris. `_miniature_repo` builds a small repository in `tmp_path`, populates the index, then writes the scratch files — including a `.cpython-311.pyc` under a `__pycache__` — and asserts none of them reach the archive. A second test asserts those scratch files really exist, so deleting them from the fixture cannot leave a passing test that proves nothing.

## Task Commits

1. **Task 1: The build, drawn from the git index** — `18c0a0b`
2. **Task 2: Assert the archive's shape (TDD)** — `e2d0137`

## Files Created/Modified

- `tools/build_addon_zip.py` — `read_identity`, `tracked_files`, `shipped_files`, `build(out_dir, repo=REPO)` and an `argparse` entry point defaulting to `dist/`
- `tests/test_build_zip.py` — twelve tests, a module-scoped archive fixture and the `_miniature_repo` helper
- `.gitignore` — `/dist/`
- `.planning/REQUIREMENTS.md` — DIST-01 corrected and retargeted to phase 3

## Decisions Made

**DIST-01 is corrected in place, not implemented literally.** The requirement named a top-level directory `plugin.onedrive/` and a filename `plugin.onedrive-<version>.zip`, both written before this add-on took its own id under ID-01. Kodi matches that directory against the manifest id and refuses a mismatch at install, so the requirement as written was unsatisfiable against the current id — implementing it literally would have produced an archive that cannot be installed, which is the one thing this plan exists to prevent. The text now names `plugin.onedrive.kn`, with the reason recorded inline beneath it, and the traceability table moves DIST-01 from phase 5 to phase 3. Same treatment the drive-enumeration requirement received when a measurement contradicted it.

**Three exclusions, and no more.** `.planning`, `tests`, `tools` — matched on the first path component. `.github`, `pytest.ini`, `.gitignore` and the two Eclipse project files therefore ship inside the archive. That is deliberate: an exclusion list that grows by taste is one that eventually excludes a source directory by accident, and none of those files does any harm on the device. An include list was rejected outright — it fails in the dangerous direction, silently dropping a new source directory the day someone adds one.

**`/dist/` is gitignored rather than added to the exclusion list.** The index is the guard this build rests on, so the right fix is to keep build output out of the index. Without it, one `git add -A` after a build would commit an archive, and the next build would ship the previous archive inside it. Solving that with a fourth exclusion entry would have treated the symptom and left the exclusion list carrying a job the index already does.

**Three guards ahead of the write.** A member-count floor (20), a check that `addon.xml` is in the member list, and a named list of index paths missing from disk. The last replaces a bare `FileNotFoundError` out of `zipfile` naming one absolute path with a message naming all of them. The floor is what stops a build from an empty or broken index producing an archive that installs and does nothing — the same failure the plan warns about for the tests, applied to the build itself.

## Deviations from Plan

### 1. [Rule 2 — Missing critical functionality] `/dist/` added to `.gitignore`

- **Found during:** Task 2
- **Issue:** The command-line entry point defaults to writing into `<repo>/dist`. `dist` is not in the exclusion list, so a build followed by `git add -A` would put an archive in the index and the next build would ship it inside the new archive — a shipped file that grows by one copy of the add-on per release.
- **Fix:** One `/dist/` entry in `.gitignore`, with the reason stated in a comment: the index is what the build reads.
- **Files:** `.gitignore`
- **Committed in:** `e2d0137`

### 2. [Rule 2 — Requirement correction] DIST-01 amended in `REQUIREMENTS.md`

- **Found during:** Task 1
- **Issue:** The plan's truth #2 requires the correction be "recorded" — the commit body carries it, but leaving `REQUIREMENTS.md` naming an id that would refuse to install means the next reader of the requirement re-derives the same contradiction.
- **Fix:** The requirement text now names `plugin.onedrive.kn`, adds the index-not-a-walk clause, and carries an indented note giving the reason and the phase that made the correction. The traceability row moved from phase 5 to phase 3 and the coverage-by-phase table was rebalanced (3 → 28, 5 → 4).
- **Files:** `.planning/REQUIREMENTS.md`
- **Committed in:** this plan's documentation commit

### 3. [Scope] Task 2's tests were green on first run

- **Found during:** Task 2
- **Issue:** The plan orders the build before the tests, so the TDD RED phase had nothing to fail against — exactly the situation plan 03-01's Task 3 hit.
- **Fix:** Rather than accept a green RED phase, the build was mutated four times to confirm the tests can fail: a filesystem walk in place of the index turned 2 red, a hardcoded top-level directory name turned 3 red, dropping the exclusion filter turned 1 red, and disabling the member floor turned 1 red. `git checkout -- tools/build_addon_zip.py` after each. Task 2 was then committed as a `test(...)` commit.
- **Committed in:** `e2d0137`

### 4. [Rule 1 — Bug, self-inflicted] An over-broad `sed` mislabelled eleven decisions in `STATE.md`

- **Found during:** state updates
- **Issue:** `state add-decision` wrote both new decisions with an unresolved `[Phase ?]` label. A `sed` intended to fix those two matched every `[Phase ?]` line in the file, relabelling eleven phase-1 decisions (the vendor lift, the `repr()`→JSON conversion, the Kodi 22 pin) as phase 3.
- **Fix:** Those eleven lines were restored to `[Phase ?]` by line range and the diff re-read to confirm. The four phase-3 decisions written by plan 03-01 were also caught by the same `sed`; those were left labelled `[Phase 3]`, which is what they are.
- **Files:** `.planning/STATE.md`
- **Verification:** `git diff .planning/STATE.md` — the only decision lines that differ are the four from 03-01 and the two added here.

---

**Total deviations:** 4 (2 × Rule 2, 1 × Rule 1, 1 scope observation)
**Impact on plan:** None on scope or shape.

## Issues Encountered

**The archive is larger than "only what ships" suggests.** Seventy members, of which `.github/`, `pytest.ini`, `.gitignore`, `.project` and `.pydevproject` are not add-on code. They ship because the exclusion list is deliberately short. It is recorded here rather than fixed so that phase 5 can decide it with the hosted repository in view, where archive size actually costs something.

**`git init` in the fixture never commits.** `_miniature_repo` runs `git add -A` and stops there: `git ls-files` reads the index, not a commit, so the fixture needs no `user.name` or `user.email` configured and cannot fail on a machine where they are unset.

## Verification Results

| Command | Result |
|---------|--------|
| `python tools/build_addon_zip.py --out-dir <tmp>` | wrote `plugin.onedrive.kn-1.0.0.zip`, 70 members |
| `python -c "import tools.build_addon_zip as b; print(b.__doc__ is not None)"` | `True` |
| `python -m pytest tests/test_build_zip.py -q` | 12 passed |
| `python -m pytest tests -q` | 76 passed, 1 skipped, 1.16s |
| `python -m pytest tests/test_vendor_gates.py -q` | 22 passed — no regression from the new top-level `tools/` directory, which the GPL header sweep now covers |

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR |
|------|-----|-------|----------|
| 2 | `e2d0137` — no red; the build was written whole in Task 1 per the plan's own ordering. Non-vacuity established by 4 mutations instead, each reverted | n/a (`18c0a0b` is the implementation) | not needed |

Task 1 is not a TDD task and carries no gate.

## Known Stubs

None. No placeholder, TODO or hardcoded empty value was left in either file created.

## Threat Flags

None. The three registered threats are addressed: T-03-07 by sourcing the member list from the index and asserting the three development directories absent behind a member-count floor, T-03-08 by reading the top-level directory name from the manifest and proving it follows a different manifest, T-03-09 by the index excluding compiled caches without a rule of their own, asserted anyway by `test_no_compiled_cache_reaches_the_archive`.

One note for the security record: `tools/build_addon_zip.py` is a new top-level directory and therefore now inside the vendor gates' shipped-source sweeps — GPL header, no `sys.path` mutation, no `eval`, and the bare-add-on-id sweep all apply to it, and all 22 gates pass with it tracked. It is excluded from the archive, not from the gates.

## User Setup Required

None.

## Next Phase Readiness

Ready. Plan 03-14 has the archive it needs for the on-device acceptance run; the build command is `python tools/build_addon_zip.py`, and the archive lands in `dist/` by default.

For phase 5, three things carry forward:

- **The exclusion list is short on purpose.** `.github`, `pytest.ini` and the two Eclipse files ship. Trim them there, with the hosted repository's size in view, not here.
- **The filename shape is `<id>-<version>.zip`**, which is what the `<dir>` schema in DIST-02 expects; the checksum index will hash this file.
- **DIST-05 is untouched.** The version comes from the manifest verbatim, so a pre-release suffix in `addon.xml` reaches the filename unaltered — that requirement's guard belongs on the manifest, not on this build.

## Self-Check: PASSED

Both created files exist on disk (`tools/build_addon_zip.py`, `tests/test_build_zip.py`); both task commits (`18c0a0b`, `e2d0137`) resolve in `git log`.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
