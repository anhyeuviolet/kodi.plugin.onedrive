---
phase: 03-authentication
plan: 09
subsystem: auth
tags: [account-list, re-authorisation, plugin-router, allow-list, error-rendering, redaction, broker-removal, python38]

requires:
  - phase: 03-authentication
    provides: "Plan 03-08's sign-in flow, account identity from the token, Provider.save_tokens and ReauthorisationRequired — this plan reuses the exchange for re-authorisation and gives that exception its first branch"
  - phase: 03-authentication
    provides: "Plan 03-05's errors.classify / classify_response and the 30044-30058 catalogue — the outcome vocabulary this plan finally renders"
  - phase: 03-authentication
    provides: "Plan 03-04's store.remove_account, which already deleted both of an account's files and had no caller until now"
  - phase: 03-authentication
    provides: "Plan 03-03's tests/gatelib.py and the two red assertions this plan owns"
provides:
  - "CloudDriveAddon._action_map — fourteen name-to-method pairs, plus _dialog_smoke from the OneDrive subclass; the router's only way to reach a method"
  - "CloudDriveAddon._reauthorise_account — the same device-code exchange keyed to an existing account, one token write, one record write, the record last"
  - "CloudDriveAddon.NEEDS_REAUTH_KEY = 'needs_reauth' — the account-record key plan 03-10's service writes and this list reads. The only coupling between them"
  - "CloudDriveAddon._released_the_handle / _signin_request_params / _acquire_tokens / _identify — the sign-in flow split so both handlers share it"
  - "CloudDriveAddon._FAILURE_STRINGS / _provider_failure / _failure_sentence — the second half of the outcome-to-sentence join 03-05 left open"
  - "KodiUtils.ADDON_STRING_FLOOR = 30000 — the catalogue boundary, asserted against the same partition set the catalogue is"
  - "tests/test_auth_gates.py — six new assertions: the derived action sweep, the affordance, the mapped-method existence check, removal-takes-the-credential, re-authorisation's single write, and the outcome-to-sentence join"
  - "tests/test_vendor_gates.py::test_localize_owns_this_addons_block"
affects: [03-10, 03-11, 03-12, 03-13, 03-14]

tech-stack:
  added: []
  patterns:
    - "An untrusted string selects an entry in a table somebody wrote down, never an attribute on an object. A stop-list is refused explicitly and the reason is in the source: the namespace a stop-list filters grows with every method added, and a mapping does not"
    - "The expected set of a sweep is derived from the tree on every run, so adding a call site cannot quietly add an unchecked one"
    - "A join between two files that name nothing of each other's contents is held by an assertion, or it is not held"
    - "Deleting apparently-dead code carries the measurement that makes it unreachable, in the commit body, rather than the word waste"
    - "A mutation harness restores from a copy it holds; and nothing else restores the working tree while uncommitted work is in it"

key-files:
  created:
    - .planning/phases/03-authentication/deferred-items.md
  modified:
    - resources/lib/vendor/clouddrive_common/ui/addon.py
    - resources/lib/vendor/clouddrive_common/ui/utils.py
    - resources/lib/addon.py
    - resources/lib/vendor/clouddrive_common/export.py
    - resources/lib/vendor/clouddrive_common/service/download.py
    - resources/lib/vendor/clouddrive_common/service/export.py
    - resources/lib/vendor/clouddrive_common/service/player.py
    - resources/lib/vendor/clouddrive_common/service/source.py
    - resources/language/resource.language.en_gb/strings.po
    - tests/test_auth_gates.py
    - tests/test_vendor_gates.py
  deleted:
    - resources/lib/vendor/clouddrive_common/remote/errorreport.py

key-decisions:
  - "The action mapping's keys are derived by a sweep over the tree, not written from memory, and the sweep also refuses an entry that routes a name to a differently-named method — aliasing belongs in _rename_action, where it is one readable table, and an alias hidden inside the mapping is how a mapping stops being the list somebody wrote down"
  - "_dialog_smoke stays in the mapping and has an assertion holding it there. It is temporary, it looks exactly like something to tidy away, and it is the only route to all three dialogs; removing it would fail nothing and would make the television acceptance pass produce a green that meant nothing"
  - "_open_common_settings is deliberately unmapped rather than deleted. Nothing constructs an address for it and the vendor gates already assert no settings row does; deleting a method from the vendored tree is 03-12's kind of change, and the modification record is that plan's file"
  - "Re-authorisation keeps the stored drives rather than fetching them again. The drive id is what every list row and every stored export references, and refetching it to arrive at the same value only adds a request that can fail"
  - "A re-authorisation that signs in as a different account writes nothing and says so, which needed one new string. Writing the blob against the record the user chose would bind one person's credential to another person's row -- silently, on a device more than one person uses, with every request afterwards reading the wrong drive under the right label"
  - "The failure handler's redaction pass is a second pass over reports the transport already redacted, and that is not theatre: this handler is reachable with a RequestException any caller can construct, and the redactor at the point of writing is the one place that covers those too"
  - "ReauthorisationRequired was given a branch it never had. It reached no branch at all and fell through to the generic error dialog, which is the one message that does not offer the one action that helps. A transient refresh failure still raises a plain RequestException and reaches none of this -- that distinction is the whole of Pitfall E"
  - "The error reporter's six call sites in five other modules were rewritten to log a stack trace. That is not a widening of scope: deleting the module without them would stop the export subsystem and both service listeners from importing at all"
  - "KodiUtils.localize's catalogue boundary moved from 32000 to 30000 and is now asserted against ADDON_STRING_IDS. No shipped caller is affected today; this closes a latent fault rather than fixing a visible one"

patterns-established:
  - "Pattern 1: a sweep that reads a construct out of source reads every syntactic shape that construct can take, or it can be stepped around by changing syntax rather than by changing behaviour"
  - "Pattern 2: a first draft of an assertion is mutation-checked against the specific omission it exists to catch, not only against the construct disappearing entirely — the account-list assertion passed its first mutation and was rewritten"
  - "Pattern 3: no blanket working-tree restore while uncommitted work is present, and a mutation harness asserts its own restore rather than trusting it"

requirements-completed: []

coverage:
  - id: D1
    description: "An action named in a plugin address is looked up in an explicit mapping; no dynamic attribute lookup survives in the router"
    requirement: "AUTH-22"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_dispatch_uses_an_explicit_mapping"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_every_constructed_action_is_routable"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_every_mapped_action_names_a_method_that_exists"
        status: pass
    human_judgment: false
  - id: D2
    description: "The temporary dialog affordance stays reachable through the mapping"
    requirement: "AUTH-22"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_the_dialog_affordance_stays_routable"
        status: pass
    human_judgment: false
  - id: D3
    description: "The account list carries a per-row menu offering search, re-authorise and remove"
    requirement: "AUTH-22"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_the_account_list_offers_re_authorisation"
        status: pass
      - kind: manual
        ref: "deferred to plan 03-14 on the television; the list has not been rendered by Kodi in this shape"
        status: deferred
    human_judgment: true
    rationale: "Whether three options read as three options on a television, navigated with a remote from a sofa, is a property of doing it. The static assertion proves the menu is built and the action is reachable; it cannot prove the row is legible or the menu operable"
  - id: D4
    description: "Re-authorisation replaces a token blob in place: one save_tokens, one save_account, the record written last, no second record"
    requirement: "AUTH-22"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_reauthorisation_replaces_a_blob_without_a_second_record"
        status: pass
      - kind: manual
        ref: "deferred to 03-13/03-14; no account has been re-authorised against the live provider"
        status: deferred
    human_judgment: true
    rationale: "The write structure is asserted statically, which is what makes cancel-safety structural. That the exchange actually returns a usable blob for an account that already exists is a live-provider fact"
  - id: D5
    description: "Removing an account removes its token file and its lock file alongside the record"
    requirement: "AUTH-20"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_removing_an_account_deletes_its_stored_credential"
        status: pass
      - kind: unit
        ref: "tests/test_token_store.py — store.remove_account's own tests, which 03-04 wrote and which this plan is the first caller of"
        status: pass
    human_judgment: false
  - id: D6
    description: "The per-drive removal option and its handler are gone from shipped source"
    requirement: "AUTH-22"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_the_per_drive_removal_path_is_gone"
        status: pass
    human_judgment: false
  - id: D7
    description: "A provider failure renders the sentence its code maps to; an unmapped one renders a generic sentence that still shows the bare code; the administrator family gets the escape hatch appended"
    requirement: "AUTH-18"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_every_failure_outcome_renders_its_own_sentence"
        status: pass
      - kind: manual
        ref: "no live refusal has been produced; the tenant hosting this registration permits the device authorization grant"
        status: deferred
    human_judgment: true
    rationale: "Same limit 03-05 recorded (D-08). What is proven is that every outcome the table can return has its own sentence, that the unmapped fallthrough keeps the bare code, that no id is missing from the catalogue and that no two outcomes render identically. Which code a genuinely blocking tenant returns, and whether the sentence reads right at three metres, are both still open"
  - id: D8
    description: "No raw request or response body is concatenated into a report that goes to the log"
    requirement: "AUTH-23"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_transport_report_redacts_credential_fields"
        status: pass
      - kind: other
        ref: "mutation: restoring the raw concatenation turns the sweep red"
        status: pass
    human_judgment: false
  - id: D9
    description: "Third-party error reporting, the prompt inviting it, and the accessor supplying its address are deleted"
    requirement: "KODI-08"
    verification:
      - kind: other
        ref: "git ls-files resources/lib/vendor/clouddrive_common/remote/errorreport.py is empty; no shipped module names ErrorReport or the accessor"
        status: pass
      - kind: unit
        ref: "tests/test_auth_gates.py::test_no_broker_references — this plan's three sites cleared; two remain, owned by 03-11 and 03-12"
        status: partial
    human_judgment: false
  - id: D10
    description: "An account marked as needing re-authorisation is labelled distinctly and its default action is signing in again"
    requirement: "AUTH-17"
    verification:
      - kind: manual
        ref: "deferred to 03-10 (which writes the marker) and 03-14 (which sees the row). Nothing writes the marker yet, so no row has ever rendered in this state"
        status: deferred
    human_judgment: true
    rationale: "The reader exists and the key is named; the writer is 03-10's. This is the single largest unverified thing this plan produced and it is recorded as such rather than claimed"

duration: 3h22m
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 09: The Account List, the Router, and the Last of the Third Party Summary

**A plugin address can no longer name an arbitrary method, an account can be signed in again or
removed completely, a provider refusal says what actually happened, and the log no longer carries
credentials — the error reporter deleted rather than disabled.**

## Performance

- **Duration:** 3 h 22 min
- **Tasks:** 3 of 3
- **Files created:** 1 (a deferred-items record)
- **Files modified:** 11
- **Files deleted:** 1
- **Suite:** 206 passed / 4 failed / 1 skipped → **217 passed / 2 failed / 1 skipped**

## Accomplishments

**A plugin address selects an entry in a table, not an attribute on an object.** The router called
`getattr(self, self._action)` where `self._action` came straight out of a `plugin://` address — and
such an address is constructible by a favourite, a stored playlist entry, a keymap or another
installed add-on, with nothing on this side able to tell which. The address therefore chose which
method ran out of everything the class and its bases happened to define, private helpers included.
`_action_map()` is fourteen name-to-method pairs plus `_dialog_smoke` from the subclass; an unmapped
name raises and takes the add-on's ordinary failure path.

**The mapping's coverage is derived, not recalled.** `test_every_constructed_action_is_routable`
sweeps dict literals with an `action` key, assignments into an existing params dict, and the whole
`plugin://` addresses in `settings.xml`, and asserts each name it finds is either mapped or rewritten
by `_rename_action`. Fourteen distinct names on this run, against a non-vacuity floor of ten. It also
refuses an entry that routes a name to a differently-named method: aliasing lives in
`_rename_action`, and an alias hidden inside the mapping is how a mapping stops being the list
somebody wrote down.

**A stop-list was refused, in the source, with the reason.** The namespace a stop-list filters grows
every time somebody adds a method — each addition silently gains an entry point, and nobody reviewing
that addition is looking at the router. The mapping gains nothing when a method is added. That
asymmetry is the whole argument and it is written where the next person to consider a stop-list will
read it.

**Re-authorisation exists and writes once.** The same device-code exchange, keyed to the account that
already exists: `save_tokens` once, `save_account` once, the record last, so a cancel anywhere above
leaves nothing behind. The needs-re-authorisation marker is cleared as part of the record assembled
in memory. The stored drives are kept rather than fetched again, because the drive id is what every
list row and every stored export references.

**The stale-credential row is the background service's only channel to a user.** The service runs at
Kodi start with nobody in front of the television and may not prompt; it writes `needs_reauth` and
stops. The list renders that account with a distinct label and points its default action at signing
in again rather than at browsing — browsing would make its first request with the credential that
already failed and show a network error instead of the one thing that fixes it.

**Removal takes the credential with it.** `store.remove_account` deletes the token file and the lock
file alongside the record. 03-04 wrote that function with the reasoning already in its docstring and
it had no caller until now.

**The per-drive removal option is gone, with the measurement rather than the word waste.**
`GET /me/drive` answers with the default drive and only that; `GET /me/drives` is 403 accessDenied
for personal accounts; `GET /drives` is 403 on both classes and is not a v1.0 endpoint at all. So an
account carries exactly one drive and the `len(drives) > 1` branch can never be taken. The matrix is
in the commit body and the comment left in the file names what to restore if the deferred
document-library work brings drive selection back.

**Thirteen provider outcomes render thirteen sentences.** `_FAILURE_STRINGS` is the second half of the
join 03-05 left open — that module returns a symbolic outcome and a bare code and holds no words at
all. The escape hatch is appended to the outcomes marked administrator-must-act and to nothing else.
An unmapped refusal still shows its bare code. The provider's own description never reaches the
screen.

**The credential leak is closed.** What stood in the failure handler concatenated the request and the
response straight into a string bound for a log file users paste into public forums verbatim, and a
failing token exchange answers with a body that *is* the credential.

**The third party is out of this file entirely.** The branch that read its address out of a request is
gone; the unauthorised half survives and now sits beside `ReauthorisationRequired`, which previously
reached no branch at all. The reporter is deleted rather than disabled, together with the prompt that
invited it and the two stored answers, and the accessor that supplied its address is deleted from the
utilities module.

## Task Commits

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | RED — every constructed action is routable | `a2eaa2e` | `tests/test_auth_gates.py` |
| 1 | GREEN — the explicit action mapping | `79f9ae3` | `ui/addon.py`, `resources/lib/addon.py`, `tests/test_auth_gates.py` |
| 2 | RED — re-authorisation and complete removal | `9026a7a` | `tests/test_auth_gates.py` |
| 2 | GREEN — the account list, re-authorise, the stale row | `82595e7` | `ui/addon.py`, `strings.po`, `tests/test_auth_gates.py`, `tests/test_vendor_gates.py` |
| 3 | RED — every outcome renders its own sentence | `7ed7ee2` | `tests/test_auth_gates.py` |
| 3 | GREEN — failure rendering, redaction, the reporter deleted | `356de0d` | `ui/addon.py`, `ui/utils.py`, `errorreport.py` (deleted), `export.py`, `service/{download,export,player,source}.py` |
| — | The catalogue boundary (known defect 2) | `c3a1445` | `ui/utils.py`, `tests/test_vendor_gates.py` |

## Gate State After This Plan

Baseline inherited: **206 passed, 4 failed, 1 skipped.** Now: **217 passed, 2 failed, 1 skipped.**
Both assertions this plan owned are green; both that remain red belong to later plans and neither was
touched.

| Assertion | State | Sites this plan cleared | Sites remaining, and whose |
|---|---|---|---|
| `test_dispatch_uses_an_explicit_mapping` | **green** | the router's `getattr(self, self._action)` | none |
| `test_transport_report_redacts_credential_fields` | **green** | `errorreport.py:73` (file deleted), `ui/addon.py:665` | none |
| `test_no_broker_references` | red | `errorreport.py:37` (file deleted), `ui/utils.py:204-205`, `ui/addon.py:788` | `settings.xml:21` — **03-11**; `addon.xml:55` — **03-12** |
| `test_custom_client_id_setting` | red | none — not this plan's | the versioned schema and the expert-level setting — **03-11** |

Six assertions were added and are green: `test_every_constructed_action_is_routable`,
`test_the_dialog_affordance_stays_routable`, `test_every_mapped_action_names_a_method_that_exists`,
`test_removing_an_account_deletes_its_stored_credential`,
`test_the_per_drive_removal_path_is_gone`,
`test_reauthorisation_replaces_a_blob_without_a_second_record`,
`test_the_account_list_offers_re_authorisation` and
`test_every_failure_outcome_renders_its_own_sentence` in `tests/test_auth_gates.py`, and
`test_localize_owns_this_addons_block` in `tests/test_vendor_gates.py`.

**No sweep was weakened.** One sweep was *widened*: `_action_map_entries` was extended to read
subscript assignments as well as dict literals, after the first version let the subclass's entry hide
behind a change of syntax. One assertion was *rewritten stronger*: the first draft of
`test_the_account_list_offers_re_authorisation` checked only that `list_accounts` named the action
somewhere, and its mutation — deleting the menu entry while leaving the stale row's address — passed
it. It now reads the `context_options.append` calls specifically.

**Every gate this plan added was mutation-checked**: five mutations for the mapping, four for the
account list, six for the rendering and redaction, two for the catalogue boundary. Seventeen
mutations, each caught, each restored from a copy the harness held, with the restore asserted rather
than assumed.

## Vendored Tree Changes (input for 03-12's modification record)

| File | Change |
|---|---|
| `remote/errorreport.py` | **Deleted.** 84 lines. `send_report` posted a stack trace to the hosted third party; `handle_exception` assembled the same report with the raw response body appended and sent it |
| `ui/addon.py` | `_action_map` added and the dynamic lookup removed from `route`; `NEEDS_REAUTH_KEY`, `_needs_reauthorisation`, `_released_the_handle`, `_signin_request_params`, `_acquire_tokens`, `_identify`, `_reauthorise_account`, `_provider_failure`, `_failure_sentence`, `_offer_signin_again` and `_FAILURE_STRINGS` added; `list_accounts` rewritten; `_remove_drive` deleted; `_remove_account` extended to the token store; the reporting prompt and `ErrorReport.send_report` call deleted; the report's raw-body concatenation routed through the transport's redactor; `import json`, `from resources.lib import auth_context`, `store`, `ReauthorisationRequired` and `Request` imports added, `ErrorReport` import removed |
| `ui/utils.py` | The hosted-address accessor deleted; `ADDON_STRING_FLOOR = 30000` added and `localize`'s boundary moved onto it |
| `export.py` | `ErrorReport` import replaced with `ExceptionUtils`; two call sites log a stack trace instead of sending one |
| `service/download.py` | `ErrorReport` import removed; one call site logs |
| `service/export.py` | `ErrorReport` import replaced with `ExceptionUtils`; three call sites log |
| `service/player.py` | The local `ErrorReport` import replaced with a local `ExceptionUtils` import; one call site logs the full stack trace rather than the bare exception |
| `service/source.py` | `ErrorReport` import removed; one call site logs |

`resources/lib/addon.py` is this repository's own file, not vendored: `_action_map` was overridden
there to add `_dialog_smoke`.

## Decisions Made

**The mapping is a plain name-to-method table and the sweep enforces that it stays one.** An entry
whose key differs from its method's name turns the assertion red. The three friendly names
(`open_folder`, `open_drive`, `open_drive_folder`) stay in `_rename_action`, which runs first, exactly
as it did before the lookup. One table for routing and one for aliasing, each readable on its own.

**`_open_common_settings` is unmapped rather than deleted.** Nothing constructs an address for it and
`test_vendor_gates` already asserts no settings row does, because the separate module whose settings
it opened no longer exists. Leaving it out of the mapping makes it unreachable, which is what the
vendor gate wants; deleting a method from the vendored tree is 03-12's kind of change and the
modification record is that plan's file.

**Re-authorisation keeps the stored drives.** The drive id is the key every list row and every stored
export references. Refetching it to arrive at the same value adds a request that can fail during the
one operation the user performed because something already failed.

**A different account signing in writes nothing.** This needed one new string, 30059. The alternative
— writing the blob against the record the user chose — binds one person's credential to another
person's row, silently, on a device more than one person uses, with every request afterwards reading
the wrong drive under the right label. It is the sort of failure nobody would ever trace back to the
button they pressed. 03-05 explicitly left 30059-30066 free for "a string nobody anticipated" with the
rule that the gate's expected set moves in the same commit; it did.

**The redaction pass in the failure handler is a second pass, and that is stated in the source.**
`rex.request` and `rex.response` are the transport's own reports and already went through
`get_body_for_report` at their source. Running them through it again is idempotent — a value already
cut to eight characters plus a marker comes back unchanged — and it is not theatre, because
`_handle_exception` is reachable with a `RequestException` any caller can construct, and a redactor at
the point of writing is the one place that covers those. `Provider.refresh_access_tokens` raises
exactly such a hand-built exception.

**`ReauthorisationRequired` got the branch it never had.** 03-08 introduced it and nothing in
`_handle_exception` looked for it, so it fell to the generic error dialog — the one message that does
not offer the one action that helps. It now shares a branch with the 401, since both mean the same
thing to the person in front of the television. A transient refresh failure still raises a plain
`RequestException` and reaches none of it: that distinction is the whole of Pitfall E, and a refresh
that failed because the Wi-Fi was not up yet must not sign anybody out.

**The reporter's other call sites were rewritten rather than left broken.** Five modules outside this
plan's stated files imported `ErrorReport` and called `handle_exception` at six places. Deleting the
module without them would have stopped the export subsystem and both service listeners from importing
at all. Each now calls `Logger.error(ExceptionUtils.full_stacktrace(e))` — the logging half of what the
reporter did, without the sending half or the raw response body it appended.

**The catalogue boundary was fixed rather than worked around again.** See deviation 4.

## Deviations from Plan

### 1. [Rule 3 — Blocking] The error reporter had six call sites in five other modules

- **Found during:** Task 3.
- **Issue:** the plan lists three files. `export.py`, `service/download.py`, `service/export.py`,
  `service/player.py` and `service/source.py` all import `ErrorReport` and call
  `ErrorReport.handle_exception(e)` — six sites. Deleting the module with those in place would break
  the import of the export subsystem and both service listeners outright.
- **Fix:** each site now logs the full stack trace. `ExceptionUtils` was added to the imports of the
  three files that lacked it; `service/player.py` keeps its local import, and now also logs the whole
  stack trace where it previously logged the bare exception and then handed it to the reporter.
- **Files modified:** the five listed above.
- **Verification:** `python -m compileall -q resources/ entrypoint.py service.py` clean; no shipped
  module names `ErrorReport`.
- **Committed in:** `356de0d`.

### 2. [Rule 2 — Missing critical functionality] Re-authorising as a different account

- **Found during:** Task 2.
- **Issue:** the plan says re-authorisation replaces the token blob for the existing account. Nothing
  guarantees the person signs into the same account on their phone. Writing the returned blob against
  the chosen record binds one identity's credential to another identity's row: every request
  afterwards reads the wrong drive under the right label, with no error and nothing in the log to
  connect it to the button that was pressed. On a family television this is not a corner case.
- **Fix:** the identity is read from the token that just arrived and compared with the record's key.
  On a mismatch nothing is written and string 30059 names the account that actually signed in.
- **Files modified:** `ui/addon.py`, `strings.po`, `tests/test_vendor_gates.py`.
- **Verification:** the write is unreachable on the mismatch path by construction — the comparison
  returns before the record is assembled.
- **Committed in:** `82595e7`.

### 3. [Rule 2 — Missing critical functionality] `ReauthorisationRequired` reached no branch

- **Found during:** Task 3, while removing the third party's half of the 401 test.
- **Issue:** 03-08 added the exception and named it in its handover notes; `_handle_exception` never
  looked for it. A refresh whose grant is finished produced the generic error dialog and no offer to
  sign in again — which defeats the point of having drawn the distinction at all.
- **Fix:** `_offer_signin_again` handles the 401 and this exception together and is the only place
  either leads to a prompt. A transient failure raises `RequestException` and reaches neither.
- **Files modified:** `ui/addon.py`.
- **Committed in:** `356de0d`.

### 4. [Rule 1 — Bug] `KodiUtils.localize` sent this add-on's own ids to Kodi's catalogue

- **Found during:** Task 3 (carried in as a known defect; a fix was invited if feasible).
- **Issue:** the boundary was `string_id < 32000`, right while the only add-on ids in the tree were
  the vendored module's 32000-32088 and wrong from the moment phase 1 renumbered this add-on's own
  strings into the 30000 block. Wrong *silently*: `localize(30042)` returned Kodi's string 30042 —
  a different sentence, on a television, with nothing raised and nothing logged.
- **Fix:** `ADDON_STRING_FLOOR = 30000`, and `test_localize_owns_this_addons_block` asserts the
  constant against the same `ADDON_STRING_IDS` set the catalogue partition is asserted against, and
  asserts the comparison actually reads it.
- **Feasibility, since the prompt asked either way:** yes, and cheaply. Every id reaching this helper
  today is 1210, 12021, 21479 or a module id at or above 32000, all of which resolve identically on
  either side of the change, so this closes a latent fault rather than fixing a visible one. 03-06's
  `_addon_string` stays: going through the add-on directly is clearer at a call site than a helper
  that has to infer which catalogue was meant.
- **Committed in:** `c3a1445`.

### 5. [Process] A blanket `git checkout` destroyed Task 2's uncommitted work

- **Found during:** Task 2, immediately after the mutation run.
- **Issue:** the mutation harness restored `ui/addon.py` correctly from the pristine copy it held.
  `git status` then showed the file modified — line endings only, LF against the index's CRLF — and a
  `git checkout --` was run to tidy that. The index was at the Task 1 commit, so it reverted every
  uncommitted Task 2 edit in that file.
- **Fix:** the edits were retyped from context, the diff reviewed line by line before committing, and
  the full suite plus `compileall` re-run. Nothing was lost.
- **Why it is recorded:** this is the mirror of what 03-05 found. 03-05's harness restored *from* the
  index and silently did nothing; this one restored correctly and then the index was used to
  "clean up" over the top. Both failures are the same mistake — treating the index as the authority
  on a working tree that is ahead of it. The rule taken from it, and now in this plan's
  patterns-established: commit before mutating, never run a blanket restore while uncommitted work is
  present, and have the harness assert its own restore. `mutate3.py` and `mutate4.py` do.

### 6. [Scope] A gate assertion was rewritten after its own mutation passed

- **Found during:** Task 2's mutation run.
- **Issue:** `test_the_account_list_offers_re_authorisation` originally checked that `list_accounts`
  contained the string `_reauthorise_account` anywhere. Deleting the context-menu entry — the exact
  omission it exists to catch — left the stale row's address behind, so the assertion stayed green.
- **Fix:** it now finds the `context_options.append` calls inside `list_accounts` and requires one of
  them to be the re-authorise entry, and reports the menu it did find when it fails.
- **Why it is recorded:** a first draft of an assertion has to be mutation-checked against the
  specific omission it is aimed at, not only against the construct vanishing entirely. That is now
  Pattern 2.

### 7. [Scope] One new string, and the partition gate widened with it

- **Found during:** Task 2. See decision "A different account signing in writes nothing".
- 30059 added, `ADDON_STRING_IDS` widened from `range(30036, 30059)` to `range(30036, 30060)` and the
  count assertion 48 → 49, all in the same commit, which is the rule 03-05 wrote into that gate's
  comment. `03-11` also edits this gate; it will read it as it finds it.

---

**Total deviations:** 7 (1 × Rule 1, 2 × Rule 2, 1 × Rule 3, 1 process, 2 scope)
**Impact on plan:** none on shape or scope. Deviations 1-3 are work the plan implied but did not
enumerate; 4 is a known defect closed with the fix the prompt invited; 5 is a self-inflicted error,
recovered in full and written down because the lesson generalises; 6 and 7 are the instrument being
made honest.

## Issues Encountered

**A first-draft assertion can pass the mutation it exists to catch.** Recorded above as deviation 6.
The general shape: an assertion written as "the source mentions X" is satisfied by any mention,
including ones that are not the thing being asserted. Mutation-checking is what surfaced it, and only
because the mutation was chosen to be the realistic omission rather than a deletion of the whole
construct.

**A comment naming a removed construct puts it back into the sweep.** The first draft of the comment
left where the hosted-address accessor stood named the accessor. `test_no_broker_references` reads
shipped source for exactly that literal, so the comment reintroduced a site the same commit had
removed. Reworded to describe it without naming it, with a pointer to `VENDORED.md`, which is excluded
from the sweep precisely so it can carry the history. Worth carrying forward: in this repository, a
comment is shipped source and a sweep does not know the difference between a use and an epitaph.

**`tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write` failed once,
on a loaded machine.** Two real threads through a `threading.Barrier` with a five-second `acquire`
timeout; the failing run took 7.98 s against a usual 3.2 s. Five runs of the test alone and three full
suites passed afterwards. Not caused by this plan, not touched, logged in `deferred-items.md`.

## Requirements

**No requirement mark was made or changed.** `git diff --stat -- .planning/REQUIREMENTS.md` is empty
across all seven commits. This plan declares seven ids and completes none of them. Checked one by one
against the later plans in this phase, per the shared-id rule 03-05 found and every plan since has
enforced by hand:

| Id | Later declaring plan(s) | Why it is not complete here |
|---|---|---|
| AUTH-17 | 03-10, 03-14 | The *reader* of the marker is here. Nothing writes it yet — that is 03-10 — so no row has ever rendered in this state, and 03-14 is where somebody sees it |
| AUTH-18 | 03-11, 03-13 | Every outcome now renders its own sentence. 03-11 owns the expert-level setting the escape-hatch sentence points at, and no live refusal has been produced |
| AUTH-20 | 03-10 | Already `Complete`, marked earlier. This plan makes removal take both files; the mark was not touched |
| AUTH-21 | 03-13 | Already `Complete`. The re-authorise labels come from the catalogue and no account name is typed; 03-13 still declares it |
| AUTH-22 | 03-14 | The list has the three options and the router reaches them. Whether it reads as an account list a person can operate with a remote is 03-14's, on the television |
| AUTH-23 | 03-11, 03-12 | Three of the five remaining sites cleared. Green only after 03-12 |
| KODI-08 | **none** | See below |

**KODI-08 is the one no later plan declares, and it is still not complete.** It reads: *"Third-party
error reporting code and the `report_error` setting are deleted; errors go to `kodi.log` only."* The
code is deleted, the prompt is deleted, the accessor is deleted, and errors now go to `kodi.log` and
nowhere else. **The `report_error` settings row survives**, in `resources/settings.xml`, because that
file belongs to `03-11` and its Task 1 names those rows explicitly as "the two rows being removed".
Ticking KODI-08 here would record as done a requirement whose own text names a thing still in the
tree — and because no later plan declares the id, the shared-id gate would not have caught it. This is
the exact failure mode 03-05's deviation 4 found; it is recorded here so `03-11` knows the mark is
waiting for it, since nothing in the tooling will tell it.

## Known Stubs

None. No placeholder, `TODO`, `FIXME` or hardcoded empty value was left in any file this plan touched.

Three things that read like omissions and are not, each recorded so nobody has to reconstruct the
reasoning:

- **`_open_common_settings` is defined and unmapped.** Unreachable on purpose; see Decisions.
- **`AccountManager.remove_drive` has no caller.** The UI option and handler were deleted as
  unreachable; the data-layer method is in a file this plan does not own. Logged in
  `deferred-items.md`.
- **Strings 32007, 32012, 32013, 32023 and 32050 are orphaned.** The partition gate asserts that every
  *referenced* id resolves, not that every declared id is referenced, so an orphan is legal and
  asserted to be so. They are in the vendored module's block, which 03-12 owns.

## Threat Flags

None. No network endpoint was added, no new file access pattern beyond the store's own removal, no
schema change. The register's six threats:

| Threat | Disposition | Where |
|---|---|---|
| T-03-40 router elevation | mitigated | `_action_map` replaces `getattr(self, action)`; `test_dispatch_uses_an_explicit_mapping` keeps it replaced and three further assertions keep the mapping honest |
| T-03-41 response body in the log | mitigated | Both fields routed through `Request.get_body_for_report`; the mutation restoring the raw concatenation turns the sweep red |
| T-03-42 third-party error reporting | mitigated | `errorreport.py` deleted, absent from `git ls-files`; the prompt, the two stored answers and the six call sites in five other modules all gone. No report is assembled for transmission anywhere |
| T-03-43 stale credential after removal | mitigated | `store.remove_account` deletes the token file and the lock file with the record; asserted by `test_removing_an_account_deletes_its_stored_credential` |
| T-03-44 failure text on screen | mitigated | Only a locally-authored sentence and, on the unmapped path, the bare `AADSTS\d+` code. `_provider_failure` consumes the description and returns no field carrying it |
| T-03-45 second live request from a failure path | mitigated | The address-changed heuristic was deleted by 03-08 with the attribute it read; the branch that read the third party's address out of a request is deleted here. Neither end of that comparison exists |

One note for `03-10`: `Failure.code` is the bare provider code and it is the only provider-controlled
value that reaches a screen anywhere in this design, constrained to `AADSTS` followed by digits by the
pattern that produced it.

## Authentication Gates

None. No task required a credential, a login or a manual step.

## Unverified, and Where It Gets Verified

Four things this plan produced are argued rather than observed:

1. **The stale-credential row has never rendered.** Nothing writes `needs_reauth` yet. **03-10** writes
   it; **03-14** sees the row. This is the largest unverified thing here, and it is the entire delivery
   path for AUTH-17.
2. **Re-authorisation has never run against the live provider.** The write structure is asserted
   statically; that the exchange returns a usable blob for an account that already exists is a
   live-provider fact. **03-13** and **03-14**.
3. **Releasing the directory handle for `_reauthorise_account`.** The same mechanism 03-08 recorded as
   unrun for `_add_account`, now used by a second handler and by the stale row's default action.
   **03-14** runs it.
4. **No mapped sentence has been read on a television.** Same limit 03-05 recorded. **03-14**.

## User Setup Required

None.

## Next Phase Readiness

Ready, with five things the following plans need from here:

- **`03-10`** writes `needs_reauth` onto the account record. The key is
  `CloudDriveAddon.NEEDS_REAUTH_KEY` in `ui/addon.py` and it is the only coupling between the writer
  and the reader; a literal that does not match it produces a marker no list ever shows. It must go on
  the record and not into the token file. `AccountManager.remove_drive` is now callerless and is in
  `account.py`, which 03-10 owns — see `deferred-items.md` item 3 before deciding anything about it.
- **`03-11`** owns two things this plan deliberately left: the `sign-in-server` row and the
  `report_error` row in `resources/settings.xml`. **KODI-08 becomes true when the second of those goes,
  and no shared-id gate will tell you** — no later plan declares that id. `ADDON_STRING_IDS` in
  `tests/test_vendor_gates.py` is now `range(30036, 30060)` with a count of 49, not 48; and
  `test_localize_owns_this_addons_block` reads that same set, so a change to this add-on's block moves
  three things, not two.
- **`03-12`** gets the Vendored Tree Changes table above as the modification record's input. Note that
  `remote/errorreport.py` is deleted and that `VENDORED.md` currently describes it as present, in the
  paragraph beginning "Second, the tree carries a third-party traceback reporter". `VENDORED.md` also
  still has to name the removed accessor, since it is the excluded document that carries the history
  and a comment in shipped source may not.
- **`03-13`** and **`03-14`** inherit the four unverified items above.
- **Everyone:** `deferred-items.md` now exists in this phase directory with five entries, the first of
  which — `import urllib` not binding `urllib.parse`, in ten shipped modules — is the one most likely
  to bite somebody who is not looking for it.

Everything written here runs on Python 3.8 (Kodi 19-21) and 3.14 (Kodi 22): no f-string, no walrus, no
positional-only parameter, `dict` ordering and `dict.pop(key, default)` are both 3.8-safe, and
`super(OneDriveAddon, self)` is written in the two-argument form the rest of this tree uses.

## Self-Check: PASSED

- `.planning/phases/03-authentication/deferred-items.md` exists on disk.
- `resources/lib/vendor/clouddrive_common/remote/errorreport.py` does not exist and is absent from
  `git ls-files`.
- All seven commits resolve in `git log`: `a2eaa2e`, `79f9ae3`, `9026a7a`, `82595e7`, `7ed7ee2`,
  `356de0d`, `c3a1445`.
- `python -m compileall -q resources/ entrypoint.py service.py` is clean.
- `python -m pytest tests -q` reports 217 passed, 2 failed, 1 skipped, and both failures are the two
  assertions named above with their owning plans.
- `git diff --stat -- .planning/REQUIREMENTS.md` is empty.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
