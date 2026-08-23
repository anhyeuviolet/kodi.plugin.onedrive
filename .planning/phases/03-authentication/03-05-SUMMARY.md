---
phase: 03-authentication
plan: 05
subsystem: auth
tags: [aadsts, entra-id, error-mapping, gettext, strings-po, kodi-strings, ten-foot-ui, python38]

requires:
  - phase: 03-authentication
    provides: "Plan 03-01's resources/lib/auth/ package — the zero-Kodi-import package this table joins, and the terminal-vs-retryable split in poll_once that decides when this table is consulted at all"
  - phase: 03-authentication
    provides: "Plan 03-03's tests/gatelib.py and its EXCLUDED_TOP_LEVEL, which is what lets the test file quote the AADSTS7000218 response verbatim while the shipped module is asserted never to name a credential parameter"
  - phase: 01-vendor-lift
    provides: "The 30000/32000 string partition and its exact-equality gate in tests/test_vendor_gates.py"
provides:
  - "resources/lib/auth/errors.py — CODE_PATTERN, thirteen mapped codes, the Failure namedtuple, extract_code, classify and classify_response"
  - "The symbolic outcome vocabulary the Kodi renderer will switch on, and the admin_must_act flag that tells it when to stop offering a retry"
  - "resources/language/resource.language.en_gb/strings.po 30036-30058 — every word this phase will put on a television"
  - "The widened catalogue partition, so no later plan in this phase has to touch the gate to add its copy"
affects: [03-06, 03-07, 03-08, 03-09, 03-10, 03-11, 03-12, 03-13, 03-14]

tech-stack:
  added: []
  patterns:
    - "The failure table is data: identifiers and a flag, never sentences, so it is testable without Kodi and renderable without duplicating the words"
    - "The whole phase's copy lands in one commit with the exact-equality gate widened beside it, rather than four commits each risking a red gate"
    - "A test file under tests/ quotes a response the shipped tree may not, and the shipped module carries the assertion that it does not"

key-files:
  created:
    - resources/lib/auth/errors.py
    - tests/test_error_map.py
  modified:
    - resources/language/resource.language.en_gb/strings.po
    - tests/test_vendor_gates.py

key-decisions:
  - "The table holds no words and no string ids: it returns a symbolic outcome and the bare code, and the Kodi layer picks the sentence — the split that lets it be tested without Kodi and rendered without a second copy of the copy that then drifts"
  - "admin_must_act is not a severity, it is the single question 'can the person holding the remote clear this themselves?' — so consent, both MFA codes and an expired password are all False, because telling that person to fetch an administrator sends them away from the one action that works"
  - "AADSTS7000218 is not marked administrator-must-act, because after shipping only somebody who already set a custom identifier can reach it, and appending 'set a custom Client ID' to their message is the one piece of advice that cannot help them"
  - "The honest union of the roadmap's candidates and the pitfall record is twelve codes, not thirteen; AADSTS70019 is a deliberate thirteenth, because device-code expiry is the terminal refusal this flow will actually produce most often"
  - "classify_response falls back to the error_codes array when a description carries no code, because that array was observed live in the spike and a body truncated by a proxy still names the refusal in it"
  - "The catalogue block is contiguous from 30036 and its outcome-to-id pairing is written into the file as a comment, so the link to errors.py is readable from either end without either file naming the other's contents"

patterns-established:
  - "Pattern 1: an entry in a routing table is proven distinct by asserting the whole outcome set has no duplicates, not by eyeballing the table"
  - "Pattern 2: a shipped module that must never say a particular thing carries the assertion that it does not, in its own test file"
  - "Pattern 3: a gate whose expected set is widened is mutation-checked in the same session against the four ways it could have been widened wrongly"

# This plan declares [AUTH-18, AUTH-05, AUTH-06, AUTH-21, AUTH-22] and completes
# none of them outright. Each is still owed by a later plan in this phase --
# AUTH-05 by 03-06 and 03-14, AUTH-06 by 03-06/03-08/03-14, AUTH-18 by
# 03-09/03-11/03-13, AUTH-22 by 03-09 and 03-14 -- and AUTH-21 was completed by
# 03-01 before this plan ran. What this plan supplies is the copy and, for
# AUTH-18, the routing table; a string in a catalogue nobody renders satisfies
# nothing. See the ## Requirements section and deviation 4.
requirements-completed: []

coverage:
  - id: D1
    description: "Thirteen failure codes each route to their own distinct outcome, over the union of the roadmap's candidates and the pitfall record"
    requirement: "AUTH-18"
    verification:
      - kind: unit
        ref: "tests/test_error_map.py::test_the_table_covers_the_union_of_the_roadmap_and_the_pitfall_record"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_every_mapped_code_routes_to_its_own_distinct_outcome"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_the_table_has_thirteen_entries"
        status: pass
    human_judgment: false
  - id: D2
    description: "The code is extracted from a realistic description paragraph by pattern, and the paragraph itself never leaves the module"
    requirement: "AUTH-18"
    verification:
      - kind: unit
        ref: "tests/test_error_map.py::test_the_code_is_extracted_from_a_realistic_description_paragraph"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_routing_reads_the_description_not_the_oauth_error_value"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_the_table_holds_no_sentence_and_no_string_id"
        status: pass
    human_judgment: false
  - id: D3
    description: "An unmapped code still reaches the screen as a bare code, and a description with no code at all classifies without raising"
    requirement: "AUTH-18"
    verification:
      - kind: unit
        ref: "tests/test_error_map.py::test_the_unmapped_outcome_preserves_the_bare_code"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_a_description_carrying_no_code_yields_the_unmapped_outcome_without_raising"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_an_absent_description_classifies_rather_than_raising"
        status: pass
    human_judgment: false
  - id: D4
    description: "No outcome maps to advice involving a credential on the registration, and AADSTS7000218's message is aimed at the person who set a custom identifier rather than at an administrator"
    requirement: "AUTH-18"
    verification:
      - kind: unit
        ref: "tests/test_error_map.py::test_no_outcome_could_be_read_as_advice_to_add_a_credential"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_the_public_client_code_is_not_an_administrator_outcome"
        status: pass
    human_judgment: false
  - id: D5
    description: "The administrator family is marked and nothing else is, so the renderer can replace a retry that cannot succeed with the escape hatch"
    requirement: "AUTH-18"
    verification:
      - kind: unit
        ref: "tests/test_error_map.py::test_the_administrator_family_is_marked_and_nothing_else_is"
        status: pass
      - kind: unit
        ref: "tests/test_error_map.py::test_a_failure_the_person_can_clear_themselves_is_not_marked"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every string this phase will show exists in the English catalogue in this add-on's reserved range, and the exact-equality partition gate is green in the same commit"
    requirement: "AUTH-22"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_string_ids_partitioned"
        status: pass
      - kind: other
        ref: "23 contiguous ids 30036-30058 verified well-formed and escape-free; en_gb 114 -> 137 entries, he_il unchanged at 73"
        status: pass
    human_judgment: false
  - id: D7
    description: "A tenant that blocks this application produces a sentence naming the cause and pointing at the expert-level custom identifier setting"
    requirement: "AUTH-18"
    verification:
      - kind: unit
        ref: "tests/test_error_map.py::test_the_administrator_family_is_marked_and_nothing_else_is (the routing half)"
        status: pass
    human_judgment: true
    rationale: "UNVERIFIED against a genuinely blocking tenant, and recorded that way rather than claimed (D-08). The tenant hosting this registration permits the device authorization grant, so no blocking response can be produced from it on demand. What is proven is that each candidate code routes to a marked outcome and that a marked outcome is the one the escape-hatch sentence is appended to; which code a real blocking tenant returns, and whether the sentence reads right on a television, are both open"
  - id: D8
    description: "The sign-in copy is legible and actionable from a sofa at three metres"
    requirement: "AUTH-05"
    verification: []
    human_judgment: true
    rationale: "Whether a sentence works on a television is a property of reading it on one. PITFALLS.md Pitfall 5 and 03-RESEARCH.md both record that a font name that does not resolve fails silently, so no static check over this catalogue can answer it. It belongs to the TCL Android TV 12 acceptance pass, together with the dialog plan that renders these strings"

duration: 35min
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 05: The Failure Table and the Phase's Catalogue Summary

**Thirteen provider refusal codes now route to thirteen distinct outcomes that hold no words, and every sentence this phase will put on a television exists in the catalogue with the exact-equality gate widened beside it in the same commit.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-23T03:30Z
- **Completed:** 2026-08-23T04:05Z
- **Tasks:** 2 of 2
- **Files created:** 2
- **Files modified:** 2
- **Suite:** 167 passed, 5 failed by construction, 1 skipped, 2.0s

## Accomplishments

- **The paragraph never reaches the screen, and the code always does.** `extract_code` runs a pattern anchored on the fixed prefix against `error_description` and returns the first match; nothing else in that paragraph — not the prose, not the markdown link, not the trace identifier — leaves the module. The two responses the tests drive it with are quoted verbatim, links and all, because a tidied paraphrase would not prove the extraction survives the real shape.
- **`admin_must_act` is the one question that matters, asked once.** Not a severity, not a category: *can the person holding the remote clear this themselves?* Consent, both MFA codes and an expired password are all `False`, because they are cleared on the phone and telling that person to fetch an administrator sends them away from the one action that works. Six codes are `True`, and those are the only ones the escape-hatch sentence is appended to.
- **The one code that misdirects is aimed at the person who can actually be reached by it.** After shipping, `AADSTS7000218` is reachable only by somebody who set their own application identifier and left the public-client switch off. Its sentence tells that person to turn the switch on and says in as many words that adding a secret will not help — and `test_no_outcome_could_be_read_as_advice_to_add_a_credential` sweeps the shipped module for the credential parameter names, the phrase "add a secret" and the word "certificate", so the module cannot drift into repeating the misdirection even in a comment a maintainer skims.
- **The table is data all the way down.** Every outcome is asserted to match `^[a-z][a-z0-9_]*$`, and the module is asserted to name no localised string id at all — so the choice of which sentence an outcome renders as stays with the Kodi layer and the words exist in exactly one place.
- **The whole phase's copy landed in one commit.** Twenty-three contiguous ids, 30036 to 30058, with the expected-identifier set and its count assertion moved in the same commit. Four later plans now add their screens without touching the gate, which was the entire reason the copy was pulled forward into this plan.
- **Both halves were mutation-checked rather than assumed.** Eight mutations of the failure table and four of the catalogue-and-gate pair, each restored afterwards; every one produced a failure, and each failure named the property it broke.

## Task Commits

1. **Task 1: The failure table (TDD)** — `bc13f94` (test, RED) → `1c12f54` (feat, GREEN)
2. **Task 2: The phase's English catalogue, and the partition gate that follows it** — `083a248` (feat)

## Files Created/Modified

- `resources/lib/auth/errors.py` — `CODE_PATTERN`, fourteen outcome constants, `FAILURES` (thirteen codes), `ROADMAP_CANDIDATES`, the `Failure` namedtuple, `extract_code`, `classify` and `classify_response`. Imports `collections` and `re` and nothing else.
- `tests/test_error_map.py` — 28 tests across extraction, routing, the unmapped fallthrough, the whole error body, the administrator family, the roadmap candidates, and four source assertions over the shipped module.
- `resources/language/resource.language.en_gb/strings.po` — 23 entries, 30036-30058, preceded by a comment block carrying the outcome-to-id pairing and the rule that 30045 is appended to the administrator family and to nothing else. 114 entries → 137.
- `tests/test_vendor_gates.py` — `ADDON_STRING_IDS` widened by `range(30036, 30059)`, the count assertion 25 → 48, and a comment recording why the widening travels in the same commit as the additions.

## Decisions Made

**The table returns identifiers; the catalogue holds the words.** `classify` hands back `Failure(outcome, code, admin_must_act)` and nothing that reads as English. The alternative — a sentence or a string id in the table — puts the copy in two places, and two copies of a sentence drift the first time one of them is reworded. The cost is one lookup in the Kodi layer; the benefit is that the whole table is testable as data without a stub library, which is what the other 27 assertions in `test_error_map.py` depend on.

**Thirteen entries, and the thirteenth is a deliberate addition.** The honest union of ROADMAP.md criterion 1a's candidates and PITFALLS.md Pitfall 4's table is **twelve** codes: the roadmap names five (`7000218`, `65001`, `50105`, `53003`, `7000014`), the pitfall record names nine, and two of those overlap. The plan's "thirteen or so" is 9 + 4 added without subtracting the overlap. Rather than pad the table to reach a number, `AADSTS70019` — the device code expiring before anybody enters it — was added on its own merits: the window is fifteen minutes, Pitfall 5 names the user who walks off to find their phone as a named failure mode, and this phase is already building an expired state and a "Get a new code" action for exactly that path. It is the terminal refusal this flow will actually produce most often, and it was the only entry in the table missing a route.

**`classify_response` reads `error_codes` when the description does not carry a code.** STACK.md records the array observed live twice — `[70016]` on a pending poll and `[7000014]` on a rejected device code. A body whose description is absent or truncated by a proxy still names the refusal there, and reading it is the difference between naming the failure and showing nothing. Made a fallback inside the module rather than a second path the caller has to remember, because a caller who forgets it gets the silent-degradation case.

**The catalogue's block is contiguous and its pairing is written down.** 30036-30058 in one run, so the phase's copy reads as one group in the file rather than scattered through the free gaps. The comment above it lists which id serves which outcome. Neither file names the other's contents — `errors.py` has no ids in it, and the `.po` has no outcome logic — so the pairing exists in exactly one place, in the file a translator will already be reading.

**British spelling, and `mfa_enrolment_required` with one L.** The catalogue is `en_gb` and the outcome identifier matches the sentence it will render, which is a small thing that stops a later reader from wondering whether they are two different concepts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] `classify_response` and the `error_codes` fallback**

- **Found during:** Task 1
- **Issue:** The plan scopes the module to the description field. But the terminal branch this table serves receives a whole JSON body, and `STACK.md` §1.4 records `error_codes` observed live on two separate responses. A body that arrives with the array and a description that a proxy truncated — or that the provider simply did not populate — classifies as unmapped with an empty code, which is the one output that puts nothing actionable on screen. Every caller would then have to remember to check the array itself, and the first one that forgot would degrade silently.
- **Fix:** `classify_response(payload)` tries the description first and falls back to the array, guarding non-mapping input. Four tests added with it, including that the description wins when both are present.
- **Files modified:** `resources/lib/auth/errors.py`, `tests/test_error_map.py`
- **Verification:** `test_a_body_with_only_an_error_codes_array_still_routes`, `test_the_description_wins_over_the_error_codes_array`, `test_a_body_with_neither_source_yields_the_unmapped_outcome`, `test_a_body_that_is_not_a_mapping_does_not_raise`; the mutation that removes the fallback turns one of them red.
- **Committed in:** `1c12f54`

**2. [Scope] The thirteenth entry is `AADSTS70019`, added on its merits rather than to reach a count**

- **Found during:** Task 1
- **Issue:** The plan's `<done>` requires thirteen codes; the union it derives them from yields twelve. Padding the table to thirteen with an arbitrary code would make the count true and the table worse.
- **Fix:** `AADSTS70019` (the device code expired before it was used) was added with its reason recorded in the source. It is the terminal refusal a fifteen-minute window produces most often, Pitfall 5 names the user it happens to, and this phase already builds the expired state and the fresh-code action it routes to. The count is now honest in both directions: `test_the_table_has_thirteen_entries` and the explicit `EXPECTED_CODES` set in the test file both pin it, and the summary records that the derived union was twelve.
- **Files modified:** `resources/lib/auth/errors.py`, `tests/test_error_map.py`
- **Verification:** deleting the entry turns two tests red.
- **Committed in:** `bc13f94`, `1c12f54`

**3. [Scope] The plan's verification expects "twenty-two green" vendor gates; the file now has twenty-three**

- **Found during:** Task 2
- **Issue:** The plan was written against a twenty-two-assertion vendor gate file. Plan 03-03 has since added `test_runbook_contains_aadsts7000218` to it, as its own summary records.
- **Fix:** None needed — recorded here so that a reader comparing the plan's verification block to the run does not read the extra assertion as an accident. `python -m pytest tests/test_vendor_gates.py -q` reports **23 passed**, and the twenty-third is 03-03's.
- **Verification:** `git log --oneline -- tests/test_vendor_gates.py` shows `71188ec` adding it.

**4. [Rule 1 — Bug] The state update flipped four requirements to Complete that later plans still owe, and the marks were reverted**

- **Found during:** state updates, after both tasks were committed
- **Issue:** `requirements mark-complete` was called with this plan's declared ids and ticked `AUTH-05`, `AUTH-06`, `AUTH-18` and `AUTH-22` in both surfaces of `REQUIREMENTS.md`. The shared-id gate 03-03's summary describes — which holds a requirement open until the *last* declaring plan finishes — did not fire. All four are still declared by later plans in this phase: AUTH-05 by 03-06 and 03-14, AUTH-06 by 03-06, 03-08 and 03-14, AUTH-18 by 03-09, 03-11 and 03-13, AUTH-22 by 03-09 and 03-14. `AUTH-05` in particular reads "the device-code dialog renders the code at the largest font the skin offers, legible from a sofa", and no dialog exists yet — nothing in this plan renders anything.
- **Fix:** All eight edits (four checkboxes, four traceability rows) were reverted, leaving `REQUIREMENTS.md` byte-identical to its previous commit. `AUTH-21` was left alone: it was already complete, marked by plan 03-01. This summary's `requirements-completed` is `[]` with a comment naming what it supplies instead, so a later reader does not have to reconstruct why the plan declared five and completed none.
- **Files modified:** `.planning/REQUIREMENTS.md` (net zero change against `HEAD`)
- **Verification:** `git diff --stat -- .planning/REQUIREMENTS.md` is empty.
- **Why not just leave them ticked:** this repository's whole instrument — the five red-by-construction gates, the non-vacuity guards, the runbook's unverified note — exists to stop a claim being recorded before it is true. A ticked `AUTH-05` would have let this phase finish with its dialog unbuilt and the record saying otherwise, which is the single failure mode all of that machinery is aimed at.

---

**Total deviations:** 4 (1 × Rule 1, 1 × Rule 2, 2 scope observations)
**Impact on plan:** None on shape or scope. Deviation 1 makes the table work on the input its caller actually holds; deviations 2 and 3 are the plan's arithmetic and the plan's baseline being corrected against the tree rather than followed off a cliff; deviation 4 is a false green in the project's own record, caught and reverted before it was committed.

## Issues Encountered

**A mutation harness that restores with `git checkout` does nothing to an untracked file.** The first non-vacuity run on `errors.py` was made before the GREEN commit, so `git checkout -- resources/lib/auth/errors.py` was a silent no-op and the mutations accumulated: the "case-insensitive prefix" mutation was still in the file when the next one was applied, which is why that run reported 1, then 3, then 4, then 5 failures instead of one apiece. The file was restored from the authored content and the harness rewritten to hold a pristine copy in memory. The corrected run is the one recorded below, and every mutation was checked against a clean file. Worth carrying forward: a mutation harness has to restore from something it holds, not from the index, or it will happily report that a test suite is catching things it is not.

**The extraction's case sensitivity is load-bearing and non-obvious.** `re.IGNORECASE` on `AADSTS\d+` looks harmless and is not: it lets ordinary prose that happens to contain those letters route a user to a specific, confident, wrong sentence. It is pinned by `test_a_lowercase_prefix_is_not_a_code` with the reason in a comment on the pattern itself, because this is exactly the sort of thing a later reader "cleans up".

## Requirements

`AUTH-18` is the requirement this plan exists for, and it is **delivered but not fully verified**. Everything mechanically checkable about it is green: the code is extracted rather than the paragraph rendered, thirteen codes route distinctly, the administrator family is marked, the escape-hatch sentence exists and is appended to that family alone, and an unmapped code survives to the screen. What cannot be checked is whether a genuinely blocking tenant returns one of these thirteen codes, because the tenant hosting this registration permits the device authorization grant and no blocking response can be produced from it on demand. This is recorded as unverified (D-08), consistent with `docs/AZURE-REGISTRATION.md` and `03-03-SUMMARY.md`, and `ROADMAP_CANDIDATES` exists in the source so the acceptance record can say which candidate was actually observed.

`AUTH-05`, `AUTH-06`, `AUTH-21` and `AUTH-22` are **supplied, not satisfied**, by this plan. What they need from here is their copy, and it exists: the code heading and instruction (`AUTH-05`), the countdown, the expired state and the fresh-code action (`AUTH-06`), nothing typed on a remote — the account labels come from the identity token, and the label marking an account needing renewal is here (`AUTH-21`), and the re-authorise option and its list labels (`AUTH-22`). The screens that render them belong to later plans in this phase, and each of those plans also declares these ids, so the shared-id gate holds them open in `REQUIREMENTS.md` until the last declaring plan finishes. That is correct: a string in a catalogue nobody renders satisfies nothing.

## Known Stubs

None. No placeholder, TODO or hardcoded empty value was left in any file this plan created or modified. The twenty-three catalogue entries are unreferenced today by design — they exist so that the four plans that will reference them do not each have to move the partition gate — and the reachability assertion in `test_string_ids_partitioned` checks that every *referenced* id resolves, not that every declared id is referenced, so an unreferenced entry is legal and asserted to be so.

The five failing assertions in `tests/test_auth_gates.py` are unchanged from the baseline this plan inherited (139 passed, 5 failed, 1 skipped → 167 passed, 5 failed, 1 skipped). They are 03-03's red-by-construction gates with owners named in its Gate State table; none of them belongs to this plan and none was touched.

## Threat Flags

None. No new network endpoint, auth path, file access pattern or schema change. The four registered threats are addressed:

| Threat | Disposition | Where |
|---|---|---|
| T-03-21 | mitigated | Only the extracted code and a locally-authored sentence reach the screen. The provider's paragraph is consumed by `extract_code` and discarded; the module returns no field carrying it, so there is no route by which provider-controlled prose can be rendered |
| T-03-22 | mitigated | No outcome maps to advice involving a credential. `test_no_outcome_could_be_read_as_advice_to_add_a_credential` sweeps the shipped module for both parameter names, "add a secret" and "certificate"; string 30046 says explicitly that adding a secret will not help, and `docs/AZURE-REGISTRATION.md` section 4 says the same in bold |
| T-03-23 | mitigated | `test_the_unmapped_outcome_preserves_the_bare_code` — the bare code survives the fallthrough, and 30044 renders it |
| T-03-24 | mitigated | `admin_must_act` is `True` for exactly the six refusals no retry can clear, asserted as an exact set, so the renderer can withdraw the retry and offer 30045 instead |

One note for the plan that renders this table: `classify` returns the *bare provider code* in `Failure.code`, and 30044 substitutes it directly. That is deliberate (T-03-23) and it is the only provider-controlled value that reaches a screen anywhere in this design. It is constrained to `AADSTS` followed by digits by the pattern that produced it, so it carries no markup and no length a label cannot hold.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Ready. The plans that render this have what they need, and four things are worth carrying forward:

- **The renderer's contract is three fields.** `Failure(outcome, code, admin_must_act)`. Look the outcome up in the pairing table in the `.po` comment; always show `code`; and when `admin_must_act` is true, append 30045 and do not offer a retry.
- **`Failure.code` can be empty, and 30044 has a `%s` in it.** A description with no code at all classifies as unmapped with `code == ''`, and substituting that into "Sign-in failed. Error code: " reads badly. The renderer owns that case; this plan deliberately did not add a twenty-fourth string for it, because whether it reads better as a dash, as a different sentence or as the OAuth `error` value is a decision that belongs with the screen.
- **Two strings serve the expiry, on purpose.** 30039 is the dialog's expired state, which sits beside the 30040 button; 30058 is the `device_code_expired` outcome's sentence for a surface that has no button. They are not duplicates and merging them would couple the dialog's layout to the failure table.
- **The catalogue does not have to move again this phase.** 30059-30066 and 30070 upward are still free if a later plan needs a string nobody anticipated, but the gate's expected set has to move in that same commit — `tests/test_vendor_gates.py` line 437 and the count assertion below it, both of which now carry a comment saying so.

One constraint inherited and preserved: `resources/lib/auth/errors.py` runs on both Python 3.8 (Kodi 19-21) and 3.14 (Kodi 22), and uses nothing newer than 3.8 — `collections.namedtuple`, `re`, and percent formatting.

## Self-Check: PASSED

Both created files exist on disk (`resources/lib/auth/errors.py`, `tests/test_error_map.py`); both modified files are in the index; all three task commits (`bc13f94`, `1c12f54`, `083a248`) resolve in `git log`.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
