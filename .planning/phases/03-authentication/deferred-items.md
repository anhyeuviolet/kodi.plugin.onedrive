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
