# OneDrive Kodi Add-on — Refactor

## What This Is

A Kodi add-on (`plugin.onedrive`) that lets you browse and play video, music, and photos stored in OneDrive directly from Kodi. This project refactors the existing v2.3.0 add-on — which no longer signs in because its default OAuth broker is a dead Heroku app — into a self-contained, self-hosted-free add-on that works on modern Kodi (20/21/22) across Windows and Android TV.

Primarily a personal-use project, but built so anyone can install it without touching Azure, running a server, or copy-pasting tokens.

## Core Value

**Sign in from the couch with a remote, and play a file from OneDrive.** Everything else is secondary — if authentication and playback work reliably on Android TV, the project succeeded.

## Requirements

### Validated

<!-- Inferred from the existing codebase — these already work when auth is available. -->

- ✓ Kodi plugin + service dual entry point (`entrypoint.py`, `service.py`) — existing
- ✓ Microsoft Graph → Kodi item mapping for video, audio, image (`_extract_item`) — existing
- ✓ Folder browsing with `@odata.nextLink` pagination — existing
- ✓ Full-text search across a drive via Graph `search(q=...)` — existing
- ✓ Automatic subtitle discovery for played video — existing
- ✓ Drive enumeration for personal, business, and SharePoint document libraries — existing
- ✓ Delta-based change sync via `@odata.deltaLink` change tokens — existing
- ✓ STRM library export, slideshow, local HTTP directory listing, download service (via `clouddrive.common`) — existing
- ✓ Kodi add-on settings surface (cache, resume, subtitles, export) — existing

### Active

**Authentication (the blocker)**

- [ ] Replace the third-party sign-in broker with in-add-on OAuth — no external server holds tokens
- [ ] Device code flow as the primary login: show a code on the TV, user authorizes on their phone
- [ ] Ship a maintainer-registered public `client_id` so users need zero Azure setup
- [ ] Advanced setting (hidden, empty by default) for a custom `client_id`, for tenants that block third-party apps
- [ ] Secure token storage and automatic refresh, with clear failure messaging when refresh is rejected
- [ ] Document the one-time Azure AD app registration steps for the maintainer

**Self-sufficiency**

- [ ] Vendor `script.module.clouddrive.common` into this repo so the add-on has no unmaintained external dependency
- [ ] Trim the vendored module to what this add-on actually uses
- [ ] Remove the dependency on the external `sign-in-server` setting entirely

**Modern Kodi compatibility**

- [ ] Run on Kodi 20 Nexus, 21 Omega, and 22 Piers
- [ ] Migrate to typed InfoTag setters (Kodi 20+ requirement)
- [ ] Migrate `resources/settings.xml` to the Kodi 19+ `version="1"` settings schema
- [ ] Drop Kodi 19 / Krypton-era compatibility shims

**Core path correctness**

- [ ] Fix `_extra_parameters` class-level mutation that corrupts folder listings after any search
- [ ] Fix `items.extend(None)` crash when a paginated listing is cancelled
- [ ] Return `[]` instead of `None` from `get_folder_items()` / `search()` on cancellation
- [ ] Percent-encode path segments in Graph URLs so names with `#`, `?`, `%`, `+`, `:` work
- [ ] Escape single quotes in OData search literals
- [ ] Pass integer durations to Kodi, not floats
- [ ] Guard direct dictionary access on Graph responses
- [ ] Convert recursive pagination to an iterative loop (removes the recursion-depth ceiling)
- [ ] Explicit `import urllib.parse`

**Confidence**

- [ ] Unit tests for the pure parsing logic (`_extract_item`, pagination, path building) against recorded Graph JSON
- [ ] CI running tests plus `kodi-addon-checker`
- [ ] Manual acceptance pass on Windows and Android TV for every phase

**Distribution**

- [ ] Buildable installable zip for fast local testing
- [ ] Self-hosted GitHub Kodi repository so Android TV updates arrive automatically after a single one-time URL entry

**Restored features (after core works)**

- [ ] STRM library export
- [ ] Slideshow
- [ ] Local HTTP directory listing (default off unless verified loopback-bound and authenticated)
- [ ] Background download service
- [ ] Resume / watched-state sync

### Out of Scope

- **Kodi 19 Matrix support** — dropping it removes the legacy settings schema and untyped InfoTag paths; the effort is better spent on versions people run.
- **Self-hosting or maintaining an OAuth broker server** — the whole point of the auth rewrite is that no server is needed.
- **Requiring users to register their own Azure app** — a remote-and-TV audience cannot do this; the embedded `client_id` exists precisely to avoid it.
- **Submitting to the official Kodi repository** — its review process adds constraints that a personal project does not need. Revisit if the add-on gets an audience.
- **SharePoint document libraries as a first-class target** — existing code paths stay, but Personal and Business are what get tested and supported.
- **Loopback / browser-redirect login flow** — device code covers both TV and desktop with one implementation; a second flow doubles the auth surface for marginal gain.
- **New features beyond v2.3.0 parity** — this is a refactor. Restore what exists, then stop.
- **Additional localizations** — English is enough for now; the existing `en_gb` and `he_il` files stay as-is.

## Context

**Current state of the codebase** (mapped 2026-08-22, see `.planning/codebase/`):

- ~300 lines of provider glue in this repo: `resources/lib/addon.py`, `resources/lib/provider/onedrive.py`, plus two thin entry points. Nearly all real behavior — HTTP, OAuth, account management, caching, UI base classes, background services — lives in `script.module.clouddrive.common` 1.4.0, an external Kodi module not in this repo.
- The upstream family of add-ons appears unmaintained; the newest upstream commit is dated 2023-01-21. `<import version="1.4.0">` in Kodi is a *minimum*, not a pin, so a future 2.x of the common module would silently satisfy it and break at runtime.
- `addon.xml` declares `xbmc.python` 3.0.0 (Kodi 19 Matrix). Kodi 21/22 behavior is unverified and no CI proves anything.
- The default `sign-in-server` is `https://drive-login.herokuapp.com`. Heroku terminated free dynos in November 2022, so this hostname is dead — and possibly re-registrable by a third party, which would hand OAuth traffic from every default install to a stranger. Note that existing installs have the old value *stored*, so changing the default alone would not fix them; the auth rewrite removes the setting entirely instead.
- `resources/settings.xml` still uses the pre-Kodi-19 `<settings><category>` schema and relies on Krypton-era `window(home).property(iskrypton)` visibility hacks.
- There are no tests, no CI, and no `.github/workflows/`. The response-parsing code is pure and highly testable, and every known bug listed in `.planning/codebase/CONCERNS.md` would have been caught by a handful of unit tests.
- `allow_directory_listing` defaults to `true` on port 8586, binding an HTTP listener that serves drive content. Whether it binds to loopback and requires a token is implemented in the external module and unverified.

**Why device code flow:** the add-on's primary target is a TV with a remote. Typing a URL, a username, and a password with a D-pad is painful; reading an 8-character code off the screen and entering it on a phone is not. Device code is also a public-client flow, so it needs no client secret — which is exactly what makes shipping an embedded `client_id` safe, and what makes the broker unnecessary.

**Why vendor the common module:** the PKCE/device-code rewrite has to replace the module's OAuth layer anyway, and the module is unmaintained upstream with an unpinnable version constraint. Owning the code removes both problems at once.

## Constraints

- **Compatibility**: Must run on Kodi 20 Nexus, 21 Omega, and 22 Piers — Kodi 19 is explicitly dropped. Typed InfoTag setters and the `version="1"` settings schema are non-negotiable consequences.
- **Platform**: Windows and Android / Android TV are the tested platforms. Linux is not verified.
- **Interaction**: Android TV with only a remote is a first-class constraint. Any flow requiring extended text entry, deep file-manager navigation, or repeated manual steps per update is a design failure — this is why the self-hosted repo matters more than the zip.
- **Accounts**: OneDrive Personal and OneDrive for Business. Some Business tenants block third-party apps pending admin consent; the add-on cannot work around this, so a custom-`client_id` escape hatch is required.
- **Dependencies**: No external OAuth broker, and after vendoring, no dependency on `script.module.clouddrive.common` from the Kodi repository.
- **Security**: OAuth tokens stay on the device. No third party sees authorization codes or refresh tokens.
- **Testing**: Kodi behavior cannot be fully unit-tested. Automated tests cover pure logic; every phase also carries a manual acceptance pass on real Windows and Android TV installs.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Device code flow for OAuth | Only flow that is genuinely usable on a TV with a remote; needs no redirect URI, no local HTTP server, and no client secret | — Pending |
| Embed a maintainer-registered public `client_id` | Public-client flows carry no secret, so embedding is safe and standard (rclone and others do the same). Gives users zero-config sign-in — strictly less work than the broker they have today | — Pending |
| Advanced setting for a custom `client_id` | Some Business tenants block third-party apps; unavoidable from the add-on's side, so provide an escape hatch that 99% of users never open | — Pending |
| Vendor `script.module.clouddrive.common` into the repo | Upstream is unmaintained, the version constraint is unpinnable, and the auth rewrite replaces its OAuth layer anyway. Owning it removes the dependency risk and unblocks the rewrite | — Pending |
| Drop Kodi 19 support | Keeping it forces the legacy settings schema and untyped InfoTag paths; Kodi 20+ is what the target platforms run | — Pending |
| Delete the `sign-in-server` setting rather than repoint it | Existing installs keep the stored dead value, so a new default fixes nothing. In-add-on auth makes the setting meaningless | — Pending |
| Core-first scoping (auth → browse → play → subtitles) | Auth is the blocker; nothing else is verifiable until it works. Export, slideshow, HTTP listing, and download service return afterward | — Pending |
| Self-hosted GitHub Kodi repository for distribution | One-time URL entry on the remote, then automatic updates forever — versus re-navigating a file manager for every zip update | — Pending |
| Skip the official Kodi repository | Its review constraints buy nothing for a primarily personal project | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-22 after initialization*
