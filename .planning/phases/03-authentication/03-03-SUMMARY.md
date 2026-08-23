---
phase: 03-authentication
plan: 03
subsystem: testing
tags: [pytest, ast, static-gates, oauth2, device-code, entra-id, runbook, setup-04]

requires:
  - phase: 01-vendor-lift
    provides: "The gate conventions this phase inherits: read the git index rather than the filesystem, report path and line rather than a count, carry a non-vacuity guard on every sweep, and keep the exclusion set in one place"
  - phase: 03-authentication
    provides: "Plan 03-01's resources/lib/auth/ package, whose SCOPES constant the scope gate reads out of source"
provides:
  - "tests/gatelib.py — the one harness both gate files read: repository root, index-backed file list, text-file list, the single exclusion set, the pattern sweep and the path-and-line report"
  - "tests/test_auth_gates.py — nine named assertions covering every static claim this phase makes, four green and five red by construction with an owning plan named for each"
  - "docs/AZURE-REGISTRATION.md — how the app registration is configured, how to recreate it, and what to do when the tenant lapses"
  - "The fifth entry in EXCLUDED_DOCS, paid for by test_runbook_contains_aadsts7000218 in the vendor gate file"
affects: [03-04, 03-08, 03-09, 03-10, 03-11, 03-12, 03-13]

tech-stack:
  added: []
  patterns:
    - "One harness module, imported by every gate file, so the exclusion set cannot drift between them"
    - "An exclusion is paid for by a positive assertion that reads the excluded document by name"
    - "A gate is written before the thing it gates, red, with an owning plan named for each red assertion"

key-files:
  created:
    - tests/gatelib.py
    - tests/test_auth_gates.py
    - docs/AZURE-REGISTRATION.md
  modified:
    - tests/test_vendor_gates.py
    - README.md

key-decisions:
  - "The harness moved rather than being copied: a second gate file that reinvents the exclusion set gives two sets that drift, and a drifting exclusion set is how a gate stops checking anything without anybody noticing"
  - "The runbook is excluded from the literal sweeps and covered by a positive assertion instead of softening the credential pattern — narrowing the pattern weakens it everywhere, naming one document weakens it in one auditable place"
  - "The endpoint sweep matches on the whole parsed path, never a prefix: /me/ is one character away from /me/drives and is the call sign-in makes first, so a prefix test would miss the only failure that breaks sign-in outright"
  - "The service sweep forbids what waits for a person, not everything named Dialog: xbmcgui.Dialog is a handle rather than a window and DialogProgressBG cannot block, and forbidding either would make the gate permanently red instead of enforceable"
  - "The tenant-block requirement is recorded as unverified in the runbook and here, not claimed as passing: no tenant available to this project blocks device code flow"

patterns-established:
  - "Pattern 1: the exclusion set lives in tests/gatelib.py and nowhere else; every gate file reads it by import"
  - "Pattern 2: adding a row to EXCLUDED_DOCS requires adding a positive assertion that reads that document by name in the same commit"
  - "Pattern 3: an assertion whose name is used by a later plan's -k selector must resolve to exactly one test, so selector names are checked against the whole file before it is committed"
  - "Pattern 4: a red assertion is committed with an owning plan named in the summary — a red assertion with no owner is a gate nobody has agreed to satisfy"

requirements-completed: [SETUP-01, SETUP-02, SETUP-03, SETUP-04, AUTH-04, AUTH-14, AUTH-17, AUTH-18, AUTH-19, AUTH-23]

coverage:
  - id: D1
    description: "The gate harness lives in one module both gate files read, and the twenty-two existing vendor gates give the same verdict before and after the move"
    verification:
      - kind: unit
        ref: "python -m pytest tests/test_vendor_gates.py -q  (22 passed before, 22 identical node ids passed after)"
        status: pass
      - kind: unit
        ref: "cd /tmp && python -m pytest $REPO/tests/test_vendor_gates.py -q  (same verdict from another working directory)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The registration runbook is tracked outside the planning directory, linked from the README, and carries the AADSTS7000218 response verbatim with the instruction not to resolve it by adding a credential"
    requirement: "SETUP-04"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_runbook_contains_aadsts7000218"
        status: pass
      - kind: other
        ref: "git ls-files --error-unmatch docs/AZURE-REGISTRATION.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "The runbook is a recovery procedure for an outage that takes out the primary user, not documentation for strangers"
    requirement: "SETUP-04"
    verification: []
    human_judgment: true
    rationale: "Whether the document reads as a recovery procedure rather than a tutorial is a property of its prose. The gate can assert that the load-bearing values and the callout are present; it cannot assert that the framing is right, and the SETUP-04 prohibition is recorded as verification: judgment for that reason"
  - id: D4
    description: "The exclusion set still lives in exactly one place after a second gate file exists, and the fifth exclusion buys a positive assertion rather than a hole"
    requirement: "SETUP-03"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_runbook_contains_aadsts7000218"
        status: pass
      - kind: other
        ref: "gatelib.source_scan(r'client_secret|client_assertion') -> [] (the pattern is unchanged and still finds nothing outside the excluded document)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every static assertion this phase owes is named and collectible today; the four that can be green are, and the five red ones fail for their intended reason"
    requirement: "AUTH-04"
    verification:
      - kind: unit
        ref: "python -m pytest tests/test_auth_gates.py --collect-only -q  (9 collected)"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_scope_string_exact"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_no_forbidden_lock_primitives"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_service_never_opens_a_dialog"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_the_replaced_flow_is_named_in_the_two_excluded_documents"
        status: pass
    human_judgment: false
  - id: D6
    description: "The five red assertions (broker, expert-level setting, plugin dispatch, unanswerable endpoints, transport redaction) each fail for the reason they were written for, and each has an owning plan"
    requirement: "AUTH-23"
    verification:
      - kind: unit
        ref: "python -m pytest tests/test_auth_gates.py -q --tb=line  (5 failed, 4 passed; each failure lists the sites it found)"
        status: fail
    human_judgment: true
    rationale: "These are red on purpose. Their status is `fail` today and that is the correct state; they turn green as plans 03-08 through 03-12 land, and only the phase verification can judge whether each went green for the right reason rather than by being weakened"
  - id: D7
    description: "AUTH-18's tenant-block behaviour is recorded as unverified rather than claimed"
    requirement: "AUTH-18"
    verification: []
    human_judgment: true
    rationale: "The tenant hosting this registration permits device code flow, so a blocking response cannot be produced on demand. The runbook records the requirement as unverified with the reason; there is nothing to automate against"

duration: 30min
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 03: The Phase's Instrument and the Registration Runbook Summary

**One gate harness both files read, nine named auth assertions written before any of them is true — four green, five red with an owner each — and the recovery procedure for the one piece of this system that lives outside the repository.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-08-23T02:52Z
- **Completed:** 2026-08-23T03:22Z
- **Tasks:** 3 of 3
- **Files created:** 3
- **Files modified:** 2
- **Suite:** 81 passed, 5 failed by construction, 1 skipped, 1.5s

## Accomplishments

- **The exclusion set survived the arrival of a second gate file.** `tests/gatelib.py` now owns the repository root, the index-backed file list, the text-file list, the one exclusion set, the pattern sweep and the path-and-line report. The move was verified the only way it can be — the same twenty-two node ids collected in the same order and passed before and after, from the repository root and from another working directory — rather than reasoned about.
- **The registration can now be recreated from the repository.** `docs/AZURE-REGISTRATION.md` carries the exact manifest values, the recreation steps with both traps called out at the step where they bite, the Graph read-back request, the acceptance check, the identifier swap, the tenant-lapse plan and the explicit non-steps. It is a recovery procedure, not a tutorial: the tenant renews on activity, and if it lapses the embedded identifier dies for every installed copy on the same day, including the one on the owner's television.
- **The fifth exclusion buys a stronger gate.** The runbook must quote a response that names both credential parameters, so its path joined `EXCLUDED_DOCS` — and `test_runbook_contains_aadsts7000218` now reads it by name and asserts the quote, the do-not-add-a-secret instruction, the supported-account value, the public-client flag and the identifier. The credential pattern itself was not softened, so its strength everywhere else is unchanged; `gatelib.source_scan(r'client_secret|client_assertion')` still finds nothing outside that one named document.
- **Five of the nine auth assertions are red, and every one of them found real sites.** The broker sweep lists fourteen lines across five files plus the settings row and the manifest disclaimer. The endpoint sweep found `/me/` → `/me` at `onedrive.py:40` — the near-miss the whole design of that assertion exists to catch, and the call sign-in makes first. The redaction sweep found one of five fields covered and five report strings built from a raw request or response body.
- **Every `-k` selector a later plan already depends on resolves to exactly one test.** `forbidden`, `broker`, `redact`, `dispatch`, `service` and `client_id` were each run against the finished file before it was committed, because a selector that quietly picks up a second, red test turns a later plan's green verification into an unexplained failure.

## Gate State

Nine assertions in `tests/test_auth_gates.py`, plus the runbook assertion which the plan placed with the four existing document assertions in `tests/test_vendor_gates.py`.

| Assertion | File | State | Owner | What turns it green |
|---|---|---|---|---|
| `test_scope_string_exact` | auth | **green** | 03-01 (landed) | Already satisfied — `SCOPES` is the locked set |
| `test_no_forbidden_lock_primitives` | auth | **green** | 03-04 | Must stay green when `lock.py` lands; the point is that `fcntl`/`threading.Lock` cannot enter |
| `test_service_never_opens_a_dialog` | auth | **green** | 03-10 | Must stay green when `startup_refresh.py` joins the service closure |
| `test_the_replaced_flow_is_named_in_the_two_excluded_documents` | auth | **green** | 03-12 | Must stay green when README and VENDORED are rewritten |
| `test_runbook_contains_aadsts7000218` | vendor | **green** | 03-03 (this plan) | Satisfied here |
| `test_no_broker_references` | auth | **red** | 03-08 → 03-09 → 03-11 → **03-12** | All four: the code paths, the accessor, the settings row and the manifest disclaimer. Green only after the last |
| `test_custom_client_id_setting` | auth | **red** | **03-11** | The versioned schema plus the expert-level, empty-by-default identifier setting |
| `test_dispatch_uses_an_explicit_mapping` | auth | **red** | **03-09** | Replacing `getattr(self, self._action)` with a written-down mapping |
| `test_no_unanswerable_provider_endpoint` | auth | **red** | **03-08** | Dropping `/me/`, `/me/drives` and the bare `/drives` from the provider |
| `test_transport_report_redacts_credential_fields` | auth | **red** | 03-08 → **03-09** | 03-08 for the redactor and the transport's own report strings; 03-09 for the two error handlers |

Red assertions and the sites they name today:

```
test_no_broker_references
  addon.xml:55, settings.xml:21,
  remote/errorreport.py:37, remote/signin.py:42,60,66,
  ui/addon.py:190,201,203,629,645,646, ui/utils.py:204,205

test_no_unanswerable_provider_endpoint
  provider/onedrive.py:40  /me/       -> /me
  provider/onedrive.py:49  /drives    -> /drives
  provider/onedrive.py:62  /me/drives -> /me/drives

test_dispatch_uses_an_explicit_mapping
  ui/addon.py:700  getattr(...) on a value, not a literal

test_transport_report_redacts_credential_fields
  remote/request.py    covers access_token; refresh_token, id_token,
                       device_code and user_code are not named
  remote/request.py:142,178,190   raw body concatenated into a report
  remote/errorreport.py:73        raw body concatenated into a report
  ui/addon.py:665                 raw body concatenated into a report

test_custom_client_id_setting
  resources/settings.xml has no version attribute, so <level> is not
  expressible and no client identifier setting exists
```

## Task Commits

1. **Task 1: Move the gate harness into one module both gate files read** — `39b86d6` (refactor)
2. **Task 2: The registration runbook, its exclusion, and its compensating assertion** — `71188ec` (docs)
3. **Task 3: The auth gate file, red by construction, with an owner named for every assertion** — `bb635c4` (test)

## Files Created/Modified

- `tests/gatelib.py` — the shared harness: `REPO`, `tracked_files`, `text_files`, `read`, `excluded`, `source_scan`, `python_sources`, `report`, and the two exclusion sets with the comment explaining what each excluded document buys
- `tests/test_auth_gates.py` — nine assertions: the scope set, the forbidden lock primitives, the broker sweep, the compensating document assertion, the expert-level setting, the service dialog closure sweep, the plugin dispatch, the unanswerable endpoints and the transport redaction
- `docs/AZURE-REGISTRATION.md` — nine sections in the order the research names, plus the unverified tenant-block note
- `tests/test_vendor_gates.py` — harness removed and imported instead; `test_runbook_contains_aadsts7000218` added; the add-on-tree Python list kept because it has no second reader
- `README.md` — a maintainer-notes section linking the runbook

## Decisions Made

**The harness moved; it was not copied.** Phase 1's comment above the exclusion set says widening it is how a gate quietly stops checking anything. That comment is load-bearing for the row this plan added, so it travelled with the set rather than being restated. `read`, `report` and `excluded` are public in `gatelib` where they were `_read`, `_report` and `_excluded`; the vendor gate file aliases the first two on import, so not one call site changed and the diff stayed a move.

**The runbook's exclusion was paid for, not granted.** Finding C's collision has exactly one honest resolution: quote the error verbatim, exclude the one document that quotes it, and assert its contents positively. Softening the credential pattern to let the quote through would have weakened it in every file in the tree to solve a problem in one.

**`/me` is matched as a whole path.** The plan calls for three shapes and warns in the same breath that a prefix test written against `/me/drives` does not catch `/me/`. The sweep therefore normalises a complete literal path by stripping one trailing slash and compares it to a set of three values. A concatenated path such as `'/drives/' + driveid + '/items/'` is left alone: that is a per-item address, it is documented, and it answers under this scope set — treating its literal prefix as a collection call would have made the assertion unsatisfiable while pretending to be strict.

**The service sweep forbids waiting, not naming.** A rule that fails on "any construction of a dialog class" over the service's import closure is red forever: the export service constructs `DialogProgressBG`, the notification helper constructs `xbmcgui.Dialog()`, and the module that defines the dialog classes constructs them inside its own factories. So the rule is `doModal()`, plus any blocking `xbmcgui.Dialog` method called on anything named like a dialog, plus construction of any other dialog class — with `Dialog` and `DialogProgressBG` named as the two that open nothing and the definition module exempted behind a guard that asserts it really is the definition module.

**Test names were chosen against the selectors later plans already carry.** `test_no_unanswerable_provider_endpoint` deliberately avoids the word *forbidden* so that plan 03-04's `pytest -k forbidden` selects the lock sweep alone, and the compensating document assertion avoids the word *broker* so that 03-11's `-k broker` selects the sweep alone. All six selectors were run against the finished file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical] The service sweep needed a definition-module exemption and two named non-blocking constructions, or it could never go green**

- **Found during:** Task 3
- **Issue:** The plan asks the sweep to fail on "any construction of a dialog class or any call that opens one" over the service entry point's own-source import closure. Computed, that closure is 24 modules and includes `ui/dialog.py` (via `service/export.py`), which constructs `QRDialogProgress` in its own factory, builds `xbmcgui.Dialog()` in two `__init__`s and calls `doModal()` at line 377. It also includes `service/export.py`, which constructs `DialogProgressBG`, and `ui/utils.py`, which constructs `xbmcgui.Dialog()` to raise a notification — the one user-facing surface the research explicitly permits the service. Written literally, the assertion is permanently red, which is exactly the failure the plan's own truth 5 warns about for the broker sweep.
- **Fix:** The rule became: fail on `doModal()`; fail on any blocking `xbmcgui.Dialog` method (`ok`, `yesno`, `select`, `input`, `browse`, …, but not `notification`) called on any receiver whose name contains "dialog"; fail on construction of any other dialog-named class. `Dialog` and `DialogProgressBG` are named as the two constructions that open nothing, each with its reason. `ui/dialog.py` is exempt because a definition module names its own classes in its own factories and the decision to open one is made at the call site — every call site in the closure is in scope — and the exemption is guarded by an assertion that the file really does define dialog classes.
- **Files modified:** `tests/test_auth_gates.py`
- **Verification:** the assertion is green today, and `python -m pytest tests/test_auth_gates.py -q -k service` — the selector plan 03-10 uses — passes.
- **Committed in:** `bb635c4`

**2. [Rule 1 — Bug] The redaction sweep flagged `len(self.response_text)`, which discloses an integer**

- **Found during:** Task 3
- **Issue:** The raw-body half of the redaction assertion flagged `remote/request.py:176`, which builds a report from `self.response_code` and `len(self.response_text)`. Logging how many bytes came back is not logging the body, and demanding it be redacted would have asked plan 03-08 to hide a number.
- **Fix:** Attributes appearing only inside a `len(...)` call are excluded from the raw set, with the reason in a comment. The five genuine sites — one in `errorreport.py`, three in `request.py`, one in `ui/addon.py` — still report.
- **Files modified:** `tests/test_auth_gates.py`
- **Verification:** the sweep now lists exactly the five sites, each of which concatenates a body rather than a measurement.
- **Committed in:** `bb635c4`

**3. [Rule 3 — Blocking] The expert-level assertion cannot name a setting id that does not exist yet**

- **Found during:** Task 3
- **Issue:** Plan 03-11 adds the custom identifier setting but names no id, and 03-11's own `read_first` says the conversion "has to satisfy it exactly as written". Hard-coding a guess would make a later plan fail for a reason unrelated to its work.
- **Fix:** The assertion accepts any setting whose `id` contains `client_id` and requires that there be **exactly one** of them — which is also the stronger claim, since two escape hatches means one of them is the one nobody reads. `-k client_id`, the selector 03-11 uses, resolves to this test alone.
- **Files modified:** `tests/test_auth_gates.py`
- **Verification:** red today with the message naming the missing schema version, as intended.
- **Committed in:** `bb635c4`

---

**Total deviations:** 3 auto-fixed (2 × Rule 2/1 on assertion scope, 1 × Rule 3 on an unknowable identifier)
**Impact on plan:** None on shape or scope. All three are the same correction: an assertion that cannot be satisfied by the plan that owns it is not a strict gate, it is a broken one — the trade the plan itself makes for the broker sweep in truth 5 and Finding F.

## Issues Encountered

**Two sibling plans expect `-k broker` and `-k redact` to be green before anything can make them so.** Plan 03-08 verifies with `pytest tests/test_auth_gates.py -q -k "broker or redact"` and plan 03-09 does the same. Neither can pass at that point, and the reason is ordering rather than any defect in those plans:

- The broker sweep also reads `resources/settings.xml:21` (the `sign-in-server` row, removed by **03-11**) and `addon.xml:55` (the disclaimer linking the broker's source, rewritten by **03-12**). Neither file is in 03-08's or 03-09's `files_modified`.
- The redaction sweep also reads `ui/addon.py:665` and `errorreport.py:73`, both of which are **03-09**'s to fix, so 03-08 cannot turn it green alone either.

Recorded rather than worked around: the fix is for those plans to run the whole suite and read the named sites, not for this plan to weaken the sweeps so an intermediate state looks finished. The Gate State table above names the last owner for each.

**The plan places the runbook assertion in the vendor gate file; the research map places it in the auth one.** `03-RESEARCH.md`'s test map lists `tests/test_auth_gates.py::test_runbook_contains_aadsts7000218`, while the plan says it "belongs with the four existing document assertions" in `tests/test_vendor_gates.py` and instructs task 3 not to duplicate it. The plan was followed. The vendor gate file is where `EXCLUDED_DOCS` is paid for, and splitting that convention across two files is the drift this plan exists to prevent.

## Requirements

`SETUP-01`, `SETUP-02` and `SETUP-03` were already satisfied before Phase 1 and are now *documented*: the runbook's table is the manifest read-back written down, and `SETUP-03`'s "no secret anywhere in the repository" is now asserted by a sweep whose one exclusion is itself asserted. `SETUP-04` is delivered here.

`AUTH-04`, `AUTH-14`, `AUTH-17`, `AUTH-18`, `AUTH-19` and `AUTH-23` are **instrumented, not satisfied**, by this plan — with the exception of `AUTH-04`, which plan 03-01 satisfied and this plan now gates. Every one of them is also declared by a sibling plan that has not produced a summary yet, so the shared-id gate holds them open in `REQUIREMENTS.md` until the last declaring plan finishes. That is the correct behaviour and it is why nothing here flips them complete.

`AUTH-18` carries a permanent qualification: the tenant-block half cannot be verified from any tenant this project controls, and both the runbook and this summary record it as unverified rather than passing.

## Known Stubs

None. No placeholder, TODO or hardcoded empty value was left in any file this plan created. The five failing assertions are not stubs — they are complete assertions over a tree that has not caught up with them yet, which is the deliverable.

## Threat Flags

None. No new network endpoint, auth path, file access pattern or schema change. The six registered threats are addressed as follows:

| Threat | Disposition | Where |
|---|---|---|
| T-03-10 | mitigated | One named document excluded; the pattern unchanged; `test_runbook_contains_aadsts7000218` reads it by name |
| T-03-11 | mitigated | The runbook names public values only, and states rather than assumes that both credential collections are empty |
| T-03-12 | mitigated | `test_dispatch_uses_an_explicit_mapping` forbids the dynamic lookup and requires a non-empty written mapping |
| T-03-13 | mitigated | `test_transport_report_redacts_credential_fields` names all five fields and forbids a raw body reaching a report |
| T-03-14 | accepted | Runbook section 1 states plainly that the identifier is public and carries no secret |
| T-03-15 | transferred | Recorded as unverified in the runbook and in this summary |

## User Setup Required

None for this plan. The registration it documents already exists and works; `docs/AZURE-REGISTRATION.md` is the procedure for the day it does not.

## Next Phase Readiness

Ready. The instrument is in place before the phase changes anything, which was the point.

- **Every later plan in this phase has a gate waiting for it.** The Gate State table names the owner. A plan that lands its work and leaves its assertion red has not finished.
- **`tests/gatelib.py` is the only place an exclusion may be added.** Plans 03-05 and 03-11 both modify `tests/test_vendor_gates.py`; neither needs to touch the harness, and if either finds it does, that is a signal worth stopping for.
- **`tests/test_auth_gates.py` is written once and is not edited again by any later plan in this phase.** That constraint is what let phase 1's plans run without contending for the gate file. A plan that finds itself wanting to change an assertion rather than satisfy it should raise it rather than edit it.
- **Two ordering facts to carry forward,** both in Issues Encountered above: the broker sweep goes green only after 03-12, and the redaction sweep only after 03-09.

## Self-Check: PASSED

All three created files exist on disk (`tests/gatelib.py`, `tests/test_auth_gates.py`, `docs/AZURE-REGISTRATION.md`); both modified files are in the index; all three task commits (`39b86d6`, `71188ec`, `bb635c4`) resolve in `git log`.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
