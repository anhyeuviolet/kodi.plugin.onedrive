# The Azure app registration

This is a recovery procedure, not a tutorial. Everything else this add-on needs is in the
repository; the app registration is not. It lives in one Microsoft Entra tenant, it was made by
hand, and nothing in this tree can recreate it. If it disappears, the add-on stops signing anyone
in — including on the television it was built for. This document exists so that outage is a
forty-minute job instead of an archaeology project.

Read section 4 before you touch anything, even if you are in a hurry. It is the one mistake that is
easy to make, looks like it worked, and publishes a credential in a GPL-licensed tree.

---

## 1. What this is, and why the identifier is public

The add-on signs in with the OAuth 2.0 device authorization grant (RFC 8628). That grant is for
**public clients**: programs that run on somebody else's machine and therefore cannot keep a secret.
Every installed copy of this add-on has the same application identifier in it, because there is
nowhere to hide it and nothing to hide.

So the GUID committed in `resources/lib/auth/device_code.py` is not a leaked credential. It is the
public name of the application, the same way a domain name is public. It identifies *which program*
is asking; it proves nothing and authorises nothing. The thing that authorises is the token the user
gets after signing in on their own phone, and that never touches this repository.

The registration has **no client secret and no certificate**, and that is a property of the design
rather than an oversight. Section 9 lists what is deliberately absent and why adding any of it would
break the grant.

---

## 2. The current registration

Exact values, as read back from the application manifest. Anything recreated has to match this
table.

| Field | Value |
|---|---|
| `appId` | `efe197b3-5c14-4d67-810f-e10406742a06` |
| `displayName` | Kodi OneDrive Add-on |
| `publisherDomain` | `e5.nguyentiendat.net` (a Microsoft 365 E5 Developer tenant) |
| `signInAudience` | `AzureADandPersonalMicrosoftAccount` |
| `requestedAccessTokenVersion` | `2` |
| `isFallbackPublicClient` | `true` — the manifest name for "Allow public client flows" |
| `passwordCredentials` | empty — no secret |
| `keyCredentials` | empty — no certificate |
| redirect URIs | none, in `publicClient`, `web` and `spa` alike |
| `verifiedPublisher` | null |

Requested scope string, which lives in the same module as the identifier:

```
https://graph.microsoft.com/Files.Read offline_access openid profile
```

`verifiedPublisher` being null means the consent screen shows an **unverified publisher** warning.
That is expected and is not worth fixing: publisher verification requires an MPN account, and the
warning costs one extra sentence of explanation to the only person who sees it.

---

## 3. Recreating it

Entra portal → **App registrations** → **New registration**.

1. **Choose "Supported account types" first, before anything else on the page.**
   Pick *Accounts in any organizational directory (Any Microsoft Entra ID tenant — Multitenant) and
   personal Microsoft accounts*, which is `signInAudience: AzureADandPersonalMicrosoftAccount`.

   This is first because it is the one field the portal will not let you change afterwards. Once the
   registration exists, the "Supported account types" radio for this value is disabled in the UI and
   the only way back is the manifest editor. Getting it wrong is also the failure that hides the
   longest: whichever account class you happen to test with keeps working, and the other one fails
   for somebody else weeks later with `AADSTS50194` or `AADSTS700016`.

2. **Name it** `Kodi OneDrive Add-on`. The name is cosmetic except that it is what the user sees on
   the consent screen, so it should read like something a person would install.

3. **Leave the redirect URI blank.** The device code grant has no redirect. Adding one is harmless
   but it invites the next reader to think there is a browser flow here.

4. Register. Copy the **Application (client) ID** from the overview page — that is the GUID that
   goes into the source constant in section 7.

5. **Turn on "Allow public client flows".**
   Authentication → scroll to **Advanced settings** → *Allow public client flows* → **Yes** → Save.

   This defaults to **off**, and it is not where you would look for it: it sits below the platform
   configuration panels, visually separated from them, and nothing in the device-code request hints
   that it exists. Skipping it produces the error in section 4 and nothing else — the device code is
   issued normally and the failure only appears at the token step.

6. **Set the access token version to 2** if it is not already. Manifest editor →
   `"requestedAccessTokenVersion": 2`. Version 1 tokens are issued against a different audience and
   the `openid`/`profile` claims the add-on reads for the account label will not be where it expects
   them.

7. **Add no API permissions.** See section 9 — the delegated permissions in the scope string are
   consented dynamically at sign-in.

---

## 4. If you see `AADSTS7000218`

The token request comes back with:

```
AADSTS7000218: The request body must contain the following parameter: 'client_assertion' or 'client_secret'.
```

**Do not fix this by adding a client secret.** The error is misleading: it is the generic
confidential-client message, and it is what Entra says when a *public* client asks for a token and
the registration has not been marked as one. The cause is step 5 above — "Allow public client
flows" is off. Turn it on and the same request succeeds unchanged.

Teams have shipped a secret to make this error go away. Two things happen when you do. The
application becomes confidential, which the device code grant does not support at all, so the flow
stays broken. And the secret is now in a GPL-licensed source tree that anybody can read, which means
it has to be rotated in the portal and scrubbed from the git history of every clone.

The symptom is unambiguous once you know it: it fires immediately, on the first token poll, with a
`device_code` that was issued normally, and it never happens intermittently.

If this reaches a *user* rather than you, they set a custom identifier of their own (section 7) and
left the switch off on their own registration. The add-on's error message is aimed at that person.

---

## 5. Verify by reading the manifest back

Verify through the Graph API, not by looking at the portal. The portal renders some of these fields
under names that do not match the manifest and hides others behind panels, so "it looks right on the
screen" is not the same claim as "the manifest says so". Every value in section 2's table was
established this way.

Sign in with an account that can read applications in the tenant (`Application.Read.All`), then:

```http
GET https://graph.microsoft.com/v1.0/applications?$filter=appId eq 'efe197b3-5c14-4d67-810f-e10406742a06'&$select=id,appId,displayName,publisherDomain,signInAudience,isFallbackPublicClient,publicClient,web,spa,passwordCredentials,keyCredentials,api,verifiedPublisher
Authorization: Bearer <token>
```

Graph Explorer is the least ceremonious way to send it. Check, in the single object that comes back:

- `signInAudience` is `AzureADandPersonalMicrosoftAccount`
- `isFallbackPublicClient` is `true`
- `api.requestedAccessTokenVersion` is `2`
- `passwordCredentials` and `keyCredentials` are both `[]`
- `publicClient.redirectUris`, `web.redirectUris` and `spa.redirectUris` are all `[]`

An empty `value` array means the filter matched nothing: either the identifier is wrong or you are
signed in to the wrong tenant.

---

## 6. The acceptance check

The registration is not proven by its manifest. It is proven by a sign-in.

```
python .planning/research/verify_device_code.py --client-id efe197b3-5c14-4d67-810f-e10406742a06
```

Use a **work or school** account. Follow the code it prints, and confirm that STEP 3 reports
`refresh_token: YES`. A missing refresh token means `offline_access` did not survive, and an add-on
that cannot refresh signs the user out again a few hours later.

Run it a second time with a **personal** Microsoft account. That second run is the whole point of
`signInAudience` in step 1, and it is the half that a maintainer testing with their own account
never covers by accident.

### What the acceptance check cannot tell you

**A tenant that blocks device code flow is not reproducible here, and the requirement covering it is
recorded as unverified.** Conditional Access can refuse this grant outright, and the add-on has an
error message and a custom-identifier escape hatch for exactly that case — but the tenant hosting
this registration *permits* device code flow, so the blocking response cannot be produced on demand
and the handling has never been observed against a real refusal. This is written down rather than
claimed as passing. If you ever do get a tenant that blocks, capture the failing response body
before you do anything else; it is the only chance to see it.

---

## 7. Swapping the identifier

There is exactly one source of the identifier:

- `CLIENT_ID` in `resources/lib/auth/device_code.py`

Change it there and nowhere else. If a second copy ever appears, the two will disagree eventually
and the failure will look like an intermittent sign-in bug.

Users get their own escape hatch through the **custom application identifier** setting, which lives
at Expert level in the add-on settings and is empty by default. It exists for the person whose
tenant refuses this registration: they register their own application by following section 3, paste
its GUID into that setting, and sign in against their own tenant's policy. Empty means "use the
built-in one", which is what almost everybody will do.

**The authority is deliberately not user-configurable.** It is a single constant pointing at
`/common`, which serves work/school and personal accounts alike — measured, three live runs, two
account classes. Exposing it as a setting would let somebody pick `consumers` or `organizations` and
break the account class they do not personally use, and there is no reading of that setting that
helps anyone.

---

## 8. If the tenant lapses

The registration lives on a Microsoft 365 E5 Developer tenant, which **renews on activity**. If it
expires, the registration goes with it.

Symptoms, from every installed copy at the same moment:

- `AADSTS700016` — the application wasn't found in the directory/tenant
- `AADSTS90002` — invalid tenant name

There is no gradual failure and no affected subset. The identifier is embedded in every copy, so
every copy fails on the same day, including the one on the maintainer's own television. Nobody will
have changed anything, which is what makes this worth writing down: the first instinct will be to
look for a regression that is not there.

The fix is to recreate the registration (section 3), put the new GUID in the constant (section 7)
and ship an update. Every user has to sign in again — refresh tokens are bound to the application
they were issued to and cannot be carried across.

**The way to not need the fix: register under a personal Microsoft account instead.** A registration
in the shared consumer directory has no tenant to expire and no activity requirement. It is the
right long-term home for this identifier, and the only reason it is not there yet is that the
developer tenant was what existed when the flow was first proven. Moving is a one-time cost of one
forced re-sign-in for everyone, paid once, instead of an outage of unpredictable timing.

---

## 9. What this registration deliberately does not have

- **No client secret.** The grant does not support one. See section 4.
- **No certificate.** Same reason.
- **No redirect URI.** There is no browser redirect in a device code flow; the user's browser talks
  to Microsoft and the add-on polls the token endpoint independently.
- **No pre-declared API permissions.** The delegated permissions in the scope string
  (`Files.Read`, `offline_access`, `openid`, `profile`) are requested at sign-in and consented then;
  the v2.0 endpoint does not require them on the registration, and the sign-in was proven end to end
  with none declared.

One reason you might add them anyway: declaring the delegated permissions on the registration is
what makes an admin-consent URL usable. If a tenant blocks the add-on and its administrator is
willing to grant consent centrally, that URL is the mechanism — and it needs the permissions to be
declared first. That is the only case where adding them buys anything.
