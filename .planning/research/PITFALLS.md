# Pitfalls Research

**Domain:** Kodi 20/21/22 media add-on + Microsoft Graph (OneDrive Personal & Business) + OAuth 2.0 device authorization grant, targeting Windows and Android TV
**Researched:** 2026-08-22
**Confidence:** MEDIUM-HIGH (see Evidence column per claim; Microsoft Graph / Entra behaviour read verbatim from Microsoft Learn, Kodi behaviour read verbatim from the `xbmc/xbmc` source tree, vendoring behaviour read from the actual `script.module.clouddrive.common` 1.4.0 source)

> **How to read the Evidence tags.** `PRIMARY` = read verbatim from an official spec/doc page or from upstream source code during this research pass. `CORROBORATED` = multiple independent community reports agreeing. `INFERRED` = my reasoning from a PRIMARY fact, not itself documented. Where research **corrected an assumption in the research question**, it is flagged **[CORRECTION]** — read those first, they are the ones that will otherwise get coded wrong.

---

## Corrections to Assumptions in the Brief

Four premises in the research question are wrong or imprecise. Fix these before planning, because each one changes what gets built.

| Assumption | Reality | Evidence |
|------------|---------|----------|
| Delta invalidation returns `resyncRequired` | v1.0 returns **HTTP 410 Gone** with error code **`resyncChangesApplyDifferences`** or **`resyncChangesUploadDifferences`**, plus a `Location` header containing a fresh `nextLink` to restart enumeration. `resyncRequired` is the retired OneDrive-API-v1 name. Handling only `resyncRequired` means the resync path never fires. | PRIMARY — [driveItem: delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0) |
| `ListItem.setInfo` was *removed* in Kodi 21/22 | Still present and functional in `xbmc/xbmc` **master** (Kodi 22 Piers), `xbmc/interfaces/legacy/ListItem.cpp:375`. It logs `LOGWARNING "…is deprecated and might be removed in future Kodi versions."` The migration is a **log-noise + type-strictness** problem, not a "the add-on stops working" problem. Do not schedule it as a blocker. | PRIMARY — source read |
| Targeting Kodi 20+ requires bumping `xbmc.python` | Every release 19→22 ships `<backwards-compatibility abi="3.0.0"/>`. Versions: 19.5=`3.0.0`, 20.5=`3.0.1`, 21.2=`3.0.1`, master=`3.0.2`. `<import addon="xbmc.python" version="3.0.0"/>` installs on all four. Bumping to `3.0.1` grants **no new API** — its only effect is to make Kodi 19 refuse to install the add-on. | PRIMARY — `addons/xbmc.python/addon.xml` at tags `19.5-Matrix`, `20.5-Nexus`, `21.2-Omega`, `master` |
| Vendoring `clouddrive.common` = copy the GitHub repo | The GitHub **default branch (`master`) is version 1.3.9** — the Python 2 / Kodi 18 line (`<import addon="xbmc.python" version="2.25.0"/>`). Version **1.4.0**, which `addon.xml` requires, lives only on the **`matrix` branch**. Vendoring the default branch silently downgrades you to Python 2 code. | PRIMARY — `raw.githubusercontent.com/cguZZman/script.module.clouddrive.common/{master,matrix}/addon.xml` |

---

## Critical Pitfalls

### Pitfall 1: Wrong authority + wrong `signInAudience` — one account class breaks and you don't find out for weeks

**What goes wrong:**
The device code endpoint is `POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode` where `{tenant}` is `common`, `consumers`, `organizations`, or a tenant GUID/domain. These are not interchangeable:

- `consumers` → **personal Microsoft accounts only**. A work account fails.
- `organizations` → **work/school only**. A personal account fails.
- `common` → both, **but only if the app registration's `signInAudience` is `AzureADandPersonalMicrosoftAccount`**.

Because the maintainer registers the Azure app once and (almost certainly) tests with their own account type first, the *other* account class is untested. The project explicitly supports both Personal and Business, so this pitfall lands squarely in scope.

**Why it happens:**
The Azure portal's default "Supported account types" radio is per-selection and easy to get wrong; the failure only reproduces with an account you don't have. Additionally, `AADSTS50194` fires only for apps created after a Microsoft cutoff date, so an older sample app registration behaves differently from a new one.

**How to avoid:**
1. Register the app with **Supported account types = "Accounts in any organizational directory (Any Microsoft Entra ID tenant - Multitenant) and personal Microsoft accounts"** (`signInAudience: AzureADandPersonalMicrosoftAccount`).
2. Use `/common` as the single authority. Do **not** expose an authority setting to users.
3. Verify the registration by reading `signInAudience` back from the app manifest, and record it in the maintainer setup doc as a checklist item — not prose.
4. Keep the authority in one constant, so the custom-`client_id` escape hatch cannot accidentally change it.

**Warning signs:**
- `AADSTS50194` — "Application isn't configured as a multitenant application. Usage of the /common endpoint isn't supported."
- `AADSTS700016` — "The application wasn't found in the directory/tenant."
- `AADSTS90002` — "InvalidTenantName."
- `AADSTS50020` — "User account from identity provider does not exist in tenant."
- Sign-in works for you, and exactly one bug reporter says "code page says the account can't be used here."

**Phase to address:** Auth phase, before any polling code. It is an Azure-portal configuration item, not code — put it in the phase's setup prerequisites so it is done before implementation starts.
*Evidence: PRIMARY — [device code grant](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code), [AADSTS error reference](https://learn.microsoft.com/en-us/entra/identity-platform/reference-error-codes)*

---

### Pitfall 2: "Allow public client flows" left off — device code returns a *confidential client* error that names a parameter you will never send

**What goes wrong:**
Entra ID has no confidential-client path for the device code grant. If the app registration does not have `allowPublicClient: true`, the `/token` endpoint returns:

```
AADSTS7000218: The request body must contain the following parameter:
'client_assertion' or 'client_secret'.
```

This is maximally misleading for a public-client add-on: it invites the developer to embed a client secret, which is exactly the thing the whole design avoids. Teams have shipped a secret to "fix" this.

**Why it happens:**
`allowPublicClient` defaults to *off* for new registrations, and the setting lives under Authentication → "Advanced settings", visually separated from the platform configuration. Nothing in the device-code request itself hints at it.

**How to avoid:**
- Set **Authentication → Advanced settings → Allow public client flows = Yes** on the maintainer's registration, and put it in the setup doc as a numbered step with the exact error text as the "if you skipped this, you'll see" note.
- Add a hard rule in the auth phase's plan: **no `client_secret` may appear anywhere in the repository, in any form, ever.** Enforce it with a CI grep for `client_secret` and `client_assertion`.
- Map `AADSTS7000218` to a specific in-add-on message aimed at the *custom client_id* user, since after shipping only they can trigger it: "This client ID is not configured for device sign-in. Enable 'Allow public client flows' in the app registration."

**Warning signs:** `AADSTS7000218` at the token step, immediately, with a valid `device_code`. Never intermittent.

**Phase to address:** Auth phase — same setup prerequisite block as Pitfall 1. The CI grep belongs in the CI phase.
*Evidence: PRIMARY (error text from AADSTS reference) + CORROBORATED (multiple Microsoft Q&A / PnP threads confirming the device-code-specific cause)*

---

### Pitfall 3: Discarding the rotated refresh token, then blaming the 90-day expiry

**What goes wrong:**
Microsoft's own wording: *"Refresh tokens replace themselves with a fresh token upon every use. The Microsoft identity platform doesn't revoke old refresh tokens when used to fetch new access tokens."*

Every `/token` refresh response contains a **new `refresh_token`**. Code that persists only `access_token` + `expires_in` and keeps re-sending the *original* refresh token appears to work indefinitely, because the old token is not revoked — until the original token hits its **90-day** lifetime, or the 90-day-inactivity clock (which never gets reset because the stored token never changes). The add-on then dies for every user at once, roughly 90 days after their sign-in, with no code change to blame.

This is the single highest-consequence bug in the whole auth rewrite: it is invisible during development, invisible in a two-week test cycle, and lands on all users simultaneously.

**Why it happens:**
The refresh looks idempotent. Most tutorials show `token = resp['access_token']` and nothing else. The existing vendored `OAuth2._validate_access_tokens` requires `refresh_token` to be present in the *stored* blob but does not force the *response's* refresh token to be written back.

**How to avoid:**
- Treat token persistence as a single atomic operation: **always write back the full token response**, and if the response omits `refresh_token`, keep the previous one — never the reverse.
- Store `issued_at` alongside, so the inactivity clock is observable.
- Write a unit test with a recorded two-step refresh fixture asserting the persisted refresh token *changed*. This is testable off-device and must be.
- Because the add-on is a media player that may sit unused for months, add a low-cost keepalive: on Kodi startup, if the stored token is older than N days (N ≈ 60), refresh proactively.

**Warning signs:**
- `AADSTS700082` — *"ExpiredOrRevokedGrantInactiveToken - The refresh token has expired due to inactivity… Expected part of the token lifecycle."*
- `AADSTS70008` — `ExpiredOrRevokedGrant`, same cause.
- `AADSTS50173` — grant expired due to revocation or password change.
- Early sign: log the refresh token's first 8 chars (never the whole token) and confirm it changes between refreshes.

**Phase to address:** Auth phase. The keepalive belongs to the service phase but the write-back and its test are non-negotiable in auth.
*Evidence: PRIMARY — [refresh tokens](https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens), AADSTS reference*

---

### Pitfall 4: Treating tenant policy rejections as add-on bugs

**What goes wrong:**
OneDrive for Business tenants can refuse a third-party public client for reasons the add-on cannot fix. These arrive as generic `invalid_grant` / `invalid_client` responses with the real reason buried in `error_description`:

| Code | Meaning | Add-on can fix? |
|------|---------|-----------------|
| `AADSTS65001` | `DelegationDoesNotExist` — user/admin hasn't consented | No — user must consent, or admin must |
| `AADSTS90094` | `AdminConsentRequired` | **No** — admin action only |
| `AADSTS53003` | `BlockedByConditionalAccess` | **No** — CA policy |
| `AADSTS530035` | `BlockedBySecurityDefaults` | **No** |
| `AADSTS50076` / `AADSTS50079` | MFA required / MFA enrollment required | No — user completes on phone |
| `AADSTS7000112` | Application disabled | No |
| `AADSTS500011` | Resource principal not found in tenant | No |
| `AADSTS50055` | Password expired | No |

If these render as "Sign-in failed. Please try again," the user retries forever and files a bug. The project already anticipates this with the custom-`client_id` escape hatch — but the escape hatch is worthless if the user is never told it exists.

**Why it happens:**
The natural error handler catches the HTTP 400 and shows a generic string. The AADSTS code is inside a long `error_description` blob that nobody parses.

**How to avoid:**
- Parse the AADSTS code out of `error_description` with a regex (`AADSTS\d+`) and route on it. Do **not** try to render Microsoft's full English description on a TV — it is paragraph-length and includes markdown links.
- Ship a small mapping table: AADSTS code → one short sentence + one action. Everything unmapped falls through to a generic message **that still shows the raw code**, because a code the user can paste into an issue is worth more than a friendly sentence.
- For the "admin must act" family (`90094`, `53003`, `530035`, `7000112`, `500011`) the message must name the escape hatch explicitly: *"Your organization blocks this app. Ask your admin to approve it, or set a custom Client ID in Settings → Advanced."*

**Warning signs:** Business users reporting "it just says failed"; log lines containing `AADSTS` that the UI never surfaced.

**Phase to address:** Auth phase (the mapping table ships with the first sign-in implementation, not later — an unmapped error at launch is what generates the bug reports you then can't diagnose).
*Evidence: PRIMARY — AADSTS error reference*

---

### Pitfall 5: A device-code dialog that is unreadable, uncancellable, or expired on a TV

**What goes wrong:**
Five separate TV-specific failures, all in one flow:

1. **`verification_uri_complete` does not exist.** Microsoft explicitly documents that it is *not* returned, despite being optional-but-common in RFC 8628. Any design that assumes a single QR-scannable "click here, you're done" URL is building on a field that will never arrive. You get `verification_uri` (`https://microsoft.com/devicelogin`) **and** a separate `user_code` that the user must type.
2. **15-minute window.** `expires_in` defaults to 900s. A user who walks to another room, can't find their phone, and comes back gets `expired_token` with no explanation.
3. **Polling too fast.** The response carries `interval`; ignoring it and polling every second earns `slow_down` behaviour and wasted battery/network on a low-end box.
4. **Uncancellable modal.** If the code dialog is a blocking `DialogProgress` with no cancel path, the only escape on a remote is force-stopping Kodi.
5. **Personal accounts sign in twice.** Microsoft documents that personal-account users on `/common` or `/consumers` are *asked to sign in again* to transfer auth state, because the device can't access their cookies. Users read this as "it didn't work" and abandon.

**Why it happens:**
Device code is usually demoed on a laptop where all five are invisible.

**How to avoid:**
- Render `user_code` at the largest legible size the dialog allows; render the QR for `verification_uri` (the module already ships a `QRDialogProgress` and a `pin-dialog.xml` skin — reuse them rather than inventing).
- Show a live countdown derived from `expires_in`, and on `expired_token` **offer a one-button restart** rather than dumping to an error.
- Sleep exactly `interval` seconds between polls, read from the response, never hardcoded. Back off further on any `slow_down`.
- The dialog must be cancellable with Back/Escape, and cancelling must abort the poll loop cleanly (see Pitfall 12 — this codebase already has a cancellation bug that returns `None`).
- Add one line of copy for personal accounts: *"You may be asked to sign in again on your phone — that's expected."*

**Warning signs:** `expired_token` in logs; users reporting "the code screen just sat there"; no `interval` in the poll loop.

**Phase to address:** Auth phase. This is the phase's actual acceptance criterion — "sign in from the couch with a remote" is the project's stated core value.
*Evidence: PRIMARY — device code grant doc (explicit `verification_uri_complete` note, 15-min default, `interval`, the personal-account re-sign-in note)*

---

### Pitfall 6: Ignoring `Retry-After` on 429 and turning a throttle into a lockout

**What goes wrong:**
Microsoft Graph returns **HTTP 429** with a `Retry-After` header in seconds and body `error.code = "TooManyRequests"`. The doc is unusually blunt: *"Avoid immediate retries, because all requests accrue against your usage limits."* A retry loop that ignores `Retry-After` extends the throttle window indefinitely — the add-on appears permanently broken.

This add-on is a throttle magnet by design: `get_drives()` currently makes a guaranteed-failing extra round trip per account load, subtitle discovery issues an extra search **per played item**, the export/slideshow features walk whole drives, and a background service polls delta. On a shared consumer OneDrive that is enough to hit limits.

**Why it happens:**
`urllib` doesn't retry, so people bolt on a naive `for attempt in range(3): ... time.sleep(1)` loop that is worse than not retrying.

**How to avoid:**
- One central HTTP layer that handles 429 (and 503) by sleeping **exactly `Retry-After`**, and exponential backoff only when the header is absent — which is what Microsoft prescribes.
- The sleep must be interruptible by `xbmc.Monitor.waitForAbort(seconds)`, never `time.sleep`, or Kodi hangs on shutdown while waiting out a 120-second throttle.
- Cap total retries and surface a real message; a spinner that never resolves is worse than an error.
- Cut throttle pressure at the source: skip the bare `/drives` call (Pitfall 8), constrain subtitle search server-side, and use delta instead of re-listing (both already flagged in `CONCERNS.md`).

**Warning signs:** `429` in the Kodi log; browsing that works, then stops working for minutes, then works again; users on large drives affected more.

**Phase to address:** Browse phase — the HTTP layer must land with the first Graph calls, because retrofitting it into scattered call sites later is the expensive version.
*Evidence: PRIMARY — [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling)*

---

### Pitfall 7: Path encoding — the `root:/…:` syntax and per-segment percent-encoding

**What goes wrong:**
`CONCERNS.md` already documents that `resources/lib/provider/onedrive.py` concatenates paths straight into Graph URLs. The precise rules, which are easy to get half-right:

- Addressing form: `/drive/root:/Documents/MyFile.xlsx:/content`. The **colons delimit the path**; a filename containing `:` would break the delimiter — but OneDrive reserves `:` in names, so that specific case cannot occur.
- **Reserved in OneDrive names** (so they will never appear): `/ \ * < > ? : |`. **OneDrive for Business additionally reserves `#` and `%`.** So `#` and `%` in a name are *possible on Personal, impossible on Business* — which is exactly why a Personal-only test pass misses nothing and a Business-only test pass misses everything.
- Legal-unencoded path chars are RFC 3986 `pchar` = `unreserved / pct-encoded / sub-delims / ":" / "@"`, where `sub-delims = ! $ & ' ( ) * + , ; =`. **`+` and `'` are sub-delims and are legal unencoded in a path segment.** They are *not* the problem the brief implies — the problem is `#`, space, and literal `%`.
- Microsoft's explicit warning: *"You can't encode an entire URL in one call, because the encoding rules for each segment of a URL are different."*

**Why it happens:**
`urllib.parse.quote(path)` with default `safe='/'` is *almost* right — it encodes `#` and space and `%` correctly and leaves `/` as a separator. The trap is calling `quote()` on the **whole URL** including `https://graph.microsoft.com/v1.0/drive/root:`, which mangles the scheme and the `root:` delimiter; or using `quote_plus`, which turns spaces into `+` and silently addresses a different (nonexistent) file.

**How to avoid:**
- One helper: build the path with `urllib.parse.quote(path, safe="/")` applied **only to the user-supplied path**, then concatenate into the fixed `.../root:` + path + `:/...` template. Never quote the template.
- Never `quote_plus` for path segments.
- Add `import urllib.parse` explicitly (already a known bug — the implicit import works only by accident).
- Fixtures for the test suite, taken verbatim from Microsoft's worked examples: `Ryan's Files` → `Ryan's%20Files`; `Break#Out` → `Break%23Out`; `estimate%s.docx` → `estimate%25s.docx`.

**Warning signs:** Graph 400/404 on specific folders only; a folder that opens on Personal but 404s when the same code path is exercised on Business; `+` appearing in a URL where a space should be.

**Phase to address:** Browse phase, with unit tests. This is pure logic and fully testable off-device — there is no excuse for finding it on a TV.
*Evidence: PRIMARY — [How to address resources](https://learn.microsoft.com/en-us/onedrive/developer/rest-api/concepts/addressing-driveitems)*

---

### Pitfall 8: OData single-quote escaping — and the fact that half this codebase already gets it right

**What goes wrong:**
Graph's `search(q='…')` takes an **OData string literal**. Inside such a literal a single quote must be doubled (`'` → `''`). Percent-encoding is *not* a substitute: `%27` decodes back to `'` server-side and still terminates the literal.

`CONCERNS.md` records the exact shape of this bug: `get_subtitles()` (line 189) does `.replace("'", "''")`; `search()` (line 179) does not. The escape was known and applied inconsistently — which means it will regress again unless it lives in one function.

The stakes are higher than a 400: an OData literal break is a **query-injection surface**, and the injected text comes from a Kodi keyboard the user controls.

**How to avoid:**
- One function, e.g. `odata_literal(s)` → `"'" + s.replace("'", "''") + "'"`, then percent-encode the assembled query string. Both call sites use it; a grep-based CI check forbids raw `search(q=` string interpolation.
- Test case: search for `Ocean's Eleven`.

**Warning signs:** Graph 400 on searches containing an apostrophe; two different escaping styles in the same file.

**Phase to address:** Browse phase (search is part of browse parity).
*Evidence: PRIMARY — RFC 3986 / OData literal rules confirmed by the addressing doc's sub-delims table; bug location from `CONCERNS.md`*

---

### Pitfall 9: `@microsoft.graph.downloadUrl` expiring mid-playback

**What goes wrong:**
Microsoft's exact wording: *"Preauthenticated download URLs are valid for a limited time. Use them immediately, as they might expire within minutes. You don't need to include an `Authorization` header when you access the download URL."*

Community measurement puts practical validity near an hour, but Microsoft documents **no duration** and warns it may be minutes. For a media add-on this is the difference between "works" and "works until you pause a two-hour film."

Concrete failures:
- Resolve the URL at listing time (when building the directory) rather than at play time → the URL can be tens of minutes stale before playback even starts.
- Kodi's player reconnects on seek or on a buffer stall. That reconnect goes to the *stored* URL. If it expired, playback dies at an arbitrary point with a generic "unable to play" — indistinguishable from a codec problem.
- **`Range` requests must go to the `downloadUrl` host, not to `/content`.** Sending `Range` to `/content` gets you a 302 and the range is lost, so seeking degrades to a full re-download — catastrophic on an Android TV box's memory.

**How to avoid:**
- Resolve `@microsoft.graph.downloadUrl` **at play time only**, in the play handler, never during directory listing.
- Prefer handing Kodi a URL it can re-resolve (a plugin path the add-on re-handles) over a bare expiring HTTPS URL, so a reconnect re-mints the link. If a bare URL is unavoidable, treat it as single-use.
- Seek/`Range` targets the `downloadUrl` host.
- Do not cache `downloadUrl` in the item cache. Cache the item id; mint the URL on demand.

**Warning signs:** Playback that starts fine and dies on the first seek; long films failing near the end; failures correlated with how long the user browsed before pressing play.

**Phase to address:** Play phase. Explicit manual acceptance item: *play a 2h+ file, pause 30 min, resume, then seek.* Nothing shorter reproduces it.
*Evidence: PRIMARY — [Download driveItem content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0)*

---

### Pitfall 10: Delta sync — wrong error code, `None` tokens, and 404-triggered amnesia

**What goes wrong:**
Three compounding bugs, two of which already exist in this codebase:

1. **Wrong error code.** Handling `resyncRequired` never fires; v1.0 emits **410 Gone** + `resyncChangesApplyDifferences` / `resyncChangesUploadDifferences`, with a `Location` header holding the restart `nextLink`. Code that doesn't handle 410 either crashes or silently keeps a dead token.
2. **Persisting `None`.** `CONCERNS.md`: `changes()` persists `extra_info['change_token']` including `None` when the delta response had no `@odata.deltaLink` — which happens whenever pagination returns early on cancellation. Result: sync state silently resets to a full enumeration, which is both slow and a throttle trigger (Pitfall 6).
3. **404 clears the token.** `on_exception` clears the change token on *any* 404, including transient ones. A single blip wipes sync state.

Plus two Graph semantics that are easy to violate:
- *"The `parentReference` property on items won't include a value for `path`… **When using delta you should always track items by id**."* Any code deriving a path from a delta result is wrong.
- The same item can appear more than once in a feed; **use the last occurrence**. Naive `dict` accumulation in iteration order happens to be right; `if id not in seen` first-wins is wrong.

**How to avoid:**
- Handle 410 explicitly: read the `Location` header, restart from that `nextLink`, and only then reconcile.
- Persist the change token only when it is non-`None`. Make this an invariant assertion, not a comment.
- Distinguish 410-resync from 404-transient. Never clear the token on a bare 404.
- Track by `id`; never reconstruct paths from delta output.
- Use `?token=latest` to grab a starting deltaLink when the add-on only needs future changes — it returns an empty `value` array and skips a full enumeration entirely.

**Warning signs:** Full re-enumeration on every service tick; `410` in logs with no matching handler; sync "working" but re-downloading everything; STRM exports duplicating.

**Phase to address:** Deferred — delta belongs with the restored background-service / export features, **after** core auth→browse→play. But the *token-persistence invariant* is cheap and should ride along with the pagination rewrite in the browse phase, since both live in `process_files`.
*Evidence: PRIMARY — [driveItem: delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0); existing-bug locations from `CONCERNS.md`*

---

### Pitfall 11: `GET /drives` is not a Microsoft Graph v1.0 endpoint

**What goes wrong:**
The v1.0 `List Drives` reference documents exactly four forms: `/groups/{id}/drives`, `/sites/{id}/drives`, `/users/{id}/drives`, `/me/drives`. **A bare `GET /drives` is not among them.** The current `get_drives()` calls `/drives` then `/me/drives` and dedupes, swallowing a 403 for personal accounts.

So the existing code pays a guaranteed-failing round trip per account load (already logged in `CONCERNS.md` as a performance bottleneck) against an endpoint that isn't in the contract — meaning its current behaviour is undefined and could change without notice.

**Why it happens:**
`/drives` appears to work in some contexts and is widely copied from Graph Explorer sessions.

**How to avoid:**
- Use `/me/drives` for the signed-in user's drives. For SharePoint document libraries (explicitly non-first-class in this project), use `/sites/{id}/drives`.
- Delete the bare `/drives` call. If SharePoint enumeration regresses, that is an acceptable trade — `PROJECT.md` scopes SharePoint out of tested support.
- Every removed round trip is also removed throttle pressure and removed Android TV latency.

**Warning signs:** A 403 in the log on every account load that nothing reacts to; account list taking two round trips to appear.

**Phase to address:** Browse phase (account/drive enumeration precedes folder listing).
*Evidence: PRIMARY — [List Drives](https://learn.microsoft.com/en-us/graph/api/drive-list?view=graph-rest-1.0)*

---

### Pitfall 12: Typed InfoTag setters turn a *silent* float bug into a *hard crash* — and the setters live in the vendored module, not the provider

**What goes wrong:**
Two things, and the second is the one that wrecks phase estimates.

**(a) Type strictness is a real regression risk, in the exact place `CONCERNS.md` already flags.** `ListItem.setInfo` parses values via `strtol` on a string — so `duration = 1234.5` was silently truncated to `1234` and nobody noticed. The typed setters are SWIG-bound to real C++ ints:

```
InfoTagVideo::setDuration(int duration)          // seconds
InfoTagVideo::setYear(int) / setEpisode(int) / setSeason(int)
InfoTagVideo::setPlaycount(int) / setUserRating(int)
InfoTagVideo::setRating(float rating, int votes, ...)
InfoTagVideo::setResumePoint(double time, double totaltime = 0.0)
```

Passing a Python `float` to an `int` parameter raises `TypeError`. The existing `duration / 1000` (true division, Python 3) produces a float. **Migrating to typed setters converts an existing latent bug into a crash on every video item.** Fix `int(ms // 1000)` *in the same commit* as the setter migration, not before or after.

**(b) The `setInfo` calls are in the module you're vendoring.** `clouddrive/common/ui/addon.py` lines **424**, **439**, **583** call `list_item.setInfo(...)`. The provider glue in this repo builds the info dicts; the module applies them. So "migrate to typed InfoTag setters" is not a change to `resources/lib/provider/onedrive.py` — it is a change to the **vendored module's item-building path**, which means it is blocked on vendoring being done first.

Also deprecated with warnings (verified in master): `setUniqueIDs`, `setRating`, `addSeason`, `setCast`, `getUniqueID`, `getRating`, `getVotes`, and — directly relevant to the "resume / watched-state sync" restored feature — the `ListItem.setProperty()` / `getProperty()` keys **`totaltime`** and **`resumetime`**, which now route to `InfoTagVideo.setResumePoint()` / `getResumeTime()` / `getResumeTimeTotal()`.

**How to avoid:**
- Sequence the roadmap so **vendoring precedes the InfoTag migration**. Any other order produces rework.
- Do the float→int fix and the setter migration atomically.
- Convert the info-dict → typed-setter mapping in **one** function in the vendored module, so there's a single place to extend.
- Because `setInfo` still works, this migration can be verified by grepping the Kodi log for `is deprecated` and requiring zero hits — a cheap, objective acceptance criterion.

**Warning signs:** `TypeError` on video items after migration; `LOGWARNING … is deprecated` still in the log after the phase claims to be done; resume points silently not persisting.

**Phase to address:** Kodi-modernization phase, **after** the vendoring phase. Not a blocker for auth — `setInfo` still functions, so this can safely sit behind auth in the ordering.
*Evidence: PRIMARY — `xbmc/interfaces/legacy/ListItem.cpp`, `xbmc/interfaces/legacy/InfoTagVideo.h` (master); `clouddrive/common/ui/addon.py` (branch `matrix`, v1.4.0)*

---

### Pitfall 13: Vendoring breaks every hardcoded `script.module.clouddrive.common` lookup

**What goes wrong:**
The module refers to itself by add-on id in at least six places, verified in the 1.4.0 source:

| File:line | Call |
|-----------|------|
| `clouddrive/common/ui/addon.py:82` | `self._common_addon_id = 'script.module.clouddrive.common'` |
| `clouddrive/common/service/export.py:40` | `self._common_addon_id = 'script.module.clouddrive.common'` |
| `clouddrive/common/ui/utils.py:33` | `common_addon_id = 'script.module.clouddrive.common'` |
| `clouddrive/common/ui/dialog.py:126` | `KodiUtils.get_addon_info("profile", "script.module.clouddrive.common")` → QR image path |
| `clouddrive/common/remote/errorreport.py:70` | `get_addon_info('version', 'script.module.clouddrive.common')` |
| `clouddrive/common/remote/signin.py:32` | builds the **User-Agent** from the common module's version |

These resolve via `xbmcaddon.Addon(id)`. Once the dependency is removed from `addon.xml` and the module is uninstalled, `xbmcaddon.Addon('script.module.clouddrive.common')` raises `RuntimeError: Unknown addon id`.

The nastiest one is **`dialog.py:126`**: it writes `qr.png` into the *common module's* profile directory. That is the QR image for the sign-in dialog — i.e. the vendoring bug lands precisely on the device-code screen, the project's core value.

Worse: if the user *also* has `plugin.googledrive` or `plugin.dropbox` installed, `script.module.clouddrive.common` is still installed, so these lookups **keep working** on the maintainer's machine and fail only for users who have nothing else from that family. That is the worst possible failure distribution.

**How to avoid:**
- Grep the vendored tree for the literal string `script.module.clouddrive.common` and resolve every hit to *this* add-on's own id/profile/version before the vendoring phase is called done. Make the grep a CI check returning zero hits.
- Replace version-in-User-Agent with this add-on's own version.
- **Test on a machine with no other cloud-drive add-on installed.** Add "uninstall `script.module.clouddrive.common` and all sibling add-ons, then run" to the vendoring phase's acceptance checklist — otherwise the test is invalid.

**Warning signs:** `RuntimeError: Unknown addon id`; QR image not rendering; works for you, fails for a clean install.

**Phase to address:** Vendoring phase — it is the phase's definition of done.
*Evidence: PRIMARY — source read of `script.module.clouddrive.common` v1.4.0 (`matrix` branch)*

---

### Pitfall 14: Vendored package-name collisions (`clouddrive`, and especially `resources`) plus the Kodi 20 `sys.path` regression

**What goes wrong:**
The module declares `<extension point="xbmc.python.module" library="/" />`, so its **repository root** goes on `sys.path`. Its root contains two top-level packages:

- `clouddrive/` — the intended one.
- `resources/` — **with an `__init__.py`**, making `resources` an importable top-level package.

`resources` is the directory name every Kodi add-on uses. If the vendored tree is placed such that its root lands on `sys.path`, `import resources.something` becomes ambiguous between this add-on's `resources/` and the vendored one.

Compounding this, **Kodi 20 shipped a `sys.path` ordering regression** (`xbmc/xbmc` issue 22985): Kodi 19 ordered *addon → dependencies → system python → site-packages*; Kodi 20 reversed it to *system python → site-packages → addon → dependencies*, so an add-on bundling its own copy of a library could silently load the system copy. Marked fixed (PR 23244), but affected 20.x builds are in the wild — and Android TV users are exactly the population that doesn't update Kodi promptly.

Third collision risk: a user with `plugin.googledrive` installed still has `script.module.clouddrive.common` on `sys.path` providing a **different-version** `clouddrive` package. Whichever appears first in `sys.path` wins. Symptom: your vendored fixes appear not to apply.

**How to avoid:**
- **Rename the vendored package.** Do not keep `clouddrive`. Move it under this add-on's own namespace, e.g. `resources/lib/onedrive_common/`, and rewrite imports. This is mechanical, one-time, and permanently immunises against every sibling add-on. Keeping the name to minimise the diff is the tempting wrong choice.
- Do **not** vendor the module's top-level `resources/` package as a top-level package. Merge its `settings.xml`, `language/`, and `skins/` into this add-on's existing `resources/`, and delete the stray `resources/__init__.py`.
- Never add a vendored directory to `sys.path` manually. Import through the add-on's own package path so normal Python resolution applies.
- Verification: `import onedrive_common; print(onedrive_common.__file__)` in the Kodi log at startup during development, asserting it points inside this add-on.

**Warning signs:** Behaviour differing between a clean box and yours; edits to vendored files having no effect; `ImportError` only on machines with sibling add-ons; a stack trace whose file paths point into `addons/script.module.clouddrive.common/`.

**Phase to address:** Vendoring phase. The rename decision must be made *before* any code is copied — reversing it later means redoing every import.
*Evidence: PRIMARY — module file tree + `addon.xml`; [xbmc/xbmc#22985](https://github.com/xbmc/xbmc/issues/22985)*

---

### Pitfall 15: Vendoring the wrong branch, dropping the module's own service, and losing its skin XML

**What goes wrong:**
Four separate ways the vendoring phase ends "done" but broken:

1. **Wrong branch.** `master` is **1.3.9** — Python 2, `<import addon="xbmc.python" version="2.25.0"/>`. Version **1.4.0** (what `addon.xml` requires) is on the **`matrix` branch**. Cloning the default branch gets you Python 2 code that imports cleanly enough to look plausible and fails at runtime.
2. **The module registers its own Kodi service.** Its `addon.xml` has `<extension point="xbmc.service" library="service.py" start="login" />`. Uninstall the module and that service simply stops existing. Whatever it does (`start="login"` implies startup/login work) must be folded into this add-on's `service.py` or it silently disappears.
3. **Transitive Kodi-repo dependencies remain.** The module imports `script.module.dateutil` and `script.module.pyqrcode`. Vendoring the module does *not* remove those; they must either stay declared in `addon.xml` or be vendored/replaced too. `pyqrcode` matters specifically because it renders the sign-in QR code.
4. **Skin XML and media.** `resources/skins/default/1080i/{pin-dialog,export-main-dialog,export-schedule-dialog}.xml` plus `resources/skins/default/media/*.png` back the `WindowXMLDialog` subclasses in `clouddrive/common/ui/dialog.py`. `WindowXMLDialog` resolves its XML relative to the add-on path it is constructed with — vendoring without updating that path yields a dialog that fails to open, again on the sign-in screen.

**How to avoid:**
- Vendor from the **`matrix`** branch (or, better, from the exact installed `script.module.clouddrive.common` 1.4.0 directory on a working Kodi install — that is ground truth for what the add-on was tested against).
- Record the upstream commit SHA and branch in a `VENDORED.md` at the vendored tree's root. Without it, nobody can ever diff against upstream again.
- Fold `service.py` deliberately: read it, decide what survives the auth rewrite, and delete the rest — the whole point of vendoring is to *trim*.
- Copy skin XML + media into this add-on's `resources/skins/` and update every `WindowXMLDialog` construction site's path argument.
- Acceptance: open every dialog the add-on can open, from a remote, on a clean install.

**Phase to address:** Vendoring phase, ordered **first** — auth, InfoTag migration, and settings all depend on owning this code.
*Evidence: PRIMARY — `addon.xml` on both branches, file tree, `clouddrive/common/ui/dialog.py`*

---

### Pitfall 16: Vendoring licences — GPL-3.0 plus an Apache-2.0 subdirectory nobody notices

**What goes wrong:**
`script.module.clouddrive.common` is `GPL-3.0-or-later` with per-file GPL headers naming *Carlos Guzman (cguZZman)*. `plugin.onedrive` is already `GPL-3.0-or-later`, so the copyleft direction is fine.

But **`clouddrive/common/cache/` carries its own `LICENSE` — Apache License 2.0**, i.e. third-party code with different obligations already nested inside. Apache-2.0 §4 requires retaining copyright/attribution notices and stating changes. A "flatten and tidy the vendored tree" pass deletes that `LICENSE` file without anyone noticing.

Two further obligations people miss:
- The GPL requires **preserving copyright notices** — the per-file headers must survive, including on files you modify. Modified files should note the modification.
- `addon.xml` currently carries a `<disclaimer>` describing the third-party sign-in server and pointing at `cguZZman/drive-login`. After the auth rewrite that text is **factually false**, and leaving it is both a documentation bug and a misleading security statement.

**How to avoid:**
- Preserve `LICENSE.txt` (GPL-3) and `clouddrive/common/cache/LICENSE` (Apache-2.0) in the vendored tree, at paths that still make clear what they cover after any reorganisation.
- Add `VENDORED.md`: upstream URL, branch, version, commit SHA, licence per subtree, and a list of local modifications.
- Keep GPL file headers; add a "Modified by …" line where you change a file.
- Rewrite the `addon.xml` `<disclaimer>` in the auth phase to describe the actual design (device code, tokens stay on device, no broker). Do not just delete it — the disclaimer is what tells users where their tokens go, and now the answer is good news.

**Warning signs:** A vendoring diff that deletes `LICENSE` files; a `<disclaimer>` still naming `drive-login` after the broker is gone.

**Phase to address:** Vendoring phase (licence files); auth phase (disclaimer rewrite).
*Evidence: PRIMARY — `LICENSE.txt`, `clouddrive/common/cache/LICENSE`, per-file headers, current `addon.xml`*

---

### Pitfall 17: Existing users — old refresh tokens are bound to the old client and cannot be migrated

**What goes wrong:**
This is the migration question, and the answer is harder than "run a settings migration."

**Where existing state lives** (verified in v1.4.0 source):
- Accounts, drives, and **OAuth tokens** → `special://profile/addon_data/plugin.onedrive/accounts.db`, a SQLite DB (`SimpleKeyValueDb`, WAL mode), one row per account.
- Settings values → `special://profile/addon_data/plugin.onedrive/settings.xml`, keyed by setting `id`. **Kodi never rewrites this on upgrade.**
- A legacy `accounts.cfg` → `accounts.db` migration already exists in `AccountManager.__init__`, renaming the old file to `accounts.cfg.migrated`. That is the pattern to copy.

**Why the tokens are unmigratable:** OAuth refresh tokens are bound to the `client_id` they were issued to. Existing users' tokens were minted through the broker's client registration. The new embedded `client_id` is a *different client*. Redeeming an old refresh token against the new client fails — the user cannot be silently carried across. **Every existing user must re-authenticate. There is no way around it.**

The bad outcome is not the re-auth; it's the *shape* of the re-auth. Naive code loads the account, tries a refresh, gets an `AADSTS` error, and shows "Sign-in failed" — leaving the user to guess whether the add-on is broken.

**Dead settings:** `sign-in-server` still holds `https://drive-login.herokuapp.com` in every existing install. `PROJECT.md` already correctly notes that changing the *default* fixes nothing, because the *stored* value persists. Removing the setting from `resources/settings.xml` orphans the stored value rather than clearing it — harmless, but it means "we deleted the setting" is not the same as "the dead URL is gone from users' machines."

Also note `allow_directory_listing` and `port_directory_listing` are defined **twice** — in `plugin.onedrive`'s `settings.xml` *and* in the module's own `settings.xml`, but the module's code reads them via `KodiUtils.get_addon_setting(...)` (unqualified, i.e. the *calling* add-on's). After vendoring, the module's copy becomes a second, orphaned settings file. Consolidate to one.

**How to avoid:**
- Write an explicit, versioned migration that runs once on first launch after upgrade, gated on a `schema_version` setting (new id, default `0`).
- Migration steps: (1) read `accounts.db`; (2) **preserve** account display names and drive selections; (3) **discard** `access_token` / `refresh_token` and mark each account `needs_reauth`; (4) archive the original DB to `accounts.db.pre-v3` rather than deleting it — a rollback path costs nothing; (5) delete the `sign-in-server` value explicitly via `xbmcaddon` if it is still addressable, and remove it from `settings.xml`; (6) set `schema_version = 1`.
- The re-auth prompt must be *proactive and explained*, shown once at first launch: *"OneDrive now signs in directly on this device. Your accounts are still here — please sign in once more to reconnect."* Not an error dialog after a failed refresh.
- **Also replace the `eval()`-based storage while you are in there** — see Pitfall 18.

**Warning signs:** Upgraded users reporting "it lost my account"; `AADSTS` errors in the log at startup with no user-facing explanation; migration re-running every launch (missing `schema_version` write).

**Phase to address:** A dedicated **migration phase**, sequenced *after* auth works (you cannot write the "sign in again" flow before the sign-in flow exists) and *before* the first distributed release. Do not fold it into auth — it needs its own acceptance pass against a real pre-upgrade install.
*Evidence: PRIMARY — `clouddrive/common/account.py`, `clouddrive/common/db.py`, current `resources/settings.xml`; OAuth client-binding is PRIMARY from the refresh-token doc ("Refresh tokens are bound to a combination of user and client")*

---

### Pitfall 18: The account store round-trips values through `eval()`

**What goes wrong:**
`SimpleKeyValueDb` persists values as Python `repr()` strings and reads them back with **`eval(row[0])`** (`clouddrive/common/db.py`, `get()` and `getall()`). This is the store that holds OAuth refresh tokens.

`eval()` on file-backed data is arbitrary code execution with the privileges of the Kodi process. It requires an attacker to write to `accounts.db` — but note the Android storage path (Pitfall 19): on Android, `special://home` resolves under `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/`, which on older Android versions is broadly readable/writable by other apps holding storage permission. A sideloaded app on a cheap TV box is a realistic threat there in a way it isn't on Windows.

Even absent an attacker, `eval()` makes the token store fragile: any malformed row raises inside a bare parse and takes out account loading entirely.

**How to avoid:**
- Replace `repr()`/`eval()` with `json.dumps` / `json.loads` during the vendoring trim. Handle the mixed-format read (try JSON, fall back to `ast.literal_eval` — **never** `eval` — for legacy rows) inside the migration from Pitfall 17, then write JSON forever after.
- If `eval` must survive temporarily, it must be `ast.literal_eval` at minimum. There is no scenario in this codebase requiring real `eval`.
- Restrict the file mode where the platform allows it.

**Warning signs:** `eval(` anywhere in the vendored tree — make this a CI grep with zero tolerance.

**Phase to address:** Vendoring phase (replace the mechanism) + migration phase (convert existing rows).
*Evidence: PRIMARY — `clouddrive/common/db.py`; Android path from Kodi docs/community*

---

### Pitfall 19: Android TV — an HTTP call with no timeout hangs the add-on forever

**What goes wrong:**
`clouddrive/common/remote/request.py:132` calls `urllib.request.urlopen(req)` **with no `timeout` argument**. Python's default is the global socket timeout, which is `None` — block indefinitely.

On Windows with wired ethernet this never manifests. On an Android TV box on marginal Wi-Fi — the exact primary target — a stalled connection means:
- The plugin process hangs on the socket. Kodi shows a spinner with no cancel.
- The user's only recovery from a remote is force-stopping Kodi.
- In the **service** process, the hang can block shutdown, so Kodi refuses to exit cleanly.

This is the highest-probability "Android TV works differently from desktop" failure in the codebase, and it is one keyword argument.

**Other Android-specific behaviours to design for:**

| Behaviour | Detail | Consequence |
|-----------|--------|-------------|
| Storage path | `special://home` → `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/` | App-scoped external storage; broader visibility than a desktop profile dir (see Pitfall 18). Always go through `xbmcvfs.translatePath` — never hardcode. The vendored module already uses `xbmcvfs.translatePath` correctly, so no Kodi-20 removal issue there. |
| `xbmc.translatePath` | Deprecated in Matrix (PR 18345), **removed** in Nexus (PR 19301) | Any remaining call raises `AttributeError` on Kodi 20+. Grep for it. |
| SQLite WAL | `db.py` sets `pragma journal_mode=wal` | WAL needs shared-memory + file locking; on some Android storage stacks (FUSE/sdcardfs) this is flaky. If account loading misbehaves only on Android, WAL is the first suspect — `journal_mode=delete` is the fallback. |
| TLS trust | Python `urllib` on Android uses its own CA bundle, not the system store | `SSL: CERTIFICATE_VERIFY_FAILED` reports are common on old/clock-skewed boxes. A box with a wrong system clock fails TLS to `login.microsoftonline.com`. **Never** "fix" this with `verifypeer=false` — that hands OAuth traffic to any MITM. Detect and message: "Check this device's date and time." |
| Service lifecycle | Android may kill or freeze the Kodi process when backgrounded | A service loop must use `xbmc.Monitor().waitForAbort(n)`, never `time.sleep(n)`, and must be resumable from persisted state — never assume in-memory continuity. Known Kodi issue #18191: `waitForAbort` doesn't always work on all add-on/script instances. |
| CPU | Low-end ARM SoCs are ~an order of magnitude slower than a desktop for Python | See Pitfall 20. |

**How to avoid:**
- Add an explicit `timeout=` to every network call in the centralised HTTP layer (Pitfall 6). A connect/read timeout in the 15–30s range is right for media metadata.
- Make every wait interruptible via `Monitor.waitForAbort`.
- Every phase's manual acceptance pass runs on a **real Android TV box with a real remote** — `PROJECT.md` already mandates this; the value is in it being non-negotiable.

**Warning signs:** Spinner that never resolves; Kodi won't exit; works on Windows, hangs on the box; `CERTIFICATE_VERIFY_FAILED` reports clustered on one hardware model.

**Phase to address:** Timeout + interruptible waits in the **browse phase** (with the HTTP layer). Service lifecycle in the restored-service phase. The Android acceptance pass is in every phase.
*Evidence: PRIMARY — `clouddrive/common/remote/request.py`, `clouddrive/common/db.py`, Kodi PRs 18345/19301; CORROBORATED — Android path, TLS reports, issue #18191*

---

### Pitfall 20: Every `ListItem` accessor takes the Kodi GUI lock unless the item is offscreen

**What goes wrong:**
In `xbmc/interfaces/legacy/ListItem.cpp`, **35 separate accessors** are wrapped in `XBMCAddonUtils::GuiLock lock(languageHook, m_offscreen)`. When `m_offscreen` is false (the constructor default), each call contends the global graphics lock.

A OneDrive folder with 500 items, each set with a dozen properties, is thousands of GUI-lock acquisitions on a device whose CPU is already the bottleneck. On a desktop this is imperceptible; on a low-end Android TV box it is the difference between a folder opening in 1 second and in 10 — the "all video addons slow to browse" complaint pattern.

Kodi's own docs say plugins normally create list items offscreen and add them later, and that `offscreen=False` is only for when you manage the container yourself. A plugin handing items to `xbmcplugin.addDirectoryItems` does **not** manage the container.

**How to avoid:**
- Construct every list item as `xbmcgui.ListItem(..., offscreen=True)`. One-line change, largest single Android TV perf win available.
- Batch with `xbmcplugin.addDirectoryItems(handle, items)` rather than per-item `addDirectoryItem` calls.
- Convert the recursive, fully-buffered pagination (`CONCERNS.md`: Python recursion limit ≈ 1000 frames ≈ 1000 Graph pages; memory grows with the whole listing) to a `while nextLink:` loop that streams pages. On a 1–2 GB Android box, buffering a very large drive listing is an OOM, not just a slowdown.
- Do the cheap work per item; defer anything expensive (extra Graph calls, subtitle discovery) out of the listing path entirely.

**Warning signs:** Folder listing time growing super-linearly with item count; a visible per-item stutter; `RecursionError`; the box getting warm while listing.

**Phase to address:** Browse phase — same commit as the pagination rewrite.
*Evidence: PRIMARY — `xbmc/interfaces/legacy/ListItem.cpp` (35 `GuiLock` occurrences), Kodi ListItem docs*

---

### Pitfall 21: A self-hosted repo whose `addons.xml.md5` is stale — updates silently stop and only you can't reproduce it

**What goes wrong:**
Kodi decides whether to re-read `addons.xml` by comparing the remote `addons.xml.md5` against the md5 it stored last time. If `addons.xml` changes but `addons.xml.md5` doesn't, **Kodi never notices the new version** — while "Check for updates" (which invalidates the stored md5 and forces a re-download) works fine. So the maintainer, who always force-refreshes, sees a working repo; users, who rely on automatic updates, see a frozen one.

Given `PROJECT.md`'s constraint — *"Any flow requiring… repeated manual steps per update is a design failure"* — a repo whose auto-update is broken defeats the entire reason the repo exists over a zip.

Specific failure modes:

| Mistake | Symptom |
|---------|---------|
| `addons.xml.md5` not regenerated after editing `addons.xml` | Auto-update never fires; force-refresh works |
| md5 computed over different bytes than served (trailing newline, CRLF vs LF) | Same as above, and maddening to debug |
| Version not strictly greater (Kodi compares Debian-style) | No update offered. `2.3.0` → `2.3.0-beta` sorts **lower**. Pre-release suffixes on a version you want users to receive are a trap. |
| Repo add-on's own `<import>` versions unsatisfiable on target Kodi | Add-on shows as available but refuses to install, with a dependency error users can't act on |
| GitHub raw URL / CDN caching | Reported `CFileCache` "Source read didn't return any data!" against `raw.githubusercontent.com`; raw URLs are CDN-cached and Kodi's file cache interacts badly. GitHub **Pages** or a Release asset is the better host. |
| Repo zip's internal directory name ≠ add-on id | Install fails with an unhelpful error |
| Oversized cache buffer in `advancedsettings.xml` | `Failed to fetch checksum {addons.xml} for repository` |

**How to avoid:**
- **Generate `addons.xml` and `addons.xml.md5` from a script in CI, never by hand.** Compute the md5 over the exact bytes that will be served.
- Serve from **GitHub Pages** (`https://<user>.github.io/<repo>/`) rather than `raw.githubusercontent.com`.
- Enforce monotonically increasing, plain `MAJOR.MINOR.PATCH` versions. No pre-release suffixes on anything users should receive.
- **Test the update path, not just the install path**: install version N on a real Android TV box, publish N+1, wait for Kodi's automatic check, and confirm it arrives *without* touching "Check for updates". This is the only test that proves the repo works.
- Run `kodi-addon-checker` in CI (already an `Active` requirement in `PROJECT.md`).

**Warning signs:** "Force refresh works but auto-update doesn't" — the canonical signature. Users stuck on an old version while you're on the new one.

**Phase to address:** Distribution phase, with the update-path test as its acceptance criterion. Note this phase cannot be validated quickly — Kodi's automatic check is periodic — so schedule it early enough that the wait doesn't block a release.
*Evidence: CORROBORATED — multiple Kodi forum threads on md5/auto-update and the `CFileCache` raw-URL failure; Debian-style version comparison is Kodi-documented behaviour*

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep the vendored package named `clouddrive` | Zero import rewrites; smallest diff | Permanent collision risk with every sibling add-on; "my fix didn't apply" debugging forever; Kodi 20 `sys.path` regression amplifies it | **Never.** Rename during the vendoring phase or not at all. |
| Keep `setInfo` instead of typed setters | Nothing breaks today; setters are still absent-free | Log spam forever; the float-duration bug stays latent; a future Kodi removes it on someone else's schedule | Acceptable to defer *behind* auth/browse/play. Not acceptable to ship v3.0 with it. |
| Store the refresh token without re-persisting the rotated one | Simpler token code | Every user's add-on dies ~90 days after sign-in, simultaneously, with no correlating change | **Never.** |
| Skip settings migration; just delete `sign-in-server` from `settings.xml` | Saves a phase | Dead Heroku URL stays in every user's `addon_data`; no `schema_version` means no path for the *next* migration either | Never — the second migration is the one that hurts |
| Keep `eval()` in the token store | No change needed | Code-execution sink holding OAuth tokens, on a platform with permissive storage | Never |
| Vendor everything, trim later | Vendoring phase finishes fast | Trimming never happens; you now maintain a large unmaintained codebase instead of a small one | Acceptable *only* if trimming is its own scheduled phase with a stated LOC target |
| No `timeout=` on HTTP calls | Nothing on Windows | Unrecoverable hangs on the primary target platform | Never |
| Hand-maintained `addons.xml` / `.md5` | Repo ships in an afternoon | Silent update breakage; the failure is invisible to the maintainer | Never — it is a ten-line script |
| Personal-account-only testing | Halves the test matrix | Business path (`#`/`%` reserved differences, consent/CA errors, `documentLibrary` branches) is entirely unverified | Acceptable per-phase; **not** at release. Needs at least one Business account in the acceptance matrix. |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Entra device code | Using `/consumers` or `/organizations` because it "worked" | `/common` + `signInAudience: AzureADandPersonalMicrosoftAccount` |
| Entra device code | Adding a `client_secret` to silence `AADSTS7000218` | Enable **Allow public client flows**; never ship a secret |
| Entra device code | Expecting `verification_uri_complete` | Microsoft does not return it; show `verification_uri` + `user_code` separately |
| Entra device code | Hardcoding a poll interval | Use the `interval` from the response; back off on `slow_down` |
| Entra token refresh | Reusing the original refresh token | Persist the new `refresh_token` from every response |
| Entra errors | Showing "Sign-in failed" | Regex `AADSTS\d+` out of `error_description`, map to an action, always show the raw code |
| Graph throttling | `time.sleep(1)` retry loop | Sleep exactly `Retry-After`, via `Monitor.waitForAbort` |
| Graph paths | `quote()` the whole URL, or `quote_plus` | `quote(path, safe="/")` on the user path only; splice into the fixed `root:` template |
| Graph OData | Percent-encoding `'` in `search(q='…')` | Double it: `'` → `''`, then encode the query string |
| Graph download | Resolving `downloadUrl` at listing time; caching it | Resolve at play time; never cache; `Range` goes to the `downloadUrl` host |
| Graph delta | Handling `resyncRequired` | Handle **410 Gone** + `resyncChangesApplyDifferences`/`resyncChangesUploadDifferences`, follow the `Location` header |
| Graph delta | Deriving paths from delta items | `parentReference.path` is absent by design — track by `id` |
| Graph delta | First-wins dedupe | Same item can recur; **last occurrence wins** |
| Graph drives | `GET /drives` | `GET /me/drives` (bare `/drives` isn't a v1.0 endpoint) |
| Kodi ListItem | `ListItem()` default | `ListItem(offscreen=True)` for plugin listings |
| Kodi ListItem | Passing a float duration to a typed setter | `int(ms // 1000)`; setters are strict `int` |
| Kodi resume | `setProperty('ResumeTime'/'TotalTime')` | `InfoTagVideo.setResumePoint(time, totaltime)` |
| Kodi paths | `xbmc.translatePath` | `xbmcvfs.translatePath` (the former is removed in Kodi 20+) |
| Kodi services | `time.sleep()` in the service loop | `xbmc.Monitor().waitForAbort(n)` |
| Kodi repo | Editing `addons.xml` by hand | Generate both files in CI; serve from GitHub Pages |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Non-offscreen `ListItem` | Listing time grows super-linearly; per-item stutter on the box | `offscreen=True` + `addDirectoryItems` batching | Noticeable ~200 items on a low-end box; painful at 500+ |
| Recursive, fully-buffered pagination | `RecursionError`; memory growth; OOM on Android | `while nextLink:` loop + streaming callback | Recursion ceiling ≈ 1000 pages; memory bites far earlier on a 1–2 GB box |
| Double drive enumeration (`/drives` then `/me/drives`) | A 403 per account load nothing reacts to | Drop the bare `/drives` call | Every account load, every launch |
| Subtitle search per played item | Extra Graph round trip on every play; throttle pressure | Constrain the query server-side; cache per parent folder | Immediately on a slow link; contributes to 429 |
| Ignoring `Retry-After` | Add-on "randomly stops working" for minutes | Central 429 handler honouring the header | Large drives / active service; escalates the longer you retry |
| `downloadUrl` cached in the item cache | Playback dies on seek or after a pause | Mint at play time only | Any pause/seek beyond the (undocumented, possibly minutes) URL lifetime |
| Full delta re-enumeration from a `None` token | Every service tick re-walks the drive | Persist only non-`None` tokens; handle 410 correctly | Every cancelled listing poisons the next sync |
| No socket timeout | Spinner forever; Kodi won't exit | Explicit `timeout=` everywhere | Any Wi-Fi glitch on Android TV |
| Class-level `_extra_parameters` mutation | Folders vanish from listings after any search | Copy per call: `params = dict(self._extra_parameters)` | First search in a long-lived service process, then permanently |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Leaving the dead `drive-login.herokuapp.com` default reachable in stored settings | The hostname may be re-registrable; a third party could receive OAuth traffic from every default install | Remove the setting **and** clear the stored value in the migration — a new default alone fixes nothing |
| Embedding a `client_secret` to work around `AADSTS7000218` | A secret in a public repo is a compromised secret; also defeats the public-client model | Enable Allow public client flows; CI grep for `client_secret`/`client_assertion` |
| `eval()` on the account/token DB | Arbitrary code execution in the store holding refresh tokens, on a platform with permissive external storage | JSON; `ast.literal_eval` at worst |
| Logging tokens on error | Refresh tokens in `kodi.log`, which users paste into public forums verbatim | Redact `access_token`/`refresh_token`/`device_code` in one place in the HTTP layer; log ≤8 chars if you must correlate |
| `verifypeer=false` / disabling TLS verification to "fix" cert errors | Trivial MITM on the OAuth exchange | Never. Diagnose (usually device clock) and message the user |
| `allow_directory_listing` defaulting to `true` on port 8586 | An unverified HTTP listener serving drive content, possibly on all interfaces | Default **off**. Re-enable only after verifying loopback binding + authentication in the now-vendored, readable code |
| `report_error` shipping payloads to an undocumented endpoint | Drive/file names, possibly tokens, leaving the device | Document the endpoint and the scrubbing, or remove the feature — it is not in the core-first scope |
| Leaving the false `<disclaimer>` in `addon.xml` | Users are told their tokens go to a third-party server that no longer exists | Rewrite it in the auth phase to describe the real design |
| Custom `client_id` setting accepting arbitrary text | A user pasting a hostile value; a support vector | Validate as a GUID; never let it change the authority |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Raw `AADSTS…` blob on screen | Unreadable at 3 metres; user learns nothing | One short sentence + one action + the bare code for bug reports |
| No countdown on the device code screen | Code expires while the user hunts for their phone; no explanation | Live countdown from `expires_in`; one-button restart on expiry |
| Uncancellable sign-in dialog | Force-stopping Kodi is the only escape from a remote | Back/Escape cancels and aborts the poll loop cleanly |
| Not warning personal-account users about the second sign-in | Users conclude it failed and give up | One line: "You may be asked to sign in again — that's expected" |
| Silent re-auth requirement after upgrade | "The update broke it" | Proactive one-time explanation naming what was preserved |
| Spinner with no timeout | Indistinguishable from a hang | Timeouts + a real error with a retry affordance |
| Burying the custom `client_id` escape hatch | Blocked business users have no path forward | The blocked-by-tenant error message names the setting explicitly |
| Requiring text entry anywhere in the happy path | D-pad text entry is the stated design failure | Device code is the only flow; custom `client_id` is the sole (advanced, opt-in) text field |
| Subtitle discovery blocking playback start | Perceptible delay before every video | Resolve subtitles asynchronously or after playback starts |

---

## "Looks Done But Isn't" Checklist

- [ ] **Device code sign-in:** often missing the `interval`-based poll delay, the `expires_in` countdown, and a cancel path — verify all three, and verify with a **personal** *and* a **work** account.
- [ ] **Token refresh:** often missing write-back of the rotated `refresh_token` — verify the persisted token *value changes* across two refreshes.
- [ ] **Error handling:** often missing the AADSTS→message map — verify by forcing at least `expired_token`, `authorization_declined`, and one revoked-token case.
- [ ] **Vendoring:** often missing the addon-id de-hardcoding — verify with `script.module.clouddrive.common` and every sibling add-on **uninstalled**.
- [ ] **Vendoring:** often missing the skin XML/media move — verify by opening every dialog, including the QR sign-in dialog.
- [ ] **Vendoring:** often missing the module's own `service.py` and its `dateutil`/`pyqrcode` dependencies — verify the add-on starts with a minimal `addon.xml`.
- [ ] **Vendoring:** often missing `clouddrive/common/cache/LICENSE` (Apache-2.0) — verify both licence files survive.
- [ ] **Path handling:** often missing the Business-reserved `#`/`%` distinction — verify with files named `Break#Out`, `estimate%s.docx`, `Ryan's Files`.
- [ ] **Search:** often missing the OData quote doubling in one of the two call sites — verify with `Ocean's Eleven`.
- [ ] **Playback:** often missing `downloadUrl` re-resolution — verify with a 2h+ file: play, pause 30 min, resume, seek.
- [ ] **InfoTag migration:** often missing the float→int duration fix and the module-side `setInfo` calls — verify zero `is deprecated` lines in `kodi.log` for a full browse+play session.
- [ ] **Settings migration:** often missing the `schema_version` write — verify the migration runs exactly once, then never again.
- [ ] **Settings migration:** often missing preservation of drive selections — verify against a real pre-upgrade `accounts.db`.
- [ ] **HTTP layer:** often missing `timeout=` and interruptible sleeps — verify Kodi exits cleanly while a request is in flight.
- [ ] **Repository:** often missing a working *automatic* update — verify N→N+1 arrives on a real Android TV box **without** pressing "Check for updates".
- [ ] **Android TV:** often missing entirely — every phase's acceptance pass runs on real hardware with a real remote, not an emulator, not `adb shell`.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong `signInAudience` on the registration | LOW | Change it in the portal; no code or client-id change. Existing tokens survive. |
| `allowPublicClient` off | LOW | Toggle in the portal; users retry sign-in. |
| Refresh token not written back | **HIGH** | Every user must re-authenticate, and you find out ~90 days late via a wave of identical reports. Fix the code, then ship a release that force-clears tokens with an explanatory prompt. This is why the unit test is mandatory. |
| Vendored package name kept as `clouddrive` | MEDIUM | Rename + rewrite imports later; mechanical but touches every file and invalidates any in-flight branches. |
| Vendored from `master` (1.3.9, Python 2) | MEDIUM | Re-vendor from `matrix`; any fixes already applied to the wrong base must be re-applied. |
| Settings migration shipped without `schema_version` | MEDIUM | The next migration cannot tell migrated from unmigrated installs; you need a heuristic probe (e.g. presence of the archived `accounts.db.pre-v3`). Ugly but survivable. |
| Deleted a vendored `LICENSE` | LOW | Restore from upstream; add `VENDORED.md`. Do it before any public release. |
| Broken `addons.xml.md5` | LOW technically, **HIGH** in practice | Fix the generator and publish. But users whose Kodi cached a stale md5 may need one manual "Check for updates" — exactly the manual step the repo existed to eliminate. Prevention is much cheaper. |
| Version number that sorts lower | MEDIUM | Publish a strictly-higher version. Anyone who installed the bad one is stuck until they do. |
| `downloadUrl` cached and expiring | LOW | Move resolution to play time; no user-visible migration. |
| `eval()` shipped in the token store | MEDIUM | Replace with JSON + a read-side fallback; no user action needed. |

---

## Pitfall-to-Phase Mapping

Phase names are topical, matching the core-first ordering in `PROJECT.md` (auth → browse → play → subtitles). Numbers are suggestions for the roadmap author.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 15 — wrong branch / lost service / lost skins | **P1 Vendor** | Add-on runs with sibling add-ons uninstalled; every dialog opens; `VENDORED.md` records branch + SHA |
| 13 — hardcoded `script.module.clouddrive.common` | **P1 Vendor** | CI grep returns zero hits; clean-install test passes |
| 14 — package collisions (`clouddrive`, `resources`) | **P1 Vendor** | `__file__` of the vendored package points inside this add-on; no top-level `resources` package remains |
| 16 — licences (GPL-3 + Apache-2.0) | **P1 Vendor** | Both `LICENSE` files present; `VENDORED.md` exists |
| 18 — `eval()` token store | **P1 Vendor** (mechanism) + **P6 Migration** (data) | CI grep for `eval(` returns zero |
| 1 — wrong authority / `signInAudience` | **P2 Auth** (setup prerequisite) | Sign-in succeeds with a personal **and** a work account |
| 2 — Allow public client flows | **P2 Auth** (setup prerequisite) | No `AADSTS7000218`; CI grep for `client_secret` returns zero |
| 3 — refresh token rotation / 90-day expiry | **P2 Auth** | Unit test asserts the persisted refresh token changes across two refreshes |
| 4 — tenant policy rejections | **P2 Auth** | Forced-error pass over the AADSTS map; unmapped errors still show the raw code |
| 5 — TV device-code UX | **P2 Auth** | Full sign-in from a remote on a real Android TV box; expiry and cancel paths exercised |
| 16b — false `<disclaimer>` | **P2 Auth** | `addon.xml` describes the real design; no `drive-login` reference |
| 6 — 429 / `Retry-After` | **P3 Browse** (HTTP layer) | Forced 429 honours the header; the wait is abortable |
| 19 — no socket timeout / Android behaviours | **P3 Browse** (HTTP layer) | Kodi exits cleanly with a request in flight; Android TV pass |
| 7 — path percent-encoding | **P3 Browse** | Unit tests over Microsoft's worked examples; live test with `#`/`%`/space/apostrophe names |
| 8 — OData quote escaping | **P3 Browse** | Search for `Ocean's Eleven` succeeds; single escaping helper |
| 11 — `/drives` vs `/me/drives` | **P3 Browse** | No 403 in the log on account load |
| 20 — GuiLock / pagination / memory | **P3 Browse** | 500-item folder listing time measured on the box; no `RecursionError` on a large drive |
| 9 — `downloadUrl` expiry | **P4 Play** | 2h+ file: play, pause 30 min, resume, seek |
| 12 — typed InfoTag setters + int strictness | **P5 Kodi modernization** (after P1) | Zero `is deprecated` lines in a full browse+play log; no `TypeError` on video items |
| settings.xml `version="1"` schema | **P5 Kodi modernization** | Settings render on 20, 21, and 22; Krypton visibility hacks gone |
| 17 — existing-user settings + account migration | **P6 Migration** (after P2) | Runs once against a real pre-upgrade profile; drives preserved; `sign-in-server` value cleared; `accounts.db.pre-v3` archived |
| 10 — delta 410 / `None` token / 404 amnesia | **P7 Restored services** (invariant rides along in P3) | Forced 410 triggers resync via `Location`; token never persisted as `None` |
| `allow_directory_listing` default | **P7 Restored services** | Default off; loopback binding + auth verified in the now-readable vendored code before re-enabling |
| 21 — repository / auto-update | **P8 Distribution** | N→N+1 arrives automatically on a real Android TV box without a manual check |

---

## Testing Pitfalls: What Cannot Be Caught Off-Device

`PROJECT.md` already commits to "automated tests cover pure logic; every phase also carries a manual acceptance pass." This section says what specifically must be manual, and why — so the checklist isn't invented from scratch each phase.

**Testable off-device (and therefore *must* be automated — every bug in `CONCERNS.md` falls here):**
`_extract_item` mapping · pagination loop (including the cancellation→`[]` contract) · path building and percent-encoding · OData literal escaping · the AADSTS→message map · token-response persistence including refresh rotation · 429/`Retry-After` handling against a stubbed client · settings-migration logic against a fixture `accounts.db`. Run under CI with `kodi-addon-checker` and Kodistubs.

**Not testable off-device — must be in the manual acceptance checklist:**

| Cannot be tested off-device | Why | Manual check |
|---|---|---|
| Device-code readability at TV viewing distance | Rendering + physical distance | Read the code from the sofa, on the actual TV |
| Remote-only navigability | D-pad focus order isn't inspectable in code | Complete sign-in → browse → play using **only** the remote |
| `verification_uri_complete` absence handling | Depends on live Entra responses | Real sign-in |
| Refresh-token rotation *in the wild* | 90-day timescale | Instrument: log the token prefix; track across weeks |
| Business-tenant consent / CA / MFA rejections | Requires a real tenant with real policy | One Business account in the matrix; ideally one with CA enabled |
| Personal vs Business reserved-character differences (`#`, `%`) | Server-side name validation | Create the files in both drive types |
| `downloadUrl` expiry mid-playback | Undocumented, time-dependent | 2h+ file with a long pause and a seek |
| Kodi version differences (20 / 21 / 22) | Behaviour lives in the C++ runtime | Install and smoke-test on each |
| InfoTag deprecation warnings | Only observable in `kodi.log` | Grep a full-session log for `is deprecated` |
| Android TV Python performance | Hardware-bound | Time a 500-item folder listing on the real box |
| SQLite WAL on Android storage | Filesystem-dependent | Account save/load on the box, repeatedly |
| TLS/cert behaviour on old Android | Device CA store + system clock | Test on the oldest target box |
| Service lifecycle when backgrounded | Android process management | Background Kodi for 30+ min, return, confirm the service recovered |
| Network-loss behaviour | Requires real interruption | Pull Wi-Fi mid-listing and mid-playback; confirm no hang |
| Kodi shutdown with a request in flight | Process-level | Start a large listing, quit Kodi, confirm clean exit |
| Repository auto-update | Kodi's periodic check | Publish N+1, wait, confirm arrival without a manual check |
| Skin XML dialog resolution | Runtime path resolution | Open every dialog on a clean install |
| Clean-install behaviour (no sibling add-ons) | Depends on what else is installed | Fresh Kodi profile, nothing else from the cloud-drive family |

**Two testing traps specific to this project:**

1. **The maintainer's machine is the worst test environment.** It has `script.module.clouddrive.common` installed (masking Pitfall 13/14), a force-refreshed repo (masking Pitfall 21), a personal account (masking Pitfalls 1/4/7), and wired ethernet (masking Pitfall 19). Every phase needs at least one pass on a **clean profile, clean add-on set, Android TV, Wi-Fi, non-personal account** — not necessarily all in one run, but tracked so the matrix gets covered before release.

2. **Recorded Graph JSON goes stale silently.** Fixtures for `_extract_item` are the right approach, but Graph response shapes drift (delta omits different properties for Business vs consumer; `@microsoft.graph.downloadUrl` may be absent in some contexts). Record fixtures from **both** a Personal and a Business drive, label them, and re-record when a live response surprises you. A green test suite against 2023-shaped JSON proves nothing about 2026 Graph.

---

## Sources

**Primary — Microsoft (official documentation, read verbatim during this pass):**
- [OAuth 2.0 device authorization grant](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code) — endpoints, tenant values, `expires_in`/`interval`, polling errors, `verification_uri_complete` non-support, personal-account re-sign-in
- [Refresh tokens in the Microsoft identity platform](https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens) — 90-day lifetime, self-replacement on every use, revocation matrix, client binding
- [Microsoft Entra authentication and authorization error codes](https://learn.microsoft.com/en-us/entra/identity-platform/reference-error-codes) — all AADSTS codes quoted above
- [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) — 429, `Retry-After`, avoid-immediate-retry guidance
- [How to address resources (OneDrive API)](https://learn.microsoft.com/en-us/onedrive/developer/rest-api/concepts/addressing-driveitems) — `root:/…:` syntax, reserved characters (incl. Business-only `#`/`%`), `pchar` grammar, worked encoding examples
- [driveItem: delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0) — 410 Gone + `resyncChangesApplyDifferences`/`resyncChangesUploadDifferences`, `Location` header, `?token=latest`, track-by-id, per-service omitted properties
- [Download driveItem content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0) — 302 to preauthenticated URL, "might expire within minutes", `Range` must target `downloadUrl`
- [List Drives](https://learn.microsoft.com/en-us/graph/api/drive-list?view=graph-rest-1.0) — the four supported forms; bare `/drives` absent
- [Invalid Client Error AADSTS7000218](https://learn.microsoft.com/en-us/troubleshoot/entra/entra-id/app-integration/confidential-client-application-authentication-error-aadsts7000218)

**Primary — Kodi (source tree, read during this pass):**
- `xbmc/xbmc` — `addons/xbmc.python/addon.xml` at tags `19.5-Matrix`, `20.5-Nexus`, `21.2-Omega`, and `master` (version/abi mapping)
- `xbmc/xbmc` — `xbmc/interfaces/legacy/ListItem.cpp` (`setInfo` present at line 375; 35 `GuiLock` sites; deprecated `totaltime`/`resumetime` properties)
- `xbmc/xbmc` — `xbmc/interfaces/legacy/InfoTagVideo.h` (typed setter signatures: `setDuration(int)`, `setResumePoint(double, double)`, …)
- [xbmc/xbmc#22985](https://github.com/xbmc/xbmc/issues/22985) — Kodi 20 `sys.path` ordering regression (fixed via PR 23244)
- Kodi PRs [18345](https://github.com/xbmc/xbmc/pull/18345) / [19301](https://github.com/xbmc/xbmc/pull/19301) — `xbmc.translatePath` → `xbmcvfs.translatePath` deprecation then removal
- [Kodi ListItem API reference](https://alwinesch.github.io/group__python__xbmcgui__listitem.html) — `offscreen` semantics, v20 deprecation notes

**Primary — the dependency being vendored (source read during this pass):**
- `cguZZman/script.module.clouddrive.common` branch `matrix` (v1.4.0) and `master` (v1.3.9) — `addon.xml`, file tree, `LICENSE.txt` (GPL-3.0), `clouddrive/common/cache/LICENSE` (Apache-2.0), `account.py`, `db.py` (`eval()`, WAL), `remote/request.py` (no timeout), `ui/addon.py` (`setInfo` at 424/439/583), `ui/dialog.py` (`WindowXMLDialog`, QR path), `ui/utils.py`, `service/*.py`, `resources/settings.xml`, `resources/skins/`

**Corroborated — community:**
- Kodi forum threads on self-hosted repository auto-update failures, `addons.xml.md5` staleness, and `CFileCache` behaviour against `raw.githubusercontent.com`
- [Kodi wiki: Add-on settings conversion](https://kodi.wiki/view/Add-on_settings_conversion) and [Add-on settings](https://kodi.wiki/view/Add-on_settings) — `version="1"` schema requirement
- Add-on migration threads: [slyguy.addons#498](https://github.com/matthuisman/slyguy.addons/issues/498), [elementum#913](https://github.com/elgatito/plugin.video.elementum/issues/913), [jellyfin-kodi#919](https://github.com/jellyfin/jellyfin-kodi/issues/919), [script.module.infotagger](https://github.com/jurialmunkey/script.module.infotagger)
- [xbmc/xbmc#18191](https://github.com/xbmc/xbmc/issues/18191) — `waitForAbort` reliability on add-on/script instances
- Kodi forum + LibreELEC threads on Android `SSL: CERTIFICATE_VERIFY_FAILED` and `xbmcvfs.translatePath` on Android
- [OneDrive/onedrive-api-docs#884](https://github.com/OneDrive/onedrive-api-docs/issues/884) — observed `downloadUrl` validity

**In-repo:**
- `.planning/PROJECT.md` — scope, constraints, decisions
- `.planning/codebase/CONCERNS.md` — existing bugs, several of which this research shows become *worse* under the planned changes (float duration → `TypeError`; `None` change token → repeated full enumeration → throttling)

**Confidence methodology note:** tiers were obtained from `gsd-tools query classify-confidence`. That classifier rates the *transport* (`webfetch` → LOW, `websearch --verified` → MEDIUM), not source authority, so it does not distinguish a blog post from `learn.microsoft.com` or from the `xbmc/xbmc` source tree. The per-claim **Evidence** tags above carry the real signal: `PRIMARY` claims were read verbatim from official documentation or upstream source during this pass and should be treated as authoritative; `CORROBORATED` claims rest on multiple agreeing community reports and should be verified on-device; `INFERRED` claims are my reasoning and are labelled as such.

---
*Pitfalls research for: Kodi 20/21/22 OneDrive add-on with in-add-on Microsoft Graph device-code auth, Windows + Android TV*
*Researched: 2026-08-22*
