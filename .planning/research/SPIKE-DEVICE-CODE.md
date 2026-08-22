# Spike: Device Code Flow and Drive Enumeration

**Run:** 2026-08-22
**Confidence:** HIGH — first-hand end-to-end runs against live endpoints with this project's own app registration, not a first-party client and not documentation.

This spike answers the question SUMMARY.md named the project's load-bearing unknown: whether our own non-first-party `client_id` works on the `/common` authority for both account classes. It was run before any implementation, as the roadmap requires.

Reproduction script: `.planning/research/verify_device_code.py` (stdlib only, same constraint the add-on runs under).

## App registration under test

| Field | Value |
|---|---|
| `appId` | `efe197b3-5c14-4d67-810f-e10406742a06` |
| `displayName` | Kodi OneDrive Add-on |
| `publisherDomain` | `e5.nguyentiendat.net` (Microsoft 365 E5 Developer tenant) |
| `signInAudience` | `AzureADandPersonalMicrosoftAccount` |
| `isFallbackPublicClient` | `true` — this is the Graph API name for "Allow public client flows" |
| `requestedAccessTokenVersion` | `2` |
| `passwordCredentials` / `keyCredentials` | empty — no secret, no certificate |
| redirect URIs | none, in `publicClient`, `web`, and `spa` |
| `verifiedPublisher` | null — consent screens show an "unverified" warning |

Requested scope string: `https://graph.microsoft.com/Files.Read offline_access openid profile`

## Result: the authority question is settled

`/common` works with this `client_id` for **both** a work/school account and a personal Microsoft account. No authority split is needed. A refresh token was issued in every run, so `offline_access` behaves as required.

| Run | Account | `tid` | `driveType` | Token |
|---|---|---|---|---|
| 1 | `nguyentiendat713@x14m4.onmicrosoft.com` | `8774cfb8-…` (E5 tenant) | business | acquired, 85 s |
| 2 | `nas@e5.nguyentiendat.net` | `8774cfb8-…` (same tenant) | business | acquired, 40 s |
| 3 | personal Microsoft account | `9188040d-6c67-4c5b-b112-36a304b66dad` | personal | acquired, 82 s |

`9188040d-6c67-4c5b-b112-36a304b66dad` is the well-known shared MSA tenant, which is how run 3 was confirmed to be a genuine personal account rather than a third work account.

Runs 1 and 2 are two distinct users in one tenant, each returning a different `sub`. That is direct evidence for the multi-account isolation requirement: `sub` is a per-app, per-user pairwise identifier and is a sound local key.

**Conditional Access did not block device code flow** on the E5 Developer tenant. This was the single largest risk in choosing that tenant, and it is now retired — for this tenant's current policy. It says nothing about other tenants, which may still block, so the custom `client_id` escape hatch remains necessary.

## Finding that invalidates a requirement: `/me/drives` is not universal

Graph's reference implies `/me/drives` serves both delegated account classes. It does not.

| Endpoint | Business | Personal |
|---|---|---|
| `GET /me/drives` | 200 | **403 `accessDenied`** |
| `GET /me/drive` | 200 | 200 |
| `GET /drives` | 403 | 403 |

**`/me/drive` is the only endpoint that works for both.** Since SharePoint document libraries are out of scope for v1, the default drive is sufficient, and the add-on needs no branch on account type at all — a simpler design than the one planned.

`/drives` returns 403 on both classes, confirming the research conclusion that it is not a usable v1.0 endpoint. Delete it.

This also explains a piece of the existing codebase that `CONCERNS.md` characterised as waste. `get_drives()` calling `/drives` and swallowing a 403 was not carelessness — it was handling this difference. The defect was that the reason was never recorded, so the behaviour read as dead code.

### Consequence

`REQUIREMENTS.md` BROWSE-08 was written as "Drive enumeration uses `/me/drives` only; the bare `/drives` call is gone." Implemented literally, that breaks every personal account. Corrected in place.

## Granted scopes differ by account class

| Run | `scope` returned |
|---|---|
| Business | `openid profile email https://graph.microsoft.com/Files.Read` |
| Personal | `https://graph.microsoft.com/Files.Read openid profile` |

Entra adds `email` for work/school accounts without it being requested, and omits it for personal. `offline_access` appears in neither granted set even though a refresh token was issued in all three runs — its absence from `scope` is normal and must not be treated as failure.

Ordering also differs between the two. Any check on this string must be membership-based, never equality or prefix matching.

## `verification_uri` must never be hardcoded

Every run returned:

```
verification_uri          https://login.microsoft.com/device
verification_uri_complete  not present
expires_in                 900
interval                   5
```

This is **not** `https://microsoft.com/devicelogin`, the URL most Microsoft documentation cites. The add-on must display whatever the server returns.

`verification_uri_complete` is absent, confirming that a QR code can only carry the plain verification URI and never the user code. The sign-in dialog must therefore be designed around a large, legible code, with the QR as a secondary convenience.

## Token lifetimes are randomised

Observed `expires_in`: 3655, 4491, 3599 seconds. Entra deliberately varies access token lifetime, so expiry must be computed from the returned value per token. Never assume 3600.

## Real fixture material found

Both drives contain names that a synthetic ASCII test set would never produce, and they are exactly the class of input BROWSE-05 targets.

Business drive root: `Ảnh`, `Anh_code77`, `Đính kèm`, `DU LIEU O DIA D`, `Fix-E5`
Personal drive root: `ASUZAC`, `Desktop`, `Đính kèm`, `Email attachments`, `Favorites`, `Kho lưu trữ cá nhân`, `Mahou Sensei Negima`, `Microsoft Teams Chat Files`

Two things worth recording as fixtures:

- Vietnamese diacritics combined with spaces, on both a business and a personal drive. The reserved-character rules differ between the two classes, so both must be captured.
- `Kho lưu trữ cá nhân` — the OneDrive Personal Vault — is returned **without a `folder` facet**, so naive folder detection classifies it as a file. Any `extract_item()` fixture set that omits this will pass while the real drive misrenders.

## What remains unverified

- Behaviour against a tenant that actually blocks third-party apps or enforces Conditional Access on device code flow. The E5 tenant permits it, so the exact `AADSTS` code that triggers the custom `client_id` escape hatch is still unknown, and AUTH-18 cannot be fully verified yet.
- Whether the E5 Developer tenant hosting this registration survives long term. If it lapses, the embedded `client_id` dies for every installed copy at once. Registering under a personal Microsoft account would avoid this.
- Refresh token rotation behaviour over time, including the 90-day inactivity expiry. Not observable in a single session.

---
*Spike completed: 2026-08-22*
