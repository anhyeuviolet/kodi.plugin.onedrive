---
phase: 03-authentication
plan: 08
subsystem: auth
tags: [device-code, broker-removal, sign-in-flow, two-clocks, redaction, graph-endpoints, python38]

requires:
  - phase: 03-authentication
    provides: "Plan 03-01's device_code module — request_device_code, poll_once, next_interval, read_identity_claims, CONTINUE_ON, TransportError and the injected post(url, fields) -> (status, body) port this plan finally builds"
  - phase: 03-authentication
    provides: "Plan 03-04's RefreshLock and per-account layout, and LIFETIME_SECONDS = 90 — the number the transport profile handed to the refresh is pinned against"
  - phase: 03-authentication
    provides: "Plan 03-05's errors.classify_response and the 30036-30058 string catalogue, which is where every sentence this flow shows comes from"
  - phase: 03-authentication
    provides: "Plan 03-06's QRDialogProgress setters — set_code, set_remaining, set_expired, reset_for_new_code, is_new_code_requested. This plan is the caller that drives all five"
  - phase: 03-authentication
    provides: "Plan 03-07's refresh() and its REQUEST_TRIES / REQUEST_DELAY_SECONDS / REQUEST_BACKOFF, plus the explicit instruction in its Next Phase Readiness section that this plan must hand those three to the transport"
provides:
  - "resources/lib/auth_context.py — the four things resources/lib/auth/ needs from Kodi: profile_path(), session_id(), wait() and log(). The list is closed on purpose"
  - "Provider.request_device_code / Provider.poll_for_token — the two renamed methods, each delegating to the pure package and doing no protocol work of its own"
  - "Provider.get_access_tokens / persist_access_tokens / save_tokens — the token-store seam, pointing at the per-account file rather than into the account record"
  - "Provider.refresh_access_tokens — the refresh, wired to refresh() with the pinned transport profile and the account's own lock"
  - "Request.get_body_for_report — five credential field names redacted in both directions, in JSON bodies, form bodies and query strings"
  - "OneDrive.get_account from the identity token's claims with a drive-owner fallback; OneDrive.get_drives as one call to /me/drive"
  - "CloudDriveAddon._add_account / _await_authorisation / _poll_once — the sign-in flow: two clocks, one sleep, one write"
  - "tests/test_auth_gates.py::test_refresh_transport_is_built_from_the_pinned_profile — the three-way coupling nothing else in the tree can see"
affects: [03-09, 03-10, 03-11, 03-12, 03-13, 03-14, browse-phase]

tech-stack:
  added: []
  patterns:
    - "The Kodi layer produces the pure package's arguments in one module with a closed list; a fifth entry there would mean the pure package grew a Kodi dependency nobody noticed"
    - "Two clocks and one sleep: the abort-aware wait is simultaneously the countdown's tick and the shutdown check, and the poll interval is a separate deadline that is never derived from it"
    - "The account record is assembled in memory and written once, last, so cancel-safety is structural rather than a chain of guards"
    - "A request path that a static sweep must read is written as a whole literal at the call site, never held behind a constant"
    - "A refusal by the identity provider is shown, not raised: raising routes an answer through the failure handler"

key-files:
  created:
    - resources/lib/auth_context.py
  modified:
    - resources/lib/vendor/clouddrive_common/remote/provider.py
    - resources/lib/vendor/clouddrive_common/remote/request.py
    - resources/lib/provider/onedrive.py
    - resources/lib/vendor/clouddrive_common/ui/addon.py
    - tests/test_auth_gates.py
  deleted:
    - resources/lib/vendor/clouddrive_common/remote/signin.py

key-decisions:
  - "The refresh's transport is built through one factory, `_post_port(tries=..., delay=..., backoff=...)`, rather than a second copy of the same closure — and the pinning gate was widened to recognise that factory rather than only a bare `Request(` construction. The assertion still fails if any of the three keyword arguments is missing or is a literal instead of a reference to refresh.py's constant, so it is no weaker; it just stopped being pressure towards duplicated transport code"
  - "A 4xx from the token endpoint is not retried (429 and every 5xx still are). The token endpoint's 4xx is a settled answer, and retrying it re-sends a credential that was just refused while holding the refresh lock. This only ever shortens a call, so it cannot disturb the worst-case arithmetic the lock lifetime is set against"
  - "A credential value shorter than twice the eight-character prefix is redacted entirely rather than fingerprinted. `user_code` is nine characters; keeping eight of them is not a fingerprint, it is the live code with one character missing"
  - "The identity-token fallback issues its own request to /me/drive rather than threading the drive response through get_account. The behaviour the plan pins is that DRIVE RESOLUTION issues exactly one request, and it does; the fallback is a separate, conditional call that only happens when the name claim is absent, and coupling the two methods to save it would have made both harder to read"
  - "The endpoint literal '/me/drive' is written at both call sites rather than held in a class constant. A path behind a name is a path test_no_unanswerable_provider_endpoint cannot read, and that sweep is the only thing between this file and the 403 that broke sign-in at its first step"
  - "A TERMINAL poll outcome is shown with self._dialog.ok and string 30044, not raised. Raising would send it through _handle_exception, which still prompts to send an error report to the third party until 03-09 deletes the reporter — so a sign-in refusal would have offered to tell that third party about itself"
  - "An absent expires_in floors the deadline at five seconds rather than looping forever. The measured server always sends it; the floor exists so a nonsense response terminates the loop with the fresh-code action offered, not so it becomes a usable window"
  - "VENDORED.md was not touched, although this plan deletes a vendored file and rewrites three more. 03-12 owns that file and owns the modification-record update; the record of what changed is in this summary's Vendored Tree Changes section, which is 03-12's input"

patterns-established:
  - "Pattern 1: the poll loop's outcome vocabulary is four named constants on the class, so the caller's dispatch is exhaustive by construction and a fifth state cannot be added silently"
  - "Pattern 2: a long-running plugin action releases its directory handle and re-enters through RunPlugin, guarded on a non-negative handle, so one method is both the row's handler and the action"
  - "Pattern 3: this add-on's own 30000-block strings go through self._addon.getLocalizedString via _addon_string(); the vendored module's 32000-block keep going through _common_addon, which is what keeps the two catalogues readable apart"

requirements-completed: []

coverage:
  - id: D1
    description: "The refresh transport is constructed from refresh.REQUEST_TRIES, REQUEST_DELAY_SECONDS and REQUEST_BACKOFF by name, not by literal"
    requirement: "AUTH-14"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_refresh_transport_is_built_from_the_pinned_profile"
        status: pass
    human_judgment: false
  - id: D2
    description: "No request is made to an endpoint the locked scope set cannot answer; /me, /me/drives and the bare /drives are all gone from the provider"
    requirement: "BROWSE-08"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_no_unanswerable_provider_endpoint"
        status: pass
    human_judgment: false
  - id: D3
    description: "The transport's report builder names all five credential fields and no report string in the transport concatenates a raw request or response body"
    requirement: "AUTH-23"
    verification:
      - kind: unit
        ref: "tests/test_auth_gates.py::test_transport_report_redacts_credential_fields (first half green; second half red on two 03-09 sites)"
        status: partial
      - kind: manual
        ref: "the redactor driven against a real token response, a form request body and a device-code response: no whole credential survives any of the three, the address, expiry and interval all survive, and a nine-character user code is removed rather than fingerprinted"
        status: pass
    human_judgment: false
  - id: D4
    description: "The poll loop advances the countdown once a second and polls only when the interval says; a slow_down raises the interval permanently without touching the countdown's rate"
    requirement: "AUTH-09"
    verification:
      - kind: manual
        ref: "the shipped _await_authorisation driven against scripted endpoints with a stubbed clock: two slow_down answers moved the poll gaps to 5, 10, 15, 15 seconds while every consecutive countdown value differed by exactly one"
        status: pass
      - kind: unit
        ref: "AST assertion in the plan: no call named sleep anywhere in _add_account, _await_authorisation or _poll_once"
        status: pass
    human_judgment: false
  - id: D5
    description: "The expiry deadline is the server's own value for this code; a twelve-second response produces twelve seconds of countdown, one set_expired call, and no further polls"
    requirement: "AUTH-06"
    verification:
      - kind: manual
        ref: "same harness, expires_in=12: three polls, max countdown 12, set_expired called exactly once"
        status: pass
    human_judgment: false
  - id: D6
    description: "Cancelling, aborting or letting the code expire leaves no account record at all"
    requirement: "AUTH-07"
    verification:
      - kind: unit
        ref: "AST assertion in the plan: save_account is called exactly once in _add_account, and it is the last write statement"
        status: pass
      - kind: manual
        ref: "same harness: cancel at tick 2 returns ABANDONED after two ticks, expiry returns without an authorised payload, and neither path reaches the write block"
        status: pass
    human_judgment: false
  - id: D7
    description: "Releasing the directory handle and re-entering as an action leaves no spinner outliving the dialog"
    requirement: "AUTH-01"
    verification:
      - kind: manual
        ref: "deferred to plan 03-14 on the television; not run here"
        status: deferred
    human_judgment: true
---

# Phase 3 Plan 08: Sign-in Against the Identity Provider, With Nothing In The Middle Summary

Device-code sign-in that talks to Microsoft directly — the broker module deleted, the account
identified from the token's own claims, and a poll loop with two clocks, one abort-aware sleep and
exactly one write.

## What Was Built

**The third party is out of the sign-in path.** `remote/signin.py` is deleted. All sixty-six lines
of it posted to a hosted server: `create_pin`, `fetch_tokens_info` and `refresh_tokens` each sent
this add-on's identity and the user's credentials through a machine nobody here controls, and
`ui/addon.py` made a live call to it — fetching the user's public address — before the user had
done anything at all. That host was measured answering on 2026-08-22, so this removed a *working*
dependency, not dead configuration.

**The provider's methods are renamed to what they do.** `create_pin` → `request_device_code`,
`fetch_tokens_info` → `poll_for_token`. `refresh_access_tokens` kept its name because it already
said refreshing. Each delegates to `resources/lib/auth/` and performs no protocol work of its own.
Renaming mattered: `AUTH-23` asks for every path referencing the broker to be gone, and leaving the
pin vocabulary in the interface would have let that criterion pass on a grep while the third party's
shape survived in the method names.

**`resources/lib/auth_context.py`** is the one place the pure package's Kodi-shaped arguments are
produced: the profile path resolved once through `translatePath`, a session identifier held in a
home-window property (shared across every sub-interpreter in one Kodi session, gone when Kodi
restarts — which is exactly the "was the lock's holder from a previous run" signal `RefreshLock`
needs), the abort-aware wait, and a logger. Four things, and the list is closed on purpose: a fifth
entry would mean `resources/lib/auth/` had grown a Kodi dependency nobody noticed.

**Tokens read and write through the per-account file.** `get_access_tokens` reads
`accounts/<sub>.json`; `save_tokens` merges through `store.merge_token_response` under the account's
own lock and writes atomically at mode 0600. `{}` before the first sign-in, which the unchanged
`OAuth2._validate_access_tokens` turns into its own "not valid" failure — the right answer, because
there is no account to make a request for.

**The account is identified from the identity token.** `get_account` no longer calls the profile
endpoint. The label is the `name` claim, the key is the `sub` claim, and both arrive with the token
response at no extra request and no extra permission. When `name` is absent the label falls back to
the default drive's owner display name.

**Drive resolution is one call to `/me/drive`.** The two calls it replaces were one wasted round
trip and one guaranteed failure.

**The sign-in flow is rewritten**: two clocks, one sleep, one write. The two-minute cap is gone, the
verification address is the server's own, the countdown runs at one hertz independently of the poll
interval, and the account record is assembled in memory and saved once, as the last statement.

**The transport redacts five credential fields in both directions.**

## Task Commits

| Task | Name | Commit | Files |
|---|---|---|---|
| — | The pinning gate, written red | `3353b50` | `tests/test_auth_gates.py` |
| 1 | The provider speaks to the identity provider; the broker module goes | `0e5d51f` | `auth_context.py` (new), `remote/provider.py`, `remote/request.py`, `remote/signin.py` (deleted), `tests/test_auth_gates.py` |
| 2 | Account identity from the token, and one drive endpoint | `e2d5ff0` | `provider/onedrive.py` |
| 3 | The sign-in flow — two clocks, one sleep, one write | `0c87edd` | `ui/addon.py` |

## The Hard Coupling, Discharged

`03-07`'s summary named one thing no test on its side could enforce: that this plan must build the
refresh's transport from `refresh.REQUEST_TRIES`, `REQUEST_DELAY_SECONDS` and `REQUEST_BACKOFF`
rather than the transport's defaults. Those constants bound one refresh at `2 * 30 + 5 = 65` seconds
and `RefreshLock.LIFETIME_SECONDS = 90` was chosen against that number and nothing else. On the
transport's own defaults the worst case is 155 seconds — sixty-five seconds *past* the lifetime, at
which point a second contender is entitled to judge a live lock stale and break it while the first
is still mid-exchange.

It is discharged, and it is no longer a comment. `refresh_access_tokens` passes the three by name,
and `tests/test_auth_gates.py::test_refresh_transport_is_built_from_the_pinned_profile` asserts it
statically — on the argument *names*, not the numbers, because asserting `tries=2` would stay green
against a literal that nobody revisited when `refresh.py` changed its arithmetic. The gate was
written first and was red for exactly the right reason ("no Request construction was found inside a
refresh function"), then went green with the rewrite.

The gate was widened once during implementation, and the reason is worth recording rather than
burying: as first written it looked only for a bare `Request(` construction inside a refresh-named
function. That would have forced a second copy of the twelve-line transport closure into
`refresh_access_tokens` purely to satisfy the sweep — a gate acting as pressure towards worse code.
It now also recognises the `_post_port` factory. It still fails if any of the three keyword
arguments is absent or is a literal rather than a reference, so nothing it asserted was given up.

`tests/test_token_store.py::test_the_second_contender_sees_the_first_contenders_write` was read
before wiring, and the shape it spelled out — acquire, re-read the store *from disk*, and only
exchange if the token has not already moved — is `refresh.refresh()`'s own, which is what
`refresh_access_tokens` calls. `save_tokens` follows the same shape for the write path: a caller
that cannot acquire the lock does **not** write, because the holder is mid-refresh and is about to
store a newer blob, and overwriting it would replace a rotated refresh token with the one it
replaced.

## Deviations from Plan

### 1. [Rule 1 — Bug] Task 2's second verify command cannot pass, and its failure is a false positive

**Found during:** Task 2, running the plan's stated verification.

**Issue:** the command is

```
re.findall(r"self\.get\('(/[^']*)'", s) ... bad = [p for p in m if p.startswith('/drives') ...]
```

That regex matches the *leading fragment* of a concatenated address. `self.get('/drives/' +
item_driveid + '/items/' + item_id + '/children')` yields the capture `/drives/`, which
`startswith('/drives')` flags — so the command reports five forbidden endpoints in the browse code,
which is out of this plan's scope and answers perfectly well under the locked scope set. It reported
them before this plan ran and it would report them after any correct change.

The plan's own authoritative gate says why the command is wrong, in its own comment: *"A concatenated
path is a per-item address ... which is a documented endpoint and answers under this scope set. Only
the collection endpoints are written as whole literals ... so the test is on the whole value, never a
prefix."*

**Fix:** the sweep was run in the form the gate uses — parse the file, take the request path only
when it is a complete string literal, and normalise before comparing. Output:

```
complete literal paths: ['/me/drive', '/me/drive']
concatenated (per-item addresses, not collections): 9
ok - no forbidden collection endpoint
```

`tests/test_auth_gates.py::test_no_unanswerable_provider_endpoint` — the assertion `03-03` wrote for
this exact criterion, and the one that named `onedrive.py:40` in the first place — is **green**. No
source file was changed to accommodate the broken command, and the command was not rewritten in the
plan.

### 2. [Rule 3 — Blocking] The address-changed heuristic had to go with the class attribute it read

**Found during:** Task 3.

**Issue:** the plan instructs deleting `_ip_before_pin` (the class attribute holding the third
party's answer). Its only other consumer is the failure handler at what was `ui/addon.py:645-651`,
which would have raised `AttributeError` from inside an exception handler on every 404 — a failure
that only surfaces while reporting another failure.

**Fix:** the heuristic block is deleted with the attribute. It is Group 3 in `03-RESEARCH.md`'s
AUTH-23 removal map, disposition **delete**, so this is the plan's own work rather than a widening
of scope; it belongs to Task 3's file and Task 3's group. Strings `32072` and `32073` are orphaned by
it, which is harmless — the string-partition gate asserts that referenced ids resolve, not that
declared ids are referenced.

The neighbouring branch at what is now line 788 (`if KodiUtils.get_signin_server() in rex.request or
httpex.code == 401`) was **left alone**: it is `03-09`'s, which keeps the 401 half as a genuine
re-authorisation trigger and drops the broker half.

### 3. [Rule 2 — Missing critical functionality] Eight characters of a nine-character code is not a fingerprint

**Found during:** Task 1, exercising the redactor.

**Issue:** the plan says "keeping at most eight leading characters where correlation is wanted".
Applied uniformly, a `user_code` of `K7QF3NBXZ` redacts to `K7QF3NBX...*removed*` — the live code
with its last character missing, in a log file, while the dialog showing it is still on screen.

**Fix:** a value not at least twice the prefix length is redacted entirely. The three tokens are
hundreds of characters long and keep their eight; the two codes do not. Verified: the whole
`user_code` is absent from the redacted device-code response, while `verification_uri`, `expires_in`
and `interval` all survive — a redactor that ate the address would have made the report useless.

### 4. [Rule 2 — Missing critical functionality] A 4xx from the token endpoint is not retried

**Found during:** Task 1.

**Issue:** the transport retries on any exception. A 400 from the token endpoint is the protocol's
final word — an expired device code, a rejected one, a refresh token already spent — and retrying it
re-sends a credential that was just refused, while holding the refresh lock.

**Fix:** `_stop_retrying_a_settled_answer` wraps the transport's `on_exception` hook (composing with
any the caller supplied) and caps `tries` on a 4xx other than 429. 429 and every 5xx still retry.
This only ever *shortens* a call, which is why it cannot disturb the 65-second arithmetic the lock
lifetime is set against.

### 5. [Rule 1 — Bug] A provider refusal is shown, not raised

**Found during:** Task 3.

**Issue:** raising on a TERMINAL poll outcome routes it into `_handle_exception`, which — until
`03-09` deletes the error reporter — prompts the user to send a report to the same hosted third
party this plan exists to remove. A sign-in refusal would have offered to tell that third party
about itself.

**Fix:** the refusal is classified with `errors.classify_response`, logged with its outcome and
code, and shown with `self._dialog.ok` using string `30044` ("Sign-in failed. Error code: %s"). The
per-outcome sentences (30046-30058) are **`03-09`'s** named deliverable — "a provider failure renders
as the sentence its code maps to" — and duplicating that map here would have put two of them in the
tree.

### 6. [Judgment] `VENDORED.md` was not touched

This plan deletes one vendored file and rewrites three more, and the project conventions ask that the
modification record stay accurate. `VENDORED.md` is in `03-12`'s `files_modified` and `03-12` owns the
record update; two plans editing one document is how a modification record acquires contradictory
entries. The Vendored Tree Changes section below is `03-12`'s input.

## Vendored Tree Changes (input for 03-12's modification record)

| File | Change |
|---|---|
| `remote/signin.py` | **Deleted.** 66 lines. Every method posted to the hosted sign-in server |
| `remote/provider.py` | Rewritten. `_signin` attribute and its import removed; `create_pin` → `request_device_code`, `fetch_tokens_info` → `poll_for_token`, both delegating to `resources/lib/auth/device_code`; `refresh_access_tokens` rewritten onto `resources/lib/auth/refresh`; `get_access_tokens` / `persist_access_tokens` repointed at the per-account token store; `resolve_client_id()`, `ReauthorisationRequired` and the `post(url, fields)` port factory added |
| `remote/request.py` | `REDACTED_FIELDS` / `get_body_for_report()` added; three report-building sites and `get_url_for_report` routed through it |
| `ui/addon.py` | `_DEFAULT_SIGNIN_TIMEOUT` and `_ip_before_pin` class attributes removed; `Request` import removed; `_add_account` rewritten; `_await_authorisation`, `_poll_once` and `_addon_string` added; the legacy `migrated`-account cleanup block and the address-changed heuristic deleted |
| `ui/dialog.py` | Untouched by this plan (`03-06`'s) |

## Gate State After This Plan

Baseline inherited: 204 passed, 5 failed, 1 skipped. Now: **206 passed, 4 failed, 1 skipped.** One
red assertion turned green, one green assertion was added, and the failure count did not rise.

| Assertion | State | Sites this plan cleared | Sites remaining, and whose |
|---|---|---|---|
| `test_no_unanswerable_provider_endpoint` | **green** | `onedrive.py:40` (`/me/` → `/me`), `:49` (`/drives`), `:62` (`/me/drives`) | none |
| `test_refresh_transport_is_built_from_the_pinned_profile` | **green** | written red here, green with Task 1 | none |
| `test_transport_report_redacts_credential_fields` | red | the field-naming half is green; `request.py:142`, `:178`, `:190` all redacted | `errorreport.py:73` and `ui/addon.py:665` — **03-09** |
| `test_no_broker_references` | red | `signin.py:42, 60, 66` (file deleted), `ui/addon.py:190, 201, 203, 645, 646` | `errorreport.py:37` and `ui/utils.py:204-205` — **03-09**; `ui/addon.py:788` — **03-09**; `settings.xml:21` — **03-11**; `addon.xml:55` — **03-12** |
| `test_custom_client_id_setting` | red | none — not this plan's | the versioned schema and the expert-level setting — **03-11** |
| `test_dispatch_uses_an_explicit_mapping` | red | none — not this plan's | the router's `getattr(self, self._action)` — **03-09** |

This is exactly the state `03-03`'s Gate State table predicted, including that the plan's stated
verification `pytest tests/test_auth_gates.py -k "broker or redact"` cannot go fully green here. No
sweep was weakened to make an intermediate state look finished.

**One coordination note for 03-11.** The application-identifier setting is read here as
`CLIENT_ID_SETTING = 'client_id'` in `remote/provider.py`. `03-11` must use that id, or the escape
hatch will exist in the settings screen and be read by nothing. Reading a setting that does not exist
yet is safe: `getSetting` returns `''`, the shape validation rejects it, and the embedded constant is
used.

## Requirements

**No requirement mark was made or changed by this plan.** `git status` shows `.planning/REQUIREMENTS.md`
untouched across all four commits. The reasoning, per the shared-id rule `03-05` found and `03-07`
enforced by hand:

Of this plan's thirteen declared ids, **twelve are also declared by a later plan in this phase**, so
none of them is this plan's to complete:

| Id | Later declaring plan(s) | Why it is not complete here |
|---|---|---|
| AUTH-01 | 03-13, 03-14 | The flow exists; nobody has signed in with it |
| AUTH-02 | 03-11, 03-12, 03-13 | The embedded identifier is resolved here; the setting is 03-11's and the live proof is 03-13's |
| AUTH-03 | 03-13, 03-14 | Both account classes are unverified against this code |
| AUTH-04 | 03-13 | Already Complete (03-01). This plan consumes `SCOPES`; it did not change the mark |
| AUTH-06 | 03-14 | The countdown and the fresh-code action are driven here and observed there |
| AUTH-07 | 03-14 | The single-write structure is here and asserted; the cancel is performed there |
| AUTH-08 | 03-14 | The server's address is passed through untouched; the QR is read by a camera there |
| AUTH-12 | 03-13 | Already Complete (03-01). This plan makes the merge the only write path; the mark was not changed |
| AUTH-19 | 03-11 | The validation and the fallback are here; the Expert-level setting is 03-11's |
| AUTH-21 | 03-09, 03-13 | Already Complete. This plan makes the label come from the token rather than the endpoint that would 403; two later plans still declare it |
| AUTH-23 | 03-09, 03-11, 03-12 | Eight of the fourteen sites are cleared here. Green only after 03-12 |
| BROWSE-08 | Phase 4 owns it | `/me/drive` is now the only drive endpoint, but the traceability table assigns the id to Phase 4 |

**AUTH-11 is the one id no later plan declares, and it was already Complete** — marked by `03-01`
when the store was built. It was arguably premature then, because nothing called the store; it is
genuinely satisfied as of `0e5d51f`, where the provider's two accessors and the sign-in flow all
write through it. The mark stands and was not re-applied.

**A note on AUTH-21's wording.** The requirement reads "Account labels come from Graph". The label
now comes from the identity token, which Microsoft documents as a superset of what its user-info
endpoint returns — so it is satisfied in substance, and the clause carrying the requirement's actual
weight is the second one: *no account name is ever typed on a remote*. That clause is satisfied
exactly. `03-RESEARCH.md` Finding A already proposed restating the requirement; that restatement is
not made here, because `REQUIREMENTS.md` is not this plan's file to edit.

## Authentication Gates

None. No task required a credential, a login or a manual step.

## Known Stubs

None. No placeholder, TODO, `FIXME` or hardcoded empty value was left in any file this plan touched.

Two things that read like stubs and are not:

- `_drive_owner_name` returns `''` when the drive will not answer. That is deliberate tolerance, not
  a stub: a sign-in that has already succeeded must not be undone because a display name could not be
  read, and an account with an empty label is a cosmetic problem where an account that failed to be
  created is not.
- The refusal message uses string `30044` alone rather than the per-outcome sentences. That is a
  boundary, not an omission — `03-09` declares the mapping and the sentences exist in the catalogue
  already.

## Unverified, and Where It Gets Verified

Three things this plan produced are argued rather than observed, and each is recorded here rather
than left to be discovered:

1. **Releasing the directory handle and re-entering through `RunPlugin`.** It follows from documented
   behaviour (`RunPlugin` invokes a plugin with `sys.argv[1] == '-1'`), from this file's own
   context-menu entries which already use it, and from `resources/lib/addon.py:232` which already
   guards on a non-negative handle. It has not been run. **Plan 03-14** runs it and confirms no
   spinner outlives the dialog.
2. **Whether `owner.user.displayName` is non-null on a business drive.** The spike script printed it;
   the run output was not transcribed into `SPIKE-DEVICE-CODE.md`. It only matters when the identity
   token carries no `name` claim, which no observed run produced. **Plan 03-13** confirms it live.
3. **That the whole flow signs a real account in.** Every piece is tested or driven against a scripted
   endpoint; none of it has met the live provider in this shape. **Plans 03-13 and 03-14.**

## Threat Flags

None. No network endpoint was added that `03-01` had not already fixed as a constant, no new file
access pattern beyond the store's own, and no schema change. The register's six threats:

| Threat | Disposition | Where |
|---|---|---|
| T-03-34 third-party exchange | mitigate | `signin.py` deleted, the pre-sign-in address lookup deleted, the address-changed heuristic deleted. Eight of the sweep's fourteen sites cleared; the rest are named above with their owning plans |
| T-03-35 response bodies in the log | mitigate | Five field names redacted in JSON bodies, form bodies and query strings, in both directions, at most eight leading characters and none at all for a short value. The transport's three report sites all route through it |
| T-03-36 user-supplied identifier | mitigate | `CLIENT_ID_PATTERN` validates the GUID shape; anything else falls back silently to the embedded constant. The authority is `device_code.AUTHORITY` and is not reachable from any setting — stated in the comment at `CLIENT_ID_SETTING` |
| T-03-37 sign-in loop and shutdown | mitigate | One `waitForAbort(1)` is the only wait in the loop, asserted by the plan's AST sweep across all three methods. A shutdown is observed within a second at any poll interval |
| T-03-38 partial account on cancel | mitigate | One `save_account`, last, asserted by AST. Every cancel check above it returns having written nothing |
| T-03-39 verification address | mitigate | `response['verification_uri']` is passed through untouched and never composed; `QRDialogProgress` asserts the scheme is https before encoding it (03-06) |

## User Setup Required

None.

## Next Phase Readiness

Ready, with four things the following plans need from here:

- **`03-09`** inherits: the two remaining raw-body report sites (`errorreport.py:73`,
  `ui/addon.py:665`); the broker sites at `errorreport.py:37`, `ui/utils.py:204-205` and
  `ui/addon.py:788`; and the per-outcome sentence map, for which `Provider.ReauthorisationRequired`
  is the exception a refresh raises when `refresh()` answers `NEEDS_REAUTHORISATION`, and a plain
  `RequestException` is what it raises on a transient failure. Those two must not be collapsed — that
  distinction is the whole of Pitfall E.
- **`03-10`** gets `auth_context.profile_path()`, `session_id()` and `wait()` ready to hand to
  `refresh()` from the service, and `Provider._lock_for` as the shape of the lock construction. It
  must keep `test_service_never_opens_a_dialog` green; nothing added here opens a dialog.
- **`03-11`** must use the setting id `client_id`, and must keep the directory-listing default off
  through the schema conversion.
- **`03-12`** gets the Vendored Tree Changes table above as the modification record's input, and owns
  the `addon.xml` disclaimer that still tells users their tokens go to a third party they no longer
  go to.

Everything this plan wrote runs on Python 3.8 (Kodi 19-21) and 3.14 (Kodi 22): no f-string, no
walrus, no positional-only parameter, and `os.makedirs(exist_ok=True)` / `re.fullmatch` / `dict`
ordering are all 3.8-safe.

## Self-Check: PASSED

- `resources/lib/auth_context.py` exists on disk; `resources/lib/vendor/clouddrive_common/remote/signin.py`
  does not, and is absent from `git ls-files`.
- All four commits resolve in `git log`: `3353b50`, `0e5d51f`, `e2d5ff0`, `0c87edd`.
- `python -m compileall -q resources/ entrypoint.py service.py` is clean — the only check that
  catches a rewrite that ate a character.
- `python -m pytest tests -q` → 206 passed, 4 failed, 1 skipped, against a baseline of 204 / 5 / 1.
- `git diff -- .planning/REQUIREMENTS.md` is empty across all four commits.

---
*Phase: 03-authentication*
*Completed: 2026-08-23*
