---
phase: 03-authentication
plan: 14
subsystem: auth
tags: [acceptance, hardware, android-tv, estuary, ten-foot-ui, device-code, readability, install, not-observed]

requires:
  - phase: 03-authentication
    provides: "Plan 03-02's tools/build_addon_zip.py — the archive installed on the television is the one it wrote"
  - phase: 03-authentication
    provides: "Plan 03-06's pin-dialog.xml and QRDialogProgress — the dialog this run read off a screen for the first time"
  - phase: 03-authentication
    provides: "Plan 03-08's sign-in flow and account identity — the path that acquired the account on the device"
  - phase: 03-authentication
    provides: "Plan 03-12's README build-and-install section — the procedure this run performed"
  - phase: 03-authentication
    provides: "Plan 03-13's live protocol verification — done off the television first, so a failure here is a Kodi problem rather than a protocol one"
provides:
  - "The acceptance record for Phase 3 on the TCL Android TV 12: device, Android version, Kodi version, active skin, and a verdict or a NOT OBSERVED marker on every checklist row"
  - "AUTH-05 settled by a person reading a screen, with the font actually in use named and the failing first reading kept"
  - "Three in-run fixes: the token blob is stamped where the payload arrives, the invalid-token message no longer prints the token, and the code renders at the largest font Estuary defines"
  - "Two device findings about Kodi on Android 12 that no emulator could have produced"
  - "Two out-of-scope feature reports, recorded undiagnosed against the phases that own them"
affects: [04, 05, 06]

tech-stack:
  added: []
  patterns:
    - "A checklist row that was not run is written down as not run, with its requirement left unmarked, because an omitted row reads later as a row that passed"
    - "A requirement that needed a fix to pass is recorded as such: the first reading is kept beside the second, since the failing one is what the prohibition exists to catch"
    - "A defect found while accepting a phase is recorded against the phase that owns it and left undiagnosed, rather than chased from inside an acceptance run"

key-files:
  created:
    - .planning/phases/03-authentication/03-14-SUMMARY.md
  modified:
    - resources/skins/default/1080i/pin-dialog.xml
    - resources/lib/vendor/clouddrive_common/ui/addon.py
    - resources/lib/vendor/clouddrive_common/remote/oauth2.py
    - resources/lib/vendor/clouddrive_common/remote/request.py
    - tests/test_auth_gates.py
    - tests/test_oauth2_tokens.py
    - tests/test_token_store.py
    - VENDORED.md
    - .planning/phases/03-authentication/deferred-items.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/WINDOWS.md

key-decisions:
  - "Five of the ten declared ids were marked. AUTH-06 and AUTH-22 are left Pending because a clause of each was not observed, and AUTH-03 stays Pending because its personal-account half is a deferred second run rather than a thing this session saw"
  - "The install went in from a USB drive through Kodi's own file manager. No network debugging channel was opened at any point, so T-03-62's mitigation is discharged by the channel never existing rather than by closing it"
  - "Installing by URL was attempted and does not work on this device. Recorded as a Phase 5 problem, not worked around here — a workaround inside an acceptance run is a change to the thing being accepted"
  - "The two feature reports found during the run are written down and left undiagnosed. Neither has a log or a repeatable trigger, and a root cause guessed from a one-line report is worse than an open question"

requirements-completed: [AUTH-01, AUTH-05, AUTH-07, AUTH-08, AUTH-17]

metrics:
  duration: "~2h across the run and three in-run fixes"
  tasks: 3
  files_changed: 12
  commits: 6
  completed: 2026-08-23

status: complete
---

# Phase 3 Plan 14: First Run on the TCL Android TV 12 Summary

A person sat down in front of a television, read a code off it, typed the code into a phone, and the
add-on remembered the account — the project's stated core value, observed for the first time, on the
machine it exists for.

## Device and software

| What | Reading |
|---|---|
| Device | **TCL Android TV 12** — the primary acceptance device, not a stand-in |
| Android version | 12 |
| Kodi version | 21.2 |
| Active skin | stock **Estuary** (default) |
| Install route | archive copied to a USB drive, installed through Kodi's own file manager |
| Install by URL | attempted, **does not work** — see device finding 2 |
| Network debugging | **never opened.** The USB route made it unnecessary |

The skin reading is load-bearing rather than bookkeeping. Kodi resolves a `<font>` name against the
active skin at render time and substitutes silently when it cannot, so a readability verdict taken on
a third-party skin would be a verdict about that skin. It was stock Estuary, so the names in
`pin-dialog.xml` are the names that rendered.

## Task 1 — install

| Row | Verdict |
|---|---|
| The archive is built by `tools/build_addon_zip.py` | PASS |
| Developer options, network debugging, pairing over `adb` | **NOT PERFORMED** — superseded by the USB route, which needs none of it |
| The archive reaches the television and installs **through Kodi's own file manager** | PASS — from a USB drive, the half of the packaging requirement no automated check can make |
| Install by URL | **FAIL** — see device finding 2 |
| Android version, Kodi version and active skin recorded | PASS — Android 12, Kodi 21.2, stock Estuary |
| Run on the real device rather than a stand-in | PASS — this is the television, and CI-06's stand-in clause was not invoked |

## Task 2 — the phase-1 checklist, repeated

Two rows of six were run.

| Row | Verdict |
|---|---|
| The add-on opens from the **video** section under its own identity | PASS |
| The add-on opens from the **music** section under its own identity | PASS |
| The **picture** section entry point | **NOT OBSERVED** — not reported either way |
| The background service starts at login | **NOT OBSERVED** — not reported |
| All three dialogs reached through the temporary dialog affordance, each rendering from this add-on's own skin directory | **NOT RUN** |
| Two openings of the code dialog write two different image paths | **NOT RUN** |
| **No dialog appears over the home screen at boot** | PASS — reported as "nothing unusual seen". This is the observable form of AUTH-17 |
| `grep -c Traceback` over the session log returns 0 | **NOT RUN** — no log was pulled |

The traceback sweep is one of the plan's own verification lines and it did not happen, in Task 2 or
in Task 3. It is recorded as not run rather than omitted.

## Task 3 — sign in from the sofa

| Row | Verdict |
|---|---|
| The code dialog appears when the add-account row is taken | PASS — the code, the countdown and the pattern image were all read off it |
| The container behind the dialog is not left spinning | **NOT OBSERVED** — not reported |
| **The code is legible from a normal seat** | **FAIL on the first build** at `font60`; **PASS** after `24702ff` took it to `WeatherTemp` (120px). Both readings are kept — see below |
| The expiry countdown is visible and ticking | **FAIL on the first build** — it was not on the screen at all; **PASS** after `24702ff` |
| The pattern image scans from a phone camera and opens the address the dialog shows | PASS at **280x280**. At the shipped **150x150** it was readable but small |
| **Sign in with a work/school account completes end to end from the television** | **PASS** — a real account was added through the device authorization grant, with no address, username or password typed on the remote |
| Back out of sign-in and the account list is exactly as it was | PASS |
| A second sign-in, cancelled part-way, leaves no partial account | **NOT SEPARATELY REPORTED** — the single Back reading above is the one that exists |
| On expiry, the "get a new code" action arrives **already focused** | **NOT RUN** — skipped |
| A fresh code carries its own countdown rather than resuming the old one | **NOT RUN** |
| Both buttons reachable with the directional pad, in a sensible order, with the intended initial focus | **NOT RUN** — skipped |
| The row's context menu offers re-authorise and remove | **NOT RUN** |
| Re-authorise completes without creating a second row | **NOT RUN** |
| Remove takes the row away and leaves the add-account row | **NOT RUN** |
| Session log swept for tracebacks | **NOT RUN** |
| Are the two buttons hard to read at `font25_title`? (deferred item 12 named this run as its instrument) | **NOT LOOKED AT** — the item stays open |

**The font actually in use is `WeatherTemp`, 120px, on stock Estuary**, and the readability verdict is
a pass at that font. It was not a pass at `font60`.

### One thing observed that belongs to another phase

**Video from OneDrive played through Kodi on the television.** That is Phase 6's goal and it was
reached incidentally, on the way to checking that an account had been added. It is recorded here as
an **observation, not as a Phase 6 requirement satisfied**: nothing was tested against Phase 6's
criteria — no seek, no resume, no bitrate, no long file across the measured 60-minute `downloadUrl`
lifetime, no second account, no second container. Phase 6 gets an encouraging data point and none of
its work removed.

## The three fixes this run produced

All three were found by running the add-on on the television and none of them could have been found
any other way this phase had available.

**`c768699` — stamp the token blob where the sign-in payload arrives.** Adding an account showed
*"Access tokens provided are not valid"* for a sign-in that had **succeeded**. A provider token
response is not a token blob: it carries `expires_in` and no `date`, and `date` is stamped locally by
`store.merge_token_response`. The vendored `OAuth2._validate_access_tokens` requires it, so the raw
payload was rejected by the first request made with it — `_identify` → `provider.get_account`, before
anything reached the network. `_acquire_tokens` now returns `store.merge_token_response({}, payload)`,
which is the single point where a poll payload becomes the blob the rest of the flow uses and is on
the path of both callers. The cheap repair — persisting earlier — was refused because it would trade
this defect for an AUTH-07 defect, and a gate now holds that seam so it cannot be taken later.

**`51d4ee0` — stop the invalid-token rejection printing the token.** The message that surfaced the
defect above was built as `'Access tokens provided are not valid: ' + Utils.str(access_tokens)`, and
that message is **not log-only**: `_handle_exception` renders a `UIException`'s root exception onto
line two of a Kodi dialog. So a live token blob — `token_type`, `scope`, `expires_in` and the access
token itself — was **displayed on a television**, and a third argument embedded the form body
carrying the refresh token, the device code and the client id. This is the finding with the sharpest
edge in the whole run: the phase spent 03-08 building a redactor for logs, and the credential came out
on the screen instead, through an exception message nobody had classed as user-facing. The message now
names the missing field and the fields that arrived, which is the whole diagnosis and none of the
secret, and the gate was widened to every `raise` in shipped source rather than moved.

**`24702ff` — take the sign-in code to the largest font Estuary defines.** Read from a normal seat the
code was legible but small. `font60` was never the largest font the skin offers: Estuary's Omega
`Font.xml` defines `WeatherTemp` at 120 and `font_clock` at 70, so 2x of headroom was unused. Control
1005 moves to `WeatherTemp` with its box 96 → 152 high, the panel grows 450 → 750 and re-centres at
top 165, and the pattern image goes 150x150 → 280x280 — the width the panel binds it to once the
address fits on one unwrapped line.

Sizing the countdown turned up **a defect that had been in the tree since 03-06**: control 1002's text
wrapped to roughly six lines of 38px inside a 156-high box, and **the line pushed out of view was the
countdown itself**. So AUTH-06's countdown was never visible on the shipped layout, on any device.
The box is now 364 high for six lines of 52px. Four gates hold the new layout and each was checked by
mutation — but what they prove is the layout's *intent*, and a layout that passes all four is
byte-identical whether the name rendered at 120px or silently fell back to 30. That distinction is
exactly what AUTH-05's prohibition is about, and it is why the verdict above is a person's reading
and not a gate's.

Two documentation commits belong to the run as well: `60201b8` and `364c373`, which gave the flaky
lock test a predicate instead of an anecdote and recorded the button sizes as an open question.

## Two device findings

Both are facts about the target device that the Phase 1 Android 11 emulator could not have produced.

**1. Kodi on Android 12 could not see zip files on external storage until its Android file permission
was changed from "while using the app" to "always".** Folders listed; files did not. A directory
listing that is present but empty reads as an empty directory, not as a permission refusal, so this
fails in the shape most likely to be misdiagnosed as a bad archive or a bad path. It is a prerequisite
for the documented install procedure and nothing in `README.md` says so.

**2. Installing by URL is not viable on this device.** Kodi's add-source browse needs a directory
listing, and adding a repository is not a way around it, because installing a repository is itself a
zip install. Every re-test therefore costs a USB round trip. This blocks convenient re-testing and it
is **Phase 5's (Distribution) problem** — recorded, not worked around.

Neither finding is a defect in this add-on, and neither changes DIST-01: the archive Kodi accepted is
the archive the build wrote.

## Two out-of-scope reports, undiagnosed

Both were noticed during the run. Phase 3 is authentication; neither is Phase 3 work, and **neither
was investigated or fixed**. Recorded in full in `deferred-items.md` as items 13 and 14.

**A — subtitles from the cloud are unreliable or broken.** Subtitles appeared once and the feature was
inert afterwards. Not reproduced in a controlled way and **no log captured**. Likely owner: **Phase 6
(Play)**. This is an unreproduced report, not a diagnosed defect: a session log from a run that shows
the failure, and a repeatable trigger, are the two missing inputs, and without them there is nothing
to distinguish a Graph-side absence from a fetch failure from a Kodi player-side one.

**B — mounting the cloud as a directory or source inside Kodi does not work.** Reported as
non-functional, with no further detail. Likely owner: **Phase 4 (Browse)**, possibly Phase 6. Same
treatment: what "does not work" means — a refusal, an empty listing, an error dialog, or a crash — is
not known, and that distinction is most of the diagnosis.

No root cause is offered for either, deliberately. A cause guessed from a one-line report tends to
survive into the plan that is supposed to find the real one.

## Requirement marks

Ten ids were declared. **Five were marked**, three were left Pending with the reason on the line, and
two were already Complete and are confirmed rather than re-applied.

03-14 is the last plan in this phase to declare any of them, so an id whose evidence is in this record
can legitimately close here. That makes the judgement below the only thing standing between the record
and a mark, which is why each row carries what it rests on.

| Id | Action | What it rests on |
|---|---|---|
| **AUTH-01** | → **Complete** | A work/school account was added from the television by reading a code off the screen and entering it on a phone. No address, username or password was typed on the remote. This is the requirement's exact sentence, observed |
| **AUTH-05** | → **Complete** | A person read the code from a normal seat and it was legible — the only instrument that exists for this. **It failed on the first build at `font60`** and passes at `WeatherTemp` (120px) after `24702ff`, on stock Estuary so no substitution is in play. A requirement that needed a fix to pass is a different fact from one that passed first time, and the failing reading is what the prohibition was written to catch |
| **AUTH-07** | → **Complete** | Backing out of sign-in with Back returned an account list exactly as it was. The remote has no Esc key, so Back is the only form the acceptance device can produce. The code half is held independently by `test_the_signin_flow_stamps_without_writing_anything` from `c768699`, which pins the no-write property at the seam the fix touched. The repeat form (a second sign-in cancelled part-way) was not separately reported |
| **AUTH-08** | → **Complete** | The pattern image was scanned with a phone camera and resolved to the address the dialog showed. The "encodes only the `verification_uri`" half is structural and already proven — the provider returns no `verification_uri_complete`, the encoder is fed the provider's address and nothing else, and an insecure source is refused |
| **AUTH-17** | → **Complete** | No dialog appeared over the home screen at boot, which is the requirement's observable form, and the code half was proven by 03-10. **Named weakness**: this is a negative observation from ordinary use, and the "background service starts at login" row was not reported, so the premise that the service ran is unconfirmed on this device. It is the weakest of the five marks and is written down as such rather than smoothed over |
| **AUTH-06** | **left Pending** | Its countdown clause passed — and only after `24702ff`, since the overflow meant the countdown was never on the screen. Its **focus clause was not observed at all**: the expiry path was skipped, so nobody has seen "get a new code" arrive already focused. The requirement is a conjunction and half of it is unmeasured. Not marked |
| **AUTH-22** | **left Pending** | The root is the account list and the add-account row works — that much the sign-in proves. **The per-row context menu offering re-authorise and remove was never opened.** That clause is half the requirement's sentence and no reading exists for it |
| **AUTH-03** | **left Pending** | The work/school half is now proven twice over: live through the shipped package in 03-13 and on the television here. The **personal-account half remains a deferred second run**, as 03-13 recorded — the spike already acquired a token on a personal account against this registration, so what is outstanding is a run, not a design question. The requirement says both, and both is not what happened |
| **CI-06** | **Complete — confirmed, not re-applied** | Already checked, set in Phase 1 as a standing obligation. This run is what discharges it for Phase 3: the acceptance pass happened **on the TCL Android TV 12 itself**, no stand-in was substituted, and every row that could not be run is recorded as not run rather than left out. The prohibition held |
| **DIST-01** | **Complete — confirmed, flag discharged** | 03-12 flagged that 03-02 had marked this Complete while 03-14 still declared it, and asked this plan to confirm rather than alter it. **Confirmed and now genuinely earned**: the archive the build wrote installed through Kodi's own file manager on the television. The install-by-URL failure is not a DIST-01 failure — DIST-01 is about the archive, and the archive was accepted |

## What this run does **not** close

Phase 3's success criterion 6 — the phase-1 checklist repeated on the real device — is **two rows of
six**. Criterion 5 is half met: the font and the pattern image are settled, the focused expiry action
is not. Whoever verifies this phase should read the NOT RUN markers above as the outstanding list
rather than as noise, and the cheapest way to close most of them is one more session on the device,
now that the install route is known and the sign-in path works.

## Deviations from Plan

**1. [Rule 1 - Bug] The sign-in reported failure on a sign-in that had succeeded**
- **Found during:** Task 3, on the device
- **Issue:** the raw provider payload was handed into the vendored `OAuth2` layer without the locally
  stamped `date`, so the first request made with it was rejected
- **Fix:** `_acquire_tokens` returns `store.merge_token_response({}, payload)`, plus two gates
- **Commit:** `c768699`

**2. [Rule 2 - Missing critical functionality] The rejection message displayed a live token on a television**
- **Found during:** Task 3, as a direct consequence of deviation 1
- **Issue:** an exception message built from the token blob is rendered into a Kodi dialog by
  `_handle_exception`, so the access token, the refresh token, the device code and the client id all
  reached a screen
- **Fix:** the message is built from field names only; the transport redactor now reaches this path;
  the credential gate widened from assignments to every `raise` in shipped source
- **Commit:** `51d4ee0`

**3. [Rule 1 - Bug] The countdown had never been visible**
- **Found during:** Task 3, while sizing the fonts
- **Issue:** control 1002 overflowed its 156-high box at `font27` and the line pushed out of view was
  the countdown — present since 03-06, on every device
- **Fix:** `font37` in a 364-high box, inside the layout change that also fixed AUTH-05
- **Commit:** `24702ff`

**4. [Deviation from procedure] The install went in over USB, not over network `adb`**
- **Found during:** Task 1
- **Why:** the plan's step 2 treated pairing over network debugging as a step with its own outcome. It
  was not needed. A USB drive plus Kodi's own file manager exercises exactly the code path the
  requirement is about, and opening no debugging channel is strictly better than opening and closing
  one
- **Consequence:** no `adb` was available, which is part of why the session log was never pulled

## Threat mitigations

| Threat | Disposition | How it went |
|---|---|---|
| T-03-62 network debugging left open on a home network | **not applicable** — mitigation discharged | No channel was ever opened. The archive travelled on a USB drive; there is nothing to confirm closed |
| T-03-63 code and address displayed to a room | accepted, as planned | The displayed code is single-use, short-lived and bound to this application, and the address is public |
| T-03-64 session log pulled from the device | **untested** | No log was pulled, so 03-08's redactor and 03-09's handler are still unexercised against a real device log. Recorded as an open row, not as a pass |
| T-03-65 stand-in substituted for the television | mitigated | The run was on the TCL. No stand-in appears anywhere in this record |

**One threat this plan did not anticipate materialised**: a credential reached the screen, not the
log, through an exception message. `51d4ee0` closes it and widens the gate to the class rather than
the instance.

## Known Stubs

None introduced. The unfinished work here is unrun checks, not unwired code, and every one of them is
named in the tables above and in the ledger.

## Test suite

`256 passed, 0 failed, 1 skipped` — run at the close of this plan. The count rose from 235 because the
three in-run fixes brought 21 new assertions with them, mostly the two new gate files' worth of
credential and layout sweeps.

`tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write` failed four
times during this run and passed on every run under about eight seconds; the predicate is recorded as
deferred item 2 and it is a property of the machine's load, not of the lock.

## Self-Check: PASSED

- `.planning/phases/03-authentication/03-14-SUMMARY.md` — FOUND
- `.planning/phases/03-authentication/deferred-items.md` — FOUND, items 13-16 present
- Commits `c768699`, `51d4ee0`, `24702ff`, `60201b8`, `364c373` — all resolve in `git log`
- `python -m pytest tests -q` → 256 passed, 1 skipped, 0 failed
- `.planning/REQUIREMENTS.md` — five checkboxes changed, three Pending lines annotated, DIST-01 and
  CI-06 annotated without their marks being touched
