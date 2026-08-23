---
phase: 03-authentication
plan: 06
subsystem: auth
tags: [kodi-skin, windowxmldialog, ten-foot-ui, focus-order, device-code, qr, estuary-fonts, python38]

requires:
  - phase: 03-authentication
    provides: "Plan 03-05's catalogue block 30036-30058 — 30038 the countdown, 30039 the expired state, 30040 the second action's label. This plan is the first thing that renders any of it"
  - phase: 01-vendor-lift
    provides: "The lifted skin tree under resources/skins/default/1080i/ and the per-invocation QR filename, both of which this plan builds on rather than reworks"
provides:
  - "resources/skins/default/1080i/pin-dialog.xml — a layout built around the code, with control 1005 for the code at font60, control 1004 for the second action, a defined left-right order and an explicit initial focus"
  - "QRDialogProgress.set_code / set_remaining / set_expired / reset_for_new_code — the four calls a two-clock poll loop drives, none of which fights focus"
  - "QRDialogProgress.is_new_code_requested() — the second button's click reported distinctly from cancel, so the caller can tell a request for a fresh code from an abandonment"
  - "A guarded destructor and an https assertion on the QR source"
affects: [03-08, 03-14]

tech-stack:
  added: []
  patterns:
    - "Focus is set at transitions only — onInit, the expiry transition, and the return from it — never inside a method a countdown calls once a second"
    - "The dialog holds no protocol: it reports the second button's click and lets the caller decide what to do about it"
    - "The words live in the catalogue and the dialog reads them by id; the XML carries no sentence of this add-on's own"

key-files:
  created: []
  modified:
    - resources/skins/default/1080i/pin-dialog.xml
    - resources/lib/vendor/clouddrive_common/ui/dialog.py

key-decisions:
  - "1004 is the second button and 1005 is the code label, following 03-RESEARCH.md's explicit id assignment rather than the reading order of the panel — the research is the record a later reader will check against"
  - "The second button is hidden from onInit rather than by a <visible> condition in the XML, because a condition in the XML wins over setVisible the next time it is evaluated"
  - "set_expired is idempotent, which is what makes 'focus moves exactly once' structural rather than a contract the caller has to honour — a loop that rediscovers expiry every tick still moves focus once"
  - "An insecure QR source is refused by skipping the image, not by raising: raising inside onInit takes the whole dialog down and with it the code, which is the one thing on the panel that still works"
  - "reset_for_new_code was added beyond the plan's three setters, because without it the expiry transition is one-way and the 'get a new code' action leaves the dialog permanently expired"
  - "The button labels are read from the add-on's catalogue through xbmcaddon.Addon().getLocalizedString, never through KodiUtils.localize, which routes every id below 32000 to Kodi's own catalogue and would silently return the wrong string"

patterns-established:
  - "Pattern 1: a font name in skin XML is accompanied by its named fallbacks in a comment, because there is no error and no log line when one does not resolve"
  - "Pattern 2: a transition method guards on its own state flag, so 'exactly once' survives a caller that calls it repeatedly"

# This plan declares [AUTH-05, AUTH-06, AUTH-07, AUTH-08] and completes NONE of
# them. All four are declared again by 03-14 (the television acceptance pass),
# and AUTH-06/07/08 also by 03-08 (the flow that drives this dialog). What this
# plan supplies is the surface; nothing renders a real code yet, and nothing
# has been read off a television. requirements mark-complete was deliberately
# not run -- see ## Requirements.
requirements-completed: []

coverage:
  - id: D1
    description: "The layout parses and declares the code control and the second button alongside the four that existed"
    requirement: "AUTH-05"
    verification:
      - kind: other
        ref: "ET.parse over pin-dialog.xml asserts {1000,1001,1002,1003,1004} <= ids; ids are 1000,1001,1002,1003,1004,1005"
        status: pass
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_skin_assets_present"
        status: pass
      - kind: unit
        ref: "tests/test_vendor_gates.py::test_resources_merged"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every font the layout names is one the stock skin defines"
    requirement: "AUTH-05"
    verification:
      - kind: other
        ref: "font30_title, font60, font27, font25_title — all four appear in Estuary's Font.xml list transcribed in 03-RESEARCH.md §The Dialog, in both the Default and Arial fontsets"
        status: pass
    human_judgment: false
  - id: D3
    description: "No focus call remains inside the per-tick update"
    requirement: "AUTH-06"
    verification:
      - kind: other
        ref: "ast walk over every FunctionDef named 'update' in dialog.py finds no setFocus call"
        status: pass
    human_judgment: false
  - id: D4
    description: "The tree still compiles and the vendor gates are green"
    requirement: "AUTH-06"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py — 23 passed"
        status: pass
      - kind: other
        ref: "python -m compileall on dialog.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "The QR encodes the provider's address and nothing else, and the address is asserted to be an https URL before an image is generated"
    requirement: "AUTH-08"
    verification:
      - kind: other
        ref: "onInit passes self.qr_code straight to pyqrcode.create, gated on _is_secure_url; the code is never appended and no address is constructed in this file"
        status: pass
    human_judgment: false
    rationale: "Source-level, not executed. The dialog cannot be imported without xbmcgui, so nothing under tests/ can drive it; the plan's own verification block is source and parse assertions for the same reason"
  - id: D6
    description: "Abandoning the dialog before it initialises does not attempt a delete on an unset path"
    requirement: "AUTH-07"
    verification:
      - kind: other
        ref: "__del__ reads getattr(self, '_image_path', None) and deletes only when truthy"
        status: pass
    human_judgment: false
    rationale: "Source-level for the same reason as D5"
  - id: D7
    description: "The code is legible from a normal seat, the countdown is seen ticking, the second action arrives focused on expiry, and both buttons are reachable in a sensible order with the directional pad"
    requirement: "AUTH-05"
    verification: []
    human_judgment: true
    rationale: "Deferred to plan 03-14, as the plan's own <human-check> states. Kodi resolves a font name against the active skin at render time and substitutes silently when it cannot, so no static check over this file can answer whether font60 rendered at 60px or fell back to 30. The named fallbacks — font52_title then font45 — are in a comment at the top of the XML so that pass has somewhere to go"

duration: 25min
completed: 2026-08-23
status: complete
---

# Phase 3 Plan 06: The Dialog, Rebuilt Around the Code Summary

**The sign-in panel now leads with the code at font60 across its full width, and the dialog class exposes four calls a once-a-second poll loop can drive without any of them stealing focus.**

## Performance

- **Duration:** 25 min
- **Tasks:** 2 of 2
- **Files created:** 0
- **Files modified:** 2
- **Suite:** 167 passed, 5 failed by construction, 1 skipped — identical to the baseline this plan inherited

## Accomplishments

- **The layout inverted.** The QR had the left third at 340×340 and the code would have gone into the shared body textbox. The provider does not return `verification_uri_complete` — measured in all three spike runs — so the QR can only ever carry the address, never the code. The code now has its own control across all 1150 points of the panel at `font60`; the QR is 150×150 and is what it actually is, a convenience that saves somebody typing an address.
- **Three font names were wrong and one of them had never rendered as written.** `font12_title` is not defined by the stock skin, on the textbox or on the cancel button, so both have fallen back to `font13` since the file was written — no error, no log line. They are now `font27` and `font25_title`, both defined in both of that skin's fontsets. The XML carries a comment naming the descending fallbacks (`font52_title`, then `font45`) and naming `WeatherTemp` as the one not to reach for, because it is specific to that skin in a way `font60` is not.
- **The focus defect is gone, and it was the direct blocker for the requirement.** `update()` ended with `setFocus(cancel)`. Called once a second by a countdown, that returns focus to cancel every tick, and a focused "get a new code" on expiry is unreachable while looking implemented. Focus is now set in `onInit`, once, and again exactly once on each transition.
- **Four calls, and none of them is a thread.** `set_code`, `set_remaining`, `set_expired` and `reset_for_new_code`. `show()` is non-blocking and the poll loop already ticks at one second on `waitForAbort(1)`, so a worker mutating controls while `onInit` may still be running — the stuck-dialog class of bug — is not needed and not present.
- **"Exactly once" is structural.** `set_expired` returns immediately if it has already run, so a caller that rediscovers expiry on every tick still moves focus once. That is a stronger guarantee than a contract the caller has to remember, and the caller in 03-08 does not yet exist to remember it.
- **The second button reports, it does not act.** `onClick` sets `new_code_requested` and nothing else; the caller reads it through `is_new_code_requested()`. A dialog that made the network call itself would be the thing that later becomes impossible to test, and it does not own the protocol.
- **Two ways out survive the transition.** Cancel stays present and focusable after expiry, and back and escape still cancel. On a device whose only other escape is force-stopping Kodi, that is the whole of T-03-27.
- **The destructor no longer deletes nothing.** `_image_path` is unset until `onInit` runs, and a dialog constructed and abandoned before that — an immediate abort — called `xbmcvfs.delete(None)` inside `__del__`, where the interpreter discards the error. It now reads the attribute through `getattr` (because `__init__` may not have completed either) and deletes only when there is something to delete.

## Task Commits

1. **Task 1: Rebuild the layout around the code** — `345999a` (feat)
2. **Task 2: The dialog class — per-tick setters, one focus decision, and a guarded teardown** — `c5329c6` (feat)

## Files Created/Modified

- `resources/skins/default/1080i/pin-dialog.xml` — rebuilt. New control `1005` (the code, `font60`, full width, centred) and `1004` (the second action). `1001` shrunk to 150×150, `1002` repositioned and moved to `font27`, `1003` moved to `font25_title`. Both buttons carry `<onleft>`/`<onright>` pointing at each other and `<onup>`/`<ondown>` pointing at themselves; the window declares `<defaultcontrol always="true">1003</defaultcontrol>`. A header comment records why the layout is shaped this way and which fonts the acceptance pass may fall back to.
- `resources/lib/vendor/clouddrive_common/ui/dialog.py` — `QRDialogProgress` gains `_new_code_btn_control`, `_code_control`, three catalogue ids, `is_new_code_requested`, `_addon_string`, `_is_secure_url`, `_render_text`, `set_code`, `format_remaining`, `set_remaining`, `set_expired` and `reset_for_new_code`. `__del__` guarded, `onInit` rewritten, `update` stripped of its focus call, `onClick` given a second branch, `create` given an optional `code` keyword. `import urllib` → `import urllib.parse`.

## Decisions Made

**1004 is the button and 1005 is the code.** Reading order would put the code at 1004, and the plan left the choice open. `03-RESEARCH.md` §The Dialog point 4 says in as many words that the "Get a new code" action "needs control id 1004 in the XML", and that document is what a later reader will check the tree against. Following it costs nothing and keeps the record and the tree agreeing; inventing a better numbering would have made them disagree over a detail nobody would think to re-derive.

**Hidden from `onInit`, not from the XML.** A `<visible>` condition in skin XML is re-evaluated, and it wins over a Python `setVisible` the next time it is. Hiding the second button in `onInit` is the only placement whose behaviour is not conditional on Kodi's evaluation order. The cost is a possible one-frame flash of the button as the window opens, which is the right trade against a button that reappears on its own.

**A bad QR source is refused by skipping the image, not by raising.** The plan says "assert it parses as a secure URL and refuse otherwise". Raising inside `onInit` is the literal reading and it is the wrong behaviour: the exception takes the dialog's initialisation down and with it the heading, the instruction and the code — the one element on the panel that would still have worked. So the image is not generated, `_image_path` stays `None` (which also keeps `__del__` correct), the refusal is logged at error level, and the person still gets a code they can type. The assertion is exactly as strict; only the consequence is chosen to leave something usable behind.

**`reset_for_new_code` exists although the plan named three setters.** Without it the expiry transition is one-way: `set_expired` flips a latch that nothing clears, so the "get a new code" action would leave the dialog showing "this code has expired" over a freshly-issued code, with the second button still on screen and focus still on it. The plan's own truth — "taking it restarts the flow with a fresh expiry read from the new response" — cannot happen without a way back. Recorded as a deviation below.

**The catalogue is read through the add-on, never through `KodiUtils.localize`.** That helper routes every id below 32000 to `xbmc.getLocalizedString`, which reads Kodi's own catalogue — correct when the module's ids were all 32000+, wrong now that this add-on's ids live in the 30000 block. Calling it with 30040 would have returned Kodi core's string 30040, silently. `_addon_string` goes to `xbmcaddon.Addon().getLocalizedString` directly and carries a comment saying why, with an English fallback so a missing catalogue entry produces a readable button rather than an empty one.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] `reset_for_new_code`, the way back out of the expiry transition**

- **Found during:** Task 2
- **Issue:** The plan specifies three setters and an expiry transition, and `set_expired` is idempotent so that focus moves exactly once. Nothing clears that latch. The dialog would therefore enter the expired state permanently: the caller fetches a fresh code, calls `set_code` and `set_remaining`, and the panel still reads "This code has expired." with the second button visible and focused. The plan's own truth about restarting with a fresh expiry has no implementation without this.
- **Fix:** `reset_for_new_code(line1, line2, line3)` clears `new_code_requested`, returns if not expired, clears the latch, rewrites the body text, hides the second button and moves focus back to cancel — because focus is sitting on a control about to disappear. It is a transition, not a tick, so setting focus there is consistent with the prohibition.
- **Files modified:** `resources/lib/vendor/clouddrive_common/ui/dialog.py`
- **Verification:** the ast sweep still finds no `setFocus` in `update`; the three focus calls are in `onInit`, `set_expired` and `reset_for_new_code`, all transitions.
- **Committed in:** `c5329c6`

**2. [Rule 1 — Bug] `import urllib` never bound `urllib.parse`**

- **Found during:** Task 2
- **Issue:** The module imports bare `urllib` at the top and calls `urllib.parse.unquote` twice at lines 253 and 257. Importing a package does not bind its submodules; those two calls have only ever resolved because some other module in the process imported `urllib.parse` first. The new `_is_secure_url` needs `urllib.parse.urlparse`, and relying on the same accident to make the QR's security assertion work is not acceptable — an `AttributeError` there would be swallowed by its own `except` and the assertion would fail open.
- **Fix:** `import urllib` → `import urllib.parse`, which binds both names, with a comment recording the reason.
- **Files modified:** `resources/lib/vendor/clouddrive_common/ui/dialog.py`
- **Verification:** `python -m compileall`; `test_tree_compiles` and the rest of the 23 vendor gates green.
- **Committed in:** `c5329c6`

### Scope Observations

**3. The plan's verification says "the twenty-two vendor gates green"; there are twenty-three.**

Same observation 03-05 recorded: 03-03 added `test_runbook_contains_aadsts7000218` after these plans were written. `python -m pytest tests/test_vendor_gates.py -q` reports **23 passed**. Nothing to fix; recorded so the count is not read as an accident.

**4. `requirements mark-complete` was not run at all.**

03-05 found this step ticking requirements later plans still owe, and reverted four marks. All four ids this plan declares are declared again by `03-14`, and three of them by `03-08` as well, so every one of them would have been a false green. The step was skipped rather than run and reverted. `git diff --stat -- .planning/REQUIREMENTS.md` is empty and all four remain `[ ]` / `Pending`. See ## Requirements.

---

**Total deviations:** 4 (1 × Rule 1, 1 × Rule 2, 2 scope observations)
**Impact on plan:** None on shape or scope. Deviation 1 completes a transition the plan described but left one-way; deviation 2 removes an accident the new security assertion would otherwise have depended on.

## Issues Encountered

**The one thing this plan is for cannot be checked by anything this plan can run.** Every assertion available — the parse, the id set, the ast sweep, the 23 gates — is satisfied equally well by a layout that renders the code at 30px because a font name did not resolve. That is Pitfall B exactly, and it is why `font60`'s fallbacks are written into the XML as a comment rather than left as knowledge. The check that means anything is a person on a sofa in plan 03-14.

**`KodiUtils.localize` is now wrong for two thirds of this add-on's strings and nothing says so at its definition.** Its `if string_id < 32000` branch was correct when every id this add-on owned was in the 32000 block; after the Phase 1 renumber into the 30000 block it silently reads Kodi's catalogue for 30000-30999. This plan works around it locally and names the trap in a comment at the call site. It is not fixed here — the helper has other callers with ids genuinely below 32000 (Kodi core strings like `222`), so correcting it is a change with a blast radius, and it belongs to a plan that can sweep every call site. Logged for whoever renders the failure table.

## Requirements

**None of the four this plan declares is complete, and none was marked.**

- **AUTH-05** — "renders the code at the largest font the skin offers, legible from a sofa". The dedicated control and `font60` exist; whether it renders at 60px and whether it is legible from a sofa are the same unanswered question, and both belong to `03-14`. Also declared by `03-14`.
- **AUTH-06** — "a live expiry countdown and, on expiry, a focused 'Get a new code'". The dialog can now do both and does neither: nothing drives `set_remaining`, nothing calls `set_expired`, and nothing acts on `is_new_code_requested()`. The flow is `03-08`. Also declared by `03-08` and `03-14`.
- **AUTH-07** — "cancelling with Back or Esc leaves no partially-created account". The dialog half is intact and the teardown defect is fixed, but the requirement is about account write ordering in `_add_account`, which `03-08` rewrites. Also declared by `03-08` and `03-14`.
- **AUTH-08** — "any QR encodes only the server-supplied `verification_uri`". This dialog now encodes what it is handed and asserts it is https, but its live caller still hands it a constructed broker address. Until `03-08` passes the provider's value through, the requirement is not met by the running add-on. Also declared by `03-08` and `03-14`.

`.planning/REQUIREMENTS.md` is byte-identical to its state before this plan ran.

## Known Stubs

None. No placeholder, TODO or hardcoded empty value was left. The four new dialog methods have no caller yet, by design — `03-08` is the plan that wires them, and this plan's commit boundary is deliberately one where the old caller still constructs and drives the dialog exactly as before, so the add-on runs between the two commits.

The five failing assertions in `tests/test_auth_gates.py` are unchanged from the inherited baseline (167 passed, 5 failed, 1 skipped, before and after). They are 03-03's red-by-construction gates with owners named in its Gate State table; none belongs to this plan and none was touched.

## Threat Flags

None. No new network endpoint, no new auth path, no schema change. One new file-access consideration and it narrows rather than widens: the image is now written only when the source URL passes the scheme check.

| Threat | Disposition | Where |
|---|---|---|
| T-03-25 | mitigated | `onInit` passes `self.qr_code` straight to `pyqrcode.create`, gated on `_is_secure_url`. No address is constructed in this file and the code is never appended to one |
| T-03-26 | mitigated | The image still encodes a public address only. The teardown deletes it and no longer fails silently on an unset path — `getattr(self, '_image_path', None)`, so it is correct even when `__init__` did not complete |
| T-03-27 | mitigated | Cancel is left visible and focusable through the expiry transition, and `onAction` still cancels on back and escape. Both buttons carry explicit left-right navigation to each other, so neither is reachable-in-principle-only |
| T-03-28 | mitigated | The per-invocation `qr-<uuid4>.png` filename is retained verbatim, with the comment explaining it left in place |

## User Setup Required

None.

## Next Phase Readiness

Ready for `03-08`, which drives this. Four things it needs to know:

- **The contract is four calls.** `set_code(code)` once per code; `set_remaining(seconds)` once per tick; `set_expired()` when the clock runs out; `reset_for_new_code(line1, line2, line3)` after a fresh code has been fetched. `is_new_code_requested()` is polled the same way `iscanceled()` already is, and `reset_for_new_code` clears it.
- **Re-read the expiry from the new response.** The provider randomises `expires_in` — 3655, 4491 and 3599 across three observed runs — so the second code's countdown must start from the new value, not the old one. `set_remaining` takes seconds and formats them as `m:ss`.
- **`set_expired` is idempotent, `set_remaining` is not a transition.** Calling `set_expired` every tick after expiry is safe and is probably the simplest loop to write. Calling `set_remaining` never changes focus, by construction and by assertion.
- **The QR source must be the provider's `verification_uri` verbatim.** Anything that is not an `https` URL produces no image at all and an error line in the log. The dialog will still show the code, which means a broken caller degrades quietly rather than loudly — worth an eye on the log during the first real run.

One constraint inherited and preserved: this file runs on Python 3.8 (Kodi 19-21) and 3.14 (Kodi 22) and uses nothing newer than 3.8.

## Self-Check: PASSED

Both modified files exist on disk and are committed; both task commits (`345999a`, `c5329c6`) resolve in `git log`; the layout parses and reports ids `1000, 1001, 1002, 1003, 1004, 1005`; the ast sweep over `update` reports `ok`; the full suite is 167/5/1, unchanged.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
