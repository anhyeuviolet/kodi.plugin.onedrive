# Phase 3: Authentication - Research

**Researched:** 2026-08-23
**Domain:** OAuth 2.0 device authorization grant inside Kodi on Android TV; cross-sub-interpreter token persistence; ten-foot dialog design
**Confidence:** HIGH on the protocol (measured), HIGH on the code inventory (read from the tree), MEDIUM on the Kodi runtime idioms (documented, not yet run on the TCL)

<user_constraints>
## User Constraints

No `CONTEXT.md` exists for this phase — `/gsd-discuss-phase` has not run. These constraints are
transcribed from `ROADMAP.md` ("Priority order", set 2026-08-23), `STATE.md` (Accumulated Context →
Decisions) and the phase brief. Treat them with the same authority a CONTEXT.md would carry.

### Locked Decisions

- Device code flow with an embedded public `client_id`. **No broker server, no client secret, ever.**
- Authority is `/common`, in **one constant**, for both account classes. No authority split, no
  user-facing authority setting. Measured, not assumed — `SPIKE-DEVICE-CODE.md`.
- Scope string is exactly `https://graph.microsoft.com/Files.Read offline_access openid profile`.
  No `Files.Read.All`, no write scope, no `.default`.
- The token-refresh lock uses `os.open(..., O_CREAT|O_EXCL)`. **`threading.Lock` and `fcntl.lockf`
  are forbidden for this purpose** — the plugin and the service are sub-interpreters inside one
  process, so neither excludes the other.
- The add-on ships as `plugin.onedrive.kn`. **No migration from v2.3.0 exists, by design** — new
  add-on id, new profile, nothing to read. Pitfall 17's migration work is *not* in this phase.
- The **TCL Android TV 12 is the primary acceptance device**, and Phase 3 carries its first run.
  Windows is not a target. A stand-in is acceptable only for API-level questions (storage paths,
  file mode bits, `O_EXCL`, loopback binding).
- **OneDrive Business is the drive type in use.** The Personal half of every requirement is
  *deferred, not deleted*. The spike already proved the protocol on a personal account, so what is
  deferred is an on-television pass, not a design question.
- `BROWSE-08` fixes `GET /me/drive` as the drive endpoint. That decision lands in Phase 4 but it
  changes the shape of the account list this phase builds — see §Multi-account structure.

### Claude's Discretion

- Where the poll loop lives (plugin invocation vs. `RunPlugin` worker) and how the dialog is driven.
- The layout of the token store on disk, the lock file format, and the stale-lock policy.
- The `AADSTS` → message mapping table's wording.
- The runbook's location and section order.

### Deferred Ideas (OUT OF SCOPE)

- Multi-device support, public distribution, backwards compatibility, Kodi versions other than what
  runs on the TCL.
- Personal-account **testing** (the protocol support stays in).
- SharePoint document libraries (`AUTH-24`, v2).
- The existing-user migration (`Pitfall 17`) — there are no existing users of `plugin.onedrive.kn`.
- Resume/watched sync, STRM export, slideshow, delta sync (v2).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-01/02/03 | Registration correctly configured, verified via manifest read-back | Already satisfied. §SETUP-04 Runbook restates the values so they can be recreated |
| SETUP-04 | Registration runbook in the repo, carrying `AADSTS7000218` verbatim | §SETUP-04 Runbook Contents — including the CI-05 grep collision this creates |
| AUTH-01 | Read a code off the TV, enter it on a phone | Measured end to end in `SPIKE-DEVICE-CODE.md`; §The Dialog covers the TV half |
| AUTH-02 | Public `client_id`, no Azure setup, no server, no copy-paste | Settled. §AUTH-23 Removal Map removes the last server dependency |
| AUTH-03 | Both account classes against the chosen authority | Settled — `/common` works for both, three live runs |
| AUTH-04 | Exact scope set | Settled. §Finding A shows this scope set **breaks `GET /me`** — load-bearing |
| AUTH-05 | Code at the skin's largest font | §The Dialog — the current skin XML names a font Estuary does not define |
| AUTH-06 | Live expiry countdown, focused "Get a new code" on expiry | §The Dialog + §Polling Without Blocking Shutdown |
| AUTH-07 | Back/Esc leaves no partial account | §The Dialog (cancel path) + §Account Write Ordering |
| AUTH-08 | QR encodes only the server-supplied `verification_uri` | Settled — server returns `https://login.microsoft.com/device`, not `microsoft.com/devicelogin` |
| AUTH-09 | Poll loop is an allow-list | §Polling — RFC 8628 §3.5 quoted verbatim |
| AUTH-10 | HTTP 400 + JSON body parsed as protocol | §Polling — RFC 6749 §5.2 is the reason it is a 400 |
| AUTH-11 | Atomically-written JSON under `special://profile/addon_data/` | §Atomic Token Persistence |
| AUTH-12 | Full write-back; retain previous `refresh_token` when omitted | §Atomic Token Persistence; Pitfall 3 |
| AUTH-13 | Test proves the persisted refresh token changes across two refreshes | §Validation Architecture |
| AUTH-14 | `O_EXCL` lock with a stale-lock breaker; no `threading.Lock`, no `fcntl.lockf` | §Cross-Process Refresh Serialisation — primary evidence for *why* |
| AUTH-15 | Loser adopts the winner's token on `invalid_grant` | §Cross-Process Refresh Serialisation |
| AUTH-16 | Proactive refresh on startup, inside the 90-day window | §Proactive Startup Refresh |
| AUTH-17 | Service never opens a sign-in dialog | §Proactive Startup Refresh — the needs-reauth signalling path |
| AUTH-18 | Tenant-block message names the cause and the custom `client_id` setting | §The AADSTS Error Map |
| AUTH-19 | Custom `client_id` setting at Expert level, empty by default | §Finding B — **Expert level requires the v1 settings schema, which is Phase 7** |
| AUTH-20 | Tokens, delta tokens, cache keys isolated per account | §Multi-Account Structure — and §Finding D, there is no live cache to isolate |
| AUTH-21 | Account labels come from Graph; nothing typed on a remote | §Finding A — `GET /me` will not answer; three alternatives given |
| AUTH-22 | Root is the account list, "Add an account…" row, per-row context menu | §Multi-Account Structure |
| AUTH-23 | `sign-in-server` and every external-broker code path gone | §AUTH-23 Removal Map — 14 sites, one of them a live network call |
</phase_requirements>

## Summary

The protocol half of this phase is finished before it starts. `SPIKE-DEVICE-CODE.md` ran the exact
flow the add-on will run, against this project's own registration, three times, on two account
classes, and settled the authority, the scope string, the refresh-token issuance, the
`verification_uri`, the randomised `expires_in`, the missing `verification_uri_complete`, and the
drive-endpoint matrix. `verify_device_code.py` is a working reference implementation in the same
stdlib-only constraint the add-on runs under. Nothing in this document re-derives any of that.

What is *not* settled is everything on the Kodi side of the boundary, and that is where the risk
now lives. Four findings below change the shape of the plan rather than decorating it: the locked
scope set makes `GET /me` return 403 so the existing `get_account()` cannot produce an account label
(**Finding A**); `AUTH-19`'s Expert-level setting is expressible only in the `<settings version="1">`
schema, which sits in the deferred Phase 7 (**Finding B**); `SETUP-04`'s demand that the runbook
carry `AADSTS7000218` *verbatim* puts the literal string `client_secret` into a tracked file, which
is exactly what `CI-05` is specified to fail on (**Finding C**); and `AUTH-20`'s "cache keys isolated
per account" has no live cache to isolate, because the only `Cache` consumer in the tree is the
`SourceService` that is scheduled for deletion (**Finding D**).

Beneath those, the durability design has one insight that decides the whole locking approach. The
plugin and the service are sub-interpreters inside **one OS process**. The `fcntl` man page states
that POSIX record locks "are associated with the process", that a second lock on a region the
process already holds is merely "converted to the new lock type", and that closing *any* descriptor
for the file "releases all of the process's locks on that file". `fcntl.lockf` therefore cannot
exclude the plugin from the service, and whichever finishes first silently drops the other's lock.
`threading.Lock` fails for the adjacent reason — separate sub-interpreters hold separate objects.
`os.open(O_CREAT|O_EXCL)` is filesystem-level and is indifferent to who is asking. `AUTH-14` is not
a stylistic preference; it is the only mechanism that works here. The same fact makes the
conventional "is the holder's pid still alive?" stale-lock breaker **degenerate** — the pid is always
alive, because it is Kodi.

**Primary recommendation:** build a pure-Python `auth` package with zero `xbmc*` imports containing
the device-code protocol, the token store and the lock; drive it from a thin Kodi-facing layer that
owns the dialog, the `Monitor`, and the settings. Resolve Findings A–D before planning tasks, because
each one changes which tasks exist.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Device-code request / poll / token exchange | Pure core (`resources/lib/auth/`) | — | Pure HTTP + JSON; `CI-01` and `AUTH-13` both require it be importable without Kodi |
| Token store (read, atomic write, merge) | Pure core | Kodi layer supplies the translated path | `os` on a real path; nothing Kodi-specific once the path is resolved |
| Refresh lock (`O_EXCL`, stale breaker) | Pure core | Kodi layer supplies the session id | Filesystem primitive; the session id is the one Kodi-derived input |
| Countdown / poll pacing / abort | Kodi layer | Pure core exposes a step function | `Monitor.waitForAbort` is Kodi-only; the protocol state machine is not |
| Sign-in dialog (code, QR, countdown, cancel) | Kodi layer (`WindowXMLDialog` + skin XML) | — | GUI |
| Account list, context menu, routing | Kodi layer (`ui/addon.py`) | — | `xbmcplugin` |
| Startup proactive refresh | Kodi service (`service.py`) | Pure core does the refresh | `AUTH-17` forbids the service from touching the GUI |
| `AADSTS` → message mapping | Pure core (table) | Kodi layer renders | Table is data; `AUTH-13`-style tests should cover it |
| Registration runbook | Repository documentation | — | `SETUP-04` is a maintainer artefact, not code |

## Findings That Change the Plan

These are the "requirements as written are unsatisfiable or self-contradictory" flags the brief asked
for. Phase 1 hit three; this phase has four plus two smaller ones.

### Finding A — `AUTH-04`'s locked scope set makes `GET /me` return 403, and `AUTH-21` depends on it

`resources/lib/provider/onedrive.py:39-44` implements `get_account()` as:

```python
me = self.get('/me/', request_params=request_params, access_tokens=access_tokens)
return { 'id' : me['id'], 'name' : me['displayName']}
```

That `displayName` is the account label — `AccountManager.get_account_display_name()` renders
`account['name']`, and `list_accounts()` puts it on the row. So `AUTH-21` ("account labels come from
Graph") is currently implemented by `GET /me`.

Microsoft's reference for that endpoint states the least-privileged delegated permission as
**`User.Read`**, for work/school **and** for personal Microsoft accounts, with no OIDC alternative
listed. [CITED: learn.microsoft.com/en-us/graph/api/user-get] The spike's granted-scope readback
confirms the token carries no such permission:

| Run | `scope` returned |
|---|---|
| Business | `openid profile email https://graph.microsoft.com/Files.Read` |
| Personal | `https://graph.microsoft.com/Files.Read openid profile` |

The spike probed `/me/drives`, `/me/drive` and `/drives`. **It never probed `GET /me`.** So this is a
documented-but-unmeasured prediction, not a measurement — but the documentation is unambiguous and
the consequence is that the first thing `_add_account` does after acquiring a token fails with 403.

Three ways out, in order of preference:

1. **Read the `id_token` claims.** `openid` is in the scope set, so the token response carries an
   `id_token`; `verify_device_code.py` already decodes it and prints `name`, `preferred_username`,
   `sub` and `tid`. Microsoft states the id_token's information "is a superset of the information
   available on UserInfo endpoint" and recommends it precisely to avoid the extra request.
   [CITED: learn.microsoft.com/en-us/entra/identity-platform/userinfo] Zero extra network calls,
   zero extra scope. It also hands over `sub`, which `SPIKE-DEVICE-CODE.md` already identified as the
   sound per-account local key. **Security note:** decode for display and local keying only, never
   validate a signature and never make an authorization decision from it — trust here comes from
   having received it over TLS directly from the token endpoint, exactly as the spike script's
   comment says.
2. **`GET https://graph.microsoft.com/oidc/userinfo`.** "UserInfo is a standard OAuth bearer token
   API hosted by Microsoft Graph"; permissions are `openid` (required) plus `profile` for the name
   claims. Returns `sub`, `name`, `family_name`, `given_name`, `picture`, `email`.
   [CITED: learn.microsoft.com/en-us/entra/identity-platform/userinfo] This satisfies `AUTH-21`
   *literally* ("from Graph") at the cost of one request. Use this if the literal reading matters.
3. **`GET /me/drive` → `owner.user.displayName`.** Already 200 on both account classes with this
   exact scope set (measured), and `/me/drive` is already being called for `BROWSE-08`. The spike
   script prints this field but the run output was not transcribed into `SPIKE-DEVICE-CODE.md`, so
   whether it is non-null is **unverified**.

**Recommendation:** option 1 for the label and the key, option 3 as a fallback when `id_token` is
absent, and drop `GET /me` from `get_account()` entirely. Whichever is chosen, this is a task, and
without it Phase 3 fails at the first sign-in.

**Requirement text to fix:** `AUTH-21` says "Account labels come from Graph". If option 1 is taken,
restate it as "Account labels come from the identity provider, never typed on a remote" — the point
of the requirement is the second clause.

### Finding B — `AUTH-19` requires the v1 settings schema, which lives in the deferred Phase 7

`AUTH-19` demands a custom `client_id` setting "at Expert level". Setting levels are declared with a
`<level>` element inside a `<setting>`, values `0` Basic / `1` Standard / `2` Advanced / `3` Expert,
and that element belongs to the `<settings version="1">` format. The pre-version format — which
`resources/settings.xml` still uses, 28 lines of `<category label="...">` and `<setting type="lsep">`
— has no level concept at all. [CITED: kodi.wiki/view/Add-on_settings, kodi.wiki/view/Settings]

`KODI-05` ("`resources/settings.xml` uses the `<settings version="1">` schema") is mapped to Phase 7,
and Phase 7 is deferred apart from criterion 4.

Two resolutions:

- **Pull the schema conversion into Phase 3.** The file is 28 lines. Phase 3 already has to edit it
  to delete `sign-in-server` (`AUTH-23`) and to add the `client_id` setting. Phase 7 criterion 4 —
  which the priority order *already* pulled out of the deferred set on security grounds — deletes
  `allow_directory_listing`, `port_directory_listing` and `report_error`, which are three of the
  remaining rows. Doing it once instead of three times is strictly cheaper. **Recommended.**
- **Restate `AUTH-19`** as "exists, empty by default, and is not reachable from the ordinary settings
  path" and accept that it is visible at all levels until Phase 7.

Note also `KODI-06` ("Krypton-era visibility conditions are gone") — `resources/settings.xml:6,7`
carry `visible="!String.IsEmpty(window(home).property(iskrypton))"`. Those disappear for free in a
schema conversion.

### Finding C — `SETUP-04` and `CI-05` collide on the string `client_secret`

`SETUP-04` requires the runbook to carry the `AADSTS7000218` symptom, and `ROADMAP.md` says
"verbatim". The verbatim error text is:

> `AADSTS7000218: The request body must contain the following parameter: 'client_assertion' or 'client_secret'.`

`CI-05` requires CI to "fail on any occurrence of `client_secret`, `client_assertion`, `eval(`, or
`script.module.clouddrive.common`". Writing the runbook as specified makes `CI-05` as specified
fail.

The repository already has the pattern for this. `tests/test_vendor_gates.py:55-56` defines
`EXCLUDED_DOCS = frozenset({'VENDORED.md', 'CREDITS.md', 'COVERAGE.md', 'README.md'})` with the
comment *"the four documents … are **required** to name the upstream module and the original add-on
id. Forgetting them produces a gate that can never go green. They are covered instead by the positive
assertions in …"*.

**Recommendation:** add the runbook path to `EXCLUDED_DOCS`, and pair it with a *positive* assertion
(`test_runbook_contains_aadsts7000218`) so the exclusion buys a stronger gate rather than a hole —
the same trade the four existing documents make. `CI-05` lands in Phase 2, so Phase 3's plan must
either land the runbook plus its exclusion together, or state the ordering dependency explicitly.

### Finding D — `AUTH-20`'s "cache keys isolated per account" has no live cache to isolate

Grepping the tree for `Cache(` finds four construction sites, all inside
`resources/lib/vendor/clouddrive_common/service/source.py` (lines 51-53, 412-414), plus the
`_clear_cache` action in `ui/addon.py:687-689`. `SourceService` is on the deletion list (`KODI-07`,
and Phase 7 criterion 4 which the priority order pulled forward on security grounds). The cache DBs
are `cache_page.db`, `cache_children.db`, `cache_items.db` in the profile root — global, not
per-account.

So the per-account state that actually exists in Phase 3 is exactly two fields, both already inside
the account record: `account['access_tokens']` and `drive['change_token']`. Both are isolated by
construction because they live under an account key.

**Recommendation:** treat the cache clause of `AUTH-20` as a **constraint on Phase 4**, not a Phase 3
deliverable — Phase 4 builds the listing cache, and it must key by account from the start. Phase 3
satisfies `AUTH-20` by proving tokens and delta tokens are per-account, and records the cache clause
as inherited by Phase 4. Do not invent a cache in Phase 3 to have something to isolate.

### Finding E (smaller) — `AUTH-05` as written is not mechanically checkable

"the largest font the skin offers" has no API behind it. Kodi resolves a `<font>` name against the
**active skin's** `Font.xml` at render time; a name the skin does not define falls back silently to
`font13`, which every skin must define. There is no way for an add-on to ask a skin for its largest
font, and no error is raised when the name is wrong.

**Recommendation:** restate as a measurable criterion — "the `user_code` is rendered by a dedicated
label control at a font of at least 60px in 1080i coordinates, and is read from the sofa during the
`CI-06` acceptance pass". See §The Dialog for the concrete font choice and the existing defect.

### Finding F (smaller) — `AUTH-23`'s grep criterion trips on documents that are required to say it

`ROADMAP.md` Phase 3 criterion 2 asks that "a grep finds … no reference to `sign-in-server` or any
external broker anywhere in the tree". Today `README.md:15` and `VENDORED.md:165,200,208` describe
the old broker flow, and they are correct to — `VENDORED.md` is the attribution and modification
record, and both are already in `EXCLUDED_DOCS`. Same resolution as Finding C: the gate excludes
the documents and a positive assertion covers them.

---

## Atomic Token Persistence on Android (AUTH-11, AUTH-12)

### The store must move off SQLite for tokens

`AUTH-11` says "atomically-written JSON under `special://profile/addon_data/`". Today tokens live at
`account['access_tokens']` inside `accounts.db`, a `SimpleKeyValueDb` — SQLite in WAL mode
(`db.py:47-48`). That is not a JSON file, and `PITFALLS.md` §"Testing Pitfalls" lists "SQLite WAL on
Android storage" as a filesystem-dependent risk requiring device testing. The requirement is a
directive to change the mechanism, not a description of what exists.

**Recommendation:** keep `accounts.db` for account metadata (labels, drives, `change_token`) so the
`AccountManager` API survives, and move **only the token blob** to a per-account JSON file. That
keeps the blast radius small, gets the atomic guarantee exactly where `AUTH-11`/`AUTH-13` need it,
and gives the `O_EXCL` lock a natural home next to the thing it protects. Splitting also means a
torn token write cannot corrupt the account list.

### `xbmcvfs` cannot do this job; `os` can

| Need | `xbmcvfs` | `os` |
|---|---|---|
| Atomic replace | `rename(file, newFileName)` only, documented in three words: *"Rename a file"*. No `replace`. | `os.replace` |
| Exclusive create | none — no way to pass `O_EXCL` | `os.open(..., O_CREAT|O_EXCL)` |
| Durability | no `fsync` exposed on `xbmcvfs.File` | `os.fsync` |
| Mode bits | none | mode argument to `os.open`, `os.chmod` |

[CITED: xbmc.github.io/docs.kodi.tv — group__python__xbmcvfs]

`AUTH-14` alone forces `os`, because `O_EXCL` has no `xbmcvfs` equivalent. Using `os` for the token
write too keeps one mental model.

Is `xbmcvfs.rename` atomic anyway? Reading the source: `CFile::Rename` builds the two `CURL`s,
creates the `IFile` loader and returns `pFile->Rename(authUrl, authUrlNew)` — **no copy+delete
fallback and no pre-delete of the destination**, just a delegation. For a local path that reaches
POSIX `rename(2)`, which states: *"If newpath already exists, it will be atomically replaced, so that
there is no point at which another process attempting to access newpath will find it missing."*
[VERIFIED: xbmc/filesystem/File.cpp, man7 rename(2)] So it would probably work — but it is
undocumented, returns a bool, and logs failures rather than raising. Prefer `os.replace`, which is
documented and raises.

### The idiom

`special://profile/addon_data/plugin.onedrive.kn/` is resolved **once** with
`xbmcvfs.translatePath()` (already wrapped as `KodiUtils.translate_path`, `ui/utils.py:227-230`), and
everything after that is plain `os` on a real path. The write sequence:

```python
# Source: composed from man7 rename(2) + Python os docs; no single upstream sample.
import json, os, uuid

def write_tokens(store_path, payload):
    """Atomically replace store_path with payload as JSON.

    store_path must be an OS path already resolved by xbmcvfs.translatePath.
    The temp file lives in the SAME directory: rename(2) fails EXDEV across
    mounts, and on Android a system temp dir is a different mount.
    """
    tmp = '%s.tmp-%s' % (store_path, uuid.uuid4().hex)
    # 0o600 at creation, not chmod after: chmod-after leaves a window in which
    # the file exists at a wider mode. os.replace renames the inode, so the
    # mode set here is the mode the final file has.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as fo:
            json.dump(payload, fo)
            fo.flush()
            os.fsync(fo.fileno())
        os.replace(tmp, store_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

Four things in that snippet are load-bearing and each has a reason a reviewer can check:

1. **Temp file in the same directory.** `rename(2)` returns `EXDEV` when "oldpath and newpath are not
   on the same mounted filesystem". [VERIFIED: man7 rename(2)] On Android the app-private directory
   under `/sdcard/Android/data/org.xbmc.kodi/files/` is not the same mount as anything
   `tempfile.gettempdir()` would return.
2. **A unique temp name.** Two writers must not collide on `.tmp`; `O_EXCL` on a fixed `.tmp` name
   would make the second writer fail rather than proceed.
3. **`fsync` before `replace`.** Without it the rename can land before the data, and a power cut
   leaves a validly-named empty file. (Fsyncing the *directory* afterwards would also make the rename
   itself durable; that is beyond what the requirements ask and can be skipped with a comment.)
4. **`0o600` at creation.** Phase 1 established that from Android 11 the app's own `Android/data`
   bypasses FUSE so the mode genuinely applies. It is defence in depth — the directory is already
   app-private and owned by Kodi's uid — but `PITFALLS.md` Pitfall 18 notes the pre-Android-11 case
   where it is the only protection, and the code should not encode an assumption about which device
   it is on.

**Does `os.replace` work on the Android app-private path?** Yes for the reason above: it is an ext4
or f2fs mount and `rename(2)` is a normal syscall there. The failure mode to watch for is not the
platform, it is a temp file on the wrong mount. `CI-06` allows an API-matched stand-in for exactly
this class of question, so this is provable on the emulator and does not need the TCL.

### `AUTH-12`: merge, never overwrite

Pitfall 3 is the highest-consequence bug in the phase and it is invisible for 90 days. The rule the
code must encode:

```python
def merge_token_response(previous, response):
    """A refresh response omitting refresh_token means 'keep the old one'.
    Never the reverse. Never write a partial blob."""
    merged = dict(previous or {})
    merged.update(response)
    if not response.get('refresh_token') and previous and previous.get('refresh_token'):
        merged['refresh_token'] = previous['refresh_token']
    merged['date'] = time.time()          # the existing field name; Provider sets it
    merged['issued_at'] = merged['date']  # new: makes the inactivity clock observable
    return merged
```

`expires_in` must be read from each response — the spike observed 3655, 4491 and 3599. Never assume
3600. The existing `oauth2.py:97` already computes expiry from the stored `expires_in` with a 600s
skew, so that part is sound.

`issued_at` is a new field and `AUTH-16` needs it. Pitfall 3's advice — "Store `issued_at` alongside,
so the inactivity clock is observable" — is the reason.

**Do not log the token.** Pitfall 3 suggests logging the first 8 characters to observe rotation.
That is the correct amount. See §Security Domain for the redaction site that does not exist yet.

---

## Cross-Process Refresh Serialisation (AUTH-14, AUTH-15)

### Why the forbidden mechanisms are forbidden — with the primary evidence

`STATE.md` records the decision as "the plugin and service are sub-interpreters in one process, so
`threading.Lock` is not shared and `fcntl.lockf` does not exclude them". The `fcntl` documentation
confirms the second half precisely, and it is worth having in front of the planner because the
failure is silent:

> "The record locks described above are associated with the process (unlike the open file description
> locks described below)."
>
> "A single process can hold only one type of lock on a file region; if a new lock is applied to an
> already-locked region, then the existing lock is converted to the new lock type."
>
> "If a process closes *any* file descriptor referring to a file, then all of the process's locks on
> that file are released, regardless of the file descriptor(s) on which the locks were obtained."

[VERIFIED: man7 F_SETLK(2const)]

Read against Kodi: the service sub-interpreter takes an `fcntl.lockf`; the plugin sub-interpreter —
same pid — asks for the same region and is granted it, because a process cannot conflict with
itself. Then the plugin closes its descriptor and the *service's* lock is released too. Two
independent failures in one mechanism, neither of which raises anything.

`threading.Lock` fails one step earlier: each sub-interpreter imports its own copy of the module and
therefore constructs its own `Lock` object. Note the tree already has one —
`KodiUtils.lock = Lock()` at `ui/utils.py:32`, used by `AccountManager.__init__` and the
service-port helpers. Leave it where it is; it is correct for what it guards. It must not be reached
for here.

`os.open(path, O_CREAT|O_EXCL)` asks the *filesystem* whether the name already exists. Nothing about
process identity, thread identity or interpreter identity enters into it. That is the whole reason
`AUTH-14` names it.

### What a correct stale-lock breaker looks like here

The usual breaker reads a pid out of the lock file and checks `os.kill(pid, 0)`. **That is degenerate
in Kodi**: the holder's pid is Kodi's pid, and Kodi is by definition alive, because it is the thing
asking. A pid check would never break a lock, including the one left behind by a sub-interpreter
that died mid-refresh.

Two signals are available and they answer different questions:

**Signal 1 — the Kodi session id, for "the holder is definitely gone".**
`KodiUtils.get_home_property` / `set_home_property` (`ui/utils.py:374-387`) read and write properties
on window 10000, which is shared across every sub-interpreter in a Kodi session and cleared when
Kodi restarts. The service writes a fresh `uuid4().hex` there at startup; every lock file records
the session id it was created under. A lock whose session id differs from the current one was left
by a previous Kodi run and is stale **immediately**, with no waiting. That covers the crash and the
force-stop cases, which on an Android TV box are the common ones.

**Signal 2 — age, for "the holder is stuck".**
Within one session, only time can decide. And the clock question matters: `time.monotonic()` has a
per-process arbitrary epoch and is meaningless once written to a file that survives a restart, so it
cannot be used. Wall time it must be — but do not write a timestamp *into* the file and compare it
against the reader's clock. Use the lock file's own `os.stat().st_mtime`, and compare with
`time.time()`. On one device that is one clock on both sides of the comparison, which removes the
"whose clock?" question entirely; the residual risk is only an NTP step *between* create and check.

Guard the step anyway. Android TV boxes without an RTC set the clock at boot, so a jump is a normal
event, not an exotic one:

```python
age = time.time() - os.stat(lock_path).st_mtime
if age < 0:
    # mtime in the future: the clock stepped backwards. Treat as "unknown",
    # not as "fresh" and not as "stale" - wait one poll and re-read. If it is
    # still in the future, break it: a permanently-future lock is unbreakable.
```

**Choose the TTL against the real worst case, not a round number.** `Request` defaults to
`tries=4, delay=5, backoff=2` with `HTTP_TIMEOUT_SECONDS = 30`, and its own comment computes the
worst-case wall time as `4*30 + 5 + 10 + 20 = 155 seconds` (`remote/request.py:44-48`). A TTL shorter
than that will break the lock held by a *live, working* refresh. Two ways to close it, and the second
is better:

- TTL ≥ 180s. Correct, but it means a genuinely wedged refresh blocks the other side for three
  minutes.
- **Give the token refresh its own request profile** — `tries=1` or `tries=2`, no long backoff ladder
  — and set the TTL to ~60s. A token refresh has no business sitting on a 155-second retry ladder;
  if it fails, the caller has a defined recovery path (`AUTH-15`, and re-auth). **Recommended**, and
  it is a smaller change than it sounds: `Request` already takes `tries`/`delay`/`backoff` as
  constructor arguments.

Also have the holder touch the lock (`os.utime`) if the operation is going to outlive the TTL. With
the recommended short request profile that should never happen, which is the point.

**Breaking must itself be race-safe, and does not have to be perfect.** Two contenders can both
decide a lock is stale. The safe sequence is: rename the stale lock aside
(`os.replace(lock, lock + '.stale-' + uuid4().hex)`) then retry the `O_EXCL` create — whoever wins
the recreate wins, and the loser sees `FileExistsError` and waits. Then delete the renamed-aside
file. The reason a residual double-break is survivable is `AUTH-15`: a loser that refreshes anyway
and gets `invalid_grant` re-reads the store and adopts the winner's token. **The breaker is allowed
to be imperfect precisely because AUTH-15 is the backstop.** Say this in the code comment; it is the
kind of reasoning that gets "hardened" into a worse design later.

### Sketch

```python
# Source: composed. No upstream sample; the shape follows from AUTH-14 + the
# fcntl(2) constraints above.
class RefreshLock(object):
    TTL_SECONDS = 60          # must exceed the refresh request's worst case

    def __init__(self, lock_path, session_id, sleep):
        self._path = lock_path
        self._session = session_id     # from KodiUtils.get_home_property
        self._sleep = sleep            # Monitor.waitForAbort; returns True on abort
        self._fd = None

    def acquire(self, timeout):
        deadline = time.time() + timeout
        while True:
            try:
                self._fd = os.open(self._path,
                                   os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.write(self._fd, json.dumps({'session': self._session}).encode())
                return True
            except FileExistsError:
                if self._is_stale():
                    self._break()
                    continue
                if time.time() >= deadline or self._sleep(0.5):
                    return False       # caller proceeds as the LOSER, see AUTH-15

    def release(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            os.unlink(self._path)
        except OSError:
            pass                       # already broken by someone else; fine
```

The `acquire` failure path returning `False` rather than raising is deliberate: **failing to get the
lock is a normal outcome**, and the caller's response is to wait a moment, re-read the store, and use
whatever the winner wrote.

### AUTH-15: the loser adopts the winner's token

The order matters. The loser must re-read **from disk**, not from whatever it loaded before the race:

```
1. try acquire  -> failed, someone else is refreshing
2. wait briefly (Monitor.waitForAbort), then re-read the token file
3. if the re-read blob's access_token differs from the one we started with,
   the winner finished: use it. Done. No network call at all.
4. if it is unchanged, the winner may still be in flight; wait and retry a
   bounded number of times.
5. only if the lock is still held past the TTL do we break it and refresh.
```

And the symmetric path — the loser refreshed anyway (it raced through step 1 before the winner
wrote) and Entra answered `invalid_grant` because the refresh token was already redeemed and
rotated: re-read the store, and if the stored `refresh_token` differs from the one just rejected,
**adopt it and do not sign the user out**. Only when the stored token is byte-identical to the one
that was rejected is `invalid_grant` a genuine dead grant.

That last condition is the whole test for `AUTH-15` and it is testable off-device: two fixtures, one
where the store moved on and one where it did not, and assert the first does not produce a re-auth
prompt.

---

## Polling Without Blocking Shutdown (AUTH-09, AUTH-10, ERR-03)

### RFC 8628, verbatim

> `authorization_pending` — "The authorization request is still pending as the end user hasn't yet
> completed the user-interaction steps."
>
> `slow_down` — "A variant of `authorization_pending`, the authorization request is still pending and
> polling should continue, but the interval MUST be increased by 5 seconds for this and all
> subsequent requests."
>
> `access_denied` — "The authorization request was denied."
>
> `expired_token` — "The `device_code` has expired, and the device authorization session has
> concluded."

Section 3.4: clients "MUST wait at least the number of seconds specified by the `interval` parameter
of the device authorization response … or 5 seconds if none was provided." Error responses follow
RFC 6749 §5.2, which is **HTTP 400 with a JSON body** — that is the whole of `AUTH-10`.
[CITED: rfc-editor.org/rfc/rfc8628]

"for this and all subsequent requests" is the permanence `AUTH-09` cares about: `interval += 5` and
it never comes back down. `verify_device_code.py:146-149` already does this and comments it.

`AUTH-09`'s allow-list is `{authorization_pending, slow_down}` and nothing else. The reason it must
be an allow-list rather than a deny-list is already written in the reference implementation's
comment — Microsoft returns undocumented error codes, and a deny-list loops forever on a real
failure.

### Two clocks, not one

The vendored loop (`ui/addon.py:206-215`) drives the countdown and the poll from the same tick and
disambiguates with `if int(remaining) % 5 == 0`. That silently couples the UI refresh rate to the
poll interval and breaks the moment `slow_down` pushes the interval to 10 or 15. Separate them:

```python
# Source: composed from RFC 8628 + the existing loop's waitForAbort usage.
interval = int(device_code_response.get('interval', 5))
deadline = time.time() + int(device_code_response['expires_in'])  # server value, never 900
next_poll = time.time()          # poll immediately, then respect interval

while True:
    now = time.time()
    if now >= deadline:
        return EXPIRED           # -> dialog offers "Get a new code", focused
    dialog.set_remaining(int(deadline - now))     # 1 Hz countdown

    if now >= next_poll:
        state, payload = poll_once()              # HTTP 400 + JSON is normal here
        if state == 'ok':
            return payload
        if state == 'slow_down':
            interval += 5                         # permanent, RFC 8628 3.5
        elif state != 'authorization_pending':
            return terminal(payload)              # allow-list: everything else stops
        next_poll = time.time() + interval

    if monitor.waitForAbort(1):                   # 1s UI tick AND the abort check
        return ABORTED
    if dialog.iscanceled():
        return CANCELLED
```

`Monitor.waitForAbort(1)` is the only sleep in the loop. It returns `True` when Kodi is shutting down,
so a shutdown is noticed within one second regardless of where the interval clock is. This is the
same pattern `cancel_operation()` already uses (`ui/addon.py:133` reads
`self._system_monitor.abortRequested()`). **Never `time.sleep` and never `xbmc.sleep` in this loop** —
neither observes the abort flag, and `ERR-03` ("quitting Kodi with work in flight shuts down
cleanly") is a Phase 4 requirement this phase must not pre-break.

### On abort, what happens to the dialog

`route()`'s `finally` block already closes `self._pin_dialog` (`ui/addon.py:711-714`), which is the
right place — it runs on the exception path and the abort path alike. Two things to add:

- Nothing may be persisted on the abort or cancel path. `AUTH-07` is satisfied by writing the
  account **exactly once, last** — see §Account Write Ordering.
- `QRDialogProgress.__del__` calls `xbmcvfs.delete(self._image_path)` where `_image_path` is `None`
  until `onInit` runs (`ui/dialog.py:112-115`). A dialog constructed and then abandoned before
  `onInit` — which is exactly what an immediate abort produces — calls `xbmcvfs.delete(None)` inside
  `__del__`, where Python swallows the error as "Exception ignored in `__del__`". Guard it.

### Where the 15-minute loop lives — a design decision the planner must make

`_DEFAULT_SIGNIN_TIMEOUT = 120` (`ui/addon.py:48`) caps the current loop at two minutes against a
server-supplied `expires_in` of ~900. `AUTH-06` wants the countdown to run to the real expiry, so the
constant goes. That raises the question of what is waiting on the loop.

Today "Add an account…" is a plain directory item (`ui/addon.py:168-171`, a 2-tuple so `isFolder`
defaults false) whose handler never calls `endOfDirectory` or `setResolvedUrl`. Kodi is left holding
a handle for the whole sign-in. At 120s that is merely rude; at 900s it blocks a container fetch for
a quarter of an hour.

Recommended shape: the row's handler releases the handle immediately and re-enters through
`RunPlugin`, which invokes a plugin with `sys.argv = [path, '-1', '']` — an intentionally invalid
directory handle, and the documented way to run a plugin action that is not a listing.
[CITED: forum.kodi.tv/showthread.php?tid=42073; corroborated by `resources/lib/addon.py:242-244`,
which already guards on `self._addon_handle >= 0`] The context-menu actions in `list_accounts`
already use `RunPlugin(...)` for `_remove_account`, so this is the file's own existing idiom, not an
import. On success the worker calls `Container.Refresh`, which `ui/addon.py:267` already does.

Confidence on this one is MEDIUM — it follows from documented behaviour and from the tree's own
patterns, but it has not been run. Plan it as a task with an observation step rather than as a
settled fact.

---

## The Dialog (AUTH-05, AUTH-06, AUTH-07, AUTH-08)

### What exists

`resources/skins/default/1080i/pin-dialog.xml`, 86 lines, a 1150×450 panel at (385, 315) in 1080i
coordinates, with four controls:

| id | type | current font | current use |
|---|---|---|---|
| 1000 | label | `font30_title` | heading (add-on name) |
| 1001 | image | — | QR, 340×340 at (20, 90) |
| 1002 | textbox | `font12_title` | all three text lines joined with `[CR]` |
| 1003 | button | `font12_title` | Cancel, label `222` (Kodi's built-in "Cancel") |

`QRDialogProgress` (`ui/dialog.py:96-170`) is a `WindowXMLDialog` that renders the QR in `onInit`
from `pyqrcode` into `<profile>/qr-<uuid4>.png`, sets the three labels through `update()`, and
handles `ACTION_PREVIOUS_MENU` / `ACTION_NAV_BACK` as cancel. Phase 1 smoke-tested it twice per
session and confirmed two distinct image paths. It is driven with `show()` plus a caller-side loop,
never `doModal()`.

`show()` is non-blocking and activates the window; `close()` reactivates the previous one; **"if your
script ends, the window will close too"**, so the caller must keep running — which the poll loop
does. `doModal()` blocks. [CITED: xbmc.github.io docs — `python__xbmcgui__window`]

### What has to be added, and one defect that is already there

**1. The code needs its own control.** Today the `user_code` would go into the shared textbox at
`font12_title`. Estuary's `Font.xml` defines `font10, font12, font13, font14, font23_narrow,
font25_narrow, font27, font27_narrow, font32, font37, font45, font60, font_clock, font_flag,
font20_title, font25_title, font30_title, font32_title, font36_title, font40_title, font45_title,
font52_title, font_MainMenu, WeatherTemp, Mono26` — in both the Default and Arial fontsets.
**There is no `font12_title`.** [CITED: xbmc/addons/skin.estuary/xml/Font.xml] When Kodi cannot
resolve a font name it falls back to `font13`, which every skin is required to define, and ultimately
to a hard-coded `arial.ttf`. [CITED: kodi.wiki/view/Fonts] So the existing dialog silently renders
its body text at `font13` (30px in Estuary) and always has. Nothing errors; nothing logs.

That is the trap for `AUTH-05`: **naming a font wrongly is invisible.** A verification step that
greps the XML for a big font name proves nothing. The check has to be the `CI-06` acceptance pass on
the TCL, with a human reading the code from the sofa.

Concrete recommendation: add a dedicated `<control type="label">` for the code with
`<font>font60</font>` — 60px, present in both Estuary fontsets. A 9-character Microsoft user code at
60px is roughly 320px wide, which fits the 770px text region with room to spare, so the layout can
be rebalanced to give the code the full panel width and shrink the QR. `font52_title` (52px) and
`font45` (45px) are the fallbacks if 60 proves too wide once a real code is on screen. Do **not**
reach for `WeatherTemp` (120px) — it is Estuary-specific in a way `font60` is not.

Also fix `font12_title` → `font27` (or `font25_title`) while in the file, so the supporting text
renders at a chosen size rather than at the fallback.

**2. The countdown does not need a thread.** `AUTH-06` reads like it needs one; it does not.
`show()` is non-blocking, so the caller's poll loop already ticks once a second on
`Monitor.waitForAbort(1)` and can call a setter on the dialog each tick. That is the existing
pattern — `ui/addon.py:206-215` already recomputes `remaining` and calls `self._pin_dialog.update(...)`
every second. Adding a worker thread would be strictly worse: `WindowXMLDialog` callbacks run on the
GUI thread, and mutating controls from a second Python thread while `onInit` may still be running is
how the "stuck on BusyDialog" class of bug is produced. **Keep it single-threaded.**

**3. `update()` steals focus every tick — this directly blocks `AUTH-06`.**
`ui/dialog.py:158` ends `update()` with `self.setFocus(self.getControl(self._cancel_btn_control))`.
Called once a second by a countdown, that forcibly returns focus to Cancel every second. `AUTH-06`
requires that on expiry a **"Get a new code" arrives focused** — impossible while `update()` is
re-focusing Cancel behind it. Move the focus call out of `update()` into `onInit`, and have the
expiry transition set focus explicitly and once.

**4. A second button.** `AUTH-06`'s "Get a new code" needs control id 1004 in the XML and an
`onClick` branch. On expiry: stop the poll loop, swap the text, show and focus 1004, hide or leave
Cancel. Clicking it re-runs the device-code request and restarts the loop with a fresh
`expires_in` — which, per the spike, will be a *different* number each time (3655 / 4491 / 3599
observed), so the countdown must re-read it and not reuse the previous value.

**5. D-pad focus order.** Two buttons on a TV means a defined left/right order and a defined initial
focus. `<onleft>` / `<onright>` on the button controls. This is precisely what an emulator cannot
answer (`CI-06`) and what the TCL pass exists to check.

**6. `AUTH-08` — the QR carries `verification_uri` and nothing else.** The server returns
`https://login.microsoft.com/device`, not the `microsoft.com/devicelogin` most documentation cites,
and `verification_uri_complete` is absent, so the QR *cannot* carry the code. Pass the server value
straight through. One cheap validation before rendering: assert it parses as an `https://` URL. The
value arrives over TLS from Microsoft so the trust comes from the transport, but a QR is a thing a
human is told to point a camera at, and asserting the scheme costs one line.

**7. Copy for personal accounts.** Pitfall 5 names it: personal-account users are asked to sign in
again on the phone, and read that as failure. One line of copy. Cheap, and `S2` defers the personal
*testing*, not the copy.

### `AUTH-07` — account write ordering

`_add_account` currently writes at 75% (`save_account`) and then does more work at 90%, with
`if self.cancel_operation(): return` scattered between steps. The rule that makes `AUTH-07` provable
rather than argued: **build the complete account record in memory, and call `save_account` exactly
once as the last statement.** Every cancel check before that point returns without having written
anything, so "no partially-created account" is a structural property rather than a sequence of
guards that must each be right.

The 90% block (`ui/addon.py:249-262`) that removes a `'migrated'` account is v2.3.0 legacy —
`STATE.md` records that no migration path exists by design. It also calls
`remove_account(driveid)` while accounts are keyed by `account['id']`, so it is wrong as well as
dead. Delete it.

---

## Multi-Account Structure (AUTH-20, AUTH-21, AUTH-22)

### The list is already most of the way there

`list_accounts()` (`ui/addon.py:137-173`) already builds the root as an account/drive list with an
"Add an account…" row (string `32005`) and a per-row context menu carrying Search, Remove account,
and — when the account has more than one drive — Remove drive. `AUTH-22` therefore needs **one new
context option, "Re-authorise"**, and the routing to reach it.

The interesting structural change comes from Phase 4, not this phase. `AUTH-22` says the root is the
*account* list; the code emits one row per **drive**, nested under each account. `BROWSE-08` fixes
`GET /me/drive` — singular — as the only endpoint that serves both account classes. One drive per
account means the two lists converge and the nesting disappears. Two consequences:

- The `size > 1` branch that offers "Remove drive" becomes unreachable, and `_remove_drive` becomes
  dead code. Decide in Phase 3 whether to delete it or leave it for `AUTH-24` (SharePoint, v2), and
  **record the decision** — `SPIKE-DEVICE-CODE.md` documents that this codebase's last piece of
  "dead" code was actually load-bearing and merely unexplained.
- `get_drives()` in `provider/onedrive.py:46-70` currently calls `/drives`, swallows the 403, then
  calls `/me/drives`. Both are wrong per the measured matrix. That rewrite belongs to `BROWSE-08` in
  Phase 4, but Phase 3 calls `get_drives()` during sign-in (`ui/addon.py:233`), so Phase 3 either
  fixes it or sign-in fails on a personal account and does a wasted 403 round trip on a business one.
  **Flag this as a Phase 3 / Phase 4 boundary crossing the planner must place deliberately.**

### Per-account isolation on disk

| State | Today | After Phase 3 |
|---|---|---|
| Account record (id, name, drives) | `accounts.db` row keyed by `account['id']` | unchanged |
| `access_tokens` | nested inside that row | **moves out** to `tokens/<account_key>.json`, mode 0600 |
| Refresh lock | does not exist | `tokens/<account_key>.lock` — per account, so two accounts never contend |
| `change_token` (delta) | `drive['change_token']` inside the account record | unchanged; already per-account by construction |
| Listing cache | `cache_page.db` etc., global, only used by `SourceService` | see Finding D — a Phase 4 concern |

`<account_key>` must be filesystem-safe. `sub` from the `id_token` is a base64url pairwise identifier
and is already safe for a filename, which is a second reason to prefer it over `me['id']`.
`SPIKE-DEVICE-CODE.md` established it is per-app and per-user, and runs 1 and 2 — two users in one
tenant — returned different `sub` values, which is the direct evidence for the isolation requirement.

### `AccountManager` interaction

`AccountManager` (`account.py`) does not need to change shape. `save_account` / `get_accounts` /
`remove_account` keep working on the metadata. Add a `TokenStore` collaborator that the provider
consults instead of `account['access_tokens']`:

- `Provider.get_access_tokens()` (`remote/provider.py:66-67`) currently returns
  `self._account_from_manager()['access_tokens']` → becomes a `TokenStore.read(account_key)`.
- `Provider.persist_access_tokens()` (`remote/provider.py:78-81`) currently mutates the account and
  re-saves it → becomes `TokenStore.write(account_key, merged)` under the lock.

That is a two-method seam, and it is the same seam `AUTH-13`, `AUTH-14` and `AUTH-15` all test
against.

`remove_account` must delete the token file too, or a removed-and-re-added account inherits a stale
blob. Small, easy to forget, and it produces a confusing bug.

---

## Proactive Startup Refresh (AUTH-16, AUTH-17)

`AUTH-16` wants a refresh on Kodi startup well inside the refresh token's 90-day lifetime;
`AUTH-17` forbids the background service from ever opening a sign-in dialog. Those two together
define the shape completely: **the service refreshes silently and records a flag; the plugin is the
only thing that may prompt.**

Design:

1. `service.py` runs at Kodi start. For each account, read the token blob and look at `issued_at`.
2. Refresh only if `now - issued_at > N days`. Pitfall 3 recommends `N ≈ 60` against a 90-day
   window; anything from 14 to 60 satisfies "well inside". Refreshing on *every* start also works and
   is simpler, at the cost of a network call and an atomic write per Kodi launch — prefer the
   threshold, because every write is a chance to leave a `.tmp-` file behind on a device that gets
   power-cut rather than shut down.
3. The refresh goes through the same `RefreshLock` the plugin uses. This is the exact scenario
   `AUTH-14` exists for: Kodi starts, the service begins a proactive refresh, and the user
   immediately opens the add-on.
4. On failure, **do not prompt**. Write `needs_reauth: true` into the *account record* (not the token
   file — the token file may be unreadable, which is one of the failure modes), and optionally raise
   a `KodiUtils.show_notification` (`ui/utils.py:186-189`, non-modal, already in the tree).
5. `list_accounts()` renders a `needs_reauth` account with a distinguishing label and points its
   default action at re-authorise instead of at browsing. The user chooses to sign in; the plugin —
   which is allowed to prompt — opens the dialog. This is also how `AUTH-18`'s tenant-block message
   reaches a user who was signed in and then got blocked.
6. Startup ordering: a service starting at boot frequently has no network yet. Bound the attempt
   (`Monitor.waitForAbort` between retries, a small number of tries) and treat "no network" as *not*
   `needs_reauth` — a transient failure must not mark an account as needing a sign-in. `PITFALLS.md`
   §Security/UX and `ERR-02` both care that "no network" and "expired token" are distinguishable.

The 90-day figure and the `AADSTS700082` / `AADSTS70008` / `AADSTS50173` symptoms are already
documented in `PITFALLS.md` Pitfall 3. Cited, not re-derived.

---

## The AADSTS Error Map (AUTH-18, and the input to ERR-02)

`ROADMAP.md` criterion 1a names four codes; `PITFALLS.md` Pitfall 4 tables nine. Implement over the
union, defensively, and mark `AUTH-18` **unverified against a genuinely blocking tenant** — the E5
tenant permits device code flow, so no blocking response can be produced on demand.

Mechanics that matter:

- Parse with `re.search(r'AADSTS\d+', error_description)`. The code is buried in a paragraph-length
  `error_description` that also contains markdown links; never render that blob on a TV.
- Route on the code. Unmapped codes fall through to a generic sentence **that still shows the bare
  code** — a code the user can read off the screen and paste into an issue is worth more than a
  friendly sentence.
- The "admin must act" family must name the escape hatch explicitly, because the setting is worthless
  if the user never learns it exists. This is what makes `AUTH-18` and `AUTH-19` one feature rather
  than two.
- `AADSTS7000218` is the one code that can only be triggered *after shipping* by a user who set a
  custom `client_id` and left "Allow public client flows" off. Its message should be aimed at that
  person, not at the maintainer.

One concrete task straight from `ROADMAP.md` criterion 1a, easy to lose: **make the terminal-error
branch of `verify_device_code.py` persist the failing response to a file.** It currently prints and
discards (`verify_device_code.py:157-166`), which is how an earlier observed failure was lost.

---

## Runtime State Inventory

This phase is not a rename or a migration, but it *removes* a working dependency and *introduces* a
new on-disk shape, so the same questions apply.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None.** `plugin.onedrive.kn` is a new add-on id with a new profile; `STATE.md` records "no migration path exists, by design". There is no prior `accounts.db` for this id, no prior tokens, no prior settings values. Verified: `ID-01` complete, and the id has never shipped. | Nothing to migrate. Do **not** import Pitfall 17's migration into this phase |
| Live service config | **The Azure app registration itself** — `efe197b3-5c14-4d67-810f-e10406742a06` on the E5 Developer tenant. It exists only in the Entra portal; nothing in the repo can recreate it. That is exactly `SETUP-04` | Write the runbook. See §SETUP-04 |
| OS-registered state | **None.** No Task Scheduler, no pm2, no systemd. The Kodi service starts from `addon.xml`'s `xbmc.service` extension point, which is already in the tree | None |
| Secrets / env vars | **None, and this is a design property, not an accident.** `SETUP-03` is satisfied: no `passwordCredentials`, no `keyCredentials`, nothing in the repo. The `client_id` is public by design and belongs in source. Verified via the manifest read-back in `SPIKE-DEVICE-CODE.md` | Keep it that way; `CI-05` is the gate |
| Build artefacts | `__pycache__/*.cpython-311.pyc` throughout the tree, untracked. `tests/test_vendor_gates.py` reads `git ls-files`, not a filesystem walk, precisely so these cannot influence a verdict | None. Note that Kodi 21 ships Python 3.8 and Kodi 22 ships 3.14 (`STATE.md`), so 3.11 `.pyc` files are local-only artefacts |
| **Third-party runtime dependency being removed** | `drive-login.herokuapp.com` was measured **alive** on 2026-08-22, not dead. `_add_account` makes a live call to `<signin-server>/ip` at `ui/addon.py:190` before anything else | This is the removal of a working third-party dependency, not dead-code cleanup. See §AUTH-23 |

---

## AUTH-23 Removal Map

Every site, from `grep -rn "signin\|sign-in-server\|get_signin_server\|drive-login\|herokuapp"`.
Fourteen of them, in five groups.

**Group 1 — the module that only exists to talk to the broker.**

| File | Disposition |
|---|---|
| `resources/lib/vendor/clouddrive_common/remote/signin.py` (66 lines, whole file) | **Delete.** Every method — `create_pin`, `fetch_tokens_info`, `refresh_tokens` — posts to the broker. Its replacement is the new device-code client |

**Group 2 — the `Provider` methods that call it.** `remote/provider.py`

| Line | Site | Disposition |
|---|---|---|
| 23 | `from ...remote.signin import Signin` | delete |
| 31 | `_signin = Signin()` | delete |
| 41 | `create_pin()` → `self._signin.create_pin(...)` | **rewrite** → `POST /{authority}/oauth2/v2.0/devicecode` |
| 44 | `fetch_tokens_info()` → `self._signin.fetch_tokens_info(...)` | **rewrite** → one poll of `POST /{authority}/oauth2/v2.0/token` |
| 75 | `refresh_access_tokens()` → `self._signin.refresh_tokens(name, refresh_token, ...)` | **rewrite** → `grant_type=refresh_token`, under the lock, with the `AUTH-12` merge |

Note the method *names* (`create_pin`, `fetch_tokens_info`) are broker vocabulary. `AUTH-23` says
"every code path referencing an external OAuth broker are gone" — renaming to
`request_device_code` / `poll_for_token` makes the grep criterion honest instead of technically
passing while the pin vocabulary survives.

**Group 3 — the live network call and the IP-change heuristic.** `ui/addon.py`

| Line | Site | Disposition |
|---|---|---|
| 190 | `self._ip_before_pin = Request(get_signin_server() + '/ip', None).request()` | **delete.** This is the live third-party call, made before anything else in sign-in |
| 201 | QR encodes `get_signin_server() + '/signin/%s' % pin` | **rewrite** → the server-supplied `verification_uri` (`AUTH-08`) |
| 203 | Body text interpolates the signin server and the pin | **rewrite** → the `user_code` in its own control (`AUTH-05`) |
| 629 | `if get_signin_server() in rex.request or httpex.code == 401:` | **rewrite** → the 401 half stays as a re-auth trigger; the broker half goes |
| 645-646 | The `/pin/` 404 + IP-changed heuristic, which makes a **second** live `/ip` call inside the error handler | **delete.** Strings `32072`/`32073` become orphaned |
| 68 (class attr) | `_ip_before_pin = None` | delete |

**Group 4 — the accessor and the setting.**

| File | Site | Disposition |
|---|---|---|
| `ui/utils.py:204-206` | `KodiUtils.get_signin_server()` | delete |
| `remote/errorreport.py:37` | `report_url = get_signin_server() + '/report'` | Deleting `get_signin_server` breaks this. `KODI-08` deletes the whole error reporter; Phase 7 criterion 4 is already pulled forward on security grounds. **Delete the reporter here** rather than leaving a broken reference — and with it the `send_report` call at `ui/addon.py:679` and the `report_error` / `report_error_invite` prompt at `674-678` |
| `resources/settings.xml:21` | `<setting label="30033" type="text" id="sign-in-server" default="https://drive-login.herokuapp.com"/>` | delete. String `30033` becomes orphaned |

**Group 5 — the documents.**

| File | Site | Disposition |
|---|---|---|
| `addon.xml:44-57` | `<disclaimer>` telling users their tokens go to a third-party sign-in server, and linking `github.com/cguZZman/drive-login` | **Rewrite.** `PITFALLS.md` §Security Mistakes names this: users are currently told their tokens go somewhere they no longer do. The new text describes device code flow against Microsoft directly, with no third party |
| `README.md:15` | Describes the old broker flow | Update to describe the new flow |
| `VENDORED.md:165, 200, 208` | Records the `signin.py` local modification and explains why a fresh profile looks empty | **Update, do not erase.** `VENDORED.md` is the modification record; deleting `signin.py` is itself a modification to record |

Both `README.md` and `VENDORED.md` are already in `EXCLUDED_DOCS` — see Finding F.

**One thing the removal cannot do:** on any machine where the old `plugin.onedrive` was installed,
the *stored* `sign-in-server` value survives in that add-on's own `settings.xml`. It is a different
add-on id with a different profile, so it is not this add-on's to clear, and there is nothing to do
about it. Noted so it is not mistaken for an omission.

---

## SETUP-04 Runbook Contents

The framing that matters: this is **not** documentation for strangers. The registration lives on a
Microsoft 365 E5 Developer tenant that renews on activity. If it lapses, the embedded `client_id`
dies for every installed copy simultaneously — including the one on the owner's own television. The
runbook is the recovery procedure for an outage that takes out the primary user.

Required contents, in order:

1. **What this is and why the `client_id` is public.** One paragraph. Pre-empts the "you committed a
   credential" reading of a GUID in source.
2. **The current registration, as a table of exact values** — copied from `SPIKE-DEVICE-CODE.md`:
   `appId efe197b3-5c14-4d67-810f-e10406742a06`, `displayName` "Kodi OneDrive Add-on",
   `publisherDomain e5.nguyentiendat.net`, `signInAudience AzureADandPersonalMicrosoftAccount`,
   `requestedAccessTokenVersion 2`, `isFallbackPublicClient true`, `passwordCredentials` and
   `keyCredentials` both empty, no redirect URIs in `publicClient`/`web`/`spa`, `verifiedPublisher`
   null.
3. **Numbered recreation steps**, with two traps called out inline:
   - Set "Supported account types" **before** anything else: once `signInAudience` is
     `AzureADandPersonalMicrosoftAccount` the portal will no longer let you change it from the UI,
     only through the manifest editor (`ROADMAP.md` prerequisite 1).
   - "Allow public client flows" lives under Authentication → **Advanced settings**, visually
     separated from platform configuration, and defaults to **off** (Pitfall 2).
4. **The `AADSTS7000218` symptom, verbatim**, as its own callout:
   `AADSTS7000218: The request body must contain the following parameter: 'client_assertion' or 'client_secret'.`
   Immediately followed by: **do not fix this by adding a client secret.** Pitfall 2 records that
   teams have shipped a secret to "fix" it, and `SETUP-03` forbids it. This paragraph is the entire
   reason `SETUP-04` exists.
   *(This is the string that collides with `CI-05` — see Finding C.)*
5. **Verify by reading the manifest back through Graph, not from the portal UI.** That is what
   `SETUP-01`/`-02`/`-03` each demand and how they were satisfied. Give the request.
6. **Acceptance check:** run `python .planning/research/verify_device_code.py --client-id <GUID>`
   with a work/school account and confirm STEP 3 reports `refresh_token: YES`. The script is the
   runbook's test.
7. **Swapping the `client_id`:** name the single source constant, and name the Expert-level setting
   (`AUTH-19`) as the per-user escape hatch. State that the authority is *not* user-configurable
   (Pitfall 1 point 4).
8. **Tenant-lapse plan** (`REL-01`): the symptom (`AADSTS700016` "application wasn't found in the
   directory/tenant", or `AADSTS90002`), the fact that it hits every installed copy at once, and the
   alternative — registering under a personal Microsoft account, which has no expiry. `STATE.md`
   carries this as an open concern; the runbook is where the answer gets written down.
9. **Explicit non-steps:** no client secret, no certificate, no redirect URI. Delegated permissions
   are consented dynamically at sign-in in the v2.0 endpoint — the spike proved this works with
   nothing pre-declared, so a `requiredResourceAccess` entry is optional. (Adding one does make an
   admin-consent URL usable, which is worth a sentence for the tenant-blocked case.)

**Location:** a tracked path outside `.planning/` — `SETUP-04` says "lives in the repo", and
`.planning/` is excluded from the gates and is planning record rather than product. `docs/AZURE-REGISTRATION.md`,
linked from `README.md`. Note that whatever path is chosen must be added to `EXCLUDED_DOCS` (Finding C).

---

## Standard Stack

No new third-party dependency. This is a deliberate constraint, not an omission: `verify_device_code.py`
was written stdlib-only "the same constraint the add-on runs under inside Kodi", and Kodi's bundled
Python has no `requests` and no `msal`.

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` / `urllib.parse` | stdlib | HTTP for devicecode/token | Already the transport in `remote/request.py`; `VND-06` gave every call an explicit `timeout=` |
| `json` | stdlib | Token store, protocol bodies | `VND-05` already converted the store off `repr()`/`eval()` |
| `os` | stdlib | `O_EXCL` lock, `os.replace`, mode bits | The only module that can express `AUTH-11` and `AUTH-14` |
| `base64` | stdlib | Decode the `id_token` payload for display | Already used this way in `verify_device_code.py:69-77` |
| `re` | stdlib | `AADSTS\d+` extraction | Pitfall 4 |

### Supporting (already vendored, no action)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `resources.lib.vendor.pyqrcode` | 1.2.1+matrix.4 | QR for `verification_uri` | `AUTH-08`. Vendored from the Kodi omega add-on zip, provenance in `VENDORED.md` |
| `xbmc` / `xbmcgui` / `xbmcvfs` / `xbmcplugin` | Kodi 20+ (`xbmc.python 3.0.1`) | Dialog, Monitor, routing, path translation | Kodi layer only |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled device-code client | `msal` | Not available in Kodi's Python; vendoring it means vendoring its dependency tree into a GPL add-on. The protocol is ~80 lines and is already written and measured |
| `os.replace` | `xbmcvfs.rename` | Probably atomic (see §Atomic Token Persistence) but undocumented, bool-returning, and cannot express `O_EXCL` — so `os` is needed regardless |
| `sub` as the account key | `me['id']` (Entra object id) | `me['id']` needs `GET /me`, which the locked scope set cannot call (Finding A) |
| Threaded countdown | Caller-side loop after `show()` | `show()` is non-blocking; a thread adds GUI-thread hazards for no benefit |

**Installation:** none. No `pip install`, no new `<import>` in `addon.xml`.

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.** Everything used is either Python
standard library or already vendored and provenance-recorded in `VENDORED.md` (`VND-09`). No
`npm install`, no `pip install`, no new `addon.xml` `<import>`. `VND-11` removed the last external
import in Phase 1.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌──────────────── Microsoft identity platform ─────────────────┐
                         │  POST /common/oauth2/v2.0/devicecode                         │
                         │  POST /common/oauth2/v2.0/token   (400 + JSON = protocol)    │
                         └──────────────────────────────────────────────────────────────┘
                                    ▲                              │
                        device_code │                              │ id_token + access + refresh
                        + user_code │                              ▼
   ┌─── Kodi layer ────────────────────────────┐   ┌─── Pure core: resources/lib/auth/ ───────────┐
   │                                           │   │                                              │
   │  plugin (entrypoint.py)                   │   │  device_code.py                              │
   │    root  -> list_accounts                 │   │    request_device_code()                     │
   │    row   -> "Add an account..."           │──▶│    poll_once()  -> pending|slow_down|ok|term │
   │             RunPlugin, handle = -1        │   │    ALLOW = {authorization_pending,slow_down} │
   │    ctx   -> re-authorise / remove         │   │                                              │
   │                                           │   │  errors.py                                   │
   │  QRDialogProgress (pin-dialog.xml)        │   │    AADSTS\d+ -> (sentence, action)           │
   │    1000 heading                           │   │                                              │
   │    1001 QR  <- verification_uri ONLY      │   │  store.py                                    │
   │    1004 user_code   font60   NEW          │   │    read()  -> dict                           │
   │    1002 body + countdown                  │◀──│    write() -> tmp+fsync+os.replace, 0o600    │
   │    1003 Cancel   1005 Get a new code  NEW │   │    merge() -> AUTH-12 keep-previous rule     │
   │                                           │   │                                              │
   │  poll loop:  waitForAbort(1) == 1 Hz tick │   │  lock.py                                     │
   │              next_poll = now + interval   │   │    O_EXCL create; stale = session mismatch   │
   │              two clocks, one sleep        │   │            OR mtime age > TTL                │
   │                                           │   │    acquire() -> False means "you lost"       │
   │  service (service.py)                     │   │                                              │
   │    startup: issued_at older than N days?  │──▶│  refresh.py                                  │
   │    NEVER opens a dialog (AUTH-17)         │   │    lock -> POST -> merge -> write -> unlock  │
   │    on failure: needs_reauth + notify      │◀──│    invalid_grant -> re-read; adopt if moved  │
   └───────────────────────────────────────────┘   └──────────────────────────────────────────────┘
                    │                                              │
                    ▼                                              ▼
   special://profile/addon_data/plugin.onedrive.kn/
     accounts.db                  (metadata: label, drives, change_token, needs_reauth)
     tokens/<sub>.json            (0600, atomically replaced, never a Kodi setting)
     tokens/<sub>.lock            (O_EXCL; per account, so accounts never contend)
```

The two arrows that matter most: the **400 + JSON** edge into `poll_once` (that is `AUTH-10` —
a transport-level reading of it turns every pending poll into a failure), and the
`invalid_grant -> re-read; adopt if moved` edge (that is `AUTH-15` — without it, losing a race signs
the user out).

### Recommended Project Structure

```
resources/lib/
├── auth/                    # NEW. Zero xbmc* imports. pytest runs it directly.
│   ├── device_code.py       # protocol: request, poll_once, the allow-list
│   ├── errors.py            # AADSTS -> (sentence, action) table
│   ├── store.py             # atomic JSON read/write/merge
│   ├── lock.py              # O_EXCL + stale breaker
│   └── refresh.py           # lock -> refresh -> merge -> write, and AUTH-15
├── kodi/                    # CI-01's eventual home for xbmc* imports (Phase 2)
├── provider/onedrive.py     # get_account() loses GET /me (Finding A)
└── vendor/clouddrive_common/
    ├── remote/signin.py     # DELETED (AUTH-23)
    ├── remote/provider.py   # three methods rewritten
    ├── remote/errorreport.py# DELETED (its only URL source is going away)
    ├── ui/dialog.py         # QRDialogProgress: focus fix, __del__ guard, code control
    └── ui/addon.py          # sign-in flow, list_accounts, _handle_exception
resources/skins/default/1080i/pin-dialog.xml   # +code label, +second button, fonts fixed
docs/AZURE-REGISTRATION.md   # NEW (SETUP-04)
```

The `auth/` split is not architecture for its own sake. `CI-01` requires it, `AUTH-13` requires it
(a test that proves the persisted refresh token changed cannot import `xbmc`), the roadmap's
criterion 3 requires it ("no `threading.Lock` or `fcntl.lockf` appears in the auth package" presumes
a package), and `tests/test_vendor_gates.py` already runs with no stub library and intends to keep
doing so.

### Pattern 1: Kodi behind a port

**What:** the pure core never imports `xbmc*`; it receives what it needs.
**When to use:** everywhere in `auth/`.

```python
# Source: composed; enforced by CI-01 and required by AUTH-13.
class RefreshContext(object):
    """Everything auth/ needs from Kodi, and nothing else."""
    def __init__(self, profile_path, session_id, sleep, log):
        self.profile_path = profile_path   # xbmcvfs.translatePath, already resolved
        self.session_id = session_id       # KodiUtils.get_home_property('auth.session')
        self.sleep = sleep                 # Monitor.waitForAbort -> True on abort
        self.log = log                     # Logger.debug, with redaction applied
```

In tests, `sleep` is `lambda s: False`, `profile_path` is a `tmp_path`, `session_id` is a literal.
No stubs, no mocks of Kodi, no import of `xbmc`.

### Pattern 2: the poll loop's two clocks

Covered in §Polling. The pattern is: **one sleep** (`waitForAbort(1)`), **two deadlines**
(`deadline` for expiry, `next_poll` for cadence). Do not derive one from the other.

### Pattern 3: write exactly once, last

Covered in §Account Write Ordering. `AUTH-07` becomes structural rather than a chain of guards.

### Anti-Patterns to Avoid

- **`threading.Lock` or `fcntl.lockf` for the refresh.** Explained above with the primary evidence.
  `KodiUtils.lock` already exists and is correct for its own uses — do not reach for it here.
- **`time.sleep` / `xbmc.sleep` in the poll loop.** Neither observes the abort flag.
- **A deny-list poll loop.** Microsoft returns undocumented codes; a deny-list loops forever on a
  real failure. `AUTH-09` is an allow-list for that reason.
- **Hardcoding `900`, `3600`, `5` or `https://microsoft.com/devicelogin`.** All four are
  server-supplied and all four have been measured to differ from the documented default.
- **Equality or prefix matching on the granted `scope` string.** Ordering differs by account class
  and `offline_access` never appears in it. Membership only. (Measured.)
- **A worker thread updating dialog controls.** `show()` is already non-blocking.
- **`setFocus` inside a per-tick update.** It is in the tree today and it blocks `AUTH-06`.
- **`getattr(self, action)` dispatch from a URL parameter.** `ui/addon.py:701` does this. See
  §Security Domain.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file replace | write-to-file-then-check, or delete-then-rename | `os.replace` on a same-directory temp | `rename(2)` is atomic; delete-then-rename has a window where the file does not exist |
| Cross-interpreter mutual exclusion | a pid file with `os.kill(pid, 0)` | `O_EXCL` + session id + mtime TTL | The pid is Kodi's and is always alive — the check is degenerate here |
| Device-code state machine | a bespoke retry/backoff scheme | RFC 8628's `interval` + permanent `slow_down` bump | Deviating earns throttling; the RFC text is quoted above |
| Account identity | a hash of the UPN, or a user-typed name | `sub` from the `id_token` | Pairwise, per-app, stable, filename-safe, measured distinct for two users in one tenant |
| Account label | a keyboard prompt | `id_token` `name` (or `/oidc/userinfo`) | `AUTH-21` forbids typing on a remote; D-pad text entry is the stated design failure |
| QR encoding | anything new | vendored `pyqrcode` | Already in the tree with recorded provenance and a smoke test |
| Error text for tenant blocks | rendering `error_description` | `AADSTS\d+` → one sentence + one action + the bare code | The description is paragraph-length with markdown links; unreadable at 3 metres |

**Key insight:** every hand-rolled candidate in this phase fails for the *same* reason — it assumes a
single-process, single-writer, well-behaved-clock, documented-defaults world. The add-on runs in
none of those. The correct instinct throughout is to push the guarantee down to the filesystem or up
to the protocol, and never to hold it in Python state.

## Common Pitfalls

Pitfalls 1, 2, 3, 5 and 17 in `.planning/research/PITFALLS.md` are this phase's pitfalls and are
**not** repeated here. Read them. Pitfall 4 (tenant policy rejections) is also this phase's, and
`ROADMAP.md` criterion 1a narrows it. Below are only the pitfalls *this* research found, which are
not in that document.

### Pitfall A: The lock TTL is shorter than the request it protects

**What goes wrong:** the stale-lock breaker fires on a live holder, both sides refresh, one gets
`invalid_grant`, and if `AUTH-15` is not implemented the user is signed out — by the safety
mechanism.
**Why it happens:** `Request`'s defaults produce a 155-second worst case, computed in its own comment
at `remote/request.py:44-48`, and 30 or 60 seconds is the intuitive TTL.
**How to avoid:** give the refresh its own short request profile *and* set the TTL above its worst
case. State the arithmetic in a comment next to the constant.
**Warning signs:** two token responses in the log within one refresh window; `invalid_grant` on a
freshly-signed-in account.

### Pitfall B: A wrong font name renders silently

**What goes wrong:** `AUTH-05` is written into the skin XML, the XML is correct-looking, and the code
renders at 30px.
**Why it happens:** Kodi falls back to `font13` when it cannot resolve a font name, and logs nothing.
`pin-dialog.xml` already names `font12_title`, which Estuary does not define.
**How to avoid:** use a name present in Estuary's `Font.xml` (`font60`, `font52_title`, `font45`),
and verify by looking at the screen — there is no static check that can catch this.
**Warning signs:** none. That is the pitfall.

### Pitfall C: `verification_uri_complete` is absent, so the QR cannot be the whole story

**What goes wrong:** the dialog is laid out around a scannable "click here, you're done" URL that
never arrives, leaving the code as an afterthought in small text.
**Why it happens:** RFC 8628 makes the field optional-but-common, and most tutorials show it.
Microsoft does not return it — measured in all three spike runs.
**How to avoid:** design the dialog around the **code** as the primary element and the QR as a
secondary convenience. That inverts the current `pin-dialog.xml` layout, where the QR occupies the
left third and the text is a body block.
**Warning signs:** a design review that talks about the QR before it talks about the code.

### Pitfall D: The plugin handle is held for the whole sign-in

**What goes wrong:** Kodi waits on a directory fetch for up to 15 minutes.
**Why it happens:** "Add an account…" is a directory item whose handler never calls `endOfDirectory`,
and removing `_DEFAULT_SIGNIN_TIMEOUT = 120` (which `AUTH-06` requires) makes it worse, not better.
**How to avoid:** release the handle and re-enter via `RunPlugin` (handle `-1`).
**Warning signs:** `CPluginDirectory` warnings in `kodi.log`; a spinner that outlives the dialog.

### Pitfall E: A transient network failure at boot marks an account as needing re-auth

**What goes wrong:** the service's proactive refresh runs before Wi-Fi is up, fails, and sets
`needs_reauth`. The user is asked to sign in again for no reason — which is the exact experience
`AUTH-16` exists to prevent.
**Why it happens:** every failure looks alike unless the code distinguishes them, and `ERR-02` (which
requires exactly that distinction) is a Phase 4 requirement.
**How to avoid:** only an `AADSTS` grant error sets `needs_reauth`. A `URLError` sets nothing and
retries later.
**Warning signs:** `needs_reauth` appearing after a router reboot.

## Code Examples

The verified patterns are inline above rather than duplicated here, because each one only makes sense
next to the constraint that forces it:

- Atomic token write with `O_EXCL` create + `fsync` + `os.replace` → §Atomic Token Persistence
- `AUTH-12` merge rule → §Atomic Token Persistence
- `RefreshLock.acquire` with session-id and mtime staleness → §Cross-Process Refresh Serialisation
- `AUTH-15` loser-adopts-winner ordering → §Cross-Process Refresh Serialisation
- Two-clock poll loop on `Monitor.waitForAbort` → §Polling Without Blocking Shutdown
- `RefreshContext` port → §Architecture Patterns

The one external example worth keeping in view is `.planning/research/verify_device_code.py` — it is a
working, measured implementation of the protocol half under the same stdlib constraint, and the
`CONTINUE_ON` set, the `post_form` 400-handling, the `slow_down` bump and the `decode_id_token`
helper transfer almost verbatim.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OAuth via a hosted broker (`drive-login.herokuapp.com`) | Device code flow direct to Microsoft, embedded public `client_id` | This phase | No third party sees which account is connected; no single point of failure |
| `verification_uri` assumed `https://microsoft.com/devicelogin` | Server returns `https://login.microsoft.com/device` | Measured 2026-08-22 | Hardcoding it sends the user to the wrong page |
| `expires_in` assumed 3600 | Randomised per token (3655/4491/3599 observed) | Measured 2026-08-22 | Expiry computed per response, always |
| `GET /me/drives` assumed universal | 403 on personal; only `/me/drive` serves both | Measured 2026-08-22 | `BROWSE-08`; also removes the account-type branch |
| Old add-on settings format | `<settings version="1">` with `<level>` | Kodi 19 Matrix+ | Required for `AUTH-19` — Finding B |
| Untyped `xbmcgui` info setters | Typed InfoTag setters | Kodi 20 | `KODI-03`, Phase 7 — not this phase |

**Deprecated/outdated:**

- `remote/signin.py` in its entirety — the broker protocol it speaks has no server this project
  intends to keep talking to.
- `remote/errorreport.py` — third-party error reporting; `KODI-08` deletes it, and `AUTH-23` breaks
  its only URL source.
- `_DEFAULT_SIGNIN_TIMEOUT = 120` — replaced by the server's `expires_in`.
- The `'migrated'` account cleanup block (`ui/addon.py:249-262`) — v2.3.0 legacy, and it removes by
  the wrong key.

## Project Constraints (from CLAUDE.md)

**No `./CLAUDE.md` or `./.claude/CLAUDE.md` exists in the repository.** `.planning/config.json` names
`claude_md_path: "./.claude/CLAUDE.md"`, but the file is not present and is not in `git ls-files`.
No `.claude/skills/` or `.agents/skills/` directory exists either.

Two repository-level conventions are enforced by tests rather than by a document, and the planner
must treat them as binding:

| Constraint | Source | Effect on this phase |
|---|---|---|
| Every shipped file carries its correct licence notice; GPL headers intact, `FOREIGN_NOTICES` for BSD/MIT files | `tests/test_vendor_gates.py::test_gpl_headers_intact` | New files under `resources/lib/auth/` need the GPL-3.0 header the rest of the tree carries |
| No `eval(` anywhere | `test_no_eval` | — |
| Every outbound HTTP call carries an explicit `timeout=` | `test_all_http_calls_have_timeout` (`VND-06`) | The new device-code and token calls must pass `timeout=` |
| String ids: 30000-30999 for this add-on, 32000-32088 reserved to the vendored module and untouched | `test_string_ids_partitioned`, `STATE.md` | New dialog strings take **free 30xxx ids**: 30012-30016, 30021-30029, 30036-30066, 30070+ are unused |
| Exclusion sets live in one place and adding to one must buy a stronger positive assertion | `tests/test_vendor_gates.py:44-56` | Findings C and F both land here |
| `VENDORED.md` records every local modification to a vendored file | `VND-09`, `test_vendored_md_sections` | Deleting `signin.py` and editing `dialog.py`/`provider.py`/`addon.py` are all modifications to record |
| Commits and docs carry no AI attribution and no GSD vocabulary | user memory | Applies to the commit for this phase |

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (8.3.5 per the compiled cache; no version pin in the repo) |
| Config file | `pytest.ini` — `[pytest]` / `testpaths = tests` |
| Quick run command | `python -m pytest tests -x -q` |
| Full suite command | `python -m pytest tests -q` |

The existing suite is one file, `tests/test_vendor_gates.py`, 23 tests, entirely over the repository
as text/XML/AST. Its docstring states: *"Nothing in this file imports a Kodi module, so it needs no
stub library and no fixtures, and the whole file runs in well under two seconds."* Phase 3 is the
first phase that needs tests over *behaviour*, and preserving the no-Kodi-import property is what
makes that possible without adding Kodistubs.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-04 | Scope string is exactly the locked set; no `.default`, no `.All`, no write scope | gate | `pytest tests/test_auth_gates.py::test_scope_string_exact -x` | ❌ Wave 0 |
| AUTH-09 | Poll continues only on `authorization_pending` and `slow_down` | unit | `pytest tests/test_device_code.py::test_poll_allow_list -x` | ❌ Wave 0 |
| AUTH-10 | HTTP 400 + JSON parsed as protocol, not transport failure | unit | `pytest tests/test_device_code.py::test_400_is_protocol -x` | ❌ Wave 0 |
| AUTH-09 | `slow_down` raises the interval by 5 permanently | unit | `pytest tests/test_device_code.py::test_slow_down_is_permanent -x` | ❌ Wave 0 |
| AUTH-11 | Store is JSON on disk at mode 0600, never a Kodi setting | unit | `pytest tests/test_token_store.py::test_written_mode_and_shape -x` | ❌ Wave 0 |
| AUTH-11 | A crash mid-write leaves the previous file intact (temp + replace) | unit | `pytest tests/test_token_store.py::test_interrupted_write_preserves_previous -x` | ❌ Wave 0 |
| AUTH-12 | A response omitting `refresh_token` retains the previous one | unit | `pytest tests/test_token_store.py::test_missing_refresh_token_retained -x` | ❌ Wave 0 |
| **AUTH-13** | The persisted refresh token **changed** across two consecutive refreshes | unit | `pytest tests/test_token_store.py::test_refresh_token_rotates -x` | ❌ Wave 0 |
| AUTH-14 | Two contenders serialise; the second sees the first's write | integration | `pytest tests/test_refresh_lock.py::test_two_processes_serialise -x` | ❌ Wave 0 |
| AUTH-14 | Two *threads in one process* also serialise (the property that survives sub-interpreters) | unit | `pytest tests/test_refresh_lock.py::test_two_threads_serialise -x` | ❌ Wave 0 |
| AUTH-14 | A lock from a previous session is broken immediately | unit | `pytest tests/test_refresh_lock.py::test_stale_by_session_id -x` | ❌ Wave 0 |
| AUTH-14 | A lock older than TTL is broken; a lock with a future mtime is not treated as fresh | unit | `pytest tests/test_refresh_lock.py::test_stale_by_age_and_clock_step -x` | ❌ Wave 0 |
| AUTH-14 | No `threading.Lock`, no `fcntl` in `resources/lib/auth/` | gate | `pytest tests/test_auth_gates.py::test_no_forbidden_lock_primitives -x` | ❌ Wave 0 |
| **AUTH-15** | `invalid_grant` + a store that moved on → adopt, do not sign out | unit | `pytest tests/test_refresh.py::test_loser_adopts_winner_token -x` | ❌ Wave 0 |
| AUTH-15 | `invalid_grant` + a store that did **not** move → genuine dead grant | unit | `pytest tests/test_refresh.py::test_unchanged_store_is_real_invalid_grant -x` | ❌ Wave 0 |
| AUTH-16 | Refresh is skipped when `issued_at` is recent and runs when it is old | unit | `pytest tests/test_refresh.py::test_startup_threshold -x` | ❌ Wave 0 |
| AUTH-16/E | A `URLError` does not set `needs_reauth`; an `AADSTS` grant error does | unit | `pytest tests/test_refresh.py::test_transient_failure_not_reauth -x` | ❌ Wave 0 |
| AUTH-18 | Each of the nine `AADSTS` codes maps to a distinct sentence; unmapped shows the bare code | unit | `pytest tests/test_error_map.py -x` | ❌ Wave 0 |
| AUTH-19 | The setting exists, is empty by default, and is validated as a GUID | unit + gate | `pytest tests/test_auth_gates.py::test_custom_client_id_setting -x` | ❌ Wave 0 |
| AUTH-20 | Two accounts get two token files and two locks; removing one deletes its file | unit | `pytest tests/test_token_store.py::test_per_account_isolation -x` | ❌ Wave 0 |
| AUTH-23 | No `sign-in-server`, no `get_signin_server`, no `herokuapp`, no broker path — outside `EXCLUDED_DOCS` | gate | `pytest tests/test_auth_gates.py::test_no_broker_references -x` | ❌ Wave 0 |
| SETUP-04 | The runbook exists and contains `AADSTS7000218` verbatim | gate | `pytest tests/test_auth_gates.py::test_runbook_contains_aadsts7000218 -x` | ❌ Wave 0 |
| AUTH-01/03/05/06/07 | Sign-in end to end; code legible from a sofa; countdown ticks; "Get a new code" focused; Back leaves nothing | **manual** | `CI-06` acceptance pass on the TCL Android TV 12 | manual-only |
| AUTH-08 | The QR resolves to the server-supplied `verification_uri` | **manual** | scan it with the phone during the acceptance pass | manual-only |
| AUTH-18 | A genuinely blocking tenant | **not verifiable** | the E5 tenant permits device code flow — record as unverified per `ROADMAP.md` 1a | n/a |

Justification for the manual-only rows: `PITFALLS.md` §"Testing Pitfalls: What Cannot Be Caught
Off-Device" already lists device-code readability at TV viewing distance, remote-only navigability,
`verification_uri_complete` absence handling, and Business-tenant policy rejections as manual by
nature. This phase adds nothing to that list.

### Sampling Rate

- **Per task commit:** `python -m pytest tests -x -q`
- **Per wave merge:** `python -m pytest tests -q`
- **Phase gate:** full suite green, plus the `CI-06` acceptance pass on the TCL, before
  `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_device_code.py` — covers AUTH-09, AUTH-10
- [ ] `tests/test_token_store.py` — covers AUTH-11, AUTH-12, AUTH-13, AUTH-20
- [ ] `tests/test_refresh_lock.py` — covers AUTH-14
- [ ] `tests/test_refresh.py` — covers AUTH-15, AUTH-16
- [ ] `tests/test_error_map.py` — covers AUTH-18
- [ ] `tests/test_auth_gates.py` — covers AUTH-04, AUTH-19, AUTH-23, SETUP-04, and the forbidden-primitive sweep
- [ ] `tests/conftest.py` — a `tmp_path`-backed token-store fixture and a fake token endpoint; **no
      Kodistubs**, because `resources/lib/auth/` must not import `xbmc*`
- [ ] Framework install: none — `pytest` is already the harness and `pytest.ini` already exists

The `test_auth_gates.py` file should reuse `test_vendor_gates.py`'s harness conventions: read from
`git ls-files` rather than walking the filesystem, report path and line rather than a count, and
carry a non-vacuity guard on every sweep. That file's own docstring explains why, and a second gate
file that quietly diverges from those rules is worse than no second file.

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | **yes** | RFC 8628 device authorization grant against Microsoft Entra. No password ever reaches the add-on. Public client, no secret (`SETUP-03`) |
| V3 Session Management | **yes** | Refresh-token rotation written back in full (`AUTH-12`); expiry computed per response; proactive refresh inside the inactivity window (`AUTH-16`); `remove_account` deletes the token file |
| V4 Access Control | **partial** | Least privilege is the scope set: `Files.Read` only, no `.All`, no write, no `.default` (`AUTH-04`). Enforced by a gate |
| V5 Input Validation | **yes** | Custom `client_id` validated as a GUID; `verification_uri` asserted `https://` before being rendered into a QR; **the `getattr(self, action)` plugin dispatch replaced with an explicit allow-list** — see below |
| V6 Cryptography | **no hand-rolling** | TLS via `urllib` with the platform trust store. `id_token` decoded for **display only**, never signature-validated and never used for an authorization decision. **Never** disable certificate verification to "fix" a cert error — diagnose the device clock instead (`PITFALLS.md` §Security Mistakes) |
| V7 Error Handling & Logging | **yes, and there is a live gap** | See the redaction finding below |
| V8 Data Protection | **yes** | Token file at mode 0600 in the app-private directory; tokens never in a Kodi setting (`AUTH-11`); the QR image contains only the public `verification_uri` and is deleted on teardown |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Refresh token written to `kodi.log`, which users paste into public forums verbatim | Information Disclosure | **Gap.** `Request.get_url_for_report` redacts only `access_token=` in the URL and the `authorization` header (`remote/request.py`), but `_handle_exception` appends `rex.response` raw (`ui/addon.py:664-665`). A failing token response therefore puts `refresh_token` and `device_code` in the log. Add one redactor in the HTTP layer covering `access_token`, `refresh_token`, `id_token`, `device_code`, `user_code`; log at most 8 characters when correlation is needed (Pitfall 3) |
| `getattr(self, self._action)` dispatch from a plugin URL parameter (`ui/addon.py:701`) | Elevation of Privilege | Any `plugin://plugin.onedrive.kn/?action=<name>` — constructible from a favourite, a `.strm`, or another add-on — calls an arbitrary method on the addon object. Replace with an explicit `{action_name: method}` allow-list. `AUTH-22` adds new actions anyway, so the dispatch is being touched regardless. Same shape as `AUTH-09`'s allow-list, for the same reason |
| A client secret embedded to "fix" `AADSTS7000218` | Information Disclosure | The runbook says do not, in bold, adjacent to the verbatim error (`SETUP-04`); `CI-05` greps for it |
| Custom `client_id` set to an arbitrary attacker-supplied string | Tampering / Spoofing | Validate as a GUID; **never** let it change the authority (Pitfall 1 point 4, `PITFALLS.md` §Security Mistakes) |
| Stale `sign-in-server` value pointing at a re-registrable hostname | Spoofing | Setting and code path deleted (`AUTH-23`). The hostname is currently **alive**, so this is removing a live dependency, not clearing dead config |
| Token store readable by a sideloaded app | Information Disclosure | Mode 0600 plus the Android 11+ app-private `Android/data` regime established in Phase 1. Assume the worst case anyway — the design must not encode which device it is on |
| Poll loop that never terminates on an undocumented error | Denial of Service | `AUTH-09`'s allow-list, plus the `expires_in` deadline |
| Polling faster than `interval` | Denial of Service (self-inflicted throttling) | RFC 8628 §3.4 minimum; permanent `slow_down` bump |
| A partially-written token file after power loss | Tampering / availability | `fsync` before `os.replace`; the previous file remains valid until the rename lands |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 + `pytest` | The whole test map | ✓ | `pytest.ini` present, `.pytest_cache` shows 8.3.5 under CPython 3.11 | — |
| `git` | Every gate reads `git ls-files` | ✓ | repo is clean on branch `matrix` | — |
| Network to `login.microsoftonline.com` | Live sign-in, `verify_device_code.py` | ✓ | three successful runs on 2026-08-22 | — |
| Azure app registration | Every live device-code test | ✓ | `efe197b3-5c14-4d67-810f-e10406742a06`, manifest read back | Custom `client_id` setting (`AUTH-19`) |
| A work/school account | `AUTH-03`, `CI-07` | ✓ | two, in the E5 tenant | — |
| A personal Microsoft account | `AUTH-03` (deferred half) | ✓ | confirmed by MSA tenant id | Deferred per S2 |
| **TCL Android TV 12 over network `adb`** | `CI-06`, Phase 3 criterion 6 | **unverified** | never driven in any recorded session | An API-30 emulator answers storage/mode/`O_EXCL` only. It answers **nothing** about D-pad, readability, GPU or performance — and those are half this phase's criteria |
| An installable zip | Installing on the TV at all | ✗ | `DIST-01` is not built | **Blocking for criterion 6.** The priority order already pulls `DIST-01` forward "at the point where the add-on first has to be installed on the TV". That point is this phase |
| A tenant that blocks device code flow | `AUTH-18` full verification | ✗ | the E5 tenant permits it | None. Record `AUTH-18` as partially verified per `ROADMAP.md` 1a |

**Missing dependencies with no fallback:**

- A blocking tenant. `AUTH-18` cannot be fully verified; the roadmap already directs that it be
  recorded as unverified rather than claimed.

**Missing dependencies with fallback:**

- `DIST-01` (the zip). Pull it forward — the priority order already sanctions this and names this
  phase as the trigger. Without it, Phase 3 criterion 6 cannot run at all.
- The TCL itself is *available* to the owner but has never been driven from a session. Plan the
  acceptance pass as an explicit task with a named setup step (enable network `adb`, pair, install
  the zip), not as a checkbox at the end.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `GET /me` returns 403 with the locked scope set. Documented (`User.Read` is the least-privileged permission) but **not measured** — the spike never probed `/me` | Finding A | If `/me` actually works, the label problem evaporates and one task is unnecessary. Cheap to settle: one `curl` with a spike token. **Do this before planning.** |
| A2 | `/me/drive`'s `owner.user.displayName` is non-null on a business drive | Finding A option 3 | The fallback label is empty. Same one-request check as A1 |
| A3 | The plugin and the service are sub-interpreters in **one OS process** on Kodi 21/22 on Android | Cross-Process Refresh Serialisation | The whole `AUTH-14` rationale rests on this. If they are separate processes, `fcntl.lockf` would work — but `O_EXCL` works either way, so the *design* is safe regardless; only the comment explaining it would be wrong. Sourced from `STATE.md`, not measured this session |
| A4 | `RunPlugin` releases the caller and passes handle `-1` | Polling / Pitfall D | The 15-minute loop would still block a container fetch. Corroborated by the tree's own `>= 0` guard, but not run |
| A5 | `font60` renders a 9-character code legibly at 1080i from a sofa | The Dialog | Falls back to a smaller `font45`/`font52_title`, or the layout is rebalanced. Settled by looking at the screen; there is no static check |
| A6 | Estuary is the active skin on the TCL | The Dialog | Font names resolve against whatever skin is active; a different skin means the `font13` fallback. Ask the owner |
| A7 | Kodi's local-file VFS reaches POSIX `rename(2)` on Android | Atomic Token Persistence | Moot under the recommendation, which uses `os.replace` on a translated path and never calls `xbmcvfs.rename` |
| A8 | A TTL of ~60s with a short-retry request profile is right | Cross-Process Refresh / Pitfall A | Too short breaks live locks; too long stalls the other side. The 155s figure it is being set against is itself recorded as **unmeasured** in `STATE.md` |
| A9 | `sub` is filename-safe as written | Multi-Account Structure | base64url is `[A-Za-z0-9_-]`, so it is. Assert it, or hash it, rather than trusting it |
| A10 | Kodi 22 ships Python 3.14 and Kodi 21 ships 3.8 | Validation Architecture | From `STATE.md`. Only matters if the auth package uses a 3.9+ construct. Keep the pure core on 3.8-compatible syntax |

## Open Questions

1. **Does `GET /me` actually 403?** (A1)
   - What we know: `User.Read` is documented as the least-privileged permission for both delegated
     account classes; the granted scope contains no such permission.
   - What's unclear: whether Entra grants `User.Read` implicitly alongside `profile` for this
     registration. It does not per the documentation, but the spike did not probe it.
   - Recommendation: **settle it before planning.** One request with a token from
     `verify_device_code.py`, added to the script's STEP 4 endpoint probe alongside
     `/me/drives`, `/me/drive`, `/drives`. Ten minutes, and it decides whether Finding A produces one
     task or none.

2. **Where does the settings-schema conversion land?** (Finding B)
   - What we know: `AUTH-19` needs `<level>`, which needs `<settings version="1">`, which is `KODI-05`
     in the deferred Phase 7.
   - What's unclear: whether the owner wants the schema pulled forward or `AUTH-19` restated.
   - Recommendation: pull it forward. The file is 28 lines and this phase edits it anyway.

3. **Does `DIST-01` come into Phase 3?** (Environment Availability)
   - What we know: Phase 3 criterion 6 requires the add-on installed on the TCL, and installing on
     Android TV requires a zip.
   - What's unclear: nothing, really — the priority order already says `DIST-01` is pulled forward
     "at the point where the add-on first has to be installed on the TV".
   - Recommendation: make it an explicit task in this phase's plan rather than an implicit
     prerequisite, so criterion 6 is not blocked by a build step nobody owns.

4. **`_remove_drive` after `BROWSE-08`.**
   - What we know: `/me/drive` is singular, so the `size > 1` branch becomes unreachable.
   - What's unclear: whether to delete it or hold it for `AUTH-24` (SharePoint, v2).
   - Recommendation: whichever is chosen, **record the reason**. `SPIKE-DEVICE-CODE.md` documents
     that this codebase's previous piece of apparently-dead code was load-bearing and merely
     unexplained, and that `CONCERNS.md` mischaracterised it as waste on that basis.

5. **How much of Phase 4's Graph work does Phase 3 pull in?**
   - What we know: sign-in calls `get_account()` and `get_drives()`, both of which are wrong
     (Finding A; the `/drives` + `/me/drives` pair). `BROWSE-08` owns the fix and sits in Phase 4.
   - What's unclear: the boundary.
   - Recommendation: Phase 3 fixes exactly what sign-in traverses and no more — `get_account()` and
     `get_drives()` — and states in the plan that it is doing so on `BROWSE-08`'s authority.

## Sources

### Primary (HIGH confidence)

- `.planning/research/SPIKE-DEVICE-CODE.md` — three live end-to-end runs against this project's own
  registration. Authority, scope set, refresh issuance, `verification_uri`, `expires_in` variance,
  absent `verification_uri_complete`, granted-scope shape, `sub` as key, drive-endpoint matrix.
- `.planning/research/verify_device_code.py` — working stdlib reference implementation.
- `.planning/research/PITFALLS.md` — Pitfalls 1, 2, 3, 4, 5, 17, 18, 19; §Security Mistakes;
  §UX Pitfalls; §"Testing Pitfalls: What Cannot Be Caught Off-Device".
- The repository itself, read this session: `ui/addon.py`, `ui/dialog.py`, `ui/utils.py`,
  `remote/oauth2.py`, `remote/signin.py`, `remote/provider.py`, `remote/request.py`, `account.py`,
  `db.py`, `cache/cache.py`, `provider/onedrive.py`, `resources/settings.xml`, `addon.xml`,
  `service.py`, `entrypoint.py`, `pin-dialog.xml`, `tests/test_vendor_gates.py`, `pytest.ini`.
- `xbmc/filesystem/File.cpp` (`CFile::Rename` — no copy+delete fallback, no destination pre-delete).
- man7 `rename(2)` — atomic replacement, `EXDEV`.
- man7 `F_SETLK(2const)` — record locks are per-process; lock conversion; close-releases-all.
- `xbmc/addons/skin.estuary/xml/Font.xml` — the full font id list.

### Secondary (MEDIUM confidence)

- learn.microsoft.com/en-us/graph/api/user-get — `GET /me` requires `User.Read`.
- learn.microsoft.com/en-us/entra/identity-platform/userinfo — `/oidc/userinfo` is Graph-hosted,
  needs only `openid`/`profile`; id_token is a superset.
- rfc-editor.org/rfc/rfc8628 §3.4, §3.5 — quoted verbatim above.
- xbmc.github.io/docs.kodi.tv — `xbmcvfs` function list; `WindowXMLDialog` `show()`/`doModal()`.

### Tertiary (LOW confidence — verify on device)

- kodi.wiki/view/Fonts — the `font13` fallback rule.
- kodi.wiki/view/Add-on_settings, kodi.wiki/view/Settings — `<level>` syntax and the v1 format.
- forum.kodi.tv/showthread.php?tid=42073 — `RunPlugin` passes handle `-1`.

## Metadata

**Confidence breakdown:**

- Protocol and scope: **HIGH** — measured three times against live endpoints with this registration.
- Code inventory and removal map: **HIGH** — every line reference read from the tree this session.
- Locking rationale: **HIGH** on the mechanism (primary man-page evidence), **MEDIUM** on the
  sub-interpreter premise (from `STATE.md`, not re-measured) — but the design is correct either way.
- Atomic persistence: **HIGH** on `rename(2)`, **MEDIUM** on the Android specifics (`CI-06` allows a
  stand-in to settle them).
- Dialog and fonts: **MEDIUM** — the font list and fallback rule are documented, but `AUTH-05` is
  settled only by looking at the television.
- Kodi runtime idioms (`RunPlugin` handle, `show()` semantics): **MEDIUM** — documented and
  corroborated by the tree's own patterns, not run.
- Finding A: **MEDIUM** — documentation is unambiguous, measurement is absent. See Open Question 1.

**Research date:** 2026-08-23
**Valid until:** 2026-09-22 (30 days). The Entra endpoints are stable; the parts most likely to drift
are the Graph permission tables and Kodi 22's Python version. Re-check Finding A if a live response
ever contradicts it.
