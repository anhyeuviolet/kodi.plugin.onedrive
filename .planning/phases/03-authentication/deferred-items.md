# Deferred items — phase 03-authentication

Things found while executing that are outside the finding plan's scope. Each
names what was seen, why it was not acted on, and where it belongs.

## Found during 03-09

**1. `import urllib` does not bind `urllib.parse`, in ten shipped modules.**

Plan 03-06 met this once and fixed it locally. The pattern is tree-wide:
`resources/lib/addon.py`, `resources/lib/provider/onedrive.py`,
`clouddrive_common/export.py`, `remote/oauth2.py`, `remote/provider.py`,
`remote/request.py`, `service/player.py`, `service/source.py`, `ui/addon.py` and
`ui/utils.py` all write `import urllib` and then call `urllib.parse.something`.

It resolves today, and it was checked rather than assumed: on this interpreter
`from urllib.error import HTTPError` leaves `urllib.parse` bound as an attribute
of the package, and every one of those modules either has that import or is
reached from one that does. So the tree works. What is fragile is *why* it
works — it depends on an implementation detail of what `urllib.error` pulls in,
and this add-on has to run on both 3.8 and 3.14. The safe form is `import
urllib.parse`, ten one-line edits.

Not done here: nine of the ten files are outside 03-09's scope, and changing
only the one it owns would leave the tree inconsistent in a way that reads as
deliberate. **Belongs to a sweep of its own**, and the check that pays for it is
a gate asserting no shipped module calls `urllib.<submodule>.` without importing
that submodule by name.

**2. `tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write` is timing-sensitive.**

It failed once during 03-09 — `'A never got in at all'` — on a run that took
7.98s against a usual 3.2s, i.e. with the machine loaded by a parallel
`compileall`. Five consecutive runs of the test alone and three consecutive full
suites all passed afterwards. It drives two real threads through a
`threading.Barrier` with a five-second `acquire` timeout, so a scheduler stall
past five seconds fails it without anything being wrong.

Not caused by and not touched by 03-09. **Belongs to whoever next works on
`resources/lib/auth/lock.py`**: the acquire timeout in the test is the knob, not
the lock's own `ACQUIRE_TIMEOUT_SECONDS`.

*Two more observations, during the 03-14 hardware fixes.* It failed twice more,
on runs of 8.45s and 8.73s, and passed on eight consecutive runs of 3.2–4.3s
around them. Both failures were on the run immediately following a
`tools/build_addon_zip.py` build, which is the same shape of cause as the
`compileall` above. That makes three failures with the same signature and a
usable predicate rather than a single anecdote: **the run exceeding roughly
eight seconds is what predicts it**, not anything about the code under test. The
suite is otherwise green at 252 passed, 1 skipped. Still not worth chasing from
inside a fix commit, and still the same knob.

*A fourth, during the AUTH-05 font fix.* Failed again on an 8.51s run, then
passed on three consecutive runs of 3.30–3.39s immediately after, with no file
touched between them. Four failures now, and every one of them on a run over
eight seconds; the predicate has held on each occasion it has been available to
check, which is what turns it from a description into something worth acting on.
Suite otherwise green at 256 passed, 1 skipped.

**3. `AccountManager.remove_drive` has no caller.**

03-09 deleted the per-drive removal option and its handler as unreachable — one
drive per account by measurement. The data-layer method they called is still in
`clouddrive_common/account.py`, which 03-09 does not own and 03-10 does. It is
harmless and it is the shape to restore if the deferred document-library work
brings drive selection back. **Left deliberately**, recorded so nobody reads it
later as an oversight.

**4. Strings orphaned by 03-09.**

`32007` (the per-drive removal option), `32023` (its confirmation), and `32012`,
`32013` and `32050` (the error-reporting prompt and its two buttons). The
partition gate asserts that every *referenced* id resolves, not that every
declared id is referenced, so an orphan is legal and asserted to be so. They sit
in the vendored module's 32000-32088 block, which 03-12 owns. `32072` and
`32073` were already orphaned by 03-08 for the same reason.

**5. `CloudDriveAddon._open_common_settings` is now unreachable.**

It was reachable only from a settings row that opened a separate module's
settings dialog, and `test_vendor_gates.py` already asserts no row does that,
because the separate module no longer exists. 03-09 left it out of the action
mapping rather than deleting it: deleting a method is `03-12`'s kind of change
to the vendored tree, and the modification record is that plan's file.

## Found during 03-11

**6. `VENDORED.md:245` describes the error reporter in the present tense.**

It reads that the reporter "posts a stack trace to the same broker as the
sign-in flow" and "is gated on the `report_error` setting". 03-09 deleted the
module and 03-11 deleted the setting, so both clauses are now history written as
if it were current. No gate catches it: `report_error` is not one of the broker
literals, and `VENDORED.md` is excluded from the sweeps precisely so it may name
what was removed.

Not corrected here: `VENDORED.md` is the modification record and **03-12 owns
it**, with 03-08's and 03-09's Vendored Tree Changes sections already queued as
that plan's input. This is one more line for the same pass, and the shape the
correction should take is the one `test_the_replaced_flow_is_named_in_the_two_excluded_documents`
already asks of `README.md` and `VENDORED.md`: say it as past.

**7. Two settings rows survive that nothing on a supported Kodi can reach.**

`resume_playing` and `save_resume_watched` are read only inside the branch that
tests the `iskrypton` home-window property, and that property is set only when
`System.BuildVersion` starts with `17.`. This add-on requires Kodi 20, so the
branch is dead and so are the two settings. The old file kept them off the
screen with a visibility condition naming that property; KODI-06 removes the
condition, so 03-11 declared both at Advanced instead — the same effect for an
ordinary user, without a condition that lies about why.

Deleting them belongs with deleting the branch that reads them, in
`service/player.py` and `ui/addon.py`. That is a vendored-tree deletion of the
same class as `KODI-07`'s, and it is **not** in any Phase 3 plan. Recorded so
that the pair, their two strings (30011 and 30018) and the three `iskrypton`
call sites are removed together rather than one at a time.

## Found during 03-12

**8. Three vendored files were silently converted from CRLF to LF.**

`clouddrive_common/ui/addon.py` (in `356de0d`), `clouddrive_common/ui/utils.py`
(in `c3a1445`) and `resources/skins/default/1080i/pin-dialog.xml` (in `345999a`)
all arrived from upstream as CRLF and are now LF throughout. Nothing depends on
it and none of it was deliberate, but it is total in a byte diff: **every line
of all three now differs from upstream**, so `git diff` against the pinned
commit shows them as wholly rewritten and says nothing about what actually
changed. Measured, not inferred — the state of every vendored file was compared
at the lift commit, at the phase-3 base and at HEAD.

Not corrected here: converting them back is itself a whole-file rewrite of three
files, and doing that inside a documentation change would bury the same problem
one commit deeper. 03-12 recorded it in `VENDORED.md` instead, with the
instruction to use `git diff --ignore-cr-at-eol` on these three until somebody
normalises them on purpose. Note that upstream is **not** uniform — `remote/provider.py`
and `export.py` arrived LF — so "normalise everything to LF" is not the repair
it looks like; the target is whatever upstream holds, per file. **Belongs to a
sweep of its own**, and the check that pays for it is a gate comparing each
vendored file's line-ending style against the pinned upstream blob.

**9. `COVERAGE.md` is in the gate harness's exclusion set and has never existed.**

`EXCLUDED_DOCS` in `tests/gatelib.py` holds five names; one of them is
`COVERAGE.md`, which is in no commit in this repository. It has been in the set
since the phase-1 gates were written and it excludes nothing. Harmless, and
harmless is the problem: an entry that does no work sits beside four that do,
and the next reader has to check the tree to tell them apart.

Not corrected here: 03-12's files are three documents, and `tests/gatelib.py` is
not among them. The record now names the discrepancy. **Belongs to whoever next
edits `EXCLUDED_DOCS`** — either delete the entry or create the document, but
not leave it as a name that resolves to nothing.

**10. The strings orphaned by 03-08 and 03-09 are still orphaned.**

Item 4 above assigned `32007`, `32012`, `32013`, `32023`, `32050`, `32072` and
`32073` to 03-12 on the grounds that they sit in the vendored module's
32000-32088 block. 03-12 does not own them: its `files_modified` is
`addon.xml`, `README.md` and `VENDORED.md`, and it touched no catalogue. The
partition gate asserts that every *referenced* id resolves, not that every
declared id is referenced, so all seven are legal where they stand.

**Belongs to whichever plan next edits `resources/language/`**, with the same
condition item 4 already states: the gate's expected set moves in the same
commit as any deletion, because that assertion is an exact equality.

## Found during 03-13

**11. Nothing stops the next `refresh.fingerprint` comparison from being written.**

03-13's harness decided rotation by putting `refresh.fingerprint()` values
through a set. That function is a log redactor — eight leading characters, sized
so a pasted Kodi log cannot carry a credential — and every refresh token this
registration issues begins `1.AXEAuM`, so it rendered three different tokens
identically and produced a confident FAIL on a run that had proved nothing. Fixed
inside the harness by digesting whole tokens, with a guard that refuses any input
that is already shortened.

The shipped code was never wrong: `test_refresh.py::test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens`
compares whole tokens read back from disk. But nothing *asserts* that it must,
and nothing stops the next equality or identity comparison from being built on
`fingerprint()` again. It is the obvious function to reach for, it is right there
in the module, and the result looks authoritative while discriminating on eight
characters of a constant prefix.

Not fixed here: 03-13's files are the two research scripts, `.gitignore` and the
runbook, and `tests/` is not among them. **Belongs to whoever next edits
`tests/test_refresh.py`**, and the check that pays for it is a gate asserting no
comparison — `==`, `!=`, `set(...)`, `in` — takes `fingerprint()` output on
either side. The same shape as the sweeps already in `test_auth_gates.py`. The
transferable statement is in 03-13's summary: an instrument built from a
redactor cannot measure identity, and its PASS is as worthless as its FAIL.

## Found during the 03-14 AUTH-05 font fix

**12. The two dialog buttons are now the smallest text on the panel.**

The AUTH-05 fix took the code to `WeatherTemp` (120) and the body block to
`font37`. Both buttons — `1003` Cancel and `1004` "Get a new code" — were left at
`font25_title` (25), because the finding was about the code and enlarging things
nobody complained about inside a fix commit is how a fix stops being reviewable.

The result is that the panel's two *actionable* elements are now its smallest
text, on a screen the whole change exists to make readable from a seat. Their
boxes are 96 high, so `font32_title` or `font36_title` would fit without any
other coordinate moving. Nothing about this is known rather than reasoned: **the
buttons were not reported as hard to read**, and the same acceptance run that
produced the font finding is the instrument that should settle it. **Belongs to
the resumed 03-14 acceptance run** — look at the buttons, and if they read
badly, they are a two-line change with the geometry already in place.

*The acceptance run happened, and it did not settle this.* The buttons were never
looked at. Task 3's directional-pad row and its two context-menu rows were skipped,
so nobody moved focus onto either button or had reason to read one. The item stays
open with its instrument unchanged: **the next session on the television**, where it
is still a two-line change with the geometry already in place. Recorded so this is
not read later as "the run looked and found nothing wrong".

*The premise above is now half out of date, and the item is still open.* In a later
session on 2026-08-23 the directional-pad row and the context-menu row were run: the
pad reaches both buttons in order, and on expiry "get a new code" arrives already
focused. So somebody has now moved focus onto both buttons — the sentence above
saying nobody had is superseded. **No legibility verdict came back with it.** Being
able to reach a button is not the same reading as being able to read it, and this
item asks the second question. It stays open with the same instrument and the same
two-line fix, and this note exists so the d-pad pass is not later mistaken for the
buttons having been looked at.

## Found during the 03-14 acceptance run

Items 13 and 14 are **feature reports from the owner, not diagnoses**. Neither was
investigated during the run and neither should be read as understood. Phase 3 is
authentication; both belong to other phases, and they are written down here because
the run is where they were seen, not because this phase owns them.

**13. Subtitles from the cloud are unreliable or broken. Likely owner: Phase 6 (Play).**

Reported: subtitles appeared once, and after that the feature was inert.

That is the whole of what is known. It was not reproduced in a controlled way and
**no log was captured**, so there is no evidence beyond the sentence above. No root
cause is offered and none should be inferred — with one uncontrolled observation, a
subtitle track absent from Graph, a fetch that failed, a temporary file Kodi could
not read, and a player-side selection problem are all equally consistent with
"appeared once, then nothing", and they have nothing in common to fix.

**The two missing inputs are named deliberately**, because whoever picks this up
should collect them before reading any code: a **session log from a run that shows
the failure**, and a **repeatable trigger** — the same file, the same subtitle
track, the same sequence of actions, twice. Until both exist this is a report.

**14. Mounting the cloud as a directory or source inside Kodi does not work. Likely owner: Phase 4 (Browse), possibly Phase 6.**

Reported: the feature does not function. There is no further detail.

Undiagnosed, and thinner than item 13: what "does not work" resolves to is unknown,
and that distinction is most of the diagnosis. A refusal to add the source, a source
that adds and lists nothing, an error dialog, a listing that appears and cannot be
opened, and a crash are five different defects in three different layers, and the
report separates none of them.

Needed before this can be worked: **which screen it fails on, what appears instead of
what was expected, and a log from that moment**.

Two facts about the tree are worth **checking first**, and neither is a diagnosis —
they are simply cheaper to rule out than anything else here. `SourceService` and its
port 8586 directory listing **still exist**; they are scheduled for deletion in Phase 7,
not gone. And Phase 1 changed `allow_directory_listing` to default to **false**, a
recorded behaviour deviation made safe by the new add-on id meaning no user has a
stored `true`. If the report is about that mechanism, "off by default" and "deleted on
purpose in a phase not yet run" are both live possibilities alongside "broken", and
they are told apart by looking, not by reasoning from here.

**15. Kodi on Android 12 cannot see files on external storage under the default file permission.**

On the TCL Android TV 12 running Kodi 21.2, Kodi's file browser listed **folders** on
a USB drive but showed **no files** inside them, until the owner changed Kodi's
Android file permission from "while using the app" to "always". After that the zip
was visible and installed.

It fails in the shape most likely to be misread: an empty listing looks like an empty
directory, not like a permission refusal, and nothing on screen says otherwise. The
Phase 1 Android 11 emulator could not have produced it.

**Belongs with the install documentation** — `README.md`'s build-and-install section,
which 03-12 owns and which does not mention it. Every future device session pays this
cost again if it is not written down there.

**16. Installing by URL is not viable on this device. Belongs to Phase 5 (Distribution).**

Attempted during the run and it does not work. Kodi's *add source* browse needs a
**directory listing**, which a plain file URL does not provide, and adding a
repository is not a way around it, **because installing a repository is itself a zip
install**.

The consequence is practical and recurring: every re-test of a new build costs a USB
round trip to the television. It is not a defect in this add-on and it does not touch
DIST-01, which is about the archive the build writes — that archive installed through
Kodi's own file manager. It is a distribution problem, and Phase 5 is where the hosted
repository that would solve it already sits. Recorded rather than worked around: a
workaround invented inside an acceptance run changes the thing being accepted.

## Found during the phase-3 verification

**17. Phase 3 added a CI-01 violation, and until now it was recorded nowhere.**

CI-01 (Phase 2) requires that only `resources/lib/kodi/` import `xbmc*`. That
directory does not exist in the tree. Phase 3 added
`resources/lib/auth_context.py`, which imports `xbmc` at module level and sits
directly under `resources/lib/` — one level above the only location CI-01
permits.

The module itself is exactly the thin adapter CI-01's architecture asks for: a
closed list of four things the pure auth package needs from Kodi, documented as
such, and it is precisely what keeps `resources/lib/auth/` free of any `xbmc`
import — independently confirmed, there is no `xbmc` import anywhere in that
package. Nothing about the module is wrong except where it is.

**Not fixed here, and the reason is not scope but ownership.** CI-01 belongs to
Phase 2, Phase 2 has not been planned, and the fix is not a file move in
isolation: it is a decision about where the Kodi adapter layer lives and what
the enforcing test reads, taken together with the four other CI requirements in
the same phase. Phase 3 ran ahead of Phase 2 by the priority order, and a phase
running ahead does not get to settle the layout of the phase it overtook. Moving
the file now would pre-empt that design and would arrive without the test that
is supposed to hold it.

**Belongs to Phase 2**, which either moves `resources/lib/auth_context.py` under
the directory CI-01 names, or restates CI-01 against the layout actually wanted
— and in either case lands the enforcing test in the same commit, because a
boundary with no test is what let this go unrecorded for fourteen plans. The
fact and its location are stated here; no fix is proposed, because proposing one
is the part that is Phase 2's.

Also recorded against `CI-01` in `.planning/REQUIREMENTS.md` and as an inherited
constraint on Phase 2 in `.planning/ROADMAP.md`, so it is visible from the
requirement and from the phase as well as from this file.
