# Phase 1: Vendor Lift — Research

**Researched:** 2026-08-22
**Domain:** Kodi add-on packaging, Python source vendoring and package renaming, add-on identity change, Kodi ABI version gating
**Confidence:** HIGH

Every claim about the upstream module in this document was produced by cloning
`cguZZman/script.module.clouddrive.common` branch `matrix` at commit
`df68e9a589a6faef2b3228f7520e77729bc05d9b` and reading the source. Every claim about Kodi
behaviour was read from `xbmc/xbmc` at a named branch. Claims are tagged
`[VERIFIED: <how>]`, `[CITED: <url>]` or `[ASSUMED]`.

---

## Summary

Phase 1 is mechanically simple and has a long, exact definition of done. The upstream module
is 39 tracked files and roughly 230 KB, of which 21 are Python. Nothing in it uses relative
imports, and every internal reference is the literal dotted prefix `clouddrive.common`, so the
package rename is a single anchored substitution across 106 import lines in the module plus 10
in this repo. The one dynamic import mechanism in the tree (`Utils.get_class`, a string→class
loader built on `__import__`) has **no callers anywhere** and should be deleted rather than
ported, which removes the only construct that could make a future rename silently wrong.

The real work is not the copy. It is four de-coupling jobs the copy exposes:

1. **Six hardcoded `script.module.clouddrive.common` id lookups** resolve through
   `xbmcaddon.Addon(id)` and raise `RuntimeError: Unknown addon id` once the module is
   uninstalled. Five of the six funnel through two assignments, so the code fix is small; the
   danger is that they keep working on any machine where a sibling cloud-drive add-on is
   installed, so the fix is only *provable* on a clean profile.
2. **The two string-id spaces collide completely.** All 26 of this add-on's `msgctxt` ids are
   also used by the module, and 22 of the 26 mean different things. `32032` is "Advanced" here
   and "Auto-Refreshed slideshow" there — and `resources/lib/addon.py:43` asks the module for
   `32032`. A naive merge of the two `strings.po` files silently mislabels most of the UI. This
   is not mentioned anywhere in the project research and is the largest single landmine in the
   phase.
3. **Two transitive Kodi-repo dependencies** (`script.module.pyqrcode`,
   `script.module.dateutil`) must go, because Success Criterion 1 permits no `<import>` other
   than `xbmc.python`. `dateutil` is one call and is replaceable with the stdlib. `pyqrcode` is
   *not* optional: it renders the QR image on the sign-in dialog named in Success Criterion 3,
   and it must be vendored (4 files, 66 KB, BSD-3-Clause plus an embedded MIT `png.py`).
4. **The identity change is mostly automatic and has exactly two hardcoded traps.** The module
   builds every `plugin://` URL from `sys.argv[0]` and `getAddonInfo('id')`, so it follows the
   new id for free. The two literal `plugin://plugin.onedrive/` strings in this repo's
   `resources/settings.xml` do not — and they are the dangerous kind of wrong, because if the
   original add-on is installed they keep working while driving the *other* add-on.

**Primary recommendation:** land the identity change first and alone (it is ~10 lines and makes
every later commit write to a clean, uncontaminated profile), then the verbatim vendor copy plus
anchored rename, then the de-hardcoding pass, then hardening and the record. Verify with a
`pytest` gate file that runs in under two seconds and that Phase 2 inherits wholesale into CI.

---

## Locked Positions Inherited by This Phase

No `CONTEXT.md` was captured for this phase. The constraints below come from `PROJECT.md` Key
Decisions, `STATE.md` Accumulated Context, and `.planning/research/SUMMARY.md` — the last two of
which record these as decided, not as options. Treat them as this phase's locked decisions.

### Locked

- Ships as `plugin.onedrive.kn` — a separate add-on, own profile, **no migration from v2.3.0**.
- Vendor from the **`matrix` branch, v1.4.0**. Not `krypton`/`master` (1.3.9, the Python 2 line).
- **Vendoring lands first and alone**, so a regression can be attributed.
- Declare `<import addon="xbmc.python" version="3.0.1"/>`.
- `SourceService` and the directory listing are **deleted, not defaulted off** — but the
  deletion is scheduled for **Phase 7**, not this phase.
- Third-party error reporting (`report_error`, `errorreport.py`) is deleted — **Phase 7**.
- `sign-in-server` and all broker code are deleted — **Phase 3**.
- Typed InfoTag setters are deferred behind auth and playback — **Phase 7**.
- Additional localizations are out of scope; `en_gb` and `he_il` stay.

### At this phase's discretion

- The vendored package name and its location in the tree (see Decision D1).
- How the two string-id spaces are reconciled (see Decision D2).
- Whether `pyqrcode` is vendored, replaced, or its call site guarded (see Decision D3).
- The internal ordering of the four plans.

### Out of scope for Phase 1

Anything that rewrites behaviour. The vendor commit's contract is "identical behaviour, modulo
the already-dead broker". Deleting `SourceService`, `errorreport`, `signin`, `html.py` or the
export subsystem belongs to Phases 3 and 7, not here — with the single exception noted under
Pitfall 8, which needs an explicit decision.

---

## Phase Requirements

| ID | Description | Research support |
|----|-------------|------------------|
| VND-01 | Vendor v1.4.0 from `matrix`, not the Python 2 line | Upstream Tree, Fact V1–V3 |
| VND-02 | Rename the vendored package under this add-on's namespace | Decision D1; Rename Mechanics |
| VND-03 | Merge the module's `resources/` into this add-on's, not a second top-level package | Resource Merge Map; Decision D2 |
| VND-04 | Every hardcoded module-id lookup resolves to this add-on | Hardcoded Id Sites (8 sites, verified) |
| VND-05 | Account store uses JSON, not `repr()`/`eval()` | `eval(` Inventory (3 sites, verified) |
| VND-06 | Every outbound HTTP call passes explicit `timeout=` | HTTP Call Inventory (1 site, verified) |
| VND-07 | Module's own `xbmc.service` folded in, decision recorded | Fact V6 — the answer is "nothing survives" |
| VND-08 | Skin XML and media copied; dialog path arguments updated | Skin Resolution; 3 construction sites |
| VND-09 | `VENDORED.md` with URL, branch, version, SHA, per-subtree licence | Licence Audit; SHA resolved |
| VND-10 | Identical behaviour on a clean profile, every dialog opens | Verification Tooling; Pitfall 6 |
| VND-11 | External `<import>` removed from `addon.xml` | Dependency Elimination (3 imports, not 1) |
| ID-01 | Id becomes `plugin.onedrive.kn`; every reference follows | Identity Change Map (8 sites) |
| ID-02 | `provider-name` names the maintainer; display name distinguishes | Identity Change Map |
| ID-03 | `LICENSE.txt` retained unchanged; copyright notices preserved | Licence Audit — module LICENSE.txt is byte-identical |
| ID-04 | `CREDITS.md` names the origin and the bundled module | Licence Audit |
| ID-05 | Repo detached from the upstream fork network, history preserved | Identity Change Map — manual, `gh` unavailable |
| KODI-01 | `xbmc.python` 3.0.1 installs on 20/21/22, rejected by 19 | Kodi Version Gating — proven from Kodi source |
| KODI-02 | Installs and runs on Kodi 20, 21, 22 | Kodi Version Gating; Environment Availability |
| SETUP-06 | Clean profile, no sibling cloud-drive add-ons; real Android TV box | Environment Availability — Windows half already satisfied |
| CI-06 | Manual acceptance on Windows and real Android TV, per phase | Validation Architecture — Manual Acceptance Matrix |

---

## Architectural Responsibility Map

| Capability | Primary tier | Secondary tier | Rationale |
|------------|-------------|----------------|-----------|
| Add-on identity, ABI floor, extension points | Kodi manifest (`addon.xml`) | — | Kodi reads it before any Python runs; nothing else can gate installation |
| Plugin/service process bootstrap | Entry scripts (`entrypoint.py`, `service.py`) | — | Kodi invokes these by path; they must stay at the repo root |
| Vendored framework (UI base, HTTP, account store, services) | `resources/lib/vendor/…` | — | Quarantine: code that exists to be deleted, reached only through the add-on's own package path |
| OneDrive semantics | `resources/lib/provider/` | vendored `remote/provider.py` | Unchanged in this phase; the import prefix is the only edit |
| Localized strings | `resources/language/` | — | One `.po` per locale per add-on; Kodi resolves ids against the owning add-on only |
| Skin XML and media for `WindowXMLDialog` | `resources/skins/default/` | — | Kodi resolves `scriptPath/resources/skins/…`; the path argument is the coupling |
| User settings | `resources/settings.xml` | — | Kodi keys stored values by add-on id; a new id means a fresh, empty store |
| QR rendering for the sign-in dialog | vendored `pyqrcode` | — | Pure-Python; belongs beside the code that calls it, not as an external add-on |

---

## Upstream Tree — What Actually Gets Vendored

`[VERIFIED: git clone + git ls-files at df68e9a]`

**Upstream:** `https://github.com/cguZZman/script.module.clouddrive.common`
**Branch:** `matrix` · **Version:** 1.4.0 · **Commit:** `df68e9a589a6faef2b3228f7520e77729bc05d9b`
**Commit date:** 2023-01-21 · **Subject:** `Kodi 20 fix` · **Licence:** GPL-3.0-or-later

The SHA is resolved. Record it verbatim in `VENDORED.md`; do not re-resolve it at execution
time, because the branch tip can move.

### Corrections to prior assumptions

| Fact | Prior assumption | Verified reality | Consequence |
|------|------------------|------------------|-------------|
| V1 | "The default branch `master` is 1.3.9" | `git ls-remote` shows only `refs/heads/krypton` and `refs/heads/matrix`; `HEAD` → `matrix`. `krypton` is the 1.3.9 / `xbmc.python 2.25.0` line. `raw.githubusercontent.com/…/master/…` still serves 1.3.9 content for a ref that no longer exists as a branch. | Cloning the default branch today gets the *right* code — but do not rely on that. Clone `--branch matrix` and pin `df68e9a`. |
| V2 | Module `addon.xml` declares one transitive dependency | It declares **three** imports: `xbmc.python` 3.0.0, `script.module.dateutil`, `script.module.pyqrcode` | VND-11 is three deletions, not one, and two of them need replacement work |
| V3 | The module's own service does unspecified startup work | Upstream `service.py` is 8 lines and runs exactly `ServiceUtil.run([SourceService(None, SourceRedirector)])` | VND-07 resolves to "nothing survives" — see Fact V6 |
| V4 | `clouddrive/common/cache/` is third-party Apache-2.0 code | `cache.py` carries a **GPL-3.0 header naming Carlos Guzman**. The adjacent `LICENSE` is unmodified Apache-2.0 boilerplate with the `[yyyy] [name of copyright owner]` placeholder never filled in, naming no one. Provenance is genuinely unclear. | Preserve the file verbatim and record the ambiguity honestly in `VENDORED.md`. Do not assert it is third-party code. |
| V5 | `DownloadService` returns a 302 | It sets `code = 307` and `headers['location']` (`service/download.py:24,37`) | Cosmetic here; matters for Phase 6's redirector spec |
| V6 | `SourceService` binds the fixed port 8586 | `BaseServerService` binds `127.0.0.1` port **0** (ephemeral) and stores the result in a runtime-written `<name>.service.port` setting. `SourceService` **overrides** `get_port()` to return `port_directory_listing`, and its `start()` is gated on `allow_directory_listing == 'true'` (`service/source.py:412–416`). `DownloadService` uses the ephemeral base. | Answers the "does it bind where it claims" question flagged for this phase as disclosure-only: **yes, loopback**, on the fixed configured port, on by default. |

### File inventory and Phase 1 disposition

Sizes are bytes from the upstream tree. "Disposition" is what Phase 1 does — later phases delete
further.

| Upstream path | Size | Phase 1 | Note |
|---|---:|---|---|
| `clouddrive/common/ui/addon.py` | 41 463 | copy | The god class. Untouched here except imports, ids, strings |
| `clouddrive/common/service/export.py` | 28 648 | copy | Quarantine |
| `clouddrive/common/service/source.py` | 18 925 | copy | Deleted in Phase 7. See Pitfall 8 |
| `clouddrive/common/ui/dialog.py` | 18 750 | copy + edit | 3 `WindowXMLDialog` sites; the `qr.png` path literal |
| `clouddrive/common/ui/utils.py` | 12 736 | copy + edit | `common_addon_id`; `dateutil`; `KodiUtils.lock` |
| `clouddrive/common/cache/LICENSE` | 11 556 | copy verbatim | Apache-2.0 boilerplate, provenance unclear (V4) |
| `clouddrive/common/remote/request.py` | 9 725 | copy + edit | The single `urlopen` site |
| `clouddrive/common/html.py` | 8 700 | copy | Pairs with `SourceService`; deleted in Phase 7 |
| `clouddrive/common/service/player.py` | 7 632 | copy | Quarantine |
| `clouddrive/common/export.py` | 6 642 | copy | Quarantine |
| `clouddrive/common/service/base.py` | 5 189 | copy | Loopback server base |
| `clouddrive/common/utils.py` | 5 187 | copy + edit | Delete dead `get_class`/`get_fqn` |
| `clouddrive/common/remote/oauth2.py` | 5 136 | copy | Replaced in Phase 3 |
| `clouddrive/common/cache/cache.py` | 5 136 | copy + edit | Third `eval(` site |
| `clouddrive/common/db.py` | 4 803 | copy + edit | `repr()`/`eval()` account store |
| `clouddrive/common/account.py` | 4 385 | copy | `accounts.cfg` legacy path is dead under a new id |
| `clouddrive/common/remote/provider.py` | 3 882 | copy | Base class this repo subclasses |
| `clouddrive/common/service/download.py` | 3 486 | copy | The 307 re-signer; Phase 6 keeps this idea |
| `clouddrive/common/remote/signin.py` | 3 446 | copy + edit | Dead broker. Hardcoded id in User-Agent |
| `clouddrive/common/remote/errorreport.py` | 3 419 | copy + edit | Deleted in Phase 7. Hardcoded id |
| `clouddrive/common/exception.py` | 2 686 | copy | Already consumed by this repo |
| `clouddrive/common/service/utils.py` | 1 640 | copy | Thread launcher |
| `clouddrive/common/ui/logger.py` | 1 628 | copy | |
| `clouddrive/{,common/,common/*/}__init__.py` | 0 | copy | Package markers; all present upstream |
| `resources/skins/default/1080i/pin-dialog.xml` | 3 151 | **merge** | Backs `QRDialogProgress` |
| `resources/skins/default/1080i/export-main-dialog.xml` | 9 646 | **merge** | Backs `ExportMainDialog` |
| `resources/skins/default/1080i/export-schedule-dialog.xml` | 4 229 | **merge** | Backs `ExportScheduleDialog` |
| `resources/skins/default/media/*.png` (7 files) | ~7 600 | **merge** | Textures referenced by the three XMLs |
| `resources/language/resource.language.en_gb/strings.po` | 7 139 | **merge, renumber** | 89 ids — see Decision D2 |
| `resources/language/resource.language.he_il/strings.po` | 8 130 | **merge, renumber** | |
| `resources/language/resource.language.pt_br/strings.po` | 7 941 | **drop** | No `pt_br` in this add-on; localizations are out of scope |
| `resources/settings.xml` | 244 | **drop, fold** | Only 2 settings, both already declared here — see Pitfall 8 |
| `resources/__init__.py` | 0 | **must not be copied** | A second importable top-level `resources` |
| `addon.xml` | 2 052 | drop | This add-on already has one |
| `service.py` | 1 228 | drop, record | Fact V6 — its whole content is out of scope |
| `LICENSE.txt` | 35 821 | drop | **Byte-identical** to this repo's `LICENSE.txt` (verified with `diff`) |
| `icon.png` | 29 372 | drop | This add-on has its own |
| `README.md`, `.project`, `.pydevproject`, `.settings/`, `.gitignore` | — | drop | Upstream IDE and repo metadata |

---

## Decisions Required Before the First File Is Copied

### D1 — The vendored package name

VND-02 requires the rename and the roadmap makes it a prerequisite, because reversing it later
means redoing every import.

**Candidates:**

| Option | Import prefix | Assessment |
|---|---|---|
| Keep `clouddrive/` at the repo root | `clouddrive.common.…` | **Rejected.** Collides with the still-installed `script.module.clouddrive.common` on any machine with a sibling add-on; whichever lands on `sys.path` first wins, and the symptom is "my edits have no effect" |
| `resources/lib/clouddrive/` | `resources.lib.clouddrive.common.…` | Nesting alone removes the collision, but the name reads as first-party code and carries no signal that it is scheduled for deletion |
| `resources/lib/vendor/onedrive_common/` | `resources.lib.vendor.onedrive_common.…` | Renames away from upstream. Obscures provenance, which the GPL attribution and future upstream diffs both want. Also produces the awkward `onedrive_common/common/` unless subtrees are collapsed |
| **`resources/lib/vendor/clouddrive_common/`** | `resources.lib.vendor.clouddrive_common.…` | **Recommended** |

**Recommendation: `resources/lib/vendor/clouddrive_common/`**, with `clouddrive/common/X` mapping
to `vendor/clouddrive_common/X` (the redundant `common/` level collapses).

Rationale:

- The substitution target is the exact literal `clouddrive.common`, which every one of the 116
  import lines uses and nothing else does — so collapsing the two levels costs nothing.
- The name still says what the code is, which serves GPL-3.0 §5(a) ("state changes") and keeps a
  future `diff` against upstream legible.
- `vendor/` marks it as quarantine — code whose success condition is that it shrinks to nothing.
- The top-level name `clouddrive` no longer exists in this add-on, so no sibling add-on can
  shadow it, and `resources.lib.vendor.clouddrive_common` is unreachable from outside this
  add-on's root.
- It sits under `resources/lib/`, which Kodi already places on `sys.path` via the add-on root, so
  **no `sys.path` manipulation is needed or permitted**.

Whichever name is chosen, record it in `VENDORED.md` and treat it as fixed.

### D2 — Reconciling the two string-id spaces

This is the phase's largest hidden risk and the project research does not mention it.

`[VERIFIED: parsed both en_gb strings.po files and compared msgctxt sets]`

- This add-on defines **26** string ids. The module defines **89**.
- **All 26 collide.** 22 of the 26 mean different things.
- Both `resources/settings.xml` labels and `getLocalizedString()` calls resolve against the
  *owning* add-on, which is why the two spaces have coexisted. After vendoring there is one
  add-on, so there is one space.

Worst examples:

| Id | This add-on | The module |
|---|---|---|
| 32000 | Player Service | Exports |
| 32004 | Automatically set subtitles… | Export to .strm files… |
| 32009 | Special: Music | Scan the QR code and sign in. |
| 32012 | Open Cloud Drive Common Settings… | Yes! Count me in |
| **32032** | **Advanced** | **Auto-Refreshed slideshow** |
| 32033 | Sign-in Server | Yes |
| 32035 | Clear cache now | The server is temporary unavailable… |
| 32068 | Allow using OneDrive as a source | Allow cloud drive addons to be used as a… |

`resources/lib/addon.py:43` and `:48` call `self._common_addon.getLocalizedString(32032)` for the
slideshow context-menu label. Merge naively and that context menu reads "Advanced".

**Two directions, and only one of them is safe.**

Renumbering the *module's* 89 ids looks attractive (it is the larger, more "vendored" set) but it
is wrong, because the module resolves some string ids **dynamically**:

`[VERIFIED: source read]`

| Site | Dynamic id source |
|---|---|
| `ui/addon.py:608` | `getLocalizedString(int(Utils.str(uiex)))` — the id is the `UIException` message; raised as `32065`, `32018`, `32021` at `ui/addon.py:227,235,244` |
| `ui/dialog.py:197,221,224` | `KodiUtils.localize(self.schedule['type'], …)` where `type` is `32081` or `32082` (`ExportScheduleDialog._startup_type`, `._daily_type`) — and **that value is persisted** in the exports store |

A mechanical `N → N+k` rewrite cannot see any of these, and the last one would also invalidate
already-persisted data.

**Recommendation: leave all 89 module ids at 32000–32088 untouched, and move this add-on's own 26
ids down by 2000 into the 30000 block** (`32000 → 30000` … `32069 → 30069`).

- Kodi reserves **30000–30999 for plugins and plugin settings**, 32000–32999 for scripts.
  `[CITED: kodi.wiki/view/Language_support, via search summary — verify the exact wording during
  execution]` This add-on is a plugin, so the 30000 block is the conventionally correct home for
  its own strings and the checker will not object.
- The edit surface is small and entirely static: 26 `msgctxt` entries in `en_gb`, 13 in `he_il`,
  every `label="32…"` in this repo's `resources/settings.xml`, and exactly three Python call
  sites (`resources/lib/addon.py:44,49,51` → `30007`, `30008`, `30009`).
- No dynamic site is touched, and no persisted value changes.
- Afterwards `_common_addon` can simply become the same `Addon` object as `_addon`
  (set `KodiUtils.common_addon_id = None`), and all ~70 `_common_addon.getLocalizedString(N)`
  calls in the vendored tree keep working **unmodified** — including the dynamic ones.

Note that four ids (32030, 32031, 32067, 32069) have identical text on both sides; they still get
renumbered on the add-on side for uniformity, and the module's copies become the live ones.

### D3 — `pyqrcode`

`[VERIFIED: downloaded script.module.pyqrcode-1.2.1+matrix.4.zip from mirrors.kodi.tv/addons/omega]`

- `ui/dialog.py:125` does a **function-local** `import pyqrcode` inside `QRDialogProgress.onInit`.
  The dialog constructs and its skin loads without it; only `onInit` raises.
- The Kodi add-on is 4 files (`__init__.py`, `builder.py`, `tables.py`, `png.py`), 66 KB zipped,
  `<platform>all</platform>`, pure Python, `<import addon="xbmc.python" version="3.0.0"/>` only.
- Licences: **BSD-3-Clause**, Copyright (c) 2013 Michael Nooner. The bundled `png.py` is **MIT**,
  Copyright (C) 2006 Johann C. Rocholl and others — i.e. `pypng` vendored inside pyqrcode.
- `pypng` is an optional dependency of PyQRCode upstream and **`script.module.pypng` does not
  exist in the Kodi nexus, omega or piers repositories** (all 404). The Kodi pyqrcode add-on
  works only because it bundles `png.py`. `[VERIFIED: HTTP status probes + zip listing]`

**Recommendation: vendor pyqrcode into `resources/lib/vendor/pyqrcode/`** (from the Kodi add-on
zip, which is the exact code the add-on was tested against), rewrite the one import site to the
vendored path, and record both licences in `VENDORED.md`. Do not guard the import and skip the QR
— Success Criterion 3 names that dialog specifically, and Phase 3 reuses it.

Rejected alternatives: keeping the `<import>` (violates Success Criterion 1); hand-rolling a QR
encoder (out of scope, and a QR encoder is exactly the kind of thing not to hand-roll).

### D4 — `dateutil`

`[VERIFIED: source read + Kodi PYTHON3-VERSION]`

Exactly one site: `ui/utils.py:243–247`, `KodiUtils.to_datetime(s)` → `dateutil.parser.parse(s)`,
with a bare `except: return None`. Called from `ui/addon.py:396` on `last_modified_date`, a Graph
ISO-8601 timestamp, purely to set a Kodi list-item date.

Kodi bundles CPython **3.11.2** (Nexus), **3.11.7** (Omega) and **3.14.6** (master / Piers), so
`datetime.datetime.fromisoformat()` — which gained `Z` and general ISO-8601 support in 3.11 — is
available on every supported target.

**Recommendation:** replace the body with `datetime.datetime.fromisoformat(s)`, normalising a
trailing `Z` defensively and keeping the existing `return None` on failure. One caveat worth a
comment in the code: `fromisoformat` accepts only 3 or 6 fractional-second digits, and Graph
sometimes emits 7 for SharePoint-backed items, so truncate the fraction before parsing rather
than relying on the `except`. `[ASSUMED — the 7-digit case was not observed in this session]`

---

## Rename Mechanics

### The import surface

`[VERIFIED: grep across both trees]`

- **106** import lines in the module tree, **10** in this repo (`resources/lib/addon.py` ×2,
  `resources/lib/provider/onedrive.py` ×3, `service.py` ×5).
- **Zero** relative imports. **Zero** bare `import clouddrive`. Every reference is
  `from clouddrive.common.<subpath> import <names>`, across 20 distinct dotted prefixes.
- **One** dynamic import mechanism exists — `Utils.get_class(fqn)` at `clouddrive/common/utils.py:94`,
  built on `__import__(data[0])` plus `getattr` — together with `Utils.get_fqn(o)` at `:89`.
  **Neither has a single caller anywhere in the module or in this repo.** They are dead code.

### The trap that breaks a naive substitution

The literal add-on id `script.module.clouddrive.common` **contains** the substring
`clouddrive.common`. A blanket `sed s/clouddrive\.common/…/g` rewrites the six hardcoded id
strings into nonsense such as `'script.module.resources.lib.vendor.clouddrive_common'` — which
still parses, still runs, and fails only at `xbmcaddon.Addon(id)` on a clean profile. This is
precisely the failure shape this phase exists to eliminate.

### Procedure

1. Copy the upstream tree verbatim into `resources/lib/vendor/clouddrive_common/`, excluding
   `resources/__init__.py`, `addon.xml`, `service.py`, `icon.png`, `LICENSE.txt`, `README.md`,
   `.project`, `.pydevproject`, `.settings/`, `.gitignore`, and the `pt_br` strings. Merge
   `resources/skins/` and the two remaining `.po` files into this add-on's `resources/`.
   Commit this alone, before any edit.
2. **Replace the add-on-id literals first.** Rewrite every occurrence of the full string
   `script.module.clouddrive.common` (8 in Python, see below) before touching imports.
3. **Then rewrite imports, anchored.** Match `^(\s*)from clouddrive\.common\.` only — not a bare
   substring — and replace with `\1from resources.lib.vendor.clouddrive_common.`. Apply the same
   to the 10 lines in this repo.
4. Delete `Utils.get_class` and `Utils.get_fqn`. Removing the only string-based import path means
   no future rename can be silently incomplete.
5. **Prove it.** Four assertions, all cheap:
   - `grep -rn "clouddrive\.common" -- .` returns **zero** hits outside the new dotted path.
   - `grep -rn "script\.module\.clouddrive\.common" -- .` returns **zero** hits.
   - `python -m compileall -q resources/ entrypoint.py service.py` exits 0 — this catches a sed
     that mangled a line, which grep cannot.
   - `grep -rn "sys\.path\.\(append\|insert\)" -- .` returns zero hits.
6. A development-only assertion is worth one line in `entrypoint.py` during the phase:
   log `resources.lib.vendor.clouddrive_common.__file__` and confirm the path points inside this
   add-on's directory, not into `addons/script.module.clouddrive.common/`.

---

## Hardcoded Id Sites

`[VERIFIED: grep across the upstream tree at df68e9a]`

Eight Python sites, not six. All resolve through `xbmcaddon.Addon(id)` and raise
`RuntimeError: Unknown addon id` once the module is uninstalled.

| Site | Call | Fix |
|---|---|---|
| `ui/utils.py:33` | `common_addon_id = 'script.module.clouddrive.common'` | Set to `None`. `get_addon(None)` → `xbmcaddon.Addon()` → the calling add-on. This one change fixes `get_common_addon()` and `get_common_addon_path()` (`ui/utils.py:44,49`) at once |
| `ui/addon.py:82` | `self._common_addon_id = '…'` | Assign `KodiUtils.common_addon_id` (i.e. `None`); `_common_addon` then aliases `_addon` |
| `service/export.py:40` | `self._common_addon_id = '…'` | Same |
| `ui/dialog.py:126` | `get_addon_info("profile", "script.module.clouddrive.common")` → `qr.png` path | Drop the id argument. **This is the one that lands on the sign-in screen** |
| `remote/errorreport.py:70` | `get_addon_info('version', '…')` | Drop the id argument (the file is deleted in Phase 7 regardless) |
| `remote/signin.py:32` | Builds the User-Agent from the module's version | Use this add-on's own version |
| `ui/addon.py:675` | `get_addon_setting('report_error', self._common_addon_id)` | Follows the `:82` fix |
| `ui/addon.py:676` | `get_addon_setting('report_error_invite', self._common_addon_id)` | Follows the `:82` fix. Note `report_error_invite` is declared in neither `settings.xml`, so it already returns `''` |

Plus one indirect: `ui/addon.py:84` reads `self._common_addon.getAddonInfo('version')`, which
after the fix returns this add-on's version — correct, and it feeds the User-Agent.

**What follows the id change automatically** (no edit needed):

- `plugin://` URL construction — `ui/addon.py:80` takes `self._addon_url = sys.argv[0]`, and
  `service/export.py:482` uses `'plugin://%s/' % self.addonid` where `addonid` comes from
  `getAddonInfo('id')`. Both track the new id.
- The profile path — `ui/addon.py:86` uses `getAddonInfo('profile')`, so `accounts.db`, the
  caches and `qr.png` all land under `special://profile/addon_data/plugin.onedrive.kn/`.
- `Cache(self._addonid, …)` at `ui/addon.py:687–689` and `service/source.py:51–53`.
- `service/base.py:86` server version string.

---

## Identity Change Map

`[VERIFIED: git grep across tracked files]`

Only eight literal occurrences of `plugin.onedrive` exist in this repo.

| File | Line | Current | Action |
|---|---|---|---|
| `addon.xml` | 2 | `id="plugin.onedrive"` | → `plugin.onedrive.kn` (ID-01) |
| `addon.xml` | 2 | `name="OneDrive"` | → a name that is distinguishable in the Kodi UI (ID-02) |
| `addon.xml` | 2 | `provider-name="Carlos Guzman (cguZZman)"` | → the current maintainer (ID-02). The upstream copyright notices stay in every file header (ID-03) |
| `addon.xml` | 2 | `version="2.3.0"` | Decide the new baseline. See note below |
| `addon.xml` | 34–36 | `<source>`, `<forum>`, `<website>` → cguZZman / addons.kodi.tv | Repoint to this repository; drop `<website>` (this add-on is not in the Kodi repo) |
| `addon.xml` | 3–6 | `<import addon="script.module.clouddrive.common" version="1.4.0"/>` | Delete (VND-11) |
| `addon.xml` | 4 | `<import addon="xbmc.python" version="3.0.0"/>` | → `3.0.1` (KODI-01) |
| `addon.xml` | 39–52 | `<disclaimer>` describing the sign-in server and `cguZZman/drive-login` | Leave for now; it becomes factually false only when Phase 3 removes the broker, and it is rewritten there |
| `resources/settings.xml` | 23 | `RunPlugin(plugin://plugin.onedrive/?action=_clear_cache)` | → `plugin.onedrive.kn`. **Silently keeps working while driving the other add-on if it is installed** |
| `resources/settings.xml` | 24 | `RunPlugin(plugin://plugin.onedrive/?action=_open_common_settings)` | Same, and the action itself becomes meaningless once there is no separate common add-on — resolve it here rather than leaving a dead menu entry |
| `resources/language/…/en_gb/strings.po` | 3 | `# Addon id: plugin.onedrive` | Comment only; update for accuracy |
| `resources/language/…/he_il/strings.po` | 3 | same | same |
| `README.md` | — | Describes upstream features including the deleted directory listing | Rewrite; add the attribution required by ID-04 |
| — | — | `CREDITS.md` does not exist | Create (ID-04) |
| `.github/ISSUE_TEMPLATE/` | — | No upstream references (checked) | No action |

**Two things that silently keep working while pointing at the old id** — both must be caught by
grep, not by testing, because on a machine with the original installed they behave correctly:

1. The two `plugin://plugin.onedrive/` literals in `settings.xml`.
2. Any `xbmcaddon.Addon('plugin.onedrive')` lookup — there are none today, but the grep gate
   should forbid the literal `plugin.onedrive` outside an `addon.xml` `<source>`/`<forum>` URL,
   with the pattern anchored so `plugin.onedrive.kn` does not match. Use a negative lookahead:
   `plugin\.onedrive(?!\.kn)`.

**On `version=`:** DIST-01 in `REQUIREMENTS.md` still says the zip is named
`plugin.onedrive-<version>.zip` with a top-level `plugin.onedrive/` directory, which contradicts
ID-01. That is Phase 5's problem, but the version number chosen here determines whether Kodi's
Debian-style comparison ever offers a downgrade later. `[ASSUMED]` A clean `3.0.0` is the obvious
choice — it is above the upstream `2.3.0` in the same namespace family, it carries no pre-release
suffix (DIST-05), and it signals a rewrite. Confirm with the maintainer before the first commit.

**ID-05** requires detaching the repository from the upstream fork network while preserving
history. The remote is `https://github.com/anhyeuviolet/kodi.plugin.onedrive.git`, and local
history has 113 commits. Detaching a fork is a GitHub-side operation (repository settings, or a
support request), not a git operation. `gh` is **not installed** on this machine, so this is a
manual checklist item, not an automatable task. Preserve the history — squashing would destroy
the attribution record while keeping the code.

---

## Kodi Version Gating (KODI-01, KODI-02)

`[VERIFIED: xbmc/xbmc source at named branches]`

| Kodi | Branch | `xbmc.python` version | `<backwards-compatibility abi>` | Bundled CPython |
|---|---|---|---|---|
| 19 Matrix | `Matrix` | 3.0.0 | 3.0.0 | — |
| 20 Nexus | `Nexus` | **3.0.1** | 3.0.0 | 3.11.2 |
| 21 Omega | `Omega` | **3.0.1** | 3.0.0 | 3.11.7 |
| 22 Piers | `master` | **3.0.2** | 3.0.0 | 3.14.6 |

There is no `Piers` branch yet; Kodi 22 is still `master`. `[VERIFIED: HTTP 404 on the Piers ref]`

Kodi's dependency test, `xbmc/addons/addoninfo/AddonInfo.cpp:221`:

```cpp
bool CAddonInfo::MeetsVersion(const CAddonVersion& versionMin, const CAddonVersion& version) const
{
  return !(versionMin > m_version || version < m_minversion);
}
```

With `<import addon="xbmc.python" version="3.0.1"/>`:

| Kodi | `m_version` | `m_minversion` | Result |
|---|---|---|---|
| 19 | 3.0.0 | 3.0.0 | `3.0.1 > 3.0.0` → **refused** |
| 20 | 3.0.1 | 3.0.0 | installs |
| 21 | 3.0.1 | 3.0.0 | installs |
| 22 | 3.0.2 | 3.0.0 | installs |

`3.0.1` grants no new API over `3.0.0`; its only effect is the mechanical Kodi 19 rejection,
which is exactly what KODI-01 asks for.

`kodi-addon-checker` agrees: `kodi_addon_checker/versions.py` `VERSION_ATTRB['xbmc.python']` lists
`nexus`, `omega` and `piers` all as `{'min_compatible': '3.0.0', 'advised': '3.0.1'}`, and
`piers` is a valid branch value in the checker. `[VERIFIED: raw source read]`

**Do not declare `3.0.2`.** It would install only on Kodi 22 and be refused by 20 and 21.

---

## `eval(` Inventory

`[VERIFIED: grep across the upstream tree]` Three sites, not two. There are no `exec(` sites and
no `compile(` sites; `re.compile` at `service/player.py:44` is a false positive for a naive grep,
so anchor the CI pattern on `\beval\s*\(` and `\bexec\s*\(`.

| Site | What it does | Replacement |
|---|---|---|
| `db.py:59` — `SimpleKeyValueDb.get` | `eval(row[0])` on a value written by `_insert` as `repr(value)` (`:91`) | `json.loads` / `json.dumps` |
| `db.py:66` — `SimpleKeyValueDb.getall` | `d[row[0]] = eval(row[1])` | Same |
| `cache/cache.py:66` — `Cache.get` | `eval(row[0])`, written by `_insert`/`setmany` as `repr(value)` | Same |

`SimpleKeyValueDb` has three users: `AccountManager` (`accounts.db`, the store that holds OAuth
refresh tokens) and `ExportManager`'s two databases (`exports`, `export-items`). `Cache` is used
only by `SourceService` and by `ui/addon.py`'s cache-clear action.

**The identity change makes this a clean swap.** Under a new add-on id there is no pre-existing
`accounts.db`, so **no mixed-format read path and no `ast.literal_eval` fallback is needed** — a
genuine simplification the project research (written before the no-migration decision) still
carries. Write JSON, read JSON, and let a malformed row raise.

Two shapes do not survive a `repr` → `json` swap and must be checked rather than assumed:
tuples become lists, and non-string dict keys become strings. Reading the write sites:

- `account.py` stores account dicts of `str`/`list`/`dict` — JSON-safe.
- `export.py:79,97,104,111` already coerces with `list(changes)` — JSON-safe.
- `Cache` stores item dicts produced by `_extract_item`, whose every value is `str`, `int`,
  `float`, `bool`, `dict` or `list`; `last_modified_date` is a string, not a `datetime` —
  JSON-safe. `[VERIFIED: read `resources/lib/provider/onedrive.py:121–170`]`

A three-line round-trip assertion in the store (`json.loads(json.dumps(v)) == v` behind a debug
flag, or a unit test over a representative account dict) is enough to prove it.

---

## HTTP Call Inventory (VND-06)

`[VERIFIED: grep for urlopen, urlretrieve, http.client, HTTPConnection, requests, socket]`

**Exactly one outbound HTTP call site exists in the entire vendored tree:**

`clouddrive/common/remote/request.py:132` — `response = urllib.request.urlopen(req)`, with no
`timeout` argument, inside a `for i in range(self.tries)` retry loop. Python's default is the
global socket timeout, which is `None` — block forever. On marginal Android TV Wi-Fi this is an
unrecoverable hang with a spinner and no way out.

Everything else in the tree is inbound or unrelated:

- `service/base.py:42` — `socket.socket(...).bind(('127.0.0.1', 0))`, an ephemeral-port probe.
- `cache/cache.py:50`, `db.py:46` — `sqlite3.connect(..., timeout=30)`, already bounded.
- `service/source.py:333` — a log string containing the word "timeout".

This repo makes no direct HTTP calls of its own.

**Recommendation:** add `timeout=` as a named constant on the request class rather than a magic
number at the call site, so Phase 4's central HTTP layer inherits one place to tune. A value in
the **15–30 s** range is right for metadata calls. `[ASSUMED — no measurement was made]` Note the
call site is shared with the download path (`request.py:139–151` streams to
`self.download_path` in `DOWNLOAD_CHUNK_SIZE` chunks), and `urlopen`'s `timeout` applies per
socket operation, not to the whole transfer — so a single value is safe for both. Sleeps in the
retry loop go through the injected `self.wait` (`request.py:113`, defaulting to `time.sleep`);
routing that through `Monitor.waitForAbort` is Phase 4's job, not this phase's.

**CI check:** assert that every `urlopen(` occurrence in the tree is followed by `timeout=` within
the same call. A regex over the source is sufficient at this size (one site); a stricter
`ast`-based check that walks `Call` nodes named `urlopen`/`urlretrieve`/`request` and asserts a
`timeout` keyword is only ~20 lines and does not go stale.

---

## Resource Merge Map (VND-03, VND-08)

### Skin XML and media

`[VERIFIED: xbmc/interfaces/legacy/WindowXML.cpp @ Omega, lines 108–137]`

`WindowXMLDialog(xmlFilename, scriptPath, defaultSkin)` resolves:

```
fallbackPath = scriptPath/resources/skins
  try  fallbackPath/<current skin id>/<res>/<xmlFilename>
  else fallbackPath/<defaultSkin>/<res>/<xmlFilename>
  else throw WindowException("XML File for Window is missing")
```

Three construction sites, all passing `KodiUtils.get_common_addon_path()`:

| Site | XML | Reachability |
|---|---|---|
| `ui/dialog.py:119` | `pin-dialog.xml` | `QRDialogProgress.create` — called from `ui/addon.py:200` |
| `ui/dialog.py:182` | `export-schedule-dialog.xml` | `ExportScheduleDialog.create` |
| `ui/dialog.py:266` | `export-main-dialog.xml` | `ExportMainDialog.create` |

Because `get_common_addon_path()` is `get_addon_info("path", KodiUtils.common_addon_id)`
(`ui/utils.py:47–49`), setting `common_addon_id = None` per D2/the id table makes all three
resolve to this add-on's own path — **no edit to the three construction sites is required**,
provided the skin tree is merged to `resources/skins/default/1080i/` and
`resources/skins/default/media/`. That is the whole of VND-08.

Verify the merge by file existence, not by reasoning: assert all three XMLs and all seven PNGs
exist at the expected paths, and that `<texture>` references inside the XMLs
(`black.png`, `dialog-bg.png`, `white.png`, `dialogbutton-fo.png`, `dialogbutton-nofo.png`,
`radio-button-on.png`, `radio-button-off.png`) each resolve to a present file.

### Settings

The module's `resources/settings.xml` declares only `allow_directory_listing` (default `true`)
and `port_directory_listing` (default **8585**). This add-on declares both already, with
`port_directory_listing` defaulting to **8586**. The module's code reads them unqualified
(`service/source.py:413,416`), i.e. against the *calling* add-on — so the module's own file has
never been the live one for this add-on. **Drop it.** There is nothing to merge.

One consequence to note in `VENDORED.md`: `KodiUtils.get_service_port` / `set_service_port`
(`ui/utils.py:189–199`) read and write a setting id `<service>.service.port` that is declared in
no `settings.xml` at all — Kodi will create it at runtime. Under a new add-on id these start
empty and are re-populated on first service start. Nothing to do; just do not be surprised by an
undeclared setting appearing in the new profile's `settings.xml`.

### Strings

Per Decision D2. Verification assertions:

1. No duplicate `msgctxt` within any single `.po` file.
2. The `en_gb` id set is exactly the add-on's renumbered 30000-block ∪ the module's 32000–32088.
3. Every numeric id referenced from Python (`getLocalizedString(N)`, `localize(N, …)`) and from
   `resources/settings.xml` `label="N"` either exists in `en_gb` or is `< 32000` and therefore a
   Kodi core string. Note the three known dynamic sites and hard-code their id sets
   (`{32065, 32018, 32021}` for `UIException`, `{32081, 32082}` for schedule types) into the
   check so the assertion is complete rather than approximately complete.

---

## Dependency Elimination (VND-11)

`addon.xml` must end this phase declaring exactly one `<import>`.

| Removed | Why it is not just a deletion | Resolution |
|---|---|---|
| `script.module.clouddrive.common` 1.4.0 | The whole point of the phase | Vendored |
| `script.module.pyqrcode` | Renders `qr.png` on the sign-in dialog named in Success Criterion 3 | Vendor 4 files (Decision D3) |
| `script.module.dateutil` | One call site, `KodiUtils.to_datetime` | stdlib `fromisoformat` (Decision D4) |

**Assertion:** parse `addon.xml` with `xml.etree` and assert `len(requires/import) == 1` and that
the single entry is `addon="xbmc.python" version="3.0.1"`. Do not grep for this — an XML parse is
both simpler and immune to comment/attribute-order noise.

---

## VND-07 — The Module's Own Service

`[VERIFIED: upstream service.py read in full]`

The module's `addon.xml` declares `<extension point="xbmc.service" library="service.py" start="login" />`,
and the file's entire executable content is:

```python
if __name__ == '__main__':
    ServiceUtil.run([SourceService(None, SourceRedirector)])
```

That is the `SourceRedirector` variant of `SourceService` — the unauthenticated directory-listing
server that this project has already decided to delete outright rather than default off.

**The explicit decision VND-07 requires is therefore: nothing survives.** Record in `VENDORED.md`:
the module's `xbmc.service` extension ran only `SourceService(None, SourceRedirector)`; that
subsystem is out of scope by decision; consequently this add-on's `service.py` gains nothing from
the fold, and the module's `service.py` is not copied. This is a two-sentence entry, but it must
be written down — otherwise a later reader cannot distinguish "considered and discarded" from
"overlooked".

Note that this repo's own `service.py` separately runs `SourceService(OneDrive)` — a different
construction, with a provider — and that instance *does* survive Phase 1 unchanged, because Phase
1 preserves behaviour. It is deleted in Phase 7 along with `KODI-07`.

---

## Licence Audit (VND-09, ID-03, ID-04)

`[VERIFIED: file reads and `diff`]`

| Subtree | Licence | Evidence | Action |
|---|---|---|---|
| This add-on (existing) | GPL-3.0-or-later | `LICENSE.txt`, per-file headers naming Carlos Guzman | Keep `LICENSE.txt` **unchanged** (ID-03) |
| Vendored `clouddrive_common/**` | GPL-3.0-or-later | Per-file headers naming Carlos Guzman; upstream `addon.xml` `<license>` | Keep every header. Add a "Modified <date>" line to each file this phase edits (GPL-3.0 §5(a)) |
| Upstream `LICENSE.txt` | GPL-3.0 text | **Byte-identical to this repo's `LICENSE.txt`** | Do not copy a second one. Note the identity in `VENDORED.md` so a future reader does not think it was lost |
| Vendored `clouddrive_common/cache/LICENSE` | Apache-2.0 boilerplate | Unmodified template; the copyright placeholder at the APPENDIX is never filled; `cache.py` itself carries a GPL-3.0 header by the same author | **Preserve verbatim, in place, beside `cache.py`.** Record in `VENDORED.md` that its provenance is unresolved and that it travels with `cache/` — if `cache/` is dropped in a later phase, this file goes with it |
| Vendored `pyqrcode/**` | BSD-3-Clause, © 2013 Michael Nooner | `LICENSE.md` in the Kodi add-on zip | Copy `LICENSE.md` into the vendored directory |
| Vendored `pyqrcode/png.py` | MIT, © 2006 Johann C. Rocholl et al. | In-file header | The header is the notice; keep it intact |

The project's success criterion says "both the GPL-3.0 and the Apache-2.0 licence files survive".
With the identical-`LICENSE.txt` finding, that resolves to: the existing root `LICENSE.txt`
(GPL-3.0) plus `resources/lib/vendor/clouddrive_common/cache/LICENSE` (Apache-2.0), plus two more
files that criterion did not anticipate — pyqrcode's `LICENSE.md` and the MIT header inside
`png.py`.

**`VENDORED.md`** must record, per VND-09: upstream URL, branch `matrix`, version `1.4.0`, commit
`df68e9a589a6faef2b3228f7520e77729bc05d9b`, the licence of each subtree, the list of files
excluded from the copy and why, and every local modification. Write the modification list as a
table keyed by file, not as prose — it is the document a future upstream diff starts from.

**`CREDITS.md`** (ID-04) must state that this add-on originates from `plugin.onedrive` by Carlos
Guzman (cguZZman), that it bundles `script.module.clouddrive.common` by the same author, and that
it bundles PyQRCode by Michael Nooner and pypng by Johann C. Rocholl — naming each licence.

---

## Common Pitfalls

### Pitfall 1: The blanket substring rename corrupts the add-on-id literals

**What goes wrong:** `script.module.clouddrive.common` contains `clouddrive.common`.
**Why it happens:** The obvious one-liner is a substring replace.
**How to avoid:** Replace the full add-on-id literal first; anchor the import rewrite on
`^\s*from clouddrive\.common\.`.
**Warning signs:** A grep for `script.module` returning strings with `resources.lib.vendor` in the
middle of them.

### Pitfall 2: The string-id merge mislabels the UI

**What goes wrong:** All 26 of this add-on's ids collide with the module's, and 22 mean different
things.
**Why it happens:** The two id spaces have always been separate because they belonged to separate
add-ons; vendoring silently unifies them.
**How to avoid:** Decision D2 — renumber this add-on's 26, never the module's 89, because the
module resolves some ids dynamically and one of those values is persisted.
**Warning signs:** A slideshow context menu labelled "Advanced"; an "Add an account…" row reading
"Auto-Refreshed slideshow".

### Pitfall 3: The hardcoded-id fix appears to work on the maintainer's machine

**What goes wrong:** `xbmcaddon.Addon('script.module.clouddrive.common')` keeps resolving as long
as any sibling cloud-drive add-on is installed, so the eight sites above look fine.
**Why it happens:** Kodi installs the module as a dependency of `plugin.googledrive` and
`plugin.dropbox` too.
**How to avoid:** SETUP-06's clean profile is not optional; it is what makes the test valid. On
this machine the Windows half is already satisfied — see Environment Availability.
**Warning signs:** `RuntimeError: Unknown addon id` reported by users and never reproducible
locally; the QR image failing to render.

### Pitfall 4: A second importable top-level `resources`

**What goes wrong:** The upstream tree ships `resources/__init__.py`, making `resources` an
importable top-level package. Copied as-is next to this add-on's own `resources/`, imports become
ambiguous.
**Why it happens:** "Copy the whole tree" is the instruction.
**How to avoid:** Exclude `resources/__init__.py` explicitly and merge only `skins/` and
`language/`. Never call `sys.path.append`.
**Warning signs:** `ImportError` only on some machines; a Kodi 20.x box behaving differently from
a 21 box — Kodi 20 shipped a `sys.path` ordering regression (xbmc/xbmc#22985) that amplifies every
shadowing bug of this class. `[CITED: github.com/xbmc/xbmc/issues/22985]`

### Pitfall 5: `<import>` deleted before the copy lands

**What goes wrong:** The add-on ends up with neither the external module nor a complete local
copy.
**How to avoid:** One commit that copies verbatim *and* removes the import *and* rewrites the
imports. The add-on must be runnable at every commit boundary in this phase.

### Pitfall 6: "Every dialog opens" cannot be tested by navigating the UI

**What goes wrong:** `QRDialogProgress` is constructed at `ui/addon.py:200`, deep inside the
broker sign-in flow, three lines after `KodiUtils.get_signin_server()` — i.e. behind the dead
Heroku dependency. Success Criterion 3 names that dialog specifically, but no amount of clicking
reaches it.
**How to avoid:** Add a temporary, phase-local plugin action (for example
`plugin://plugin.onedrive.kn/?action=_dialog_smoke`) that constructs and shows each of the three
`WindowXMLDialog` subclasses in turn with dummy arguments, confirming the skin XML resolves, the
textures load, and `qr.png` is written to the *new* profile directory. Delete the action at the
end of the phase, or keep it behind a debug setting. The alternative — asserting the XML files
exist — proves the copy but not the path argument, which is the thing that actually breaks.
**Warning signs:** `WindowException("XML File for Window is missing")` appearing for the first
time in Phase 3, weeks after the vendor commit was signed off.

### Pitfall 7: `py_compile` is the only check that catches a mangled rewrite

**What goes wrong:** A regex rewrite that eats a character produces a file that greps clean and
fails at import.
**How to avoid:** `python -m compileall -q` over the whole tree in the same gate as the greps. It
takes under a second for 21 files.

### Pitfall 8: Phase 1 imports a live, on-by-default loopback listener into a fresh profile

**What goes wrong:** `allow_directory_listing` defaults to `true`, so on first run under the new
add-on id, `SourceService` binds `127.0.0.1:8586` and serves an unauthenticated, enumerable index
of the whole drive. This is a decided Phase 7 deletion, but Phase 1's contract is "identical
behaviour", so the naive reading is that it must be carried live.
**Verified facts, so the decision can be made on evidence rather than inference:**
`BaseServerService._interface = '127.0.0.1'` (`service/base.py:32`); `SourceService.get_port()`
overrides the ephemeral base and returns `port_directory_listing` (`source.py:412`);
`SourceService.start()` is gated on `allow_directory_listing == 'true'` (`source.py:416`); there
is no token or authorisation check anywhere in `service/base.py`.
**The decision the plan must surface:** either (a) carry it live and record it in `VENDORED.md`
as a known liability with a forward reference to KODI-07, or (b) flip that one default attribute
to `false` in this phase and record the behaviour delta alongside the already-declared "modulo
the dead broker" exception. Option (b) is a one-attribute change to a feature whose own upstream
documents it as not working, and the new add-on id means no user has a stored `true` to override
it. `[ASSUMED — needs maintainer confirmation, because it is a deliberate deviation from
"identical behaviour"]`

### Pitfall 9: The `_open_common_settings` action outlives the thing it opened

**What goes wrong:** `resources/settings.xml:24` offers "Open Cloud Drive Common Settings…",
routed through `RunPlugin(plugin://plugin.onedrive/?action=_open_common_settings)`. After
vendoring there is no separate common add-on, so the entry either errors or opens this add-on's
own settings recursively.
**How to avoid:** Decide it here — remove the setting row (and its string), or repoint it. Leaving
it is a visible dead end on the settings screen, which the phase's acceptance pass will find but
only if someone opens Settings.

---

## Don't Hand-Roll

| Problem | Do not build | Use instead | Why |
|---|---|---|---|
| QR encoding for the sign-in dialog | A QR encoder | Vendored `pyqrcode` + its bundled `png.py` | Reed–Solomon error correction, version/mask selection and a PNG writer — all four already exist, pure-Python, `<platform>all</platform>`, and it is the exact code the add-on was tested against |
| ISO-8601 parsing | A regex date parser | `datetime.datetime.fromisoformat` | Available on CPython 3.11+, which every target Kodi bundles. The only sharp edge is fractional-second digit count, which is a two-line normalisation, not a parser |
| Key/value persistence | A new store format | `json.dumps`/`json.loads` into the existing SQLite `store` table | The schema and the retry/WAL handling already work; only the serializer is unsafe |
| Verifying "the rename is complete" | A code-reading review | `grep` + `compileall` + an XML parse, in a committed gate file | The failure mode is a machine-checkable absence, and a review cannot prove an absence |
| Multi-version Kodi testing | A container/VM matrix in this phase | Kodi's own `-p` portable mode with separate data directories | This phase needs four installs on one desktop, not reproducible CI images. CI for the checker arrives in Phase 2 |

---

## Runtime State Inventory

This is a rename and re-identification phase, so runtime state matters more than files.

| Category | Items found | Action required |
|---|---|---|
| **Stored data** | `special://profile/addon_data/plugin.onedrive/accounts.db` (SQLite/WAL, `repr()`-encoded, holds OAuth tokens), `cache_page.db`, `cache_children.db`, `cache_items.db`, `exports.db`, `export-items.db`. **On this machine none of these exist** — `%APPDATA%\Kodi\userdata\addon_data` contains only `peripheral.joystick` and `skin.estuary`. | **None.** The new id means a new, empty profile directory. This is the decided no-migration position and it is what makes the `eval` → JSON swap a pure code edit with no data path |
| **Live service config** | The module writes an undeclared setting `<service>.service.port` at runtime (`ui/utils.py:189–199`) for each of `download`, `source`, `export`, `player`. Not in git, not in any `settings.xml`. | **None.** Re-created on first service start under the new id |
| **OS-registered state** | No Windows service, scheduled task, or registry entry. Kodi's own add-on database (`Database/Addons*.db`) records installed add-on ids, but installing under a new id is an ordinary install. On Android, the add-on lives under `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/`. | Uninstall the old id from the test boxes if present, so the clean-profile condition holds. Nothing to migrate |
| **Secrets / env vars** | No secrets, no `.env`, no environment variables. The only credential-shaped value is the `sign-in-server` setting, which points at a dead host and is deleted in Phase 3. | **None** |
| **Build artifacts / installed packages** | No build step; the repository *is* the shippable directory. No `.egg-info`, no compiled output. `.gitignore` covers `*.pyc`/`*.pyo`; stale `__pycache__` under the old package name will exist in any Kodi profile that ran the pre-rename code. | Delete `__pycache__` directories in the test installs after the rename, or reinstall the add-on cleanly, so a stale `clouddrive` package cannot be imported |

**Verified by:** reading `account.py`, `db.py`, `cache/cache.py`, `ui/utils.py` and
`ui/addon.py:86`; listing `%APPDATA%\Kodi\userdata\addon_data` and `%APPDATA%\Kodi\addons`.

---

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| Python 3 | Rename scripts, gate tests | ✓ | 3.11.9 | — (and it matches Kodi 20/21's 3.11) |
| `pytest` | The verification gate | ✓ | 8.3.5 | `unittest` |
| `git` | Vendoring, history preservation | ✓ | 2.48.1 | — |
| Network to github.com | Cloning the upstream tree | ✓ | — | — |
| Kodi 21 Omega (Windows) | KODI-02, acceptance pass | ✓ | 21.3 at `C:\Program Files\Kodi` | — |
| **Clean Kodi profile** | SETUP-06, VND-10 | ✓ | `%APPDATA%\Kodi\addons` contains **no** `plugin.onedrive`, `plugin.googledrive`, `plugin.dropbox` or `script.module.clouddrive.common`; `addon_data` holds only `peripheral.joystick` and `skin.estuary` | — **the Windows half of SETUP-06 is already satisfied** |
| Kodi 20 Nexus | KODI-02 | ✗ | — | Portable install (`kodi.exe -p`) alongside 21 |
| Kodi 22 Piers | KODI-02 | ✗ | — | Nightly build, portable install. Kodi 22 has no release branch yet |
| Kodi 19 Matrix | KODI-01 negative test | ✗ | — | Portable install; or accept the manifest-logic proof above plus a single install attempt |
| Real Android TV box | SETUP-06, CI-06 | ? | — | **No fallback.** Nothing about a 10-foot interface is verifiable from a desktop |
| `adb` | Deploying to and reading logs from the box | ✓ | 1.0.41 | Manual sideload + Kodi's log viewer |
| `kodi-addon-checker` | `addon.xml` sanity | ✗ | — | `pip install kodi-addon-checker` (0.0.36 on PyPI). Belongs to Phase 2's CI-04, but is cheap and useful here for the manifest |
| `gh` | ID-05 fork detach | ✗ | — | GitHub web UI. Fork detachment is not a git operation regardless |
| An installed `script.module.clouddrive.common` 1.4.0 | Ground-truth source | ✗ | — | Clone `matrix` @ `df68e9a` — already done and verified in this session |

**Missing with no fallback:** real Android TV hardware. Confirm availability before planning the
acceptance pass, because CI-06 is a phase requirement and this phase establishes the standard.

**Missing with fallback:** Kodi 19, 20 and 22 installs. Kodi supports portable mode
(`kodi.exe -p`, data directory beside the executable), so four versions can coexist on the one
Windows machine without profile contamination. `[ASSUMED — portable mode is long-standing Kodi
behaviour but was not exercised in this session]`

---

## Verification Tooling

Concrete, runnable checks per success criterion. This project has no test harness; the minimum
viable check is a **single `pytest` file of pure assertions over the repository as text** — no
Kodi stubs, no fixtures, no framework decisions that Phase 2 would have to undo. Phase 2 lifts
this file into CI unchanged (CI-05).

Proposed location: `tests/test_vendor_gates.py`. Run time target: under 2 seconds.

### Automatable — Success Criterion 1

```bash
# zero hits, all three
git grep -n "script\.module\.clouddrive\.common" -- . ':!.planning' ':!VENDORED.md' ':!CREDITS.md'
git grep -nE "\b(eval|exec)\s*\(" -- . ':!.planning'
git grep -nE "plugin\.onedrive(\.kn)?" -- . ':!.planning' | grep -vE "plugin\.onedrive\.kn"

# exactly one import, and it is xbmc.python 3.0.1
python - <<'PY'
import xml.etree.ElementTree as ET
r = ET.parse('addon.xml').getroot()
imports = r.findall('./requires/import')
assert len(imports) == 1, [i.attrib for i in imports]
assert imports[0].attrib == {'addon': 'xbmc.python', 'version': '3.0.1'}, imports[0].attrib
assert r.attrib['id'] == 'plugin.onedrive.kn'
PY
```

Express each as a `pytest` function so a failure names the offending file and line. `VENDORED.md`
and `CREDITS.md` must be excluded from the id grep — they are *required* to name the upstream
module, and forgetting the exclusion produces a gate that can never go green.

### Automatable — rename completeness

```bash
git grep -n "clouddrive\.common" -- . ':!.planning' | grep -v "resources\.lib\.vendor\.clouddrive_common"   # zero
git grep -nE "sys\.path\.(append|insert)" -- .                                                              # zero
python -m compileall -q resources/ entrypoint.py service.py                                                 # exit 0
```

### Automatable — timeout sweep

An `ast` walk asserting every `Call` to `urlopen` / `urlretrieve` carries a `timeout` keyword.
One site today; the check costs ~20 lines and does not go stale as Phase 4 adds call sites.

### Automatable — resources

- All three skin XMLs and all seven media PNGs exist at
  `resources/skins/default/{1080i,media}/`.
- Every `<texture>` filename in the three XMLs resolves to a present file.
- No duplicate `msgctxt` within either `.po`; the `en_gb` id set matches the expected union; every
  statically referenced id exists, with the two dynamic id sets hard-coded into the check.
- Both licence files present: root `LICENSE.txt`, and
  `resources/lib/vendor/clouddrive_common/cache/LICENSE`, plus pyqrcode's `LICENSE.md`.

### Semi-automatable — Success Criterion 2 (KODI-01/KODI-02)

The manifest logic is proven above from Kodi source, so the install matrix is a confirmation, not
a discovery. Four portable installs, one action each:

| Kodi | Expected | How |
|---|---|---|
| 19 Matrix | Install **fails**, log names the unmet `xbmc.python` dependency | Install from zip |
| 20 Nexus | Installs; plugin lists; service starts | Install from zip, then check `kodi.log` for both entry points |
| 21 Omega | Same | Same |
| 22 Piers (nightly) | Same | Same |

The log assertion is mechanical: a successful load writes lines naming both `entrypoint.py` and
`service.py` under the new add-on id. Grep for the new id and for `Traceback` in the same pass.

### Genuinely manual — Success Criteria 3 and 5 (CI-06)

Not automatable, and honest about why: Kodi renders in a window, the add-on is driven by a
D-pad, and the dialogs are skin-rendered.

| Check | Windows (Kodi 21) | Android TV box |
|---|---|---|
| Install on a clean profile with no sibling add-ons | ✓ | ✓ |
| Plugin root opens; account list renders (empty is correct) | ✓ | ✓ |
| Settings screen opens; every category and row renders with correct labels | ✓ | ✓ (with the remote) |
| Every string reads correctly — this is the D2 regression surface | ✓ | ✓ |
| All three `WindowXMLDialog`s open via the phase-local smoke action; `qr.png` appears under the **new** profile | ✓ | ✓ |
| Service starts at login; no `Traceback` and no `Unknown addon id` in `kodi.log` | ✓ | ✓ |
| Add-on is navigable end to end with only a remote | — | ✓ |

Capture the Android log with `adb logcat` or by pulling
`/sdcard/Android/data/org.xbmc.kodi/files/.kodi/temp/kodi.log`, and attach both logs to the phase
record. "No traceback in a full pass" is the single most valuable artifact this phase produces,
because Phases 3–7 will all ask "was that already broken after vendoring?".

---

## Validation Architecture

### Test framework

| Property | Value |
|---|---|
| Framework | `pytest` 8.3.5 on CPython 3.11.9 — already installed; matches Kodi 20/21's bundled 3.11 |
| Config file | none — see Wave 0 |
| Quick run command | `python -m pytest tests/test_vendor_gates.py -q` |
| Full suite command | `python -m pytest tests -q && python -m compileall -q resources/ entrypoint.py service.py` |

No Kodi stub library is needed and none should be introduced here. Every assertion in this phase
is over the repository as text or as XML. Phase 2 owns `Kodistubs`, fixtures and the layering
test; adding them now would be scaffolding this phase does not use.

### Phase requirements → test map

| Req | Behaviour | Type | Automated command | Exists? |
|---|---|---|---|---|
| VND-01 | Vendored tree matches upstream `matrix` @ `df68e9a` | unit | `pytest tests/test_vendor_gates.py::test_vendored_sha_recorded -q` | ❌ Wave 0 |
| VND-02 | No `clouddrive.common` reference outside the vendored path | unit | `::test_no_legacy_package_prefix` | ❌ Wave 0 |
| VND-03 | No second top-level `resources` package; skins and strings merged | unit | `::test_resources_merged` | ❌ Wave 0 |
| VND-04 | Zero `script.module.clouddrive.common` literals | unit | `::test_no_hardcoded_module_id` | ❌ Wave 0 |
| VND-05 | Zero `eval(`/`exec(`; store round-trips through JSON | unit | `::test_no_eval` + `::test_store_json_roundtrip` | ❌ Wave 0 |
| VND-06 | Every `urlopen` call carries `timeout=` | unit | `::test_all_http_calls_have_timeout` | ❌ Wave 0 |
| VND-07 | Decision recorded in `VENDORED.md` | unit | `::test_vendored_md_sections` | ❌ Wave 0 |
| VND-08 | Skin XML and media present; textures resolve | unit | `::test_skin_assets_present` | ❌ Wave 0 |
| VND-09 | `VENDORED.md` fields; both licence files present | unit | `::test_licences_present` | ❌ Wave 0 |
| VND-10 | Identical behaviour, every dialog opens, clean profile | **manual** | Manual acceptance matrix | n/a |
| VND-11 | Exactly one `<import>`, `xbmc.python` 3.0.1 | unit | `::test_addon_xml_imports` | ❌ Wave 0 |
| ID-01 | No `plugin.onedrive` outside `plugin.onedrive.kn` | unit | `::test_addon_id_everywhere` | ❌ Wave 0 |
| ID-02 | `provider-name` and display name changed | unit | `::test_addon_xml_identity` | ❌ Wave 0 |
| ID-03 | `LICENSE.txt` unchanged; GPL headers intact | unit | `::test_license_unmodified` (hash) + `::test_gpl_headers_intact` | ❌ Wave 0 |
| ID-04 | `CREDITS.md` names origin, module, pyqrcode, pypng | unit | `::test_credits_content` | ❌ Wave 0 |
| ID-05 | Repo detached from fork network; history preserved | **manual** | GitHub settings + `git rev-list --count HEAD` ≥ 113 | partial |
| KODI-01 | Kodi 19 refuses; 20/21/22 accept | **manual** | Install matrix (manifest logic already proven) | n/a |
| KODI-02 | Runs on 20, 21, 22 | **manual** | Install matrix + log assertions | n/a |
| SETUP-06 | Clean profile + real Android TV box | **manual** | Windows half verified; Android half outstanding | partial |
| CI-06 | Manual acceptance on Windows and Android TV | **manual** | Manual acceptance matrix | n/a |

### Sampling rate

- **Per task commit:** `python -m pytest tests/test_vendor_gates.py -q` — under 2 s, so there is
  no excuse to skip it. Every commit in this phase must leave the add-on installable and the gate
  green, because the phase's whole value is attributability.
- **Per plan merge:** the quick run plus `python -m compileall -q` plus, once available,
  `kodi-addon-checker . --branch=omega`.
- **Phase gate:** full gate green, install matrix complete, and one full manual acceptance pass on
  Windows and on the Android TV box, on a clean profile, with both logs archived.

### Wave 0 gaps

- [ ] `tests/test_vendor_gates.py` — every automated assertion above
- [ ] `pytest.ini` (or `[tool.pytest.ini_options]`) — `testpaths = tests`, nothing else
- [ ] A phase-local `_dialog_smoke` plugin action, so Success Criterion 3 is testable at all
- [ ] `pip install kodi-addon-checker` on the development machine
- [ ] Kodi 19, 20 and 22 portable installs
- [ ] Confirm the Android TV box is available and reachable over `adb`

Nothing else. Do not build a Kodi-stub harness in this phase.

---

## Security Domain

`security_enforcement: true`, ASVS level 1.

### Applicable ASVS categories

| Category | Applies | Standard control in this phase |
|---|---|---|
| V2 Authentication | no | No auth code changes here; the broker is untouched until Phase 3 |
| V3 Session Management | no | — |
| V4 Access Control | **yes** | The vendored `SourceService` HTTP listener has no authorisation check of any kind (`service/base.py` contains no token, password or credential check). See Pitfall 8 |
| V5 Input Validation | **yes** | ASVS V5.2.4 forbids dynamic code execution on untrusted input. The three `eval(` sites read from an on-disk SQLite file, one of which holds OAuth refresh tokens. VND-05 is the control |
| V6 Cryptography | no | Nothing cryptographic is written or changed |
| V7 Error Handling / Logging | **yes** (deferred) | `remote/errorreport.py` posts tracebacks to a third-party endpoint. Vendored intact in this phase; deleted in Phase 7 (KODI-08). Record it in `VENDORED.md` as a carried liability |
| V12 Files and Resources | **yes** | `qr.png` is written into the add-on profile; after the id fix that is the new, correctly-scoped profile |
| V14 Configuration | **yes** | `addon.xml` must declare exactly one dependency; every vendored file's provenance is recorded |

### Known threat patterns

| Pattern | STRIDE | Mitigation in this phase |
|---|---|---|
| Deserialisation via `eval()` on file-backed data | Elevation of Privilege | Replace with `json.loads`. On Android, `special://home` resolves under `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/`, which older Android versions expose to any app holding storage permission — so the "attacker must already write to your disk" defence is weaker here than on a desktop |
| Unauthenticated loopback index of the entire drive | Information Disclosure | Verified loopback-bound on the configured port, gated on a setting that defaults to `true`, with no authorisation. Decided deletion in Phase 7; Pitfall 8 asks whether the default should be flipped now |
| Traceback exfiltration to a third party | Information Disclosure | `errorreport.py` carried intact; the `report_error` setting already defaults to `false`. Deleted in Phase 7 |
| Dependency confusion / package shadowing | Tampering | The rename plus the no-`sys.path`-manipulation rule; asserted by the module `__file__` check |
| Supply chain: vendored third-party code | Tampering | Pin the upstream SHA in `VENDORED.md`; take pyqrcode from the Kodi add-on zip (the tested artifact), not from PyPI |

---

## Package Legitimacy Audit

This phase installs **no** package manager dependencies into the shipped add-on — that is its
point. Two source trees are vendored, and two development tools are used.

| Package | Registry | Age | Downloads | Source repo | Verdict | Disposition |
|---|---|---|---|---|---|---|
| `script.module.clouddrive.common` 1.4.0 | Kodi (vendored, not installed) | last commit 2023-01-21 | n/a | `github.com/cguZZman/script.module.clouddrive.common` | OK | Vendored at `df68e9a`, SHA pinned |
| `script.module.pyqrcode` 1.2.1+matrix.4 | Kodi repo (vendored, not installed) | PyQRCode 1.2.1 dates to 2016 | present in nexus, omega and piers mirrors | `github.com/mnooner256/pyqrcode`; `pypi.org/project/PyQRCode` | OK | Vendored from the Kodi add-on zip; BSD-3-Clause + MIT recorded |
| `script.module.dateutil` | Kodi repo | — | present in all three mirrors | — | OK | **Removed** — replaced by stdlib |
| `script.module.pypng` | — | — | **404 in nexus, omega and piers** | — | n/a | Never referenced directly; `png.py` ships inside pyqrcode |
| `pytest` 8.3.5 | PyPI (dev only) | mature | very high | `github.com/pytest-dev/pytest` | OK | Already installed |
| `kodi-addon-checker` 0.0.36 | PyPI (dev only) | maintained by Team Kodi | low but expected for a niche tool | `github.com/xbmc/addon-check` | OK | Install locally; CI in Phase 2 |

**Removed due to a SLOP verdict:** none.
**Flagged suspicious:** none.

`kodi-addon-checker` was not verified against a registry in this session — the version number
comes from the project research. `[ASSUMED]` Confirm with `pip index versions kodi-addon-checker`
before the plan pins it.

---

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|---|---|---|---|
| `<import addon="xbmc.python" version="3.0.0"/>` | `3.0.1` on Kodi 20/21/22 | Nexus, 2022 | The one-line Kodi 19 gate (KODI-01) |
| `dateutil.parser.parse` | `datetime.fromisoformat` | CPython 3.11 | Removes a dependency outright |
| `repr()`/`eval()` persistence | `json` | long-standing | The control for VND-05 |
| Depending on a shared `script.module.*` framework | Vendoring under the add-on's own namespace | — | The whole phase. The Kodi 20 `sys.path` regression made shared-module shadowing materially worse |
| Fixed service ports | Ephemeral bind on `127.0.0.1:0` | already in v1.4.0's `BaseServerService` | Phase 6's redirector inherits the right pattern; `SourceService` is the outlier that overrides it |

**Deprecated / outdated in the vendored tree** (noted, not acted on in this phase):
`ListItem.setInfo` (still functional in Kodi 22, log-warns; migrated in Phase 7 atomically with
the integer-duration fix); the pre-Kodi-19 `<settings><category>` schema; `window(home).property(iskrypton)`
visibility conditions (`ui/addon.py:92` reads it); `Utils.get_class`/`get_fqn` (dead code, delete
here).

---

## Ordering and Risk

The roadmap expects four plans. The ordering below is chosen so that each commit's blast radius
is attributable, which is the phase's stated reason for existing.

**Plan 1 — Identity and Kodi gating.** `addon.xml` id, name, version, provider, source/forum/website;
the two `plugin://` literals in `settings.xml`; `xbmc.python` → `3.0.1`; `CREDITS.md`; README;
the fork detach and the SETUP-06 environment confirmation.
*Why first:* it is roughly ten lines, it is independently verifiable, and it guarantees that every
later commit in the phase writes to a fresh, uncontaminated `addon_data` directory. The add-on
still `<import>`s the external module at this point, so it still runs, and any regression is
unambiguously the identity change. Requirements: ID-01…05, KODI-01, KODI-02, SETUP-06.

**Plan 2 — Verbatim copy, rename, dependency removal.** The clone at `df68e9a`, the exclusion list,
the resource merge, the anchored import rewrite in the documented order, deletion of the three
`<import>` entries, vendoring pyqrcode, replacing dateutil, deleting `Utils.get_class`/`get_fqn`,
and recording the VND-07 decision.
*Why here:* it is the phase's "the add-on must still work identically" checkpoint. If it does not,
stop and fix before anything else. Requirements: VND-01, VND-02, VND-03, VND-07, VND-11.

**Plan 3 — De-hardcoding.** The eight add-on-id sites, the string-id renumbering and merge, the
settings consolidation and the `_open_common_settings` decision, and the `_dialog_smoke` action
that makes Success Criterion 3 testable.
*Why here:* every item is a change that looks correct on a contaminated machine and fails on a
clean one, so it belongs in one commit that the clean-profile pass validates as a unit.
Requirements: VND-04, VND-08.

**Plan 4 — Hardening and record.** `eval` → JSON, the `timeout=` sweep, `VENDORED.md`, the licence
audit, the full gate file, the install matrix and the manual acceptance pass on Windows and the
Android TV box.
Requirements: VND-05, VND-06, VND-09, VND-10, CI-06.

Plans 3 and 4 are the largest; if the plan wants five, the natural cut is between the string-id
merge and the id de-hardcoding, because the string work has its own verification surface.

### Where the landmines are, ranked

1. **The string-id collision** (Decision D2). Complete, silent, affects most of the UI, and is not
   caught by any grep the project has planned. Caught only by reading labels on screen — which is
   why the manual acceptance pass must include "open Settings and read every row".
2. **The clean-profile requirement** (Pitfall 3). Structural, not a matter of care. Already
   satisfied on the Windows machine, which is a real piece of luck — protect it by not installing
   any sibling cloud-drive add-on there.
3. **The substring rename trap** (Pitfall 1). Cheap to avoid if known, corrupting if not.
4. **`pyqrcode`** (Decision D3). The obvious reading of "no imports beyond `xbmc.python`" is to
   drop it, and dropping it breaks the exact dialog Success Criterion 3 names.
5. **The unreachable QR dialog** (Pitfall 6). The criterion cannot be met by navigation; a test
   affordance has to be built for it.
6. **The carried-live directory listener** (Pitfall 8). A security posture question disguised as a
   fidelity question.

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | Kodi reserves 30000–30999 for plugins and 32000–32999 for scripts | Decision D2 | If the ranges differ, `kodi-addon-checker` may object to the renumbering. The collision fix still works — only the target block would move. Verify the wiki wording during execution (`kodi.wiki/view/Language_support` returned 403 to automated fetch in this session) |
| A2 | A 15–30 s `timeout=` is right for Graph metadata calls | HTTP Call Inventory | Too low causes spurious failures on slow Wi-Fi; too high reproduces the hang. No measurement was made. Confirm on the Android box during acceptance |
| A3 | Graph may emit 7-digit fractional seconds that `fromisoformat` rejects | Decision D4 | If it never happens, the normalisation is harmless. If it does and the normalisation is skipped, list-item dates silently vanish (the existing bare `except` already swallows it) |
| A4 | `3.0.0` is the right new version number | Identity Change Map | A wrong choice is hard to reverse — Kodi's version comparison will not offer a downgrade. Needs maintainer confirmation |
| A5 | Kodi portable mode (`-p`) allows four versions on one Windows machine without profile contamination | Environment Availability | If not, the install matrix needs VMs or a second machine, which changes the phase's effort estimate |
| A6 | Flipping `allow_directory_listing` to `false` in this phase is acceptable | Pitfall 8 | It is a deliberate deviation from "identical behaviour". Needs maintainer confirmation either way; the alternative is to carry a live unauthenticated listener into a fresh profile |
| A7 | `kodi-addon-checker` 0.0.36 is current | Package Legitimacy Audit | Only affects a dev-tool pin. Verify with `pip index versions` |
| A8 | The Android TV box is available for this phase | Environment Availability | CI-06 is a phase requirement; without hardware the phase cannot be signed off, and the standard it establishes for Phases 2–8 is unproven |

---

## Open Questions

1. **Is `plugin.onedrive.kn` final, and what version number does it start at?**
   - Known: ID-01 fixes the id. DIST-01 still spells the old zip name, which Phase 5 must
     reconcile.
   - Unclear: the starting version.
   - Recommendation: settle both in Plan 1, and note the DIST-01 wording as a Phase 5 follow-up
     rather than editing `REQUIREMENTS.md` from inside this phase.

2. **Carry the directory listener live, or flip its default now?**
   - Known: loopback-bound, fixed configured port, no authorisation, on by default, deleted in
     Phase 7.
   - Unclear: whether the phase's fidelity contract should bend for it.
   - Recommendation: put it to the maintainer as a one-line decision in Plan 1, so Plan 2's
     "identical behaviour" checkpoint has an unambiguous target.

3. **Does the `_open_common_settings` action get removed or repointed?**
   - Known: it opens an add-on that will no longer exist.
   - Recommendation: remove the row and its string in Plan 3; it is dead UI either way.

4. **How far does "behaves exactly as it did before" extend, given the broker is dead?**
   - Known: sign-in cannot complete, so account listing, browsing and playback are all
     unreachable in a fresh profile.
   - Unclear: what the acceptance pass can actually assert beyond "loads, renders, opens dialogs,
     no traceback".
   - Recommendation: write the acceptance checklist as the concrete list in Verification Tooling
     rather than as the phrase "identical behaviour", which cannot be checked.

---

## Sources

### Primary (HIGH confidence — read directly in this session)

- `github.com/cguZZman/script.module.clouddrive.common`, branch `matrix`, commit
  `df68e9a589a6faef2b3228f7520e77729bc05d9b` — full clone; file inventory, sizes, and source reads
  of `addon.xml`, `service.py`, `account.py`, `db.py`, `cache/cache.py`, `cache/LICENSE`,
  `exception.py`, `utils.py`, `remote/request.py`, `service/base.py`, `service/download.py`,
  `service/source.py`, `ui/addon.py`, `ui/dialog.py`, `ui/utils.py`, and both `strings.po` files
- `git ls-remote` on the same repository — branch inventory (`krypton`, `matrix`; `HEAD` → `matrix`)
- `github.com/xbmc/xbmc` at `Matrix`, `Nexus`, `Omega`, `master` — `addons/xbmc.python/addon.xml`,
  `tools/depends/target/python3/PYTHON3-VERSION`, `xbmc/addons/addoninfo/AddonInfo.cpp`
  (`MeetsVersion`), `xbmc/interfaces/legacy/WindowXML.cpp` (skin path resolution)
- `github.com/xbmc/addon-check` `master` — `kodi_addon_checker/versions.py` (`VERSION_ATTRB`),
  `check_dependencies.py`
- `mirrors.kodi.tv/addons/{nexus,omega,piers}/` — module presence probes;
  `script.module.pyqrcode-1.2.1+matrix.4.zip` downloaded and its contents and licences read
- This repository — `addon.xml`, `entrypoint.py`, `service.py`, `resources/lib/addon.py`,
  `resources/lib/provider/onedrive.py`, `resources/settings.xml`, both `strings.po` files,
  `LICENSE.txt` (byte-compared against upstream), `README.md`, `.github/`, git remote and history
- Local environment probes — Kodi 21.3 install and profile contents, Python 3.11.9, pytest 8.3.5,
  adb 1.0.41, absence of `kodi-addon-checker` and `gh`

### Secondary (MEDIUM confidence)

- `pypi.org/pypi/PyQRCode/json` — `requires_dist` is null; pypng documented as optional for `.png()`
- `kodi.wiki/view/Language_support` — string-id ranges, obtained via search summary; direct fetch
  returned HTTP 403
- `github.com/xbmc/xbmc/issues/22985` — Kodi 20 `sys.path` ordering regression, cited from the
  project's own research rather than re-read here
- `.planning/research/{SUMMARY,PITFALLS,ARCHITECTURE}.md` — the project's prior research pass;
  used as a starting hypothesis and corrected where this session's source reads disagreed

### Tertiary (LOW confidence)

- The Kodi portable-mode assumption (A5) — not exercised
- The `timeout=` value range (A2) — no measurement
- The 7-digit fractional-second case (A3) — not observed

---

## Metadata

**Confidence breakdown:**

- Upstream inventory and dispositions: **HIGH** — full clone, per-file reads, sizes and SHA verified
- Rename mechanics: **HIGH** — every import form enumerated; the one dynamic mechanism proven dead
- Hardcoded id and `eval`/HTTP inventories: **HIGH** — exhaustive greps over the actual tree
- String-id collision analysis: **HIGH** — both `.po` files parsed and compared programmatically
- Kodi version gating: **HIGH** — manifest values and `MeetsVersion` read from Kodi source; the
  checker's advised values confirm independently
- Licence findings: **MEDIUM-HIGH** — file contents verified; the `cache/LICENSE` provenance is
  genuinely unresolved and is recorded as such rather than guessed
- Environment availability: **HIGH** for this Windows machine, **unknown** for the Android box
- Timeout value, version number, portable mode, `pyqrcode` decision acceptance: **LOW to MEDIUM**
  — see the Assumptions Log

**Research date:** 2026-08-22
**Valid until:** the upstream module is frozen (last commit 2023-01-21), so the vendoring facts do
not expire. The Kodi facts should be re-checked when Kodi 22 branches from `master`, at which
point `xbmc.python` may move past 3.0.2 — which would not affect the `3.0.1` declaration, but
would change the Piers install matrix.
