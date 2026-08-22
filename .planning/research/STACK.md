# Stack Research

**Domain:** Kodi 20/21/22 video add-on browsing Microsoft OneDrive via Microsoft Graph, with in-add-on OAuth 2.0 device authorization grant (public client, embedded `client_id`, no broker server)
**Researched:** 2026-08-22
**Confidence:** HIGH — every Kodi claim is verified against Kodi C++ source at the relevant release branch/tag; every Microsoft claim is verified against current Microsoft Learn docs, and the device-code protocol behaviour was additionally verified by live HTTP probes against `login.microsoftonline.com`.

> **Basis for the HIGH rating.** No curated docs MCP (Context7/Ref) was available this session, so the automated `classify-confidence` seam — which grades purely by *provider id* — rates `webfetch`/`websearch` as LOW. That grade does not fit this research: the sources here are (a) vendor-official Microsoft Learn pages, (b) the canonical Kodi C++ source read directly from `github.com/xbmc/xbmc` at named release branches and tags, (c) the live Kodi add-on index at `mirrors.kodi.tv`, and (d) first-hand HTTP probes of Microsoft's own endpoints. Claims resting on anything weaker are marked inline. The one genuinely unproven assumption is flagged under *Open Risks to Validate in Phase 1*.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Kodi Python API `xbmc.python` | declare `3.0.1` | Host add-on ABI | `3.0.1` is the exact value that installs on Kodi 20/21/22 and **blocks** Kodi 19 — see §4. It is also the value `kodi-addon-checker` lists as `advised` for `nexus`, `omega`, and `piers`. |
| CPython (Kodi-embedded) | 3.11 minimum | Language runtime | Kodi 20.0 Nexus bundles CPython **3.11.0**, 21.x Omega **3.11.7**, 22 Piers **3.13.5+**. Target Python **3.11** syntax/stdlib; f-strings, `dataclasses`, `:=`, `typing` generics are all safe. |
| Python stdlib `urllib.request` + `json` | stdlib | All HTTP: Graph + OAuth token endpoints | Zero add-on dependencies to resolve at install time on Android TV. Sufficient for GET/POST + form encoding + streaming reads. See §3 for why this beats `requests`. |
| Microsoft identity platform v2.0 endpoint | `/common` authority | OAuth 2.0 device authorization grant (RFC 8628) | `/common` is the **only** authority value that admits both personal Microsoft accounts and work/school accounts. Verified live: `/common/oauth2/v2.0/devicecode` returns a valid `device_code`. |
| Microsoft Graph REST | `v1.0` | Drive/DriveItem browsing, search, delta, download URLs | `https://graph.microsoft.com/v1.0` — do not use `beta`. |
| Kodi settings schema | `<settings version="1">` | Add-on settings UI | Mandatory shape for Kodi 19+; the pre-19 `<settings><category>` shim is deprecated. Verified against Kodi master `SettingDefinitions.h` and a live Team Kodi add-on. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `script.module.requests` | **2.31.0** (Nexus, Omega, Piers — identical) | HTTP client | **Optional fallback only.** Adds 4 transitive Kodi add-on dependencies. Use only if you hit a concrete `urllib` limitation. |
| `script.module.urllib3` | **2.2.3** (Nexus/Omega/Piers) | Transitive of `requests` | Never import directly. |
| `script.module.certifi` | **2023.5.7** (Nexus/Omega/Piers) | CA bundle | Transitive of `requests`. Note: **stale CA bundle** — another reason to prefer stdlib + platform trust store. |
| `script.module.idna` | **3.10.0** | Transitive of `requests` | Never import directly. |
| `script.module.chardet` | **5.1.0** | Transitive of `requests` | Never import directly. |
| `script.module.six` | `1.16.0+matrix.1` | Py2/Py3 compat | **Do not use.** Kodi 20+ is Python 3.11 only. |
| `script.module.inputstreamhelper` | 0.8.5 | InputStream.Adaptive bootstrap | Not needed — OneDrive serves plain progressive HTTP files, not DASH/HLS. |

> Availability verified by enumerating `https://mirrors.kodi.tv/addons/{nexus,omega,piers}/`. Versions are **identical across all three repos**, so a single `<import>` line works on Kodi 20, 21 and 22.

### Development Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| `Kodistubs` (PyPI) | **21.0.0** | Importable stubs for `xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcaddon`, `xbmcvfs`, `xbmcdrm` | Dev/test-only dependency. Latest release is 21.0.0 (Omega API); there is **no** 22/Piers release yet. Sufficient — the API surface this add-on uses is stable. |
| `kodi-addon-checker` (PyPI) | **0.0.36** | Official Team Kodi add-on linter | Run as `kodi-addon-checker --branch omega .`. Valid `--branch` values include `nexus`, `omega`, `piers`. |
| `pytest` | latest | Unit test runner | Pure-logic tests only (parsing, pagination, URL building, token state machine). |
| `unittest.mock` | stdlib | Fake `xbmc*` modules and HTTP | Preferred over stubs where behaviour (not just import) matters. |
| `responses` or hand-rolled `urlopen` fake | latest | Record/replay Graph JSON | Fixtures from real Graph responses. |

---

## 1. Microsoft Identity Platform — Device Authorization Grant

### 1.1 Authority: which value supports BOTH account types

| Authority | Signs in | Verdict |
|-----------|----------|---------|
| `https://login.microsoftonline.com/common/` | **Work/school accounts AND personal Microsoft accounts** | ✅ **USE THIS** |
| `https://login.microsoftonline.com/organizations/` | Work/school accounts only | Escape hatch for tenants only |
| `https://login.microsoftonline.com/consumers/` | Personal Microsoft accounts (MSA) only | Escape hatch for MSA only |
| `https://login.microsoftonline.com/{tenantId-or-domain}/` | One specific tenant | Pair with the custom-`client_id` advanced setting |

**Decision: `common`.** Confidence HIGH.

**Contradiction resolved (important):** the MSAL.NET device-code article still carries a stale "Constraints" block saying *"the authority ... needs to be Tenanted"* and cites `AADSTS90133: Device Code flow is not supported under /common or /consumers endpoint`. That is **obsolete**. The same page's own later section states device code works with `/common` or `/consumers` since MSAL.NET 4.5, and the protocol reference (`v2-oauth2-device-code`, doc updated 2026-06-15) states `tenant` *"Can be `/common`, `/consumers`, or `/organizations`."*

**Verified empirically on 2026-08-22** — a live `POST` to all three authorities returned a valid device-code response:

| Authority | HTTP | `verification_uri` | `expires_in` | `interval` |
|-----------|------|--------------------|--------------|------------|
| `common` | 200 | `https://login.microsoft.com/device` | 900 | 5 |
| `consumers` | 200 | `https://www.microsoft.com/link` | 900 | 5 |
| `organizations` | 200 | `https://login.microsoft.com/device` | 900 | 5 |

Note `consumers` returns a **different** `verification_uri`. **Never hardcode `https://microsoft.com/devicelogin`** — always render the `verification_uri` (or the `message`) returned in the response.

### 1.2 Device authorization request

```
POST https://login.microsoftonline.com/common/oauth2/v2.0/devicecode
Content-Type: application/x-www-form-urlencoded

client_id=<APPLICATION_CLIENT_ID>
&scope=https%3A%2F%2Fgraph.microsoft.com%2FFiles.Read%20offline_access%20openid%20profile
```

| Parameter | Required | Notes |
|-----------|----------|-------|
| `client_id` | Yes | Application (client) ID GUID. |
| `scope` | Yes | Space-separated. URL-encode the whole value. |

Optional: append `?mkt=xx-XX` **as a query parameter on the URL** to localize the human-readable `message`.

**Response (200, JSON):**

| Field | Type | Use |
|-------|------|-----|
| `device_code` | string | Secret; send to `/token`. Never display. |
| `user_code` | string | Short code to display on the TV. Observed 8–9 chars, e.g. `HGMGNV9K9`. Render in a large, unambiguous font. |
| `verification_uri` | string | Display this. Do **not** hardcode. |
| `expires_in` | int | Observed **900** (15 min). Drive the on-screen countdown from this. |
| `interval` | int | Observed **5**. Minimum seconds between polls. |
| `message` | string | Pre-localized human sentence; simplest correct UI is to display this verbatim. |

**`verification_uri_complete` is NOT returned by Microsoft.** The docs call this out explicitly. That means **there is no server-provided one-shot URL to encode into a QR code**. If you want a QR code you must build `verification_uri` yourself (without the code) and the user still types the `user_code`.

### 1.3 Token polling request

```
POST https://login.microsoftonline.com/common/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code
&client_id=<APPLICATION_CLIENT_ID>
&device_code=<device_code from step 1.2>
```

`grant_type` must be exactly `urn:ietf:params:oauth:grant-type:device_code`. No `client_secret`, no `redirect_uri`, no PKCE.

**Success (200, JSON):** `token_type` (always `Bearer`), `scope`, `expires_in` (observed 3599), `access_token`, `refresh_token` (**only if `offline_access` was requested**), `id_token` (only if `openid` was requested).

### 1.4 Polling semantics — verified

**Critical implementation fact: pending polls return HTTP 400, not 200.** Verified live (`http_status=400` with `error=authorization_pending`). Any code that calls `raise_for_status()` / treats non-2xx as fatal will break the flow. **You must parse the JSON body of 4xx responses.**

| `error` | Observed `error_codes` | Meaning | Required client action |
|---------|------------------------|---------|------------------------|
| `authorization_pending` | `[70016]` (`AADSTS70016`) — **verified live** | User hasn't finished | Sleep ≥ `interval`, poll again |
| `slow_down` | — | Polling too fast | **Increase `interval` by 5 s permanently** and continue (RFC 8628 §3.5) |
| `authorization_declined` | — | User denied | Stop; return to unauthenticated state |
| `expired_token` | — | `expires_in` elapsed | Stop; offer "start over" |
| `bad_verification_code` | — | Documented by Microsoft | Stop; treat as fatal |
| `invalid_grant` | `[7000014]` (`AADSTS7000014`) — **verified live** | What Microsoft *actually* returns for an unrecognised `device_code` | Stop; treat as fatal |

> **Gap in Microsoft's own docs, worth encoding as a rule:** Microsoft's error table lists `bad_verification_code` but a live probe with a garbage `device_code` returned `invalid_grant` / `AADSTS7000014`. Microsoft also does **not** document `slow_down`, but it is a mandatory RFC 8628 code and can appear.
>
> **Therefore: the polling loop must be written as an allow-list, not a deny-list.** Continue polling *only* on `authorization_pending` and `slow_down`. Treat **every other** `error` value — documented or not — as terminal, and surface `error_description` (which carries the `AADSTS` code and Trace ID) to the user/log.

Also per RFC 8628 §3.5: on a **connection timeout**, back off (exponential, e.g. double the interval) before retrying.

### 1.5 Refresh token behaviour

```
POST https://login.microsoftonline.com/common/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

client_id=<APPLICATION_CLIENT_ID>
&grant_type=refresh_token
&refresh_token=<stored refresh token>
&scope=https%3A%2F%2Fgraph.microsoft.com%2FFiles.Read%20offline_access
```

No `client_secret` — public client.

Rules, from Microsoft Learn:

- **Default lifetime: 90 days** for this scenario (24 h applies only to SPAs and email-OTP flows — neither applies here).
- **Refresh tokens rotate.** Every refresh returns a **new** `refresh_token`. *"Replace the old refresh token with this newly acquired refresh token"* and *"Securely delete the old refresh token after acquiring a new one."* → the token store must be **write-after-every-refresh**, and the write must be atomic (temp file + rename) so a crash mid-write cannot lose the account.
- **`scope` on refresh is optional** and must be equal to or a subset of the original grant.
- **Revocation is normal, not exceptional.** Password change (password-based public-client tokens), user revoking sessions, or admin revoking all refresh tokens all invalidate the token. The add-on must catch `invalid_grant` on refresh and present *"sign in again"*, not a stack trace.
- Refresh tokens are bound to user+client, **not** to resource or tenant.

**Practical policy:** refresh when the access token is within ~5 minutes of `expires_in`, and also refresh reactively on a Graph `401`. Persist `expires_at` as an absolute epoch timestamp, not the relative `expires_in`.

---

## 2. Azure AD App Registration

| Setting | Required value | Source of truth |
|---------|----------------|-----------------|
| **Supported account types** | *"Any Entra ID Tenant + Personal Microsoft accounts"* → manifest `"signInAudience": "AzureADandPersonalMicrosoftAccount"` | App manifest reference |
| **`requestedAccessTokenVersion`** | **`2`** — *mandatory*: "If `signInAudience` is `AzureADandPersonalMicrosoftAccount`, the value must be `2`." | App manifest reference |
| **Allow public client flows** | **Yes** → manifest `"allowPublicClient": true` | Manifest ref: *"If this value is set to true the fallback application type is set as public client... The default value is **false**"* |
| **Redirect URI** | **Not required for device code.** Register `https://login.microsoftonline.com/common/oauth2/nativeclient` as type `InstalledClient` anyway | MSAL.NET device-code guidance |
| **Client secret / certificate** | **NONE. Never create one.** | Public clients "must not use secrets or certificates" |

**Why `allowPublicClient: true` is non-negotiable:** Entra infers app type from `replyUrlsWithType`. Device code performs no redirect, so there is nothing to infer from. With the default `false`, Entra falls back to *confidential client* and rejects the token request demanding a `client_assertion` or `client_secret` (`AADSTS7000218`). This is the single most common device-code misconfiguration.

**The manifest editor caveat:** once `signInAudience` is `AzureADandPersonalMicrosoftAccount`, *"you can't change the supported Microsoft accounts in the UI. Instead, you must use the application manifest editor."* Document this in the maintainer runbook.

### 2.1 Delegated scopes — evaluated

Requested scope string (recommended):

```
https://graph.microsoft.com/Files.Read offline_access openid profile
```

| Scope | Verdict | Rationale |
|-------|---------|-----------|
| **`Files.Read`** | ✅ **REQUIRED — and sufficient** | Graph reference lists `Files.Read` as the **least privileged** permission for `GET /drives/{id}/items/{id}/children` **and** `GET /me/drives`, for **both** *Delegated (work or school)* **and** *Delegated (personal Microsoft account)*. |
| **`offline_access`** | ✅ **REQUIRED** | *"your app must explicitly request the `offline_access` scope, to receive refresh tokens."* Without it there is no `refresh_token` and the user re-authenticates every hour. |
| `openid` | ✅ Recommended | Yields `id_token` → stable `sub` for keying multiple accounts locally. Cheap; no extra consent line. |
| `profile` | ✅ Recommended | Gives a display name for the account chooser **without** an extra Graph `/me` round-trip. |
| `User.Read` | ⚠️ **Optional — prefer to drop** | Only needed if you call `GET /me`. `profile` + `id_token` already give a display name. Fewer scopes = a shorter consent screen = fewer tenant-admin blocks. Add it only if `/me` is genuinely needed. |
| **`Files.Read.All`** | ❌ **DO NOT REQUEST** | Listed only as a *higher privileged* alternative. Requesting it enlarges the consent prompt and materially raises the odds a Business tenant admin blocks the app. Add later, per-user, only if a real SharePoint use case appears. |
| `Sites.Read.All` | ❌ Not for v1 | Work/school only; needed only to enumerate arbitrary SharePoint document libraries via `/sites/{id}/drives`. Out of scope per PROJECT.md. |
| `Files.ReadWrite*` | ❌ Never | This add-on is read-only. Requesting write on a user's whole OneDrive from a TV box is indefensible. |
| **`https://graph.microsoft.com/.default`** | ❌ **NOT APPROPRIATE** | Three independent reasons: (a) `.default` prompts for *every* permission on the registration, not the ones you need — the opposite of least privilege for a multi-tenant public app; (b) *"Clients can't combine static (`.default`) and dynamic consent in a single request"*, so you could not also request `offline_access`/`openid` alongside it; (c) `.default` is *required* only for on-behalf-of and client-credentials — neither applies. |

**Fully-qualified vs. bare scope:** `scope=Files.Read` is equivalent to `scope=https://graph.microsoft.com/Files.Read` (Graph is the default resource when the identifier is omitted). Use the **fully-qualified** form — it is unambiguous and survives any future default change.

**Business-tenant reality (design constraint, not a bug):** some tenants require admin consent for any third-party app. The add-on cannot work around this. Detect `AADSTS65001` / `consent_required` / `AADSTS90094` at sign-in and route the user to the custom-`client_id` advanced setting with a clear message. This is exactly what the hidden `client_id` setting exists for.

---

## 3. MSAL Python vs. Hand-Rolled — Verdict

### Verdict: **hand-roll the device-code flow with `urllib.request` from the stdlib. MSAL Python is not viable.**

Confidence **HIGH**. Three independent blockers, each fatal on its own:

1. **MSAL is not in the Kodi repository.** Enumerating `https://mirrors.kodi.tv/addons/{nexus,omega,piers}/` shows **no `script.module.msal`**. Kodi add-ons may only `<import>` add-ons published in a repository Kodi can resolve — so there is nothing to depend on.
2. **MSAL's dependency chain is unshippable.** `msal` 1.37.0 requires `requests`, **`PyJWT[crypto]`**, and **`cryptography>=2.5,<51`**. `cryptography` is a compiled extension (Rust + OpenSSL) requiring per-architecture binaries for `windows-x86_64`, `android-armv7`, `android-aarch64`, … There is **no `script.module.cryptography`** in any Kodi repo, and vendoring compiled wheels into a `<platform>all</platform>` add-on is not a thing Kodi supports.
3. **MSAL solves problems this add-on doesn't have.** MSAL exists for token caching across resources, broker integration, CAE, and multi-authority discovery. Here the entire protocol surface is: one POST to `/devicecode`, a polling loop, and one POST to `/token` with `grant_type=refresh_token`. That is **~120 lines** of pure, unit-testable Python.

### Kodi-repository HTTP/auth modules — complete enumeration

Verified present in **all three** target repos (nexus / omega / piers) at **identical versions**:

| Add-on ID | Version | Verdict |
|-----------|---------|---------|
| `script.module.requests` | 2.31.0 | Optional fallback |
| `script.module.urllib3` | 2.2.3 | Transitive only |
| `script.module.certifi` | 2023.5.7 | Transitive only (stale CA bundle) |
| `script.module.idna` | 3.10.0 | Transitive only |
| `script.module.chardet` | 5.1.0 | Transitive only |
| `script.module.six` | 1.16.0+matrix.1 | Do not use — Python 3.11 only |
| `script.module.oauthlib` | 3.2.2 | Not needed (see below) |
| `script.module.requests_oauthlib` | 1.3.1+matrix.1 | Not needed (see below) |
| `script.module.pyjwt` | 2.8.0 | Not needed — never validate Microsoft's tokens |
| `script.module.dateutil` | — | Not needed — `datetime.fromisoformat` handles Graph timestamps on 3.11 |
| `script.module.simplejson`, `script.module.pysocks`, `script.module.kodi-six`, `script.module.myconnpy`, `script.module.requests-cache`, `script.module.inputstreamhelper` | — | Not applicable |

**Absent from every Kodi repo:** `msal`, `cryptography`, `httpx`, `authlib`, `google-auth`, `charset-normalizer`.

**Why not `oauthlib` / `requests_oauthlib` even though they exist:** `oauthlib` 3.2.2 has **no device authorization grant client**. RFC 8628 client support did not land in `oauthlib` 3.2.x. You would still hand-roll the flow and merely inherit a dependency.

**Why `urllib.request` over `requests` 2.31.0:**

- **Zero install-time dependency resolution on Android TV.** Every `<import>` is another add-on Kodi must fetch and enable at install and at every update. Fewer moving parts on the platform you cannot easily debug.
- `requests` in Kodi pins `certifi` **2023.5.7** — a CA bundle over 3 years stale. `urllib.request` on Windows and Android uses the platform trust store via Kodi's OpenSSL build, which is maintained.
- The stdlib is trivially fakeable in tests (`unittest.mock.patch('urllib.request.urlopen')`); no network layer to stub.
- The one place `requests` clearly wins — streaming downloads — is not needed: Kodi's player fetches the media URL itself; Python never proxies the byte stream.

**Concrete stdlib pattern for the token endpoint** (this is the shape the plan should specify, because it is where naive code breaks):

```python
import json, urllib.request, urllib.parse, urllib.error

def _post_form(url, fields, timeout=20):
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # REQUIRED: OAuth errors arrive as HTTP 400 with a JSON body.
        return e.code, json.loads(e.read().decode("utf-8"))
```

---

## 4. Kodi API Versions — what `addon.xml` must declare

### 4.1 Ground truth (read from `addons/xbmc.python/addon.xml` on each branch)

| Kodi release | Branch | `xbmc.python` version | `backwards-compatibility abi` |
|--------------|--------|-----------------------|-------------------------------|
| 19 Matrix | `Matrix` | `3.0.0` | `3.0.0` |
| **20 Nexus** | `Nexus` | **`3.0.1`** | `3.0.0` |
| **21 Omega** | `Omega` | **`3.0.1`** | `3.0.0` |
| **22 Piers** | `master` | **`3.0.2`** | `3.0.0` |

### 4.2 The resolution rule (from Kodi C++ source, identical on Nexus / Omega / master)

`CAddonInfo::MeetsVersion(versionMin, version)`:

```cpp
return !(versionMin > m_version || version < m_minversion);
```

and, from `DependencyInfo`, when `<import>` omits `minversion`:

```cpp
versionMin(versionMin.empty() ? version : versionMin)
```

So for `<import addon="xbmc.python" version="V"/>` the add-on installs iff **`V <= installedVersion`** and **`V >= abi`**.

Applying it:

| `<import ... version="…">` | Kodi 19 | Kodi 20 | Kodi 21 | Kodi 22 |
|----------------------------|---------|---------|---------|---------|
| `3.0.0` | ✅ | ✅ | ✅ | ✅ |
| **`3.0.1`** | ❌ | ✅ | ✅ | ✅ |
| `3.0.2` | ❌ | ❌ | ❌ | ✅ |

### 4.3 Prescription

```xml
<requires>
  <import addon="xbmc.python" version="3.0.1"/>
</requires>
```

**One line. That is the whole answer.** It installs on Kodi 20, 21 and 22 and is *rejected by Kodi 19* — which is exactly the stated goal, and enforces the Kodi-19 drop mechanically rather than by convention. It also matches `kodi-addon-checker`'s `advised` value for `nexus`, `omega`, **and** `piers` (`min_compatible: 3.0.0, advised: 3.0.1`), so the linter is clean on all three branches.

- **Do not** declare `3.0.0` — Kodi 19 users would install it and hit the untyped-InfoTag paths you are deleting.
- **Do not** declare `3.0.2` — that locks out Kodi 20 and 21.
- **Do not** use the `minversion=` attribute here. It exists (parsed since Kodi 19) but adds nothing: a bare `version="3.0.1"` already yields exactly the wanted range, and `minversion` is a subtlety future maintainers will misread.
- **Delete** `<import addon="script.module.clouddrive.common" version="1.4.0"/>` entirely once vendored.

### 4.4 Bundled CPython — language level you may target

| Kodi | CPython (from `tools/depends/target/python3/PYTHON3-VERSION` at release tag) |
|------|------|
| 20.0 Nexus | **3.11.0** |
| 20.5 Nexus | 3.11.2 |
| 21.0 / 21.2 Omega | **3.11.7** |
| 22.0a1 Piers | 3.13.5 (master now 3.14.6) |

**Target Python 3.11.** Safe: f-strings, `:=`, `dataclasses`, `functools.cached_property`, `datetime.fromisoformat` (3.11 handles the `Z` suffix Graph emits), `typing` PEP 604 unions, `tomllib`. **Not safe:** anything 3.12+ (e.g. PEP 695 `type` statement, `itertools.batched`) — Kodi 20 must still run it.

### 4.5 Other manifest changes required

- **Typed InfoTag setters are mandatory on Kodi 20+.** `ListItem.setInfo()` is deprecated; use `li.getVideoInfoTag().setTitle(...)`, `.setDuration(int)`, `.setMediaType(...)`. `setDuration()` takes an **`int`** — the existing float-division bug (`/ 1000`) will now raise, not merely warn. Use `int(ms // 1000)`.
- Update `<news>`, `<source>`, `<website>`, `<forum>` to point at the fork; the checker validates these URLs.
- Delete the `<disclaimer>` describing the sign-in server — it will be false.

---

## 5. Kodi Settings Format (`<settings version="1">`)

### 5.1 Schema — element and attribute names

Verified from Kodi master `xbmc/settings/lib/SettingDefinitions.h`.

Structure: `settings` → `section` → `category` → `group` → `setting`.

Child **elements** of `<setting>`: `level`, `default`, `value`, `constraints`, `control`, `visible`, `requirement`, `enable`, `dependencies`/`dependency`, `updates`/`update`, `options`/`option`, `minimum`, `step`, `maximum`, `allowempty`, `allownewoption`, `delimiter`, `minimumitems`, `maximumitems`, `data`.

**Attributes** of `<setting>`: `id`, `label`, `help`, `type`, `parent`, `ref`, `format`, `delayed`.

### 5.2 Canonical minimal example (a real Team Kodi add-on, `service.xbmc.versioncheck`, master)

```xml
<?xml version="1.0" ?>
<settings version="1">
    <section id="service.xbmc.versioncheck">
        <category help="" id="general" label="32020">
            <group id="1">
                <setting help="" id="versioncheck_enable" label="32021" type="boolean">
                    <level>0</level>
                    <default>true</default>
                    <control type="toggle"/>
                </setting>
            </group>
        </category>
    </section>
</settings>
```

`label` and `help` take **numeric string IDs** resolved from `resources/language/resource.language.en_gb/strings.po` (use IDs ≥ 30000 for add-ons). `<group id="…">` is required; the id is arbitrary.

### 5.3 Marking a setting "advanced" vs. truly hidden — two different mechanisms

Kodi `SettingLevel` enum (`xbmc/settings/lib/SettingLevel.h`):

| `<level>` | Name | Visible when the settings screen is at… |
|-----------|------|------------------------------------------|
| `0` | Basic | always |
| `1` | Standard | Standard and above |
| `2` | **Advanced** | Advanced and above |
| `3` | Expert | Expert only |
| `4` | Internal | never shown in the UI |

- **For the custom `client_id`** — the PROJECT.md requirement "hidden, empty by default" — use **`<level>3</level>`** (Expert). The setting is real, editable, and empty by default, but a normal user browsing the add-on's settings will never see it. Level 2 (Advanced) is acceptable but noisier.
- **`<visible>`** is a *condition*, not a level. Use it for conditional display (e.g. `<visible>!String.IsEmpty(client_id)</visible>`), or `<visible>false</visible>` to hard-hide a value you still want persisted. Do **not** use `<visible>false</visible>` for the custom `client_id` — the user must be able to reach it.

```xml
<category id="advanced" label="30900">
  <group id="1">
    <setting id="custom_client_id" type="string" label="30901" help="30902">
      <level>3</level>
      <default></default>
      <constraints><allowempty>true</allowempty></constraints>
      <control type="edit" format="string"/>
    </setting>
  </group>
</category>
```

### 5.4 Reading settings from Python (Kodi 20+)

Kodi 20 introduced `xbmcaddon.Addon().getSettings()`, returning a `Settings` wrapper, and **deprecated** `getSettingString/Bool/Int/Number`. Since Kodi 19 is dropped, use the new API:

```python
import xbmcaddon
s = xbmcaddon.Addon().getSettings()
client_id = s.getString('custom_client_id')     # '' when unset
s.setString('custom_client_id', value)
```

`Settings` exposes `getBool/getInt/getNumber/getString` and `setBool/setInt/setNumber/setString` (plus `*List` setters). Verified in `xbmc/interfaces/legacy/Settings.h` on master.

The legacy `Addon().getSetting(id)` (always returns `str`) still works on 20/21/22 and is what Kodistubs 21.0.0 models most completely — acceptable if a stub gap bites, but prefer `getSettings()`.

### 5.5 Migration note

Kodi does **not** migrate values when you restructure `settings.xml`. Setting **ids** are the persistence key — `special://profile/addon_data/plugin.onedrive/settings.xml` is keyed by `id` only, so ids that keep their name keep their value across the schema rewrite. Deliberately **rename or delete** `sign-in-server` so no stale dead-Heroku value can survive (per PROJECT.md's "delete rather than repoint" decision), and default `allow_directory_listing` to `false` **under a new id** so existing `true` values do not carry over.

---

## 6. Token Storage on Device

### What Kodi offers

| Mechanism | Path / API | Suitable for refresh tokens? |
|-----------|------------|------------------------------|
| Add-on settings (`Addon().getSettings().setString`) | `special://profile/addon_data/<id>/settings.xml` | ❌ **No** |
| Add-on profile directory | `xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))` → resolves `special://profile/addon_data/<id>/` | ✅ **Yes** |
| `xbmcvfs.File` / `xbmcvfs.mkdirs` / `xbmcvfs.exists` | VFS-aware file IO | ✅ Yes |
| Window properties (`xbmcgui.Window(10000).setProperty`) | In-memory, process-scoped | ⚠️ In-memory access-token cache only |
| OS keychain / Android Keystore | — | ❌ Not exposed to Kodi Python. No secure enclave is available. |

### Prescription

**Store the refresh token in a JSON file in the add-on profile directory. Never in a Kodi setting.**

Reasons a setting is wrong:
1. Every add-on setting is **rendered in the Settings UI**. Even at `<level>4</level>` it lands in a plaintext XML the user, a skin, or a support-log uploader can read.
2. Kodi's **debug log** and community "upload your log" workflows routinely capture add-on settings. A refresh token in `settings.xml` is a refresh token in a pastebin.
3. Settings are string-typed and not designed for multi-account structures; this add-on supports "unlimited accounts".
4. Rotation writes on **every refresh** — hammering the settings store triggers `onSettingsChanged` churn across the plugin and the service process.

```python
import os, json, xbmcvfs, xbmcaddon

def _token_path():
    profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
    xbmcvfs.mkdirs(profile)
    return os.path.join(profile, 'accounts.json')
```

Rules for the store:
- **Atomic writes**: write `accounts.json.tmp`, `os.replace()` onto `accounts.json`. Refresh-token rotation means a torn write loses the account permanently.
- **Single-writer discipline**: `entrypoint.py` (plugin) and `service.py` (service) are **separate processes**. Concurrent refreshes will race and one will persist a now-invalid rotated token. Guard with a lock file, or make the **service** the sole refresher and have the plugin read-only + retry.
- **`chmod 0600`** on POSIX (best-effort; a no-op on Android, but free).
- Key accounts by the `sub`/`oid` claim from `id_token`, or by Graph `drive.id` — not by display name.
- **Do not encrypt with a key stored next to the file.** That is obfuscation, not security, and it adds a failure mode. Be honest in the README: tokens are stored on-device in the Kodi profile, protected by filesystem permissions. This is what rclone, the Azure CLI, and every other device-code client do.
- **`xbmcvfs.translatePath`, not `xbmc.translatePath`** — the latter was removed in Kodi 19 (`@python_v19 New function added (replaces old xbmc.translatePath)`).

---

## 7. Packaging and Distribution

### 7.1 Installable add-on zip

Kodi resolves a repository add-on's download URL from source (`AddonInfoBuilder.cpp`) as:

```cpp
m_path = AddFileToFolder(repo.datadir, addon->m_id,
                         Format("{}-{}.zip", addon->m_id, addon->m_version.asString()));
```

So the zip **must** be named `plugin.onedrive-<version>.zip` and **must** contain a single top-level directory named exactly `plugin.onedrive/`:

```
plugin.onedrive-3.0.0.zip
└── plugin.onedrive/
    ├── addon.xml
    ├── icon.png            (512x512 or 256x256 PNG)
    ├── fanart.jpg          (1280x720 or 1920x1080)
    ├── LICENSE.txt
    ├── entrypoint.py
    ├── service.py
    └── resources/
        ├── settings.xml
        ├── lib/
        └── language/resource.language.en_gb/strings.po
```

Exclude from the zip: `.git*`, `.github/`, `tests/`, `*.pyc`, `__pycache__/`, `.project`, `.pydevproject`, `.idea/`. `kodi-addon-checker` flags blacklisted filetypes and files marked executable.

### 7.2 Self-hosted GitHub repository — exact layout

Kodi's `CRepository` reads a `<dir>` block. **The flat pre-Gotham schema is gone** — Kodi master logs an error: *"Repository add-on … uses old schema definition for the repository extension point! This is no longer supported."*

`repository.onedrive/addon.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<addon id="repository.onedrive" name="OneDrive Add-on Repository"
       version="1.0.0" provider-name="Kenny Nguyen">
  <requires>
    <import addon="xbmc.addon" version="20.0.0"/>
  </requires>
  <extension point="xbmc.addon.repository" name="OneDrive Add-on Repository">
    <dir minversion="20.0.0">
      <info compressed="true">https://raw.githubusercontent.com/&lt;user&gt;/&lt;repo&gt;/main/repo/addons.xml.gz</info>
      <checksum verify="sha256">https://raw.githubusercontent.com/&lt;user&gt;/&lt;repo&gt;/main/repo/addons.xml.gz.sha256</checksum>
      <datadir zip="true">https://raw.githubusercontent.com/&lt;user&gt;/&lt;repo&gt;/main/repo</datadir>
      <artdir>https://raw.githubusercontent.com/&lt;user&gt;/&lt;repo&gt;/main/repo</artdir>
      <hashes>sha256</hashes>
    </dir>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="en_GB">OneDrive add-on repository</summary>
    <description lang="en_GB">Install and auto-update the OneDrive add-on.</description>
    <platform>all</platform>
    <license>GPL-3.0-or-later</license>
    <assets><icon>icon.png</icon></assets>
  </extension>
</addon>
```

`<dir>` element semantics, read from `CRepository::ParseDirConfiguration`:

| Element/attr | Meaning |
|--------------|---------|
| `<info>` | URL of the index. `.gz` extension (or a gzip MIME type) triggers decompression. |
| `<checksum verify="sha256">` | URL of a file whose first whitespace-delimited token is the digest of the **index**. `verify` selects the algorithm. |
| `<datadir>` | Base URL. Kodi appends `/<addon.id>/<addon.id>-<version>.zip`. |
| `<artdir>` | Base URL for `icon.png` / `fanart.jpg`. Defaults to `datadir` if omitted. |
| `<hashes>` | Per-**zip** digest algorithm: `sha256`, `md5`, `false`, or `true` (deprecated alias for md5). Kodi first looks for a `Content-SHA256`/`Content-MD5` HTTP header and only then falls back to fetching `<zipurl>.<alg>`. |
| `@minversion` / `@maxversion` | Kodi (`xbmc.addon`) version range this `<dir>` applies to. |

Resulting on-disk layout in the GitHub repo:

```
repo/
├── addons.xml                      (optional uncompressed copy)
├── addons.xml.gz                   ← <info>
├── addons.xml.gz.sha256            ← <checksum verify="sha256">
├── plugin.onedrive/
│   ├── plugin.onedrive-3.0.0.zip
│   ├── plugin.onedrive-3.0.0.zip.sha256
│   ├── icon.png
│   └── fanart.jpg
└── repository.onedrive/
    ├── repository.onedrive-1.0.0.zip
    ├── repository.onedrive-1.0.0.zip.sha256
    └── icon.png
```

`addons.xml` is `<addons>` wrapping each add-on's full `<addon>` element verbatim:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addons>
  <addon id="plugin.onedrive" ...> ... </addon>
  <addon id="repository.onedrive" ...> ... </addon>
</addons>
```

**Use SHA-256, not MD5.** Kodi logs on every repo refresh: *"Repository has MD5 hashes enabled — this hash function is broken and will only guard against unintentional data corruption."* SHA-256 support for both `<checksum verify>` and `<hashes>` is present in Nexus, Omega, and master (verified in all three branches). The classic `addons.xml.md5` recipe from old wiki tutorials is **legacy**; it works, but ship SHA-256.

**Serve over HTTPS.** `CRepository`'s constructor emits a warning for plain-HTTP `datadir` and for `verifypeer=false`. `raw.githubusercontent.com` (or GitHub Pages) satisfies this.

**Android TV one-time flow** (matches the "remote-only" constraint): the user adds a *file source* pointing at the repo URL once, installs `repository.onedrive-1.0.0.zip` from it, and thereafter every `plugin.onedrive` release is auto-offered. Kodi rechecks every 24 h by default (`recheckAfter`), or per the `X-Kodi-Recheck-After` response header, clamped to 1 h–1 week. **Bump the *repository* add-on's version essentially never** — bump only `plugin.onedrive`, since repository updates are the one thing that still requires manual intervention.

### 7.3 CI

A GitHub Actions workflow should, on tag:
1. `kodi-addon-checker --branch omega .` (and `--branch piers`, `--branch nexus`) — must pass.
2. `pytest`.
3. Build `plugin.onedrive-<version>.zip` from `addon.xml`'s `version` attribute (single source of truth).
4. Regenerate `repo/addons.xml`, gzip it, and write all `.sha256` sidecars.
5. Commit to the repo branch / publish to GitHub Pages.

Use `--skip-dependency-checks` **only** if you deliberately depend on something outside the official Kodi repos. After vendoring `clouddrive.common`, the only dependency is `xbmc.python`, so the full check should pass clean.

---

## 8. Testing Off-Device

### Kodi stubs

| Package | Version | Notes |
|---------|---------|-------|
| **`Kodistubs`** (PyPI, `pip install Kodistubs`) | **21.0.0**, `requires_python >=3.6` | The de-facto standard. Provides importable `xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcaddon`, `xbmcvfs`, `xbmcdrm` with correct signatures and docstrings. Every function is a no-op returning a default. |

- Release history: `20.0.0` → `20.0.1` → `21.0.0`. **No 22/Piers release exists.** Not a problem: this add-on's API surface (`ListItem`, `getVideoInfoTag`, `addDirectoryItem`, `Addon`, `Dialog`, `translatePath`) is unchanged in 22.
- Kodistubs is a **dev/test dependency only** — never `<import>` it and never ship it.
- **Kodistubs gives you importability, not behaviour.** For anything where the return value matters (settings, `Dialog.yesno`, `translatePath`), inject a fake with `unittest.mock` or install a lightweight in-memory fake module into `sys.modules` in `conftest.py`. A hybrid — Kodistubs for the wide surface, hand-written fakes for the 6–8 calls you actually assert on — is the right shape.

### What to unit-test (all pure, all off-device)

The parsing layer is already pure. Cover:
- `_extract_item` against recorded Graph `driveItem` JSON — video, audio, image, folder, `remoteItem`, `package`, missing-facet.
- `@odata.nextLink` pagination as an **iterative loop**; assert cancellation returns `[]`, never `None`.
- Graph path building with names containing `#`, `?`, `%`, `+`, `:`, `'` → per-segment `urllib.parse.quote`.
- OData `search(q='…')` literal escaping (`'` → `''`) **before** quoting.
- `int` duration conversion (`int(ms // 1000)`).
- **The device-code polling state machine** — this is new, high-risk code and 100% testable with a fake `urlopen`: pending → pending → success; pending → `slow_down` (assert interval increased by 5); → `expired_token`; → `invalid_grant`; HTTP 400 body parsing; timeout backoff.
- **Token store**: rotation persists the new refresh token; atomic replace; corrupt-file recovery.

### `kodi-addon-checker` — what it validates (v0.0.36)

Artwork presence/size/validity; `addon.xml` + LICENSE presence; add-on `version` validity for the repo generator; XML and JSON well-formedness; folder name == add-on id; legacy `strings.xml` translation format; legacy language folder names (`English` vs `resource.language.en_gb`); blacklisted strings; blacklisted filetypes; new dependencies in `addon.xml`; entrypoint file complexity; add-on already present in a lower repo; add-on present in an upper repo with a lower version (would break user migration); Python 3 compatibility; the `version` attribute of `<import>` entries against a per-Kodi-version table; `addon.xml` against the official XSD schemas; files marked executable; **unused `script.module` dependencies**; presence of extension points in dependencies; `forum`/`source`/`website` URL validity; PO file validity.

> The "unused `script.module` addons" check is a direct argument for the stdlib approach: declaring `script.module.requests` and then not importing it is a lint failure.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `urllib.request` (stdlib) | `script.module.requests` 2.31.0 | If you need connection pooling across hundreds of Graph calls in one session, or automatic retry/redirect semantics you don't want to write. Cost: 5 extra add-on dependencies and a 2023 CA bundle. |
| `/common` authority | `/consumers` | Personal-account-only build, or if a future Entra change breaks `/common` for MSA. Note the different `verification_uri` (`https://www.microsoft.com/link`). |
| `/common` authority | `/organizations` or `/{tenantId}` | Pair with the custom-`client_id` advanced setting for a locked-down Business tenant. |
| `Files.Read` | `Files.Read.All` | Only if a user reports they need SharePoint document libraries beyond their own OneDrive. Costs a much scarier consent prompt. |
| Device code flow | Auth code + PKCE + loopback | Explicitly out of scope per PROJECT.md. Only revisit if Microsoft deprecates device code for MSA. |
| SHA-256 repo hashes | MD5 (`addons.xml.md5`) | Never for a new repo. Only if targeting a Kodi older than Gotham, which you are not. |
| Profile-dir JSON token store | Kodi settings | Never. |
| Kodistubs 21.0.0 | Hand-written `sys.modules` fakes | Use fakes *in addition* wherever a return value is asserted on. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **MSAL Python (`msal`)** | Not in any Kodi repo; requires `cryptography` (compiled Rust/OpenSSL) and `PyJWT[crypto]`, neither shippable in a `<platform>all</platform>` add-on | ~120 lines of `urllib.request` implementing RFC 8628 directly |
| **`cryptography`, `PyJWT`** | Not needed. Never validate or parse tokens for an API you don't own — Microsoft explicitly warns MSA tokens *"may also be encrypted for consumer users"* and *"will not validate as a JWT"* | Treat `access_token` as an opaque bearer string |
| **`https://graph.microsoft.com/.default`** | Prompts for *every* registered permission, cannot be combined with `offline_access`/`openid` in one request, and is only *required* for OBO / client-credentials | Explicit scopes: `Files.Read offline_access openid profile` |
| **`Files.Read.All`, `Files.ReadWrite*`, `Sites.Read.All`** | Over-privileged for a read-only browser; sharply raises the odds a Business tenant admin blocks consent | `Files.Read` |
| **A client secret or certificate** | Public clients "must not use secrets or certificates". A secret embedded in a GPL add-on is public by definition, and its presence turns the app confidential and breaks device code | `allowPublicClient: true`, no credential |
| **`allowPublicClient` left at its `false` default** | Entra falls back to confidential-client and rejects the token request demanding `client_assertion`/`client_secret` (`AADSTS7000218`) | Set **Allow public client flows = Yes** |
| **Hardcoding `https://microsoft.com/devicelogin`** | `/consumers` returns `https://www.microsoft.com/link`; `/common` currently returns `https://login.microsoft.com/device`. These change | Render the `verification_uri` / `message` from the response |
| **Relying on `verification_uri_complete`** | Microsoft explicitly does **not** return it | No server-provided QR URL; display `user_code` separately |
| **`raise_for_status()` on the token endpoint** | Verified: `authorization_pending` arrives as **HTTP 400**. Raising kills every device-code login | Catch `HTTPError` and parse `e.read()` as JSON |
| **Deny-list polling (only handling the 4 documented errors)** | `slow_down` is undocumented by Microsoft but mandated by RFC 8628; a bogus `device_code` returns `invalid_grant`/`AADSTS7000014`, **not** the documented `bad_verification_code` | Allow-list: continue only on `authorization_pending` / `slow_down`; everything else terminates |
| **`<import addon="xbmc.python" version="3.0.0"/>`** | Kodi 19 would install the add-on | `version="3.0.1"` |
| **`<import addon="xbmc.python" version="3.0.2"/>`** | Locks out Kodi 20 **and** 21 | `version="3.0.1"` |
| **`script.module.clouddrive.common`** | Unmaintained since 2023-01-21; `<import version="1.4.0">` is a *minimum*, so a future 2.x silently satisfies it and breaks at runtime | Vendor and trim into the repo; delete the `<import>` |
| **`xbmc.translatePath`** | Removed in Kodi 19 | `xbmcvfs.translatePath` |
| **`ListItem.setInfo()`** | Deprecated in Kodi 20; typed setters are strict | `li.getVideoInfoTag().setDuration(int(...))` etc. |
| **`script.module.six`, `kodi-six`** | Python-2 compatibility shims; Kodi 20+ is CPython 3.11+ | Delete |
| **`script.module.oauthlib` / `requests_oauthlib`** | oauthlib 3.2.2 has **no** RFC 8628 device-grant client — you'd hand-roll anyway and gain a dependency | stdlib |
| **`script.module.dateutil`** | `datetime.fromisoformat` on 3.11 parses Graph's `…Z` timestamps natively | stdlib `datetime` |
| **Storing refresh tokens in Kodi settings** | Rendered in the Settings UI, captured by Kodi debug-log uploads, and rotation-write churn triggers `onSettingsChanged` across two processes | Atomic JSON file in `special://profile/addon_data/plugin.onedrive/` |
| **Legacy `<settings><category>` schema, `window(home).property(iskrypton)`** | Krypton-era; the Kodi shim is deprecated | `<settings version="1">` with `<section>/<category>/<group>` |
| **`addons.xml.md5` / `<hashes>true</hashes>`** | Kodi logs the hash as "broken" on every repo refresh | `<hashes>sha256</hashes>` + `<checksum verify="sha256">` |
| **The flat pre-`<dir>` repository extension schema** | Kodi ≥21 hard-errors: *"no longer supported"* | `<dir>` with `<info>/<checksum>/<datadir>/<artdir>/<hashes>` |
| **Python 3.12+ syntax** (PEP 695 `type`, `itertools.batched`) | Kodi 20 Nexus ships CPython 3.11.0 | Target 3.11 |
| **`beta` Microsoft Graph endpoint** | Unstable, no SLA | `https://graph.microsoft.com/v1.0` |

---

## Version Compatibility

| Component | Compatible with | Notes |
|-----------|-----------------|-------|
| `<import addon="xbmc.python" version="3.0.1"/>` | Kodi 20.x, 21.x, 22.x | Rejected by Kodi 19 (`MeetsVersion`: `3.0.1 > 3.0.0`). Exactly the desired matrix. |
| Python **3.11** language level | Kodi 20 (3.11.0) → 22 (3.13.5+) | Floor is Kodi 20.0. |
| `script.module.requests` 2.31.0 | nexus, omega, piers repos | Same version in all three; one `<import>` line if you use it at all. |
| Kodistubs 21.0.0 | Kodi 20/21/22 code | No Piers release; API surface used here is unchanged. |
| `kodi-addon-checker` 0.0.36 | `--branch nexus|omega|piers` | All three branches known; `xbmc.python` advised `3.0.1` for all three. |
| `<checksum verify="sha256">` / `<hashes>sha256</hashes>` | Kodi 20, 21, 22 | Verified in `Repository.cpp` on `Nexus`, `Omega`, and `master`. |
| `Addon().getSettings()` | Kodi 20+ | New in v20; `getSettingString/Bool/Int/Number` deprecated in v20 but still functional. |
| `xbmcvfs.translatePath` | Kodi 19+ | Replaced `xbmc.translatePath`. |
| Device code + `/common` | Current (probed 2026-08-22) | Re-verify at implementation time; this is the single highest-leverage assumption. |

---

## Open Risks to Validate in Phase 1

1. **`/common` + device code with a real personal Microsoft account and a real work account, using *our own* registered `client_id`.** The probe above used a Microsoft first-party client. Microsoft first-party clients are pre-authorized in ways third-party ones are not — confirm end-to-end with the maintainer's registration before building anything on top. **This is the one spike that must happen first.**
2. **Consent screen on a Business tenant.** Determine which `AADSTS` code surfaces when the tenant blocks third-party apps, so the custom-`client_id` escape hatch can be triggered with a precise message rather than a generic failure.
3. **Two-process token refresh race** between `entrypoint.py` and `service.py`. Rotation means the loser of the race persists a dead token. Decide the single-writer design before implementing refresh.

---

## Sources

**Microsoft — official docs (HIGH confidence)**
- `learn.microsoft.com/entra/identity-platform/v2-oauth2-device-code` (doc updated 2026-06-15) — endpoints, POST bodies, response fields, error table, `verification_uri_complete` non-support, `/common`|`/consumers`|`/organizations`
- `learn.microsoft.com/entra/identity-platform/msal-client-application-configuration` — authority semantics; `common` = work/school **and** personal
- `learn.microsoft.com/entra/identity-platform/reference-app-manifest` — `allowPublicClient`, `signInAudience`, `requestedAccessTokenVersion`, `replyUrlsWithType`
- `learn.microsoft.com/entra/identity-platform/quickstart-register-app` — Supported account types labels
- `learn.microsoft.com/entra/identity-platform/scopes-oidc` — `offline_access`, `openid`, `profile`, `.default` and the static/dynamic-consent restriction
- `learn.microsoft.com/entra/identity-platform/refresh-tokens` — 90-day lifetime, rotation, revocation matrix
- `learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow` — refresh-token redemption body and token-endpoint error codes
- `learn.microsoft.com/graph/api/driveitem-list-children` — permissions table (`Files.Read` least-privileged for personal **and** work/school)
- `learn.microsoft.com/graph/api/drive-list` — `/me/drives` permissions
- `learn.microsoft.com/entra/msal/dotnet/.../device-code-flow` — "Allow public client flows"; ⚠️ contains a **stale** `/common` constraint, superseded

**Live protocol probes, 2026-08-22 (HIGH confidence — first-hand)**
- `POST /{common,consumers,organizations}/oauth2/v2.0/devicecode` → 200 + `device_code`/`user_code`/`verification_uri`/`expires_in=900`/`interval=5`
- `POST /common/oauth2/v2.0/token` (pending) → **HTTP 400**, `authorization_pending`, `error_codes [70016]`
- `POST /common/oauth2/v2.0/token` (bogus `device_code`) → HTTP 400, **`invalid_grant`**, `error_codes [7000014]`

**Kodi — primary source (HIGH confidence)**
- `xbmc/xbmc` `addons/xbmc.python/addon.xml` @ `Matrix`, `Nexus`, `Omega`, `master` — versions + `abi`
- `xbmc/addons/addoninfo/AddonInfo.cpp` @ `Nexus`, `master` — `MeetsVersion`
- `xbmc/addons/addoninfo/AddonInfo.h` — `DependencyInfo` (`versionMin` defaults to `version`)
- `xbmc/addons/addoninfo/AddonInfoBuilder.cpp` @ `master` — `<import>` / `backwards-compatibility` parsing; repo zip path construction
- `xbmc/addons/AddonManager.cpp` @ `master` — `IsCompatible`
- `xbmc/addons/Repository.cpp` / `Repository.h` @ `Nexus`, `Omega`, `master` — `<dir>` schema, `checksum@verify`, `hashes`, gzip index, MD5 warning, flat-schema removal
- `xbmc/settings/lib/SettingDefinitions.h`, `SettingLevel.h` @ `master` — settings element/attribute names, `SettingLevel` enum
- `xbmc/interfaces/legacy/Settings.h`, `Addon.h`, `ModuleXbmcvfs.h` @ `master` — `getSettings()` (v20), deprecations, `translatePath` (v19)
- `addons/service.xbmc.versioncheck/resources/settings.xml` @ `master` — canonical `version="1"` example
- `tools/depends/target/python3/PYTHON3-VERSION` @ tags `20.0-Nexus`, `20.5-Nexus`, `21.0-Omega`, `21.2-Omega`, `22.0a1-Piers`

**Kodi ecosystem (HIGH confidence — live index / official tooling)**
- `mirrors.kodi.tv/addons/{nexus,omega,piers}/` — complete module enumeration and versions; **absence** of `script.module.msal` and `script.module.cryptography`
- `xbmc/repo-scripts@matrix:script.module.requests/addon.xml` — transitive dependency chain
- `xbmc/addon-check` `versions.py`, `check_dependencies.py`, `README.md`, `__init__.py` — `VERSION_ATTRB` table, `ValidKodiVersions`, feature list
- PyPI JSON API — `Kodistubs` 21.0.0, `kodi-addon-checker` 0.0.36, `msal` 1.37.0 (`requires_dist` proving the `cryptography` chain)

**Standards (HIGH confidence)**
- RFC 8628 §3.5 — `authorization_pending`, `slow_down` (+5 s, permanent), `access_denied`, `expired_token`; "MUST stop polling on any other error"; connection-timeout backoff

---
*Stack research for: Kodi 20/21/22 OneDrive add-on with in-add-on OAuth 2.0 device authorization grant*
*Researched: 2026-08-22*
