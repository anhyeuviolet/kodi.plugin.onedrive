---
phase: 01-vendor-lift
plan: 03
subsystem: identity
tags: [addon.xml, kodi, gettext, strings.po, settings.xml, versioning, i18n]

# Dependency graph
requires:
  - "01-02 — tests/test_vendor_gates.py, which owns the three assertions this plan turns green"
provides:
  - "The add-on id plugin.onedrive.kn — every later commit in the phase writes to a fresh addon_data profile"
  - "The Kodi 19 gate: xbmc.python 3.0.1, refused by Kodi 19 and accepted by 20, 21 and 22"
  - "A free 32000-block string namespace for the 89 module ids that 01-04 merges in"
  - "The 30000 block occupied by this add-on's own 25 en_gb and 12 he_il ids"
  - "allow_directory_listing defaulted off, ahead of the subsystem's deletion in Phase 7"
affects: [01-04, 01-05, 01-06, 01-07, phase-05-dist]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Identity-first: the id changes before anything else, so no intermediate commit can contaminate the original add-on's profile"
    - "Rewrite by call site, not by number, wherever two id namespaces share a file"
    - "The dangerous-literal rule: a plugin:// host pointing at the wrong add-on keeps working perfectly, so it is repointed in the same commit that changes the id"

key-files:
  created: []
  modified:
    - addon.xml
    - resources/settings.xml
    - resources/language/resource.language.en_gb/strings.po
    - resources/language/resource.language.he_il/strings.po
    - resources/lib/addon.py

key-decisions:
  - "Display name is OneDrive KN and provider-name is Kenny Nguyen — recorded verbatim; the gate asserts non-equality with the upstream values rather than pinning these, so they can be adjusted without editing a test"
  - "version is 1.0.0, per the plan and the gate, not the 3.0.0 that 01-RESEARCH.md floated as [ASSUMED] A4 — the two ids never compare against each other, so there is no downgrade path to protect"
  - "kodi.wiki/view/Language_support was reachable this session (HTTP 200 with a browser UA, where research recorded a 403) and confirms the 30000/32000 split verbatim — assumption A1 is now verified, not assumed"
  - "The module import stays declared in addon.xml; removing it here would leave the add-on with neither the external module nor a local copy"
  - "The disclaimer block is untouched — it still describes what the code does until Phase 3 removes the broker"

patterns-established:
  - "A blanket numeric rewrite is only ever safe in a file that holds exactly one id namespace, and only before a merge introduces a second"

requirements-completed: [ID-01, ID-02, KODI-01]

coverage:
  - id: D1
    description: "The manifest declares the new id, version, distinguishable name and current maintainer, with source and forum repointed and website dropped"
    requirement: ID-02
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_addon_xml_identity"
        status: pass
    human_judgment: false
  - id: D2
    description: "No occurrence of the bare add-on id survives anywhere in the tree outside this repository's own URL"
    requirement: ID-01
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_addon_id_everywhere"
        status: pass
    human_judgment: false
  - id: D3
    description: "allow_directory_listing defaults to false and no settings row opens the vanished common-settings add-on"
    requirement: ID-01
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_directory_listing_default_off"
        status: pass
    human_judgment: false
  - id: D4
    description: "The en_gb id set is exactly the 25 expected 30000-block ids, the he_il set exactly 12, and neither contains 30012"
    verification:
      - kind: unit
        ref: "Task 2 <verify> block — set equality against the expected partition"
        status: pass
    human_judgment: false
  - id: D5
    description: "addon.py calls 30007/30008/30009 on this add-on and still calls 32032/32053/32058 on the module"
    verification:
      - kind: unit
        ref: "Task 2 <verify> block — six literal call-site assertions"
        status: pass
    human_judgment: false
  - id: D6
    description: "xbmc.python 3.0.1 refuses Kodi 19 and installs on 20, 21 and 22"
    requirement: KODI-01
    verification:
      - kind: manual
        ref: "01-07 install matrix"
        status: deferred
    human_judgment: true
    rationale: "A claim about an external dependency resolver cannot be proven from inside this repository. The manifest half is asserted here; the behavioural half is the install matrix in 01-07."

# Metrics
duration: 20min
completed: 2026-08-22
status: complete
---

# Phase 1 Plan 03: Add-on Identity and String Namespace Summary

**The add-on becomes a different add-on — `plugin.onedrive.kn` 1.0.0 under a new maintainer, with a Kodi 19 gate Kodi enforces mechanically and its own 25 strings moved out of the 32000 block, clearing the way for the 89 ids arriving next.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-22T20:31:00+07:00
- **Completed:** 2026-08-22T20:50:25+07:00
- **Tasks:** 2 of 2
- **Files modified:** 5 (0 created, 5 modified)

## Accomplishments

- Changed **what this add-on is** before changing what it contains. Because the id is new, every later commit in the phase writes to a fresh `addon_data` directory, and the original add-on's tokens, caches and databases are never read or written — which is also why no migration exists to get wrong.
- Armed the Kodi 19 gate as a **declaration Kodi itself enforces**, not a runtime check the add-on could get wrong: `xbmc.python` 3.0.1 is above Kodi 19's 3.0.0 and at or below what 20, 21 and 22 ship.
- Repointed **both** `plugin://` literals in `settings.xml` in the same commit as the id change. These are the failure mode that testing cannot catch: on a machine with the original add-on installed they keep working perfectly while driving the other add-on.
- Moved this add-on's ids into the 30000 block **before** the module's strings arrive, which is the only window in which a blanket rewrite is safe.
- Deleted `32012` and the settings row it labelled, rather than renumbering a row that would have had nothing left to open.

## Task Commits

1. **Task 1: Add-on identity, maintainer attribution, and the Kodi 19 gate** — `a2c6db2` (feat)
2. **Task 2: String ids into the 30000 block, settings screen consolidated** — `5d1cc6d` (refactor)

## Files Created/Modified

- `addon.xml` — id, name, version, provider-name; `xbmc.python` 3.0.0 → 3.0.1; `source`/`forum` repointed; `website` deleted; `news` replaced with a v1.0.0 entry.
- `resources/settings.xml` — 23 labels renumbered, both `plugin://` hosts repointed, the common-settings row deleted, `allow_directory_listing` defaulted off.
- `resources/language/resource.language.en_gb/strings.po` — header comments updated; 25 ids renumbered; the `32012` block deleted.
- `resources/language/resource.language.he_il/strings.po` — same, 12 ids.
- `resources/lib/addon.py` — three `self._addon.getLocalizedString` call sites moved to the 30000 block; the three `self._common_addon` call sites untouched.

CRLF line endings and UTF-8 encoding are byte-preserved in all five files — the Hebrew `.po` was checked explicitly.

## The values chosen, recorded verbatim

| Attribute | Was | Is now |
|---|---|---|
| `id` | `plugin.onedrive` | `plugin.onedrive.kn` |
| `name` | `OneDrive` | `OneDrive KN` |
| `version` | `2.3.0` | `1.0.0` |
| `provider-name` | `Carlos Guzman (cguZZman)` | `Kenny Nguyen` |

`OneDrive KN` differs from `OneDrive` by more than case or surrounding whitespace, so the two render distinguishably side by side in Kodi's add-on browser. The gate deliberately asserts non-equality rather than pinning these strings, so the presented name can be revised later without touching a test — what it may not be is the upstream value.

**On `version = 1.0.0`.** `01-RESEARCH.md` floated `3.0.0` as `[ASSUMED]` A4, reasoning that it sits above the upstream `2.3.0`. That reasoning only applies within one id namespace, and there no longer is one: Kodi compares versions per add-on id, and `plugin.onedrive.kn` never compares against `plugin.onedrive`. The plan and the gate both specify `1.0.0`, which is what a new add-on starting its own version line should carry. A4 is resolved, in the plan's direction.

## What kodi.wiki says about the id ranges

Assumption A1 in `01-RESEARCH.md` was recorded as unverified because `kodi.wiki` returned 403 to an automated fetch during research. **It was reachable this session** — HTTP 200 with a browser user-agent — and `https://kodi.wiki/view/Language_support` states, verbatim:

> These IDs are reserved by Kodi:
> - strings 30000 thru 30999 reserved for plugins and plugin settings
> - strings 31000 thru 31999 reserved for skins
> - strings 32000 thru 32999 reserved for scripts
> - strings 33000 thru 33999 reserved for common strings used in add-ons

This add-on is a plugin (`xbmc.python.pluginsource`), so 30000–30999 is exactly where its own strings belong; the bundled common module is a script-class module, so 32000–32999 is where its 89 ids belong. The two blocks the phase uses are the two blocks the convention assigns. **A1 is verified, not assumed** — and `kodi-addon-checker` has no grounds to object to the renumbering.

## The renumbering, precisely

| File | Ids before | Ids after | Count |
|---|---|---|---|
| `en_gb` | 32000–32012, 32017–32020, 32030–32035, 32067–32069 | 30000–30011, 30017–30020, 30030–30035, 30067–30069 | 26 → **25** |
| `he_il` | 32000–32012 | 30000–30011 | 13 → **12** |

`32012` is the one that does not survive. Its text is *"Open Cloud Drive Common Settings…"* — the label of the settings row that opened the separate common-settings add-on. After bundling there is no separate add-on to open, so the row could only error or loop back into these same settings. Both the string and its row are deleted, and `30012` deliberately does not exist in either file. This is exactly the assertion 01-02 corrected its gate to make (`30012 not in en_gb`, `32012 in en_gb` once the module's differently-meaning `32012` arrives).

**Why the ordering is load-bearing.** The module's 89 ids collide completely with this add-on's 26, and 22 of the 26 mean something different on each side. A blanket `msgctxt "#32NNN"` → `"#30NNN"` rewrite is correct today because these files contain nothing but this add-on's own ids. Run after 01-04's merge, the identical command would silently renumber the module's ids as well — including three resolved at runtime from a `UIException` message and two persisted in the export schedule store, neither of which any static rewrite can see. That is the whole reason this work sits in 01-03 and not beside the vendor copy.

**`addon.py` was rewritten by call site, not by number** (threat T-1-14). The three calls that move go through `self._addon`; the three that stay — 32032, 32053, 32058 — go through `self._common_addon`, and two of them sit on the *same lines* as calls that moved. A numeric rewrite of this file would have retargeted the slideshow context-menu label from the module's "Auto-Refreshed slideshow" to a 30000-block id that does not exist, producing a blank menu entry rather than an error. An acceptance criterion asserts both sets survived correctly.

## Recorded behaviour deviation: `allow_directory_listing`

This is a deliberate, one-attribute departure from the phase's "identical behaviour" contract, flagged here so 01-07 can record it in `VENDORED.md` and no later reader mistakes it for a regression. `default="true"` → `default="false"`.

The reasoning: the gated service binds a loopback port and serves an **enumerable index of the entire drive with no authorisation check anywhere in the server base class**; on Android every installed app can reach loopback; the module's own upstream documents the feature as not working; and because the add-on id is new, **no user has a stored `true` that would override the new default** — the flip is complete rather than partial, which it would not have been under the old id. The subsystem is deleted outright in Phase 7 under KODI-07. Research assumption A6 asked for maintainer confirmation either way; the alternative was carrying a live unauthenticated listener into a fresh profile on first run.

## Gate movement

Full suite before this plan: **15 failed, 7 passed**. After: **12 failed, 10 passed**. Exactly the three this plan owns went green, and no previously-green gate regressed.

| Gate | Before | After |
|---|---|---|
| `test_addon_xml_identity` | red | **green** |
| `test_addon_id_everywhere` | red | **green** |
| `test_directory_listing_default_off` | red | **green** |

`test_string_ids_partitioned` is **still red, correctly** — it asserts the *union* of both blocks, and the module's 32000-block ids do not arrive until 01-04 Task 2. Half of its precondition is now satisfied.

`test_addon_xml_imports` is **still red, and for the intended reason**: `xbmc.python` is now 3.0.1, but two `<import>` elements remain because `script.module.clouddrive.common` is deliberately still declared. Removing it here would leave the add-on with neither the external module nor a local copy — an uninstallable intermediate commit. 01-05 Task 2 removes it in the same commit that makes the local copy live, and an acceptance criterion in this plan asserts it survived.

## Decisions Made

1. **`OneDrive KN` / `Kenny Nguyen` / `1.0.0`**, recorded verbatim above. Resolves research assumption A4 in the plan's direction.
2. **The 30000/32000 split is now sourced, not assumed** — kodi.wiki quoted above. Resolves A1.
3. **The module import stays** through 01-03 and 01-04. This is the commit-boundary installability guarantee, and it is asserted rather than merely printed, so it cannot be dropped by accident.
4. **The `<disclaimer>` is untouched.** It describes the sign-in server, which is still exactly what the code does until Phase 3 removes the broker. Rewriting it here would make the manifest describe behaviour the add-on does not have.
5. **`<website>` is deleted rather than repointed.** It pointed at `addons.kodi.tv`, which lists the upstream add-on; this add-on is not published in the Kodi repository, so there is no correct value.
6. **`<news>` rewritten to a v1.0.0 entry.** The old text announced a Kodi 20 fix in a version line this add-on no longer shares.

## Deviations from Plan

None — the plan executed exactly as written. No auto-fix rule fired, no architectural question arose, and no acceptance criterion needed adjustment.

## Issues Encountered

- **`.planning/config.json` was modified-but-uncommitted on arrival** (orchestrator bookkeeping, not this plan's doing). It was deliberately excluded from both task commits, which stage only the five source files, matching what 01-02 did.

## User Setup Required

None. This plan installs nothing and touches no external service.

## Follow-ups for later phases

- **DIST-01 zip naming — Phase 5.** `REQUIREMENTS.md` DIST-01 still specifies a zip named `plugin.onedrive-<version>.zip` containing a top-level `plugin.onedrive/` directory. Both now contradict ID-01. `REQUIREMENTS.md` is not edited from inside this phase, so this is carried explicitly: **Phase 5 must update DIST-01 to `plugin.onedrive.kn-<version>.zip` with a top-level `plugin.onedrive.kn/` directory**, or the packaged add-on will not install under the id it declares.
- **VENDORED.md — 01-07 Task 2.** The `allow_directory_listing` default flip is a recorded behaviour delta and needs its entry in the behaviour-differences section.
- **ID-05 — manual.** Detaching the repository from the upstream fork network is a GitHub-side operation; `gh` is not installed on this machine. Unchanged by this plan.

## Next Phase Readiness

- **01-04 can merge the module's strings cleanly.** The 32000 block is empty in both `.po` files, so the merge cannot produce a duplicate `msgctxt` — the failure that would have silently mislabelled most of the settings screen and both context menus.
- **01-04 and 01-05 write to a fresh profile.** Every install from this commit forward uses `addon_data/plugin.onedrive.kn/`.
- **Carry-forward for 01-04:** `test_string_ids_partitioned` needs the module's 32000–32088 ids merged into `en_gb` *including* the module's own `32012` ("Yes! Count me in"), which is a different string from the one deleted here. Do not treat the absent `30012` as something to restore.
- **Carry-forward for 01-05:** `test_addon_xml_imports` expects exactly one `<import>`. `xbmc.python` is already correct at 3.0.1; only the `script.module.clouddrive.common` line needs removing, and only in the commit that makes the bundled copy live.

## Self-Check: PASSED

- `addon.xml`, `resources/settings.xml`, both `strings.po`, `resources/lib/addon.py` — all present and modified
- `a2c6db2`, `5d1cc6d` — both present in git history
- No tracked file was deleted by either commit (`git diff --diff-filter=D` empty across both)
- `python -m compileall -q resources/ entrypoint.py service.py` exits 0
- Both `.po` files and `settings.xml` remain CRLF-only and valid UTF-8

---
*Phase: 01-vendor-lift*
*Completed: 2026-08-22*
