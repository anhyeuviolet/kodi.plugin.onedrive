---
phase: 03-authentication
plan: 11
subsystem: settings
tags: [settings-schema, kodi-v1-schema, expert-level, client-id, broker-removal, error-reporting-removal, krypton, strings]

requires:
  - phase: 03-authentication
    provides: "Plan 03-08's CLIENT_ID_SETTING = 'client_id' and resolve_client_id() in remote/provider.py — the reader this plan finally gives a setting to"
  - phase: 03-authentication
    provides: "Plan 03-09's deletion of remote/errorreport.py and its six call sites — the code the report_error row gated, without which removing the row would have disabled a live feature rather than removing a dead one"
  - phase: 03-authentication
    provides: "Plan 03-05's 30036-30058 catalogue and the widened ADDON_STRING_IDS gate, and specifically string 30045, which names this setting by category and by level"
  - phase: 03-authentication
    provides: "Plan 03-03's tests/gatelib.py, test_custom_client_id_setting and the broker sweep — the two red assertions this plan owns"
provides:
  - "resources/settings.xml in the <settings version='1'> schema: one section, two categories, six groups (KODI-05)"
  - "The client_id setting — id exactly 'client_id', <level>3</level>, empty default, allowempty, in the Advanced category (AUTH-19)"
  - "The clear-cache action's new id, 'clear_cache' — the old format did not require one and the new one does"
  - "Strings 30070 (label) and 30071 (help) in en_gb"
  - "tests/test_vendor_gates.py::test_directory_listing_default_off, strengthened to read the <data> child as well as the action attribute"
affects: [03-12, 03-13, 03-14, phase-07]

tech-stack:
  added: []
  patterns:
    - "An assertion written against one file format is checked against the other before the format is changed, and widened rather than left to pass by reading an attribute the new format does not have"
    - "A setting's level is chosen during a conversion, not defaulted: the schema demands one per row, so the conversion is where a row that nothing can reach stops sitting beside a row that everything does"
    - "A row removed because its code is gone is removed together with the strings it referenced and the expected-id set that names them, in one commit, because the partition gate is an exact equality"

key-files:
  created: []
  modified:
    - resources/settings.xml
    - resources/language/resource.language.en_gb/strings.po
    - tests/test_vendor_gates.py
    - .planning/phases/03-authentication/deferred-items.md
  deleted: []

key-decisions:
  - "The schema conversion was pulled out of the deferred Phase 7 into this plan, on cost rather than on preference. The <level> element AUTH-19 needs exists only in the versioned schema, so against the old file the requirement was not implementable at all; the file was twenty-eight lines, this phase had to edit it twice anyway, and Phase 7 would have touched the same rows a third time"
  - "resume_playing and save_resume_watched are declared at Advanced rather than carried across at Basic. Their Krypton visibility condition was constantly FALSE on every supported Kodi, not constantly true as the plan's rationale said, so dropping it as KODI-06 requires would have made two settings that do nothing newly visible. Advanced reproduces their current effect on an ordinary user without a condition that names a Kodi release this add-on cannot run on"
  - "The stale-settings-row assertion was widened to read the <data> child as well as the action attribute. The versioned schema has no action attribute, so the plan's own note — that the gate 'stays green' after the conversion — describes an assertion that would still run and would no longer be able to fail. Widening cost one edit in a file already being changed, and was mutation-checked"
  - "client_id declares <allowempty>true</allowempty>. Empty is the value that means 'use the registration built into the add-on', it is the shipped default, and a Kodi string setting without allowempty refuses to let the user type it back"
  - "The clear-cache row was given the id 'clear_cache'. The old format did not require an id on an action row and the new one does; an action names no stored value, so there is nothing for the new id to key and no user choice it can discard"
  - "The three catalogue entries were removed rather than renumbered downwards to close the gap. 30032, 30034, 30035 and the 30036-30059 block are referenced by number from the settings file and from resources/lib/auth/errors.py's callers; closing a gap moves labels"
  - "Only AUTH-19, KODI-05, KODI-06 and KODI-08 were marked Complete. AUTH-02, AUTH-18 and AUTH-23 are in this plan's frontmatter but are also declared by 03-12 and 03-13, and a shared requirement is complete when the last of its plans lands, not the first"

patterns-established:
  - "Pattern 1: before converting a file that assertions read, read the assertions first and convert inside what they tolerate — then check whether any of them can still fail afterwards, because a gate that survives a conversion by reading nothing is worse than one that goes red"
  - "Pattern 2: a mutation harness holds the original bytes itself, restores from that copy in a finally block, and asserts byte-equality afterwards. Nothing else restores the working tree while uncommitted work is in it (inherited from 03-09 Pattern 3, used again here)"

requirements-completed: [AUTH-19, KODI-05, KODI-06, KODI-08]

coverage:
  - id: D1
    description: "resources/settings.xml is in the versioned schema, with section, category and group structure"
    requirement: "KODI-05"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_custom_client_id_setting — its first assertion is root.get('version') == '1'"
        status: pass
      - kind: other
        ref: "ET.parse of the file; one <section>, two <category>, six <group>, fourteen <setting>"
        status: pass
      - kind: manual
        ref: "the file has not been loaded by Kodi. Whether the settings dialog renders on Kodi 20/21/22 is a property of a running Kodi and belongs to 03-14"
        status: deferred
    human_judgment: true
    rationale: "A file that parses as XML is not a file Kodi accepts. Three constructs carry residual risk and are named so the acceptance pass has something to look at: <close>true</close> inside the action's button control, which reproduces the old option=\"close\"; the two setting ids that contain hyphens (cache-expiration-time survives, and it is read by name from get_cache_expiration_time); and integer edit controls where the old format said type=\"number\""
  - id: D2
    description: "A custom application identifier setting exists, at Expert level, empty by default, and readable by the code that resolves it"
    requirement: "AUTH-19"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_custom_client_id_setting — exactly one setting whose id names a client identifier, <level> present and equal to 3, <default> present and empty"
        status: pass
      - kind: other
        ref: "the id is the literal string 'client_id', which is what remote/provider.py's CLIENT_ID_SETTING holds; grep confirms one definition and three resolve_client_id() call sites"
        status: pass
      - kind: manual
        ref: "no value has been typed into it on a device, and no tenant has refused the built-in registration, so the escape hatch has never been used end to end"
        status: deferred
    human_judgment: true
    rationale: "The gate proves the setting is present, expert-level and empty, and grep proves the id matches its reader exactly. What it cannot prove is that Kodi lets an expert-level string setting be cleared back to empty on a remote — that is what allowempty is for and it is untested on hardware — nor that a real blocked tenant is rescued by filling it in"
  - id: D3
    description: "The Krypton-era visibility conditions are gone from the settings file"
    requirement: "KODI-06"
    verification:
      - kind: other
        ref: "grep: no 'iskrypton' and no 'visible=' anywhere in resources/settings.xml; the three remaining iskrypton sites are all in Python and are the branch, not the condition"
        status: pass
    human_judgment: false
  - id: D4
    description: "The setting that named the third-party sign-in host is removed, default and all"
    requirement: "AUTH-23"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_no_broker_references — this plan's site (settings.xml:21) is cleared; one remains, addon.xml:55, owned by 03-12"
        status: partial
    human_judgment: false
  - id: D5
    description: "The report_error setting is deleted; nothing in shipped source reports an error to a third party"
    requirement: "KODI-08"
    verification:
      - kind: other
        ref: "grep for 'report_error' across every .py, .xml and .po outside .planning returns nothing; 'ErrorReport' returns nothing; git ls-files carries no errorreport module"
        status: pass
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_string_ids_partitioned — the catalogue no longer declares 30030 or 30031, asserted by exact equality against the narrowed expected set"
        status: pass
    human_judgment: false
  - id: D6
    description: "The directory-listing default survived the conversion unchanged"
    requirement: "KODI-05"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_directory_listing_default_off — it falls back to the <default> child, which is the form the converted file uses"
        status: pass
      - kind: other
        ref: "the same test's deviation half, test_vendored_deviations_are_recorded, still finds allow_directory_listing named in VENDORED.md"
        status: pass
    human_judgment: false

metrics:
  duration: 26m
  tasks_completed: 2
  files_created: 0
  files_modified: 4
  suite_before: "233 passed / 2 failed / 1 skipped"
  suite_after: "234 passed / 1 failed / 1 skipped"

duration: 26m
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 11: The Settings File, Converted, With an Escape Hatch and Without Two Dead Rows Summary

**The settings file moved to the versioned schema so that the one setting a blocked tenant depends
on could exist at all — and the last two rows configuring things that no longer exist went with the
conversion rather than after it.**

## Performance

- **Duration:** 26 min
- **Tasks:** 2 of 2
- **Files modified:** 4 (three shipped, one planning record)
- **Suite:** 233 passed / 2 failed / 1 skipped → **234 passed / 1 failed / 1 skipped**

The one remaining failure is `test_no_broker_references`, and it now reports exactly one site:
`addon.xml:55`, which belongs to plan 03-12. The site this plan owned, `settings.xml:21`, is gone.

## Accomplishments

**The file is in the versioned schema (KODI-05).** One `<section>`, two `<category>` elements, six
`<group>` elements, fourteen `<setting>` elements, each with a `<level>`, a `<default>` and a
`<control>`. Every surviving identifier, label and default was carried across unchanged, because an
identifier is what a stored value is keyed by and renaming one does not migrate a user's choice, it
discards it silently. The four `lsep` separator rows of the old file became the four groups of the
Services category, keeping their labels — that is what an `lsep` was standing in for.

**The escape hatch exists (AUTH-19).** `client_id`, empty, `<level>3</level>`, in the Advanced
category, with `<allowempty>true</allowempty>` and an edit control. Its id is the literal string
`client_id`, which is exactly what `CLIENT_ID_SETTING` in `remote/provider.py` reads — a near-miss
would have shipped a setting that looks like the escape hatch, reads like the escape hatch and does
nothing. String 30045, the sentence appended to every outcome the error table marks
administrator-must-act, names this setting by category ("under Advanced") and by level ("at Expert
level"); the three now agree.

**There is deliberately no authority setting beside it.** This setting changes *which* application
asks for the credential. A configurable authority would change *where* the credential is sent. They
look alike on a settings screen and they are not alike at all, and the file says so in a comment
above the setting so that the absence reads as a decision rather than an omission.

**The third-party host row is gone, default and all (AUTH-23).** Not hidden: a hidden row still
ships a default naming a hostname on a service where a lapsed name can be re-registered by anybody,
and a stored value is still a stored value when nothing reads it.

**The error-reporting row is gone, and with it its whole category (KODI-08).** The code it gated was
deleted in 03-09; this was the last surface through which it could have been switched back on.
Verified explicitly rather than inferred — see below.

**The Krypton conditions are gone (KODI-06).** All three of them, not just the two the research note
named.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Convert the schema and add the expert-level identifier setting | `3f20640` | `resources/settings.xml`, `resources/language/resource.language.en_gb/strings.po`, `tests/test_vendor_gates.py` |
| 2 | Remove the two dead rows and the catalogue entries that follow them | `94ddc3d` | `resources/settings.xml`, `resources/language/resource.language.en_gb/strings.po`, `tests/test_vendor_gates.py` |

## Files Created/Modified

**Modified**

- `resources/settings.xml` — rewritten in the versioned schema; two rows removed; `client_id` added
- `resources/language/resource.language.en_gb/strings.po` — 30070 and 30071 added; 30030, 30031 and 30033 removed
- `tests/test_vendor_gates.py` — `ADDON_STRING_IDS` narrowed to 48; the stale-row assertion widened
- `.planning/phases/03-authentication/deferred-items.md` — two items added, both for other plans

## KODI-08, verified explicitly

This is the one requirement in the phase that no later plan declares, so nothing downstream would
have caught it being left open. 03-09 deleted the code and recorded its half as `partial` because
the setting survived. The setting is now gone, and the whole requirement was checked rather than
assumed:

| Clause | Check | Result |
|--------|-------|--------|
| Third-party error reporting code is deleted | `git ls-files` names no `errorreport` module; `grep -rn "ErrorReport"` over every `.py` outside `.planning` | nothing |
| The `report_error` setting is deleted | `grep -rn "report_error"` over every `.py`, `.xml` and `.po` outside `.planning` | nothing |
| Its strings are not left as orphans | 30030 and 30031 removed from en_gb; `test_string_ids_partitioned` asserts the catalogue by exact equality against the narrowed set | green |
| Errors go to `kodi.log` only | 03-09's rewrite of the six call sites in five modules to log a stack trace; unchanged by this plan | inherited |

`KODI-08` is marked **Complete**.

One line outside shipped source still describes the reporter in the present tense —
`VENDORED.md:245` — and it is recorded in `deferred-items.md` as item 6 for 03-12, which owns that
file. It is documentation of a removal, not a surface: no gate covers it because `report_error` is
not a broker literal and `VENDORED.md` is excluded from the sweeps on purpose.

## What this removal cannot reach

On a machine where the **original** add-on was installed, its own stored value for the sign-in host
survives in that add-on's profile. It is a different add-on with a different identity, and its
settings are not this one's to write. There is nothing to be done about it, and recording it is what
keeps it from later reading as an omission rather than a boundary.

## Decisions Made

See `key-decisions` in the frontmatter. The two worth reading in prose:

**The plan's rationale for the Krypton conditions was wrong in a way that mattered.** It said the
conditions "can never be false on any version that can install this add-on". Reading
`service/player.py:38-39`, the `iskrypton` home-window property is set **only** when
`System.BuildVersion` starts with `17.`, and this add-on requires Kodi 20. So the property is never
set, and of the two distinct expressions in the file, `String.IsEmpty(...)` — which guarded
`ask_resume` — was constantly **true**, while `!String.IsEmpty(...)` — which guarded
`resume_playing` and `save_resume_watched` — was constantly **false**. Dropping the first changes
nothing anyone can see. Dropping the second would have made two settings *newly visible* that
nothing on a supported Kodi reads, which is the opposite of what KODI-06 is for. Both are now
declared at Advanced: same effect on an ordinary user with a remote, no condition naming a Kodi
release that cannot run this add-on. Deleting the rows outright would mean deleting the branch that
reads them in two vendored modules, which is `KODI-07`'s class of change and is in no Phase 3 plan;
it is recorded as `deferred-items.md` item 7 so the pair, their strings and the three `iskrypton`
call sites go together rather than one at a time.

**A gate that survives a conversion by reading nothing is worse than one that goes red.** The plan
noted that `test_directory_listing_default_off`'s stale-row half reads an `action` attribute the new
schema does not have, and asked for that to be written down. It is written down — and the assertion
was also widened to read the `<data>` child, which is where the versioned schema puts a built-in
function. Without that it would have kept running, kept passing, and stopped being able to fail.
Mutation-checked: changing the clear-cache row's `<data>` to name `_open_common_settings` turns it
red, and the harness restored the file from bytes it held itself and asserted byte-equality
afterwards.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical verification] The stale-settings-row assertion could no longer fail**

- **Found during:** Task 1
- **Issue:** `test_directory_listing_default_off` reads `n.get('action')` to find a row that opens
  the deleted module's settings dialog. The versioned schema has no `action` attribute — it uses a
  `<data>` child — so after the conversion the assertion would have been vacuous.
- **Fix:** read both forms. Mutation-checked against the exact omission it exists to catch.
- **Files modified:** `tests/test_vendor_gates.py`
- **Commit:** `3f20640`

**2. [Rule 2 - Missing critical functionality] `client_id` needed `allowempty`**

- **Found during:** Task 1
- **Issue:** Kodi string settings default to `allowempty` false. Empty is this setting's shipped
  default *and* the value that means "use the built-in registration", so without the constraint a
  user who opened the box and wanted to back out could not put it back.
- **Fix:** `<constraints><allowempty>true</allowempty></constraints>`.
- **Files modified:** `resources/settings.xml`
- **Commit:** `3f20640`

**3. [Rule 1 - Bug] Dropping the Krypton conditions as written would have exposed two dead settings**

- **Found during:** Task 1
- **Issue:** described above under Decisions Made. The plan's stated reason for dropping the
  conditions holds for one of the two expressions and is inverted for the other.
- **Fix:** conditions dropped as KODI-06 requires; the two rows the false condition was hiding
  declared at Advanced, with the reasoning in a comment in the file and a deferred item naming what
  finishes the job.
- **Files modified:** `resources/settings.xml`, `.planning/phases/03-authentication/deferred-items.md`
- **Commit:** `3f20640`

### Additions the plan implied but did not enumerate

- **Two new strings.** The plan counted the three catalogue entries that leave; it did not count the
  ones that arrive with the new setting. 30070 is its label and 30071 its help, added to en_gb in
  Task 1 with `ADDON_STRING_IDS` widened in the same commit, then narrowed by three in Task 2. The
  set ends at 48. `he_il` was checked and carries none of the three removed ids — it holds
  30000-30011 and the module block only — so it needed no edit, which is the answer to "keep the two
  catalogues in step" rather than an omission of it.
- **An id for the clear-cache action.** The old format did not require one on an action row; the new
  one does. `clear_cache` names no stored value.

## Requirement Marks Kept, and Why

The plan's frontmatter declares six. Four were marked and three of those six were deliberately left
alone, because a requirement declared by more than one plan is Complete only when the **last** of
them lands:

| Requirement | Marked | Why |
|-------------|--------|-----|
| AUTH-19 | **Complete** | 03-11 is the last of the three plans that declare it (03-03, 03-08, 03-11). The setting exists, is Expert, is empty, and its id matches its reader exactly |
| KODI-05 | **Complete** | Declared by 03-11 alone. The file is `version="1"` with section, category and group structure |
| KODI-06 | **Complete** | Declared by 03-11 alone. No `visible=` and no `iskrypton` survive in the settings file |
| KODI-08 | **Complete** | Declared by 03-09, which left it partial because the setting survived. Not in 03-11's frontmatter, so it would have been missed by the automatic marking; verified clause by clause above and marked by hand |
| AUTH-02 | left Pending | Also declared by 03-12 and 03-13 |
| AUTH-18 | left Pending | Also declared by 03-13, which owns the message this setting is pointed at from |
| AUTH-23 | left Pending | Also declared by 03-12, which owns `addon.xml:55` — the one site the broker sweep still reports |

The traceability table's Phase column for KODI-05, KODI-06 and KODI-08 was corrected from Phase 7 to
Phase 3, which is where they actually landed. Leaving it would have told Phase 7 to deliver three
things that are already done.

## Issues Encountered

**XML comments cannot contain `--`.** The first draft of the file used the repository's prose style,
which uses `--` as a dash, inside a comment. `ET.parse` refused it at line 143. Rewritten as two
sentences. Worth knowing before the next person writes a comment in this file.

## Next Phase Readiness

**For 03-12 (the vendored tree and its record):**

- `test_no_broker_references` now reports exactly one site: `addon.xml:55`, in the `<disclaimer>`.
  That is the last one. Clearing it turns the phase's last red assertion green.
- `deferred-items.md` item 6: `VENDORED.md:245` describes the error reporter and the `report_error`
  setting in the present tense. Both are now gone. The record should say so as past, which is what
  `test_the_replaced_flow_is_named_in_the_two_excluded_documents` already asks of that file for the
  sign-in flow.
- `VENDORED.md`'s deviations section still names `allow_directory_listing`, and it must keep doing
  so — `test_vendored_deviations_are_recorded` asserts it, and the deviation survived the conversion.

**For 03-14 (the television pass):**

Three constructs in the converted file have never been loaded by Kodi and are the things to look at
first if the settings dialog misbehaves:

1. `<close>true</close>` inside the clear-cache button control, reproducing the old `option="close"`.
2. The two setting ids containing hyphens — `cache-expiration-time` survives and is read by name
   from `KodiUtils.get_cache_expiration_time`.
3. `type="integer"` with an `edit` control where the old format said `type="number"`, on
   `port_directory_listing`, `cache-expiration-time` and `slideshow_refresh_interval`.

Also worth a glance on the remote: whether the `client_id` box can be cleared back to empty, and
whether an Expert-level setting is reachable at all from the settings screen as the skin renders it.

**For Phase 7:**

`KODI-05`, `KODI-06` and `KODI-08` are done and their traceability rows now say Phase 3. `KODI-07`
is untouched and its two settings rows — `allow_directory_listing` and `port_directory_listing` —
were converted, not deleted, on purpose: the listener behind them is deleted by that criterion, and
removing only the settings would leave it running with no way to turn it off.

## Self-Check: PASSED

- `resources/settings.xml` — FOUND, parses, `version="1"`
- `resources/language/resource.language.en_gb/strings.po` — FOUND, 30070/30071 present, 30030/30031/30033 absent
- `tests/test_vendor_gates.py` — FOUND, `ADDON_STRING_IDS` is 48
- `.planning/phases/03-authentication/deferred-items.md` — FOUND, items 6 and 7 present
- Commit `3f20640` — FOUND in `git log`
- Commit `94ddc3d` — FOUND in `git log`
- Suite: 234 passed, 1 failed (`addon.xml:55`, 03-12's), 1 skipped
