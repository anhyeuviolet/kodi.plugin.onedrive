---
phase: 01-vendor-lift
plan: 06
subsystem: security
tags: [json, eval, deserialization, sqlite, http-timeout, urlopen, asvs, android]

# Dependency graph
requires:
  - "01-04 — the vendored tree the three eval( sites and the untimed HTTP call arrived in, verbatim and unedited"
  - "01-02 — tests/test_vendor_gates.py, which held test_no_eval and test_all_http_calls_have_timeout red until this plan"
provides:
  - "resources/lib/vendor/clouddrive_common/db.py — the key-value store reading and writing JSON; backs the account store holding OAuth refresh tokens and both export databases"
  - "resources/lib/vendor/clouddrive_common/cache/cache.py — the item, children and page caches reading and writing JSON"
  - "resources/lib/vendor/clouddrive_common/remote/request.py — Request.HTTP_TIMEOUT_SECONDS = 30, the one place a central HTTP layer inherits to tune"
  - "A tree with no dynamic code execution construct anywhere outside tests/"
  - "The stored on-disk format for the profile databases: JSON text in the same TEXT columns, no schema change"
affects: [01-07, phase-03-auth, phase-04-http, phase-06-playback]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Coerce at the write site, never special-case the serializer — the shapes JSON cannot carry are fixed where they are produced, so the store stays a dumb pipe"
    - "No compatibility read path where no prior data can exist — a new add-on id turns a migration problem into a non-problem, and a fallback evaluator would restore the exact vulnerability being removed"
    - "A timeout as a named class constant rather than a call-site literal, carrying its own reasoning and its unmeasured status in a comment beside it"
    - "Byte-level patch scripts with per-substitution occurrence assertions, so a surprise refuses to write rather than writing something plausible"

key-files:
  created: []
  modified:
    - resources/lib/vendor/clouddrive_common/db.py
    - resources/lib/vendor/clouddrive_common/cache/cache.py
    - resources/lib/vendor/clouddrive_common/service/source.py
    - resources/lib/vendor/clouddrive_common/remote/request.py

key-decisions:
  - "All four repr( write sites were converted, not the two the plan names — db.setmany and cache.setmany are write sites too, and the plan's own acceptance criterion requires zero repr( in db.py"
  - "The page cache stores a response body as bytes, a third shape JSON cannot carry that the plan did not enumerate; it is decoded at the write site in source.py, which is the exact inverse of the read path's existing Utils.encode"
  - "30 seconds, recorded as unmeasured — the value is a recommended range, not a measurement, and is confirmed on the Android test phone in 01-07"
  - "The retry loop's sleep is untouched; its worst-case wall time of 155 seconds at the class defaults is recorded rather than bounded"
  - "The SQLite connection timeout of 30 seconds is untouched in both modules — concurrent access is neither improved nor worsened by a serializer change"

patterns-established:
  - "Every write site is read before a serializer swap, and the reading is recorded per site — a round-trip test proves the serializer, not the data that reaches it"
  - "A round-trip claim is exercised against real SQL through the real statements, twice, not asserted about the json module in the abstract"

requirements-completed: [VND-05, VND-06]

coverage:
  - id: D1
    description: "The three dynamic-evaluation reads in the key-value store and the item cache are replaced by JSON decoding; no dynamic code execution construct remains anywhere in the tree outside tests/"
    requirement: VND-05
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_no_eval"
        status: pass
    human_judgment: false
  - id: D2
    description: "All four matching write sites encode through JSON, and no compatibility read path or fallback evaluator exists"
    requirement: VND-05
    verification:
      - kind: unit
        ref: "grep -c 'repr(' and grep -c 'literal_eval' over db.py — both 0"
        status: pass
    human_judgment: false
  - id: D3
    description: "An account dictionary, an export record, an items-info map, a changes list, an extracted item and a children-name list each survive two consecutive encode-then-decode round trips unchanged, through the real SQL statements against a real sqlite3 file"
    requirement: VND-05
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_store_json_roundtrip"
        status: pass
      - kind: integration
        ref: "scratch probe: real sqlite3 db, real insert-or-replace and select statements, six payloads x two laps x three accessors — 0 failures"
        status: pass
    human_judgment: false
  - id: D4
    description: "The two shapes that do not survive the swap are asserted rather than assumed — a tuple decodes as a list and a non-string dict key decodes stringified — and every write site was read against that list"
    requirement: VND-05
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_store_json_roundtrip (the two negative assertions)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The SQLite connection timeout of 30 seconds is unchanged in both database modules; no new locking was introduced"
    requirement: VND-05
    verification:
      - kind: unit
        ref: "grep -c 'timeout=30' db.py and cache.py — 1 each; git diff shows neither _get_connection touched"
        status: pass
    human_judgment: false
  - id: D6
    description: "The single outbound HTTP call carries an explicit timeout sourced from a named class constant, and the syntax-tree sweep that proves it finds exactly one call site and asserts it is not zero"
    requirement: VND-06
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_all_http_calls_have_timeout"
        status: pass
    human_judgment: false
  - id: D7
    description: "The comment at the constant states why one value correctly serves both the metadata path and the chunked download path"
    requirement: VND-06
    verification:
      - kind: unit
        ref: "grep -c 'per socket operation' request.py — 1"
        status: pass
    human_judgment: false
  - id: D8
    description: "The whole tree still compiles after both edits"
    verification:
      - kind: unit
        ref: "tests/test_vendor_gates.py#test_tree_compiles; python -m compileall -q resources/ entrypoint.py service.py exits 0"
        status: pass
    human_judgment: false
  - id: D9
    description: "30 seconds is the right timeout on a real Android TV device on marginal Wi-Fi — low enough to escape a hang, high enough not to fail a slow but healthy metadata call"
    requirement: VND-06
    verification:
      - kind: manual
        ref: "01-07 acceptance pass on the Android test phone"
        status: deferred
    human_judgment: true
    rationale: "The value came from a recommended range, not a measurement. Nothing inside this repository can distinguish a correct 30 from a wrong 30; only a real device on a real degraded network can."
  - id: D10
    description: "A stored account, export or cached page written by the previous format is never read — no database from a previous installation exists under the new add-on id"
    requirement: VND-05
    verification:
      - kind: manual
        ref: "01-07 acceptance pass on a clean profile"
        status: deferred
    human_judgment: true
    rationale: "The claim is about what is absent from a user's disk, not about what is present in the repository. A clean-profile install is the only thing that demonstrates it, and it is exactly what 01-07 runs."

# Metrics
duration: 12min
completed: 2026-08-22
status: complete
---

# Phase 1 Plan 06: Close the Evaluator and the Unbounded Call Summary

**The add-on stops turning a file on disk into running code and stops making a network call that can block forever: three `eval(` reads and four `repr(` writes become JSON, one `urlopen` gains a named 30-second timeout, and reading every write site first turned up a third shape JSON cannot carry that the plan did not know about.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-08-22T21:17:00+07:00
- **Completed:** 2026-08-22T21:29:00+07:00
- **Tasks:** 2 of 2
- **Files:** 0 created, 4 modified

## Task Commits

1. **Task 1: the serializer swap** — `94640f6` — `fix: stop evaluating stored database rows as Python source` — 3 files (`db.py`, `cache/cache.py`, `service/source.py`), +14 / −8
2. **Task 2: the timeout** — `f8d1f51481a0704c3625f536a23b78e0278fbf44` (short `f8d1f51`) — `fix(request): bound the outbound HTTP call with an explicit timeout` — 1 file, +20 / −1

Task 2's acceptance criterion is self-relative by design, because 01-05 and 01-06 are both wave 3 and `HEAD~1` could be either plan's commit. Checked as the plan specifies: `git show --name-only --format= f8d1f51481a0704c3625f536a23b78e0278fbf44` lists exactly one path, `resources/lib/vendor/clouddrive_common/remote/request.py`.

## Accomplishments

- Removed the interpreter from the read path of the database that holds OAuth refresh tokens. Every stored row is now decoded, not executed.
- Removed the only way this add-on could hang forever on a network call, and put the value somewhere a future HTTP layer can inherit rather than rediscover.
- Read all seven write sites before editing any of them, and found one the plan had not accounted for. The plan's own instruction — coerce at the write site rather than special-case the serializer — is what made that finding actionable instead of a blocker.
- Proved the round trip against real SQL rather than against the `json` module in isolation: six representative payloads, two laps each, through the actual `insert or replace` and `select` statements now in the code, across all three accessors (`get`, `getall`, `setmany`).
- Left the two things the plan said to leave alone genuinely alone: the SQLite connection setup and the retry loop's injected sleep.

## For VENDORED.md — the local modifications this plan adds

01-07 assembles the record; these are this plan's rows.

### The three read sites converted

| File | Line (before) | Was | Now |
|---|---:|---|---|
| `resources/lib/vendor/clouddrive_common/db.py` | 59 | `return eval(row[0])` | `return json.loads(row[0])` |
| `resources/lib/vendor/clouddrive_common/db.py` | 66 | `d[row[0]] = eval(row[1])` | `d[row[0]] = json.loads(row[1])` |
| `resources/lib/vendor/clouddrive_common/cache/cache.py` | 66 | `return eval(row[0])` | `return json.loads(row[0])` |

Those are exactly the three sites 01-04 carried forward. There are no `exec(` and no `compile(` sites anywhere in the tree. The `re.compile` in the player service is a false positive for a naive text sweep, which is why the gate anchors on the function name with a word boundary.

### The write sites converted — four, not two

| File | Line (before) | Was | Now |
|---|---:|---|---|
| `resources/lib/vendor/clouddrive_common/db.py` | 74 (`setmany`) | `kv[1] = repr(kv[1])` | `kv[1] = json.dumps(kv[1])` |
| `resources/lib/vendor/clouddrive_common/db.py` | 91 (`_insert`) | `(key, repr(value))` | `(key, json.dumps(value))` |
| `resources/lib/vendor/clouddrive_common/cache/cache.py` | 76 (`setmany`) | `kv[1] = repr(kv[1])` | `kv[1] = json.dumps(kv[1])` |
| `resources/lib/vendor/clouddrive_common/cache/cache.py` | 96 (`_insert`) | `(key, repr(value), expiration,)` | `(key, json.dumps(value), expiration,)` |

`import json` added to both files. Neither GPL header was touched, and neither file appears in the gate suite's `FOREIGN_NOTICES` map.

### The write-site audit, per site

The plan asks for confirmation that no write site produces a tuple or a non-string dictionary key. Every site was read. Below is what each one actually stores.

**`SimpleKeyValueDb` — three users, seven call sites**

| Caller | Site | Value stored | Verdict |
|---|---|---|---|
| `account.py:43` | migration of `accounts.cfg` | the value came out of `json.loads` moments earlier | JSON-native by construction |
| `account.py:54` | `save_account` | `{'id': str, 'name': str, 'drives': [ {...} ], 'access_tokens': {...}}` | str keys throughout; values str, list, dict, int, float, None |
| `export.py:51` | migration of `exports.cfg` | out of `json.loads` | JSON-native by construction |
| `export.py:66` | migration of `export-*.items` | out of `json.loads` | JSON-native by construction |
| `export.py:79` | `save_export` | the dict built in `ui/dialog.py:336` | str keys; values str, bool, int, and `schedules`, a list of `{'type': int, 'at': str}` |
| `export.py:97` | `save_items_info` | `items_info`, keyed by item id | keys are OneDrive item ids, always `str`; values are four-key str dicts |
| `export.py:104`, `export.py:111` | `save_pending_changes`, `save_retry_changes` | `list(changes)` | already coerced from `deque` at the write site by upstream, at all four call sites the plan names |

`account['drives']` comes from `OneDriveProvider.get_drives`, which builds `{'id': str, 'name': str, 'type': str}` and to which `persist_change_token` may add a `change_token` string or `None`. `account['access_tokens']` is the OAuth token response parsed from JSON, plus `tokens_info['date'] = time.time()`, a float. No tuple, no non-string key.

`db.setmany` has no caller anywhere in the tree. It was converted regardless — a live `repr(` in a store whose read path is now `json.loads` is a landmine for the first person to call it, and the plan's acceptance criterion requires zero `repr(` in the file.

**`Cache` — three instances, six write sites**

| Caller | Site | Value stored | Verdict |
|---|---|---|---|
| `source.py:215` | `_items_cache.set` | the list from `provider.get_folder_items` | list of `_extract_item` dicts |
| `source.py:224` | `_items_cache.setmany` | `[[key, item], ...]` | same item dicts |
| `source.py:274`, `source.py:295` | `_items_cache.set` | one `_extract_item` dict | same |
| `source.py:228` | `_children_cache.set` | `children_names` | list of `str` |
| `source.py:344` | `_page_cache.set` | `{'pending': True}` | trivially JSON-native |
| `source.py:377` | `_page_cache.set` | `cached_page` | **carried bytes — see the deviation below** |

`OneDriveProvider._extract_item` was read in full. Every value it produces is `str`, `int`, `float`, `bool`, `None`, `dict` or `list`; `last_modified_date` is `Utils.get_safe_value(f, 'lastModifiedDateTime')`, a string straight off the Graph response and not a `datetime`, exactly as the plan states. The only mutation applied afterwards is `ExportService.on_before_add_item`, which sets `item['origin']` to a string.

### The timeout

| Constant | Value | Where |
|---|---:|---|
| `Request.HTTP_TIMEOUT_SECONDS` | `30` | `resources/lib/vendor/clouddrive_common/remote/request.py`, class body |

Passed at `urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT_SECONDS)` — the one outbound HTTP call site in the whole tree. Confirmed by a tree-wide sweep: no other `urlopen`, no `urlretrieve`, no `http.client`, no `requests`. The service base class binds an ephemeral loopback socket to discover a free port, which is inbound; both database modules open SQLite connections whose 30-second timeout is a lock timeout, not a network one.

**The value is unmeasured.** Fifteen to thirty seconds is a recommended range for metadata calls, not a measurement of this add-on on this network. Too low produces spurious failures on slow Wi-Fi; too high reproduces the hang the change exists to remove. It is confirmed on the Android test phone during 01-07's acceptance pass.

**One value serves both paths** because the timeout applies per socket operation, not to a whole transfer: it bounds how long a single `read` may block, not how long a large file may take to arrive. A 4 GB download over a slow link never trips it as long as bytes keep arriving. That reasoning is a comment at the constant, because the obvious objection to a single constant is precisely the one that turns out not to hold.

**Worst-case wall time of the retry loop** is the number of tries multiplied by the timeout, plus the injected waits between attempts. At this class's defaults (`tries=4`, `delay=5`, `backoff=2`): `4 × 30 + 5 + 10 + 20 = 155 seconds`. It is recorded, not bounded — the wait goes through an injected function that defaults to `time.sleep`, and routing it through Kodi's abort-aware wait is Phase 4's work, not a behaviour change to make in a phase whose contract is preservation.

## Gate movement

Suite before this plan: **5 failed, 17 passed**. After: **3 failed, 19 passed**.

| Gate | Before | After Task 1 | After Task 2 | Owner |
|---|---|---|---|---|
| `test_no_eval` | red | **green** | green | this plan |
| `test_store_json_roundtrip` | green | green | green | this plan |
| `test_all_http_calls_have_timeout` | red | red | **green** | this plan |
| `test_tree_compiles` | green | green | green | — |
| `test_gpl_headers_intact` | green | green | green | 01-05 |
| `test_vendored_sha_recorded` | red | red | red | 01-07 |
| `test_vendored_md_sections` | red | red | red | 01-07 |
| `test_credits_content` | red | red | red | 01-07 |

The three still red are 01-07's documentation gates. Nothing this plan owns is red, and no gate that was green went red.

`test_store_json_roundtrip` was already green before this plan, because it exercises the `json` module against representative payloads rather than importing the store — the store needs Kodi's `xbmc` modules, which are not importable in the test environment. That is the right design for a gate, but it means the gate alone does not prove the *code path* round-trips. See the probe below.

## Verification beyond the gates

The gate proves the serializer. A throwaway probe proved the code path: a real `sqlite3` file, the exact `insert or replace into store(key, value) values(?,?)` and `select value from store where key = ?` statements now in `db.py`, six payloads — an account with tokens, an export record with schedules, an items-info map, a changes list, an extracted item with `audio`/`video`/`folder` sub-dicts and `None` values, and a children-name list — each pushed through **two** laps and through all three accessors (`get`, `getall`, `setmany`). Zero failures. The page cache's coerced body was checked separately: `BytesIO.getvalue()` → decode → two JSON laps → re-encode produced bytes identical to the original.

The probe is a scratch file and is deliberately not committed; it needs no Kodi modules and can be rebuilt from this paragraph.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The page cache stores bytes, a third shape JSON cannot carry**

- **Found during:** Task 1, in the pre-edit write-site audit
- **Issue:** `Source.do_GET` at `service/source.py:371` did `content_value = cached_page['content'].getvalue()` on a `BytesIO`, then stored that dict in the page cache at line 377. `repr(bytes)` round-tripped fine through `eval`; `json.dumps(bytes)` raises `TypeError: Object of type bytes is not JSON serializable`. Left alone, every directory-listing page response would have raised on cache write the moment the listing server was enabled. The plan enumerates two non-surviving shapes, a tuple and a non-string key; bytes is a third it did not anticipate.
- **Why it is in scope:** it is a defect introduced by this task's own change, and the plan gives the remedy in advance — "coerce it at the write site rather than special-casing the serializer".
- **Fix:** `content_value = Utils.str(cached_page['content'].getvalue())`. This is the exact inverse of what the read path already does: the same handler wrote those bytes with `Utils.encode`, which is `Utils.unicode(txt).encode('utf-8')`, and the read path at line 337 re-encodes with `Utils.encode` before serving. Every body written is HTML or a JSON string, so the decode is total and lossless. A four-line comment at the site states why.
- **Files modified:** `resources/lib/vendor/clouddrive_common/service/source.py` (one file beyond the plan's `files_modified` list)
- **Verification:** the probe above showed the body byte-identical after two round trips, with `response_code` and `headers` preserved.
- **Committed in:** `94640f6`

---

**2. [Rule 1 — Bug] There are four `repr(` write sites, not two**

- **Found during:** Task 1, in the same audit
- **Issue:** The plan's `must_haves` truth says "the two matching write sites", and its action text names "the key-value store's insert and the cache's insert and bulk-set" — which is itself three. The tree has four: `db.py:74` (`setmany`), `db.py:91` (`_insert`), `cache.py:76` (`setmany`), `cache.py:96` (`_insert`). Converting only the named ones would have left `db.setmany` writing `repr` output into a store whose read path is now `json.loads`, so any future caller would get a `JSONDecodeError` on read.
- **Fix:** all four converted. The plan's own acceptance criterion — `grep -c 'repr(' db.py` returns 0 — is only satisfiable this way, so the criterion and the prose disagreed and the criterion is the stricter and correct one.
- **Files modified:** none beyond the two the plan already lists
- **Verification:** `grep -c 'repr(' db.py` and `grep -c 'repr(' cache.py` both 0; `test_no_eval` green.
- **Committed in:** `94640f6`

---

### Precondition note

`.planning/config.json` was modified-but-uncommitted on arrival — orchestrator bookkeeping carried in from earlier plans, not this plan's doing. It was deliberately kept out of both commits, as 01-02 through 01-05 did. The source tree was clean before and after each commit.

---

**Total deviations:** 2 auto-fixed, both Rule 1. **Impact on scope:** one extra file (`service/source.py`), four lines of comment and one expression. Every acceptance criterion in the plan passes as written, including the two that the second deviation is the only way to satisfy.

## Prohibitions honoured

| Prohibition | How |
|---|---|
| VND-05 safety — no compatibility read path evaluating a legacy value as Python source | None added. `grep -c 'literal_eval' db.py` returns 0, no try-the-old-format-first branch exists, and a malformed row now raises `JSONDecodeError` rather than being interpreted. The new add-on id means no prior database exists to need one |
| VND-05 privacy — no credential-shaped value moved out of the profile database into a setting or a log line | Nothing moved. The change is the serializer only; `access_tokens` stays in `accounts.db` in the profile directory. No `Logger` call was added, and none of the four write sites logs its value |
| VND-06 transparency — this plan's edits must reach 01-07's record | The three read sites, the four write sites, the write-site audit per site, the timeout value with its unmeasured status and reasoning, and the retry loop's 155-second worst case are all recorded above under "For VENDORED.md" |

## Threat register outcomes

| Threat ID | Disposition | Outcome |
|---|---|---|
| T-1-01 | mitigate | Closed. No dynamic code execution construct remains outside `tests/`; `test_no_eval` green |
| T-1-19 | mitigate | Closed. No fallback evaluator, no flag, no migration shim |
| T-1-02 | mitigate | Closed. `timeout=self.HTTP_TIMEOUT_SECONDS` on the one call site; `test_all_http_calls_have_timeout` green and non-vacuous, having found exactly one call |
| T-1-20 | mitigate | Held. No credential-shaped value changed location |
| T-1-SC | accept | Nothing installed; `json` is standard library |

No new threat surface was introduced. `service/source.py` was edited but no network endpoint, auth path, file access pattern or schema changed — a value the same function already produced is now stored as text rather than bytes.

## Issues Encountered

- **Heredocs are blocked in this environment**, as 01-04 recorded. Both edits were made by Python patch scripts written to the scratch directory, each asserting the expected occurrence count of every substitution and refusing to write on a mismatch.
- **`db.py` is LF-only while every other vendored file is CRLF.** That is upstream's own convention for that file and was preserved: both edits were byte-level replacements, and each file's ending counts were checked before and after. Staging used `git -c core.autocrlf=false add`, as 01-04 established, and the index blobs were confirmed to carry `db.py` at 127 lone LFs, `cache.py` at 128 CRLF, `source.py` at 421 CRLF, `request.py` unchanged in convention.

## User Setup Required

None. No package-manager install, no dependency added; `json` is standard library.

## Known Stubs

None. Both tasks are complete implementations, not placeholders.

## Carry-forward for 01-07

- **VENDORED.md's local-modification table** takes the two tables under "For VENDORED.md" above: three read sites and four write sites, plus the one write-site coercion in `service/source.py`. That third file is a local modification to a vendored file and belongs in the record even though the plan's `files_modified` did not name it.
- **The timeout row** is `Request.HTTP_TIMEOUT_SECONDS = 30`, flagged **unmeasured**, with the per-socket-operation reasoning and the 155-second retry worst case.
- **Two acceptance-pass items are deferred to 01-07** and are the only unproven claims here: that 30 seconds behaves correctly on a real Android device on marginal Wi-Fi (D9), and that a clean-profile install never meets a database in the previous format (D10).
- **A note worth carrying:** `test_store_json_roundtrip` exercises the `json` module, not the store, because the store imports Kodi modules. It is a correct gate but not a complete proof; the probe described under "Verification beyond the gates" is what closes that gap, and re-running it is cheap if these files are ever touched again.
- **`source.py:296` has an upstream bug** — `get_subtitles` caches `item` under the subtitles key instead of `subtitles`. It is pre-existing, unrelated to this plan, out of scope under the scope boundary, and noted here only so it is not mistaken for damage from this change.

## Next Phase Readiness

- Phase 3's token store inherits a profile database that is JSON text in the same schema — same table, same TEXT columns, no migration.
- Phase 4's central HTTP layer inherits one named constant to tune rather than a literal to hunt for, and a gate that will fail the moment it adds a call site without a timeout.
- The two security findings this phase owns are closed, and both are enforced by syntax-tree checks rather than text matching, so neither goes stale as the tree grows.

## Self-Check: PASSED

- `resources/lib/vendor/clouddrive_common/db.py` — found, contains `json`, 0 `repr(`, 0 `eval(`
- `resources/lib/vendor/clouddrive_common/cache/cache.py` — found, contains `json`, 0 `repr(`, 0 `eval(`
- `resources/lib/vendor/clouddrive_common/remote/request.py` — found, `HTTP_TIMEOUT_SECONDS` present twice
- `resources/lib/vendor/clouddrive_common/service/source.py` — found, coercion present
- `94640f6` and `f8d1f51481a0704c3625f536a23b78e0278fbf44` — both present in git history
- `git show --name-only --format= f8d1f51481a0704c3625f536a23b78e0278fbf44` lists only `resources/lib/vendor/clouddrive_common/remote/request.py`
- No tracked file was deleted by either commit (`git diff --diff-filter=D` empty for both)
- `python -m compileall -q resources/ entrypoint.py service.py` exits 0
- Full suite: 3 failed, 19 passed — all three failures belong to 01-07
- Working tree clean after both commits, excluding the pre-existing `.planning/config.json`

---
*Phase: 01-vendor-lift*
*Completed: 2026-08-22*
