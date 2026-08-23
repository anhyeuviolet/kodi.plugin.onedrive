---
phase: 03-authentication
plan: 12
subsystem: docs
tags: [disclaimer, manifest, readme, vendoring-record, broker-removal, line-endings, build-and-install]

requires:
  - phase: 03-authentication
    provides: "Plan 03-03's tests/gatelib.py, its EXCLUDED_DOCS set, test_no_broker_references and test_the_replaced_flow_is_named_in_the_two_excluded_documents — the sweep this plan clears the last site of, and the positive assertion that pays for the two exclusions"
  - phase: 03-authentication
    provides: "Plan 03-02's tools/build_addon_zip.py and its dist/ default — the command and the archive name the readme now documents"
  - phase: 03-authentication
    provides: "Plan 03-03's docs/AZURE-REGISTRATION.md — the runbook the readme links from the place a reader meets the question of why the identifier is public"
  - phase: 03-authentication
    provides: "Plans 03-08 and 03-09's Vendored Tree Changes tables, written expressly as this plan's input, and the two whole-file deletions they made"
  - phase: 03-authentication
    provides: "Plan 03-11's deletion of the sign-in-server settings row, which left addon.xml:55 as the sweep's last site"
provides:
  - "addon.xml — a disclaimer describing the device authorization grant that ships, and a release note naming the change in user-facing terms"
  - "README.md — the shipped sign-in flow, the runbook link, and a build-and-install section (DIST-01's user-facing half)"
  - "VENDORED.md — a 'Rewriting sign-in' block with one row per vendored file this phase changed, both deletions, the CRLF-to-LF conversions, and resources/skins/ finally named as vendored surface"
  - "The auth gate file fully green: 235 passed, 0 failed, 1 skipped"
affects: [03-13, 03-14, phase-07]

tech-stack:
  added: []
  patterns:
    - "A document that is exempt from a sweep pays for the exemption by describing what replaced what it names — so the old vocabulary is marked as history rather than erased, and the exclusion is not a hole"
    - "Every number and every claim in a record is measured against the tree at the moment it is written, including numbers copied out of a prior document that was itself written from measurement"
    - "A whole-file line-ending change is recorded as a modification, because it is invisible in review and total in a byte diff"

key-files:
  created:
    - .planning/phases/03-authentication/03-12-SUMMARY.md
  modified:
    - addon.xml
    - README.md
    - VENDORED.md
    - .planning/phases/03-authentication/deferred-items.md
    - .planning/REQUIREMENTS.md
  deleted: []

key-decisions:
  - "The disclaimer's link to the third party's source and its invitation to host a copy were dropped rather than reworded. Both described a thing the add-on no longer touches; a reworded sentence about a server that is not in the exchange is still a sentence about a server that is not in the exchange"
  - "resources/skins/ is named as vendored surface. Ten of the 38 copied files live there, the record never said so, and its own instruction — 'if you change anything under resources/lib/vendor/, add a row here' — read as though the vendored surface stopped at that path. This phase rewrote one of those ten"
  - "The three CRLF-to-LF conversions found in the tree are recorded rather than reverted. Converting them back is itself a whole-file rewrite, and doing one inside a documentation change buries the same problem a commit deeper; upstream is not uniform either, so 'normalise to LF' is not the repair it looks like"
  - "Only AUTH-23 was marked Complete. AUTH-02 is declared by 03-13 and DIST-01 by 03-14, so neither is this plan's to close; VND-09 was already Complete and this plan is what makes it true again"
  - "COVERAGE.md's phantom entry in EXCLUDED_DOCS is named in the record and deferred rather than removed. tests/gatelib.py is not this plan's file, and an exclusion that does nothing is a documentation problem before it is a code one"

patterns-established:
  - "Pattern 1: verify a modification record against the tree at three points — the lift, the phase base, and HEAD — rather than against the prior document. That is what surfaced the line-ending drift and the miscounted call sites; neither is visible from any summary"
  - "Pattern 2: when a plan enumerates the files it expects to have changed, diff the range and use the diff as the enumeration. This plan's task 3 named five vendored files; the range named twelve"

requirements-completed: [AUTH-23]

coverage:
  - id: D1
    description: "The manifest disclaimer describes the flow that ships and names no third-party sign-in server"
    requirement: "AUTH-23"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_no_broker_references — green, zero sites, with the sweep's six literals unchanged"
        status: pass
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_addon_xml_identity and ::test_addon_xml_imports — both green; the edit stayed clear of every row they assert"
        status: pass
      - kind: other
        ref: "ET.parse('addon.xml') succeeds; the file is still CRLF throughout, as its blob was before"
        status: pass
      - kind: manual
        ref: "how the disclaimer renders in Kodi's add-on browser on the television. It is eleven lines of prose in a box the skin sizes; nothing in this repository can measure that"
        status: deferred
    human_judgment: true
    rationale: "The sweep proves the old vocabulary is gone. It cannot prove the replacement is true, and the truth of it is the whole requirement — the disclaimer is the only statement a user reads about where their credentials go. Every clause was checked against the code that implements it: the grant and the authority against resources/lib/auth/device_code.py, the public identifier and the absent secret against docs/AZURE-REGISTRATION.md's read-back of the application manifest, and the read-only permission against the SCOPES constant"
  - id: D2
    description: "The readme describes the shipped flow, links the runbook, and documents the build and install"
    requirement: "AUTH-23, DIST-01"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_the_replaced_flow_is_named_in_the_two_excluded_documents — the readme names the device authorization grant and marks the server it replaced as past"
        status: pass
      - kind: other
        ref: "grep -c AZURE-REGISTRATION README.md returns 2; the build command, the archive name and the dist/ default were read out of tools/build_addon_zip.py rather than recalled"
        status: pass
      - kind: manual
        ref: "the install procedure has not been performed. Whether Add-ons -> Install from zip file accepts this archive on the TCL is 03-14's acceptance run"
        status: deferred
    human_judgment: true
    rationale: "The two facts the person at the television needs are the command and the two screens. The Unknown sources prerequisite was added on judgment: it is not in the plan, and without it the documented procedure fails on a stock Kodi with a dialog that does not explain itself"
  - id: D3
    description: "Every local modification this phase made to the vendored tree is recorded, including two whole-file deletions"
    requirement: "VND-09"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_vendored_sha_recorded and ::test_vendored_md_sections — both green; every required heading survives and the pinned digest is untouched"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_the_replaced_flow_is_named_in_the_two_excluded_documents — VENDORED.md names the replacement and marks the old flow as past"
        status: pass
      - kind: other
        ref: "git diff --numstat f3fa0cf..HEAD -- resources/lib/vendor/ resources/skins/ — twelve vendored files and one skin, every one of which now has a row"
        status: pass
      - kind: other
        ref: "the recorded upstream commit df68e9a... appears in no line of this plan's diff of VENDORED.md, so it was not re-pinned"
        status: pass
    human_judgment: true
    rationale: "A gate can assert that headings exist and that a digest is present. It cannot assert that the rows are true, and the value of the record is entirely in whether they are. Each row was written from the diff of the file it describes, not from the prior summaries; two of the summaries' numbers turned out to be wrong and are corrected below"

metrics:
  suite_before: "234 passed / 1 failed / 1 skipped"
  suite_after: "235 passed / 0 failed / 1 skipped"
  vendored_files_recorded: 12
  vendored_files_deleted: 2

duration: 45m
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 12: Documents That Tell the Truth About a System That Changed Underneath Them Summary

**The manifest stopped telling users their credentials travel through a server they no longer reach,
the readme describes the sign-in that ships and how to build and install it, and the vendored tree's
modification record gained the twelve files, two deletions and three silent line-ending conversions
that this phase produced.**

## Performance

- **Duration:** 45 min
- **Tasks:** 3 of 3
- **Files modified:** 5 (three shipped documents, two planning records)
- **Suite:** 234 passed / 1 failed / 1 skipped → **235 passed / 0 failed / 1 skipped**

The phase's auth gate file is fully green. The one skip is unrelated and predates this plan.

## Accomplishments

**`addon.xml:55` is gone and the broker sweep is green (AUTH-23).** That line was the last site in
the tree, and it was the worst kind: not dead code but a statement to the user that their tokens go
to a third party, complete with a link to that party's source and an invitation to host a copy. The
disclaimer now says what happens — the OAuth 2.0 device authorization grant straight to Microsoft, a
code entered on the user's own phone, a public application identifier rather than a secret, no
server in the middle, no password seen by the add-on, and read-only permission on the user's own
files. **No sweep was weakened.** `BROKER_LITERALS` still holds all six patterns and
`test_the_replaced_flow_is_named_in_the_two_excluded_documents` still reads both excluded documents
by name.

**The release notes name the change.** Sign-in going direct is the one change in this phase a user
could otherwise discover only by reading source, so it is the one that belongs in the notes.

**The readme describes the flow that ships, and what it replaced (AUTH-23).** The status section
said sign-in still went through a third-party server and that replacing it was the next piece of
work; both statements had been false for four plans. It now describes the code on the television,
the address and QR beside it, the phone, the refresh token held locally and renewed at Kodi start
and whenever a request needs a fresher one. The server it replaced is kept, in the past tense, with
the reason it went — a third party in the middle of every account connection — and the date it was
last measured answering, so that a reader can tell "removed on purpose" from "stopped working".

**The build and install are written down (DIST-01's user-facing half).** The command, the archive it
writes, that the name follows `addon.xml`, that the archive holds only indexed and shipping files,
and the two Kodi screens. The Unknown sources prerequisite was added on judgment; see deviations.

**The modification record covers this phase (VND-09).** A new **Rewriting sign-in** block carries one
row per vendored file changed, both whole-file deletions with their line counts, the eight rewritten
error-reporter call sites, the rebuilt skin, and the line-ending conversions. The old flow is in the
past tense in both places that described it, including the note explaining why a fresh profile looks
empty. **The pinned upstream digest was not recomputed and not re-pinned.**

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | The manifest's disclaimer and release notes | `5c6383c` | `addon.xml` |
| 2 | The readme — the flow, the runbook link, and how to build and install | `7503188` | `README.md` |
| 3 | Record every modification this phase made to the vendored tree | `c509fb3` | `VENDORED.md`, `.planning/phases/03-authentication/deferred-items.md` |

## Files Created/Modified

**Modified**

- `addon.xml` — disclaimer rewritten (11 lines for 11); one release note added. Identity, version,
  provider, imports, licence, source and forum rows untouched; the blob is still CRLF
- `README.md` — status section rewritten; one bullet added to the differences list; the install
  section replaced with a build-and-install section
- `VENDORED.md` — the **Rewriting sign-in** block (ten rows), the skins named as vendored, three
  corrections to claims that had gone stale, deviation 1 and the reporter paragraph put in the past
  tense, and the two retry budgets stated together
- `.planning/phases/03-authentication/deferred-items.md` — items 8, 9 and 10
- `.planning/REQUIREMENTS.md` — AUTH-23 marked Complete, and nothing else

**Created**

- `.planning/phases/03-authentication/03-12-SUMMARY.md`

## What the Tree Said That the Summaries Did Not

The plan named five vendored files and pointed at two summaries as the authoritative list. Diffing
the phase range instead — `f3fa0cf..HEAD` — produced twelve vendored files plus one skin, and three
discrepancies that no summary contains.

**1. Three files were converted from CRLF to LF, wholesale.** `clouddrive_common/ui/addon.py` in
`356de0d`, `clouddrive_common/ui/utils.py` in `c3a1445`, and
`resources/skins/default/1080i/pin-dialog.xml` in `345999a`. All three arrived from upstream as
CRLF. Nothing depends on the change and none of it was deliberate, but it is total in a byte diff:
every line of all three now differs from upstream, so a diff against the pinned commit shows the
files as wholly rewritten and says nothing about what actually changed. This is precisely the
failure the modification record exists to prevent, and it was invisible to every review that
produced it. Found by comparing the line-ending state of every vendored file at the lift commit, at
the phase base and at HEAD.

**2. `resources/skins/` is vendored and the record never said so.** The lift commit merged the
module's three dialog skins and their seven textures into it; nothing under that directory predates
the lift. Ten of the 38 copied files therefore live outside `resources/lib/vendor/`, while the
record's own instruction named only that path. This phase rewrote `pin-dialog.xml` from 86 lines to
150, which under the old wording was not a vendored-tree change at all.

**3. The error reporter had eight call sites, not six.** 03-09's summary says six across five
modules. The diff shows two in `export.py`, one in `service/download.py`, three in
`service/export.py`, one in `service/player.py` and one in `service/source.py`. Eight. The record
says eight.

Two further stale claims were corrected in the same pass, both about the gate harness: `source_scan`
moved to `tests/gatelib.py` in 03-03, and `EXCLUDED_DOCS` holds five names rather than four. One of
those five, **`COVERAGE.md`, has never existed in this repository** — it has been in the exclusion
set since the phase-1 gates and excludes nothing.

## Decisions Made

**The third party's source link and hosting invitation were dropped, not reworded.** A disclaimer
that mentions a server the add-on does not contact is a statement about a data flow that does not
happen, whichever way the sentence is turned. The whole paragraph went.

**The disclaimer got shorter, not longer.** It renders in an add-on browser on a television. The
three OAuth reference URLs the old text carried were links nobody on a remote control can follow.

**The readme keeps the server it replaced.** It is one of two documents exempt from the sweep, and
the exemption is paid for by an assertion that reads it by name. A document that erases what it
replaced takes the exemption without paying for it — and the reader most in need of that paragraph
is the one who met the old flow in an older checkout.

**The line-ending drift is recorded rather than repaired.** Converting three files back is itself a
whole-file rewrite; doing one inside a documentation change buries the same problem a commit deeper
with no test able to see it. The record now names the three files, the commit that converted each,
and the workaround (`git diff --ignore-cr-at-eol`). It also warns that upstream is not uniform —
`remote/provider.py` and `export.py` arrived LF — so the target for a future sweep is whatever
upstream holds per file, not LF everywhere.

**`_open_common_settings` and `AccountManager.remove_drive` stay, and are recorded.** Both are
unreachable, both were left deliberately by 03-09, and deleting either is a vendored-code change in
a plan whose three files are documents. The record names them so a later reader does not take them
for oversights. Deferred item 5 assigned the first to this plan; it is not this plan's to make.

**The retry budgets are stated together.** The record had the transport's default worst case
(155 s) and nothing about the short profile sign-in and refresh actually use (65 s), which is the
number `RefreshLock.LIFETIME_SECONDS = 90` is set against. Two numbers that must move together were
in two different places, one of which was no place at all.

## Deviations from Plan

### 1. [Rule 2 — Missing critical functionality] Seven more vendored files than the plan enumerated

- **Found during:** Task 3.
- **Issue:** the plan lists five vendored files plus the two deletions. The phase range contains
  twelve vendored files and one skin. The seven the plan does not name are `export.py`,
  `service/download.py`, `service/export.py`, `service/player.py`, `service/source.py` (the
  error-reporter call sites), `remote/request.py`'s redactor being larger than "a redactor covering
  five field names" suggests, and `pin-dialog.xml`, which the record did not treat as vendored at
  all. A record that covers five twelfths of a phase's changes is not a record.
- **Fix:** every one of the twelve, plus the skin, has a row. The five error-reporter modules share
  one row with their per-file call-site counts, because the change is identical in all five and five
  rows saying the same thing is worse than one row saying it once with the numbers.
- **Files modified:** `VENDORED.md`.
- **Verification:** `git diff --numstat f3fa0cf..HEAD -- resources/lib/vendor/ resources/skins/`
  against the rows, one by one.
- **Committed in:** `c509fb3`.

### 2. [Rule 2 — Missing critical functionality] The install procedure omitted its prerequisite

- **Found during:** Task 2.
- **Issue:** the plan asks for "the two facts they need": the command and that it installs from
  Kodi's file manager. On a stock Kodi, **Install from zip file** is refused until
  **Settings → System → Add-ons → Unknown sources** is on, with a dialog that does not say what to
  do about it. A documented procedure that fails at its last step is worse than no procedure.
- **Fix:** one clause naming the setting and its path.
- **Files modified:** `README.md`.
- **Committed in:** `7503188`.

### 3. [Judgment] Three stale claims corrected outside the plan's brief

- **Found during:** Task 3.
- **Issue:** the plan asks for this phase's changes. Three claims already in `VENDORED.md` were
  false against the tree: the harness's location, the size and membership of the exclusion set, and
  `COVERAGE.md`'s existence. All three sit in a paragraph a reader consults to find out what the
  sweep actually does.
- **Fix:** corrected in place, with the `COVERAGE.md` discrepancy stated rather than quietly
  dropped, since removing the entry is an edit to `tests/gatelib.py` and that file is not this
  plan's.
- **Files modified:** `VENDORED.md`, and deferred item 9.
- **Committed in:** `c509fb3`.

### 4. [Judgment] Two claims in the record were checked before being carried forward, and one changed

- **Found during:** Task 3.
- **Issue:** the phase brief warns that Phase 1's recorded counts were corrected once already
  against the tree. Both counts still in the file were re-measured: `utils.py`'s "150 → 138 lines"
  is correct, and "All 38 copied files matched" is correct. 03-09's "six places" for the error
  reporter is not; it is eight.
- **Fix:** the correct number is in the record. Nothing that measured true was touched.
- **Committed in:** `c509fb3`.

## Requirement Marks Kept, and Why

The plan declares four ids. **One was marked.**

| Id | Also declared by | Mark | Why |
|---|---|---|---|
| **AUTH-23** | 03-03, 03-08, 03-09, 03-11 | **Complete — set by this plan** | 03-12 is the last plan in the phase to declare it, and its runnable form is `test_no_broker_references`, which is green with the sweep's six literals intact. The setting went in 03-11, the code paths in 03-08 and 03-09, the last document site here |
| AUTH-02 | 03-08, 03-11, **03-13** | Pending — unchanged | 03-13 still declares it. The public identifier ships and the escape hatch exists, but nobody has signed in with either; the live proof is 03-13's |
| VND-09 | Phase 1 | Complete — already set, not re-applied | Marked in Phase 1 and arguably stale from 03-08 until this commit, since the record described a tree that had changed underneath it. It is true again as of `c509fb3`. The mark was not touched |
| DIST-01 | 03-02, **03-14** | Complete — already set by 03-02, not touched | This plan documented the build; it did not deliver it. 03-14 still declares the id for the on-device install, so under the shared-id rule it is arguably premature — but it was set by 03-02 against a requirement its own test suite satisfies, and un-marking another plan's mark from here would be as silent a change as the one the rule exists to prevent. Flagged rather than altered, for 03-14 to confirm |

`git diff -- .planning/REQUIREMENTS.md` shows exactly two changed lines, both AUTH-23: its checkbox
and its traceability row.

## Issues Encountered

None that blocked. The line-ending discovery cost a measurement pass over every vendored file at
three points in history; that pass is what makes the record trustworthy and is written up above so
the next person does not have to invent it.

## Known Stubs

None. Nothing was left placeholder, and no claim in any of the three documents is asserted without
having been checked against the file that implements it.

Three things are recorded as **deferred rather than done**, each with an owner, in
`deferred-items.md` items 8, 9 and 10: the line-ending normalisation, the `COVERAGE.md` phantom
exclusion, and the seven orphaned catalogue strings that item 4 had assigned to this plan.

## Threat Flags

None. No file this plan touched executes, and none of the three documents gained a URL, an
endpoint, a credential or a path the add-on reads.

The register's three threats:

| Threat | Disposition | Where |
|---|---|---|
| T-03-55 manifest disclaimer | mitigate | Rewritten to the shipped flow; `test_no_broker_references` green with the sweep intact; every clause checked against the code implementing it |
| T-03-56 modification record | mitigate | Twelve vendored files, one skin and two deletions recorded; the vendored surface corrected to include `resources/skins/`; the line-ending drift named so a future upstream diff is interpretable |
| T-03-57 excluded documents | mitigate | Both keep their exclusion and both keep paying for it — each names the device authorization grant and marks the server it replaced as past, which is what `test_the_replaced_flow_is_named_in_the_two_excluded_documents` reads them for |

## User Setup Required

None.

## Next Phase Readiness

Ready. Three things the remaining plans should know:

- **03-13** owns AUTH-02's live proof. The readme and the disclaimer both now assert that no server
  other than the provider takes part and that the shipped identifier is public by design; if the
  live run contradicts either, both documents are wrong and this plan's files are where the
  correction goes.
- **03-14** owns DIST-01's install. The readme's build-and-install section is written from
  `tools/build_addon_zip.py` and has not been performed. If the archive is refused, or if Unknown
  sources is not where the readme says it is on Kodi 21/22, that section is what needs the edit.
- **Whoever next touches a vendored file** should read the line-ending row before diffing.
  `git diff` without `--ignore-cr-at-eol` on `ui/addon.py`, `ui/utils.py` or `pin-dialog.xml` shows
  a whole-file rewrite and hides the real change.

## Self-Check: PASSED

- `addon.xml`, `README.md` and `VENDORED.md` all exist on disk and all three parse or read as
  expected; `ET.parse('addon.xml')` succeeds.
- All three commits resolve in `git log`: `5c6383c`, `7503188`, `c509fb3`.
- `python -m pytest tests -q` → **235 passed, 1 skipped, 0 failed**, run after each task and again
  after the last.
- The pinned upstream digest `df68e9a589a6faef2b3228f7520e77729bc05d9b` appears in no line of this
  plan's diff of `VENDORED.md`, so it was neither recomputed nor re-pinned.
- Committed blob line endings are unchanged from their prior convention: `addon.xml` CRLF,
  `README.md` and `VENDORED.md` LF.
