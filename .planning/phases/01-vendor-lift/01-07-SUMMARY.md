---
phase: 01-vendor-lift
plan: 07
subsystem: record-and-acceptance
tags: [vendored-md, credits, readme, dialog-smoke, kodi-addon-checker, android, adb, json-rpc, acceptance]

# Dependency graph
requires:
  - "01-01 — the four-version Kodi matrix and the Android instrument"
  - "01-04 — the exclusion list, the modified-file list and the pinned upstream SHA"
  - "01-05 — the eight id sites, the two QR write guards and the bundled QR encoder"
  - "01-06 — the serializer swap and the HTTP timeout"
provides:
  - "VENDORED.md — provenance pinned to a commit, licences by subtree, the exclusion list, the local-modification table keyed by file, the service-extension-point decision and four recorded deviations"
  - "CREDITS.md — all four attributions with their licences"
  - "README.md — an accurate description with the attribution ID-04 requires"
  - "OneDriveAddon._dialog_smoke — the affordance that makes all three WindowXMLDialog subclasses reachable without a network round trip or a human at a browser"
  - "A full clean acceptance pass on Kodi 21.3 on Android 11 with zero tracebacks, both logs archived"
  - "A recorded scope decision: Windows is not a target for this add-on, the TCL Android TV 12 is the primary acceptance device, and the four-version Kodi install matrix is not pursued"
  - "The measured fact that the sign-in broker is alive, which corrects a record every later phase would have inherited"
affects: [phase-03-auth, phase-07-cleanup, phase-02-ci]

tech-stack:
  added: []
  patterns:
    - "Drive Kodi over its own JSON-RPC web server rather than by clicking: Files.GetDirectory renders the plugin root, Addons.ExecuteAddon runs an action, Input.* walks a dialog, and adb exec-out screencap is the eye"
    - "Resolve every label id in settings.xml against the merged catalogue, so every row is checked and not only the rows a screenshot happens to show"
    - "A debug affordance stubs its awkward collaborators rather than asking for a live server, so the check is repeatable"

key-files:
  created:
    - VENDORED.md
    - CREDITS.md
  modified:
    - README.md
    - addon.xml
    - resources/lib/addon.py

key-decisions:
  - "The recorded deviation that the sign-in broker is dead is wrong and was corrected: drive-login.herokuapp.com answered 200, issued a code, and the add-on began polling. The reason to replace it is that a third party holds the OAuth exchange, not that it is gone"
  - "The install matrix and the Windows acceptance row cannot be run from this shell: the interactive session is disconnected and Kodi logs FATAL CApplication::Create: Unable to create window. Extracting the add-on into the addons directory is not a substitute, because it bypasses the very dependency gate row 1 exists to test"
  - "kodi-addon-checker is run against a staged directory named after the add-on id, because the development checkout is named OneDrive.Addon and the folder-name check is about the shipped artefact"
  - "The supplementary log is redacted before archiving: the broker's reply carries the requester's public IP and an encrypted credential blob"
  - "The Windows leg and the four-version install matrix are dropped by the owner's decision, because Windows is not a target for this personal-use add-on — not because they were blocked. KODI-02 is narrowed rather than satisfied, and stays unchecked"
  - "The TCL Android TV 12 is the primary acceptance device from here on, not a pre-release checkbox. Its first acceptance run is deferred to Phase 3, because Phase 1 leaves the add-on able to install and open dialogs and nothing else"

requirements-completed: []
requirements-partial: [VND-07, VND-09, VND-10, ID-04, CI-06]
requirements-blocked: []
requirements-descoped: [KODI-02]

metrics:
  duration: "~2h"
  completed: 2026-08-23
  tasks: "3 of 3 closed — Tasks 1 and 2 complete; Task 3 closed with its Android row filled and its Windows rows descoped"

status: complete
---

# Phase 1 Plan 07: The Record and the Acceptance Pass Summary

**The record is written and the whole gate suite is green for the first time — 22 of 22 — and the add-on has been driven end to end on Kodi 21.3 on Android 11 with no traceback in the log. Along the way the acceptance pass overturned one of the deviations the record was about to enshrine: the sign-in broker everyone believed dead since 2022 answered on the first request. The Windows half of the
acceptance pass was then dropped by the owner's decision — Windows is not a target for this add-on — and the plan
closes on the Android row, with everything Windows never established written down as unestablished.**

## Performance

- **Duration:** ~2 h
- **Tasks:** 3 of 3 closed. Tasks 1 and 2 complete; Task 3 closed with its Android row filled and its Windows rows
  descoped by decision rather than filled
- **Files:** 2 created, 3 modified

## Task commits

| # | Commit | What |
|---|---|---|
| 1 | `c9d9a0f3cf8cc5e124e8295db4acc0415d4b77af` | `feat(addon)`: the `_dialog_smoke` action — **only** `resources/lib/addon.py` |
| — | `b5065ab` | `fix(manifest)`: drop the obsolete `start` attribute (deviation 1 below) |
| 2 | `9db3ae3` | `docs`: VENDORED.md, CREDITS.md, README.md |
| — | `49ad7f6` | `docs`: correct the sign-in record (deviation 2 below) |
| — | `be4f9c8`, `831ac7e` | `fix(addon)`: the smoke action cleans up after itself (deviation 3 below) |

`git show --name-only --format= c9d9a0f3cf8cc5e124e8295db4acc0415d4b77af` lists exactly one path,
`resources/lib/addon.py`, as the plan's self-relative criterion requires.

## Task 1 — the dialog smoke action

The base class dispatches by `getattr(self, self._action)` (`ui/addon.py:700`), so adding the
method was sufficient; there is no action map to register in. That was read before writing, as the
plan directs.

Everything the method needs is imported **inside** it, so removing the affordance is one contiguous
block in this repository's own file and never another local modification to a vendored file.

It constructs the QR dialog **twice**, waits for `onInit` to have written the image rather than
assuming it has, and logs the resolved path each time. It also copies each image to a stable name,
because the dialog deletes its own image on teardown and the acceptance pass has to be able to look
at the file rather than only at a log line.

`ExportMainDialog` needed more than dummy strings. Its `onInit` reads an export out of a store and,
finding none, opens a **modal folder browser that waits for a human** — which would have made the
whole affordance unrunnable unattended. It is given a throwaway export store of its own with one
record already in it, plus stubs for the two collaborators it only ever asks for a display name.
Nothing touches the real account store and nothing makes a network call.

### Task 1 acceptance criteria

| Criterion | Result |
|---|---|
| `_dialog_smoke` present on `OneDriveAddon` by AST | `ok` |
| `grep -c QRDialogProgress` / `ExportScheduleDialog` / `ExportMainDialog` | 5 / 5 / 5 |
| `python -m compileall -q resources/ entrypoint.py service.py` | exit 0 |
| `test_gpl_headers_intact` | pass |
| `grep -c mkdirs` in `ui/dialog.py` | 1 |
| `grep -c uuid4` in `ui/dialog.py` | 1 |
| Two constructions log two different paths | **observed on the device**, quoted below |
| Commit lists only `resources/lib/addon.py` | confirmed |

## Task 2 — the record

`VENDORED.md` carries the six required headings, the pinned commit, the exclusion list with a
reason per path, a local-modification table keyed by file (including both QR write guards, the
serializer swap, the timeout with its **unmeasured** status and the date-parse truncation), the
VND-07 decision naming `SourceService` and `SourceRedirector`, and four recorded deviations. It
also states plainly what it cannot settle: the Apache-2.0 file beside the cache module names nobody
and the module beside it is GPL, and this record does not resolve the contradiction by guessing.

`CREDITS.md` names all four attributions. `README.md` no longer advertises the local
directory-listing server.

**The gate suite is 22 of 22 green** for the first time in the phase. The three that were red —
`test_vendored_sha_recorded`, `test_vendored_md_sections`, `test_credits_content` — are green
because the documents exist and say what they must, not because any assertion was weakened. No
assertion in `tests/test_vendor_gates.py` was edited by this plan.

### `kodi-addon-checker` — output recorded verbatim

The plan's literal command checks the development checkout, whose directory is named
`OneDrive.Addon`. That produces a folder-name error the shipped artefact does not have, so the
checker was run twice: once literally, and once against a staged directory named after the add-on
id, which is what a zip actually contains.

**Run 1 — `kodi-addon-checker . --branch=omega`, before any fix:**

```
INFO: Checking add-on OneDrive.Addon
INFO: Created by Kenny Nguyen
ERROR: Addon id and folder name does not match.
INFO: This is a new addon
failed validating {'point': 'xbmc.service', 'library': 'service.py', 'start': 'login'} with XsdAttributeGroup(['point', 'id', 'name', 'library']):

Reason: 'start' attribute not allowed for element
...
ERROR: Schema validation failed for the following points: xbmc.service
WARN: 404 Client Error: Not Found for url: https://github.com/anhyeuviolet/kodi.plugin.onedrive/issues
WARN: 404 Client Error: Not Found for url: https://github.com/anhyeuviolet/kodi.plugin.onedrive
INFO: Image icon exists
INFO: icon dimensions are fine 256x256
INFO: Image fanart exists
INFO: fanart dimensions are fine 1280x720
INFO: fanart file size is fine 39KB
INFO: PO files are valid
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.gitignore
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.project
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.pydevproject
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.pytest_cache\.gitignore
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.pytest_cache\CACHEDIR.TAG
ERROR: We found 2 problems and 7 warnings, please check the logfile.
```

**Run 2 — the same command after the schema fix, with the test cache removed:**

```
INFO: Checking add-on OneDrive.Addon
INFO: Created by Kenny Nguyen
ERROR: Addon id and folder name does not match.
INFO: This is a new addon
INFO: Valid XML file found
WARN: 404 Client Error: Not Found for url: https://github.com/anhyeuviolet/kodi.plugin.onedrive/issues
WARN: 404 Client Error: Not Found for url: https://github.com/anhyeuviolet/kodi.plugin.onedrive
INFO: Image icon exists
INFO: icon dimensions are fine 256x256
INFO: Image fanart exists
INFO: fanart dimensions are fine 1280x720
INFO: fanart file size is fine 39KB
INFO: PO files are valid
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.gitignore
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.project
WARN: Found non whitelisted file ending in filename .\OneDrive.Addon\.pydevproject
ERROR: We found 1 problems and 5 warnings, please check the logfile.
```

**Run 3 — `kodi-addon-checker plugin.onedrive.kn --branch=omega` against the staged add-on
directory, i.e. what the zip contains:**

```
INFO: Checking add-on plugin.onedrive.kn
INFO: Created by Kenny Nguyen
INFO: Addon id matches folder name
INFO: This is a new addon
INFO: Valid XML file found
WARN: 404 Client Error: Not Found for url: https://github.com/anhyeuviolet/kodi.plugin.onedrive/issues
WARN: 404 Client Error: Not Found for url: https://github.com/anhyeuviolet/kodi.plugin.onedrive
INFO: Image icon exists
INFO: icon dimensions are fine 256x256
INFO: Image fanart exists
INFO: fanart dimensions are fine 1280x720
INFO: fanart file size is fine 39KB
INFO: PO files are valid
WARN: We found no problems and 2 warnings, please check the logfile.
```

**Zero findings of severity ERROR on the shipped artefact.** Every finding, dispositioned:

| Finding | Severity | Disposition |
|---|---|---|
| `Addon id and folder name does not match` | ERROR | **Not a defect — an artefact of checking the checkout in place.** The development directory is `OneDrive.Addon`; the shipped directory is `plugin.onedrive.kn`, and run 3 confirms `Addon id matches folder name`. Packaging must keep producing a folder named after the id; that belongs to the CI phase |
| `'start' attribute not allowed for element` / `Schema validation failed for xbmc.service` | ERROR | **Fixed here** (`b5065ab`). The attribute was removed with Kodi 19; the add-on targets 20 and newer, where every service starts after profile login regardless, so removing it changes no runtime behaviour |
| `404 Client Error` for the `source` and `forum` URLs (×2) | WARN | **Accepted.** The repository is private, so an unauthenticated `GET` is a 404 by design. The URLs are correct; the checker cannot see them. Re-check when the repository is made public |
| `.gitignore`, `.project`, `.pydevproject` non-whitelisted (×3) | WARN | **Deferred to the CI phase.** Development metadata that must not be in the zip; the staging step already excludes all three, which is why run 3 does not report them. The exclusion needs to live in a build script rather than in a scratch file |
| `.pytest_cache/.gitignore`, `.pytest_cache/CACHEDIR.TAG` (×2) | WARN | **Fixed here** by removing the directory before checking. It is generated by a local test run, already gitignored, and never in the zip |

### Task 2 acceptance criteria

| Criterion | Result |
|---|---|
| `python -m pytest tests/test_vendor_gates.py -q` | **22 passed** |
| `grep -c df68e9a…` in VENDORED.md | 1 |
| `grep -c '^## Local modifications'` / `'^## Service extension point'` / `'^## Recorded behaviour deviations'` | 1 / 1 / 1 |
| `grep -c allow_directory_listing` / `_dialog_smoke` in VENDORED.md | 1 / 2 |
| `grep -c mkdirs` / `uuid4` in VENDORED.md | 1 / 1 |
| `grep -c source_scan` / `test_no_hardcoded_module_id` in VENDORED.md | 1 / 1 |
| `grep -c 'Michael Nooner'` / `'Johann C. Rocholl'` in CREDITS.md | 1 / 1 |
| `.planning/phases/01-vendor-lift/COVERAGE.md` non-empty, names Phase 3 | yes, 2 mentions — re-read and still accurate; nothing that landed introduced an external API |
| `test ! -e COVERAGE.md` at the repository root | passes — no copy was added to the shippable directory |
| README names the author and points at CREDITS.md | `ok` |

## Task 3 — the acceptance pass

### Android row — FILLED

Instrument: AVD `kodi_api30`, `system-images;android-30;google_apis;x86_64`, Android 11 / API 30,
Kodi **21.3 (21.3.0) Git:20251031-a3a448d26b**, Platform Android x86 32-bit, GL renderer
`SwiftShader 4.0.0.1`.

**Clean profile, confirmed before installing, not after.** `ls` over the add-ons directory and over
`userdata/addon_data`, filtered for `onedrive|googledrive|dropbox|clouddrive`, returned nothing;
`addon_data` held only `peripheral.joystick` and `skin.estuary`.

**The `addon_data` deletion, verbatim, with Kodi closed:**

```
adb shell rm -rf /sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/plugin.onedrive.kn
```

followed by `ls -d` on the same path returning
`No such file or directory`. The whole pass then ran in one Kodi session from that genuinely absent
profile directory.

| Check | Result |
|---|---|
| Add-on recognised | `broken: false`, `enabled: true`, `version 1.0.0`, dependency `xbmc.python minversion 3.0.1` satisfied by `3.0.1` |
| Both entry points loaded under the new id | `CPythonInvoker(0, …/plugin.onedrive.kn/service.py): start processing` and `CPythonInvoker(2, …/plugin.onedrive.kn/entrypoint.py): start processing` |
| Service starts at login | `Service 'export' started.`, `Service 'player' started.`, `Service 'download' started in port 44485` |
| Directory-listing service | **not started** — `grep -c "Service 'source' started"` returns **0**, which is deviation 2 confirmed by observation rather than by reading the manifest |
| Plugin root on a clean profile | one row, `Add an account...`, no error dialog — empty is the correct result |
| Settings screen | opens and renders; every row read correctly (below) |
| All three dialogs through the smoke action | all three constructed, rendered and closed; screenshots captured |
| `grep -c Traceback` over the full-pass log | **0** |
| `grep -ci 'unknown addon'` | **0** |

**Both QR image paths, quoted from the pulled log, from one session:**

```
dialog-smoke: QR image path 1 of 2: /storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/plugin.onedrive.kn/qr-c463cfb25f0141cb91248111ac54bbca.png
dialog-smoke: QR image exists 1 of 2: True
dialog-smoke: QR image path 2 of 2: /storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/plugin.onedrive.kn/qr-7bf7aac6207c4719aa443c97fa520fd9.png
dialog-smoke: QR image exists 2 of 2: True
```

They differ, both exist on disk, and both sit under **this** add-on's id in the path. Two identical
paths would have been a phase-gate failure; they are not identical, and the per-invocation filename
guard is now an observation rather than a claim. The comparison is made against a retrieved file,
not a transcription.

**The three skin files all resolved under this add-on's own directory** — the thing asserting file
existence could never prove:

```
Loading skin file: …/addons/plugin.onedrive.kn/resources/skins/default/1080i/pin-dialog.xml
Loading skin file: …/addons/plugin.onedrive.kn/resources/skins/default/1080i/pin-dialog.xml
Loading skin file: …/addons/plugin.onedrive.kn/resources/skins/default/1080i/export-schedule-dialog.xml
Loading skin file: …/addons/plugin.onedrive.kn/resources/skins/default/1080i/export-main-dialog.xml
```

**Settings labels — every row, not only the visible ones.** Two checks, because a screenshot only
shows what fits. Visually, the Services category renders with the group headings *Player Service*,
*Export Service*, *Source Service* and *Auto-Refreshed slideshow*, and *Allow using OneDrive as a
source* is visibly **off**. Statically, every `label` id in `resources/settings.xml` was resolved
against the merged `en_gb` catalogue: **22 rows, 0 unresolved**, and every one reads correctly —
`30067 Services`, `30032 Advanced`, `30030 Collaboration`, `30004 Automatically set subtitles from
cloud drive`, `30068 Allow using OneDrive as a source`, `30069 Source server port…`, `30033
Sign-in Server`, `30035 Clear cache now`, `30031 Report errors automatically…` and the rest. **No
label reads as a plausible wrong word.** This is the phase's largest silent risk and it is clean.

**The three dialogs, seen:** the QR dialog rendering its heading *Dialog smoke 1 of 2* with the QR
image and a *Cancel* button; the schedule dialog rendering *Schedules — Every [Day] at [00:00]*
with *Cancel* and *Save*; and the export dialog rendering *OneDrive KN - Export to .strm files…*
with *Cloud Drive*, *Cloud Folder*, *Destination*, four toggles, the schedules list and
*Cancel / Save / Save & Run*. Textures render in all three.

**Not claimed:** D-pad focus order, ten-foot readability, low-end performance and real GPU or codec
behaviour. The instrument ran on SwiftShader and none of the four was checked. They belong to the
deployment box under CI-07.

### Windows rows and the install matrix — BLOCKED *(superseded)*

> **Superseded on 2026-08-23.** Read this subsection as a record of what was true at 23:23 on 2026-08-22, not as a
> standing fact. The session blocker it describes later cleared, and the leg was then dropped by decision rather than
> by inability. See **The Windows leg — closed by decision, not by evidence** below, which corrects two specific
> statements made here.

Not run, and not runnable from this shell. The interactive Windows session is **disconnected**
(`query session` shows session 1 in state `Disc`), so Kodi cannot create a rendering surface:

```
2026-08-22 23:23:02.796  FATAL <general>: CApplication::Create: Unable to create window
```

Kodi 19.5 was launched with `-p` to establish this and died at that line every time; there is no
audio endpoint either. This is a property of the session, not of the add-on.

Extracting the add-on into the add-ons directory is **not** a substitute for the matrix. It was
tried on Kodi 19 and the result proves the point: Kodi logged `plugin.onedrive.kn v1.0.0 installed`
next to `xbmc.python v3.0.0 installed` — i.e. the add-on was accepted on a Kodi whose `xbmc.python`
is **older than the 3.0.1 the manifest requires**, because manual extraction bypasses the
dependency gate that the zip installer applies. Row 1 exists precisely to exercise that gate, so
reading this as a pass would have been the exact failure the row is designed to catch. The
extraction was undone; `kodi-19.5/portable_data/addons` holds only `packages` and `temp` again.

The zip is built and staged and ready: `plugin.onedrive.kn-1.0.0.zip`, 226,652 bytes, 63 files, at
`C:\Users\nguyentiendat07\AppData\Local\Temp\claude\D--AppDev-Kodi-OneDrive-Addon\1d48d616-8cc9-4348-9f78-49f3f4e6ed44\scratchpad\stage\`.

### Wireless debugging

Nothing to close. The Android instrument is a local emulator, as 01-01 recorded when the phone
proved unavailable; it is reached over the loopback adb transport, not over a network pairing.
`adb devices -l` lists exactly one target, `emulator-5554`, and no `adb connect` pairing exists.
`T-1-09` rates its exposure `low` on the basis that a debugging window on a handset lasts only as
long as the phase — **no handset was ever paired, so that window was never opened.** If a physical
device is used for the Windows-equivalent leg later, this control has to be honoured then.

### Archived artefacts

| Artefact | Path |
|---|---|
| Full clean acceptance log (definitive) | `D:\KodiPortable\_logs\android-acceptance\kodi-android-acceptance.log` — 146,341 bytes, **0 tracebacks** |
| Screenshots of the pass | `D:\KodiPortable\_logs\android-acceptance\*.png` |
| Dense capture of the three dialogs | `D:\KodiPortable\_logs\android-acceptance\dialogs\t00–t39.png` |
| Settings screen walk | `D:\KodiPortable\_logs\android-settings\*.png` |
| Supplementary probe (debug logging, sign-in) | `D:\KodiPortable\_logs\android-supplement\kodi-android-supplement.log` — 200,436 bytes, **0 tracebacks**, redacted |
| Superseded earlier runs, kept for audit | `D:\KodiPortable\_logs\superseded-android-pass-01\`, `…-02\` |

The supplementary log is **redacted**: the broker's reply carries the requester's public IP address
(61 occurrences) and an encrypted credential blob (1). Both are replaced with placeholders. One
over-eager redaction was undone — the IPv4 sweep matched the SwiftShader version string, whose true
value was recovered from the unredacted log archived in 01-01 rather than guessed. The definitive
acceptance log needed no redaction: nothing signed in during it, and the only addresses it contains
are the emulator's own `10.0.2.15` and `10.0.2.16`.

`T-1-24` accepted archived logs on the basis that no account was ever signed in. That rationale
held for the acceptance log and **stopped holding for the supplementary one the moment a sign-in was
started**, which is why it was redacted. The register's note that this rationale expires at Phase 3
is correct and arrives sooner than expected.

## The Windows leg — closed by decision, not by evidence

*Recorded 2026-08-23, closing Task 3.*

### The decision, and the reason

This add-on is written for one person's own use. Their device is a **TCL television running Android TV 12**. Windows
Kodi was never a target; it was an instrument of convenience, and the four-version install matrix came from a
general-purpose acceptance standard inherited by the phase rather than from anything this project needs. The owner
stopped the Windows run while it was in progress and directed the effort at the target device instead. Working on
backwards compatibility across Kodi versions and desktop platforms is explicitly not being pursued.

**The Windows leg is dropped because Windows is not a target — not because it was hard.** That distinction matters
for anyone reading this later: the run was progressing when it was stopped, and the earlier "blocked" record above
had already ceased to be true. Nothing here is a retreat from a difficulty.

Other devices, other users and public sharing remain "best to have". They are not what this milestone is being
steered by.

### What was harvested from disk, and what it establishes

The interrupted run left four Kodi logs behind. Kodi writes them at launch, so they cost nothing to read; **no Kodi
was started to produce them, nothing was installed, and nothing under `%APPDATA%\Kodi` or `D:\KodiPortable` was
modified.** They were read and nothing else.

| Kodi | Log | Size | Session window |
|---|---|---|---|
| 19.5 (19.5.0) Git:20221224-f8fdeb6b1b | `D:\KodiPortable\kodi-19.5\portable_data\kodi.log` | 300,730 B | 06:34:27 → 06:36:50 |
| 20.5 (20.5.0) Git:20240303-4b95737efa | `D:\KodiPortable\kodi-20.5\portable_data\kodi.log` | 395,659 B | 06:37:57 → 06:39:34 |
| 22.0-BETA1 (21.90.801) Git:20260621-77395cf42e | `D:\KodiPortable\kodi-22.0-beta1\portable_data\kodi.log` | 208,121 B | 06:40:35 → 06:43:06 |
| 21.3 (21.3.0) Git:20251031-a3a448d26b, main profile | `C:\Users\nguyentiendat07\AppData\Roaming\Kodi\kodi.log` | 91,685 B | 06:56:43 → 06:57:02, **cut off mid-run** |

No `.old.log` exists beside any of them. `grep -c Traceback` returns **0** on all four.

**Kodi 19.5 — the zip was offered and mechanically refused:**

```
06:34:27.053 CAddonMgr::FindAddons: xbmc.python v3.0.0 installed
06:34:55.600 CAddonInstaller: installing from zip '…\stage\plugin.onedrive.kn-1.0.0.zip'
06:34:55.603 DEBUG CAddonInstallJob[plugin.onedrive.kn]: requires xbmc.python version 3.0.1 which is not available
06:34:55.603 ERROR CAddonInstallJob[plugin.onedrive.kn]: The dependency on xbmc.python version 3.0.1 could not be satisfied.
```

`plugin.onedrive.kn` appears three times in that log and never as an installed add-on; `entrypoint.py` and
`service.py` appear zero times; and `kodi-19.5\portable_data\addons\` holds no `plugin.onedrive.kn` today.

**Kodi 20.5 — installed from the zip, both entry points ran, all three sub-services started:**

```
06:38:27.726 CAddonInstaller: installing from zip '…\stage\plugin.onedrive.kn-1.0.0.zip'
06:38:27.860 CAddonMgr::FindAddon: plugin.onedrive.kn v1.0.0 installed
06:38:27.863 CPythonInvoker(1, …\plugin.onedrive.kn\service.py): start processing
06:38:27.873 …: instantiating addon using automatically obtained id of "plugin.onedrive.kn" dependent on version 3.0.1 of the xbmc.python api
06:38:29.155 [plugin.onedrive.kn][service-export-14836]: Service 'export' started.
06:38:29.155 [plugin.onedrive.kn][service-player-46476]: Service 'player' started.
06:38:29.165 [plugin.onedrive.kn][service-download-3700]: Service 'download' started in port 56216
06:39:20.100 CPythonInvoker(3, …\plugin.onedrive.kn\entrypoint.py): start processing
06:39:20.462 …entrypoint.py: script successfully run
```

The real sign-in route was also driven there, not the smoke action, and the dialog opened and closed cleanly:

```
06:39:24.153 CScriptRunner: running add-on script OneDrive KN('plugin://plugin.onedrive.kn/', '-1', '?action=_add_account&content_type=video')
06:39:26.508 Loading skin file: D:\…\plugin.onedrive.kn\resources\skins\default\1080i\pin-dialog.xml
06:39:31.728 ------ Window Deinit (…\pin-dialog.xml) ------
```

**Kodi 22.0-BETA1 — installed from the zip, service ran, all three sub-services started:**

```
06:41:10.133 CAddonInstaller: installing from zip '…\stage\plugin.onedrive.kn-1.0.0.zip'
06:41:10.234 Addon Manager: Found addon: 'plugin.onedrive.kn v1.0.0'
06:41:10.245 …\service.py: instantiating addon … dependent on version 3.0.1 of the xbmc.python api
06:41:11.668 Service 'export' started.  /  Service 'player' started.
06:41:11.678 Service 'download' started in port 57005
06:42:51.297 …\entrypoint.py: script successfully run
```

**Kodi 21.3, main profile — the run that was stopped.** It reached the smoke action and the first dialog, and the
log simply ends there:

```
06:57:02.431 CPythonInvoker(1):  ?action=_dialog_smoke
06:57:02.728 dialog-smoke: addon id: plugin.onedrive.kn
06:57:02.728 dialog-smoke: dialog scriptPath: C:\…\addons\plugin.onedrive.kn\
06:57:02.728 dialog-smoke: profile path: C:\…\userdata\addon_data\plugin.onedrive.kn\
06:57:02.734 Loading skin file: C:\…\plugin.onedrive.kn\resources\skins\default\1080i\pin-dialog.xml
```

### What this evidence is **not**

It is uncontrolled. It is kept because the bytes were already written, and it is **not** an acceptance row. Stated
plainly, so nobody later mistakes it for one:

- **No profile was verified clean before any of the four runs.** Sibling cloud-drive add-ons happen not to appear in
  any of the logs, which is weaker than having checked for them, and `addon_data` was never inspected beforehand.
- **No run reached the settings walk.** The 22-row label check exists only for Android.
- **No run reached the export dialogs.** `export-main-dialog.xml` and `export-schedule-dialog.xml` appear **zero**
  times across all four logs. Only `pin-dialog.xml` was ever loaded on Windows.
- **No run produced a QR image path.** The two-differing-paths check has no Windows evidence at all — the 21.3 run
  was stopped with the first dialog on screen, before any path was logged.
- **Nothing was seen.** No screenshot was taken on Windows, and none of the four runs was observed by anyone signing
  this record. Only the log bytes survive.

**Therefore no Windows acceptance row is filled, and none is claimed.**

### Two corrections this harvest forces on the record above

**1. The "not runnable from this shell" blocker is not a standing fact.** The superseded subsection above records
Kodi dying at `CApplication::Create: Unable to create window` because the interactive session was disconnected. That
was accurate at 23:23 on 2026-08-22. By 06:34 on 2026-08-23 all four Kodi versions started, created windows and ran
to a clean exit. The blocker was a property of a session that has since changed.

**2. The Kodi 19 refusal was exercised — but not under a controlled run.** The subsection above records only a manual
*extraction* onto Kodi 19, and it is right to refuse to read that as a pass. The harvested 19.5 log shows something
different and stronger: the actual zip was handed to Kodi 19.5's installer and was refused, for the exact declared
reason, with `xbmc.python v3.0.0` on that Kodi against the manifest's `3.0.1`. That is precisely the mechanism
**KODI-01** asserts.

This does not promote the row to an acceptance pass — the run was unobserved and the profile unverified — but it is
no longer accurate to describe the refusal as untested. The honest state of KODI-01 is recorded under
**Requirements** below.

### Two defects in the test method — not in the product

The interrupted executor wanted to redo its smoke pass over two concerns. Both are defects in its own rig. Neither
was ever a finding against `resources/lib/addon.py` or the vendored tree, and neither should be re-opened as a
product bug.

**1. F10 was not in the keymap on disk when Kodi started.** The rig intended to trigger the smoke action from a key
binding, and wrote the binding to the profile's keymap directory after Kodi had already read that directory at
startup. Kodi therefore never had the binding. This is an ordering mistake in the harness — a file written after the
program that reads it had started — and says nothing about the add-on. The action was reached over JSON-RPC instead,
which is the route the Android row used throughout.

**2. The QR write met a directory the plugin root had already created.** The rig treated "the QR directory already
exists" as suspicious. It is not: opening the plugin root constructs the add-on's own profile directory as a matter
of course, so by the time the smoke action runs the directory is legitimately present. The guard actually under test
is the **per-invocation filename**, not the absence of the directory. The check was aimed at the wrong object.

### The Android row's instrument gap

The one filled acceptance row ran on an emulator: AVD `kodi_api30`, **Android 11 / API 30**, software rendering
through SwiftShader. The device this add-on is for is a **TCL television running Android TV 12 / API 31** — one API
level higher, a different form factor, a real GPU, a real remote and a low-end SoC. **The acceptance row did not run
on the target hardware, and it is one API level below it.**

The row remains this phase's evidence, and it is sound evidence for what it covers: the add-on loads under its own
id, both entry points run, the service starts at login, all three dialogs construct and render from this add-on's
own skin directory, two QR constructions produce two different paths, and the log carries zero tracebacks. Those are
API-level facts and an emulator is a fair instrument for them.

It is **not** evidence for API 31 behaviour, D-pad focus order, ten-foot readability, real GPU or codec behaviour,
low-end performance, or a vendor ROM's storage rules. None of those was checked and none is claimed.

### Standing deferred claims — still not passed

| Claim | Status |
|---|---|
| `Request.HTTP_TIMEOUT_SECONDS = 30` is the right value | **Unmeasured.** No network throttling was applied in any run, on any platform, in 01-06 or here. The value's entire justification is marginal Android TV Wi-Fi, and no run has been anywhere near that condition. It must not be reported as validated. |
| Whether a vendor ROM blocks shell access to `Android/data` | **Unanswerable on the instruments used.** The emulator is an AOSP image with no vendor storage policy, unchanged since 01-01. The question resolves the first time the add-on runs on the TCL. |

### Requirements

| Requirement | State | Note |
|---|---|---|
| **KODI-02** — installs and runs on Kodi 20 Nexus, 21 Omega and 22 Piers | **Unchecked. Not satisfied.** | Narrowed by the owner's decision: Windows is not a target and the multi-version matrix is not pursued. Uncontrolled logs show 20.5 and 22.0-BETA1 installing from the zip and starting both entry points, and 21.3 loading and running the plugin — but none of that is a controlled acceptance row, and 21 Omega was only ever exercised on Android. Verification of this requirement, in whatever form the project still wants it, moves out of Phase 1. |
| **KODI-01** — manifest declares `xbmc.python 3.0.1`; installs on 20/21/22, rejected by 19 | **Left checked, with a gap stated here.** | The install half is evidenced on Android (21.3, controlled) and on Windows 20.5 / 22.0-BETA1 (uncontrolled). The **Kodi 19 refusal half was never exercised under a controlled, observed run** — it is evidenced only by the harvested 19.5 log quoted above, from an unobserved run on an unverified profile. That log is specific and matches the declared mechanism exactly, which is why the checkbox is not being silently removed. **It is flagged here for the owner to decide**: accept the harvested log as sufficient, or re-run the refusal once under controlled conditions. |

No other requirement's checkbox was touched by this closure.

### What moves to a later phase

The first acceptance run on the **TCL Android TV 12** is deferred to **Phase 3 (Authentication)**, and is recorded
there. The reason is timing, not priority: Phase 1 leaves the add-on able to install, load and open its dialogs and
nothing else, so a TCL run today would prove very little beyond what the emulator already showed. Phase 3 is the
first point at which the add-on does something a person can actually use, which is the first run worth spending the
target device's time on. The TCL is the primary acceptance device from Phase 3 onward, not a pre-release checkbox.

## Deviations from plan

### 1. [Rule 1 — Bug] The manifest failed schema validation

- **Found during:** Task 2, first `kodi-addon-checker` run
- **Issue:** `<extension point="xbmc.service" library="service.py" start="login" />`. The `start`
  attribute was removed with Kodi 19; the schema for `xbmc.service` accepts `point`, `id`, `name`
  and `library` only. An ERROR finding, and the plan's criterion requires none.
- **Fix:** the attribute removed. On Kodi 20, 21 and 22 — the only versions this add-on targets —
  every service starts after profile login regardless, so no runtime behaviour changes. Verified
  on the device: the service starts at login and all three sub-services report started.
- **Files:** `addon.xml` — **Commit:** `b5065ab`

### 2. [Rule 1 — Bug] The sign-in broker is not dead, and the record said it was

- **Found during:** Task 3, confirming the recorded deviations rather than assuming them
- **Issue:** Every prior record in this phase states that `drive-login.herokuapp.com` has been
  offline since November 2022 and that sign-in, account listing, browsing and playback are
  therefore all unreachable. Driving `_add_account` on the instrument showed otherwise:

  ```
  Request URL: https://drive-login.herokuapp.com/ip                → answered
  Request URL: https://drive-login.herokuapp.com/pin  (provider=onedrive)
    → {"pin":"…","password":"<redacted>","owner":"<redacted-public-ip>","provider":"onedrive"}
  Request URL: https://drive-login.herokuapp.com/pin/<code>        → polling, as designed
  ```

  The QR dialog then rendered the live code with a 78-second expiry and its own *Your source id
  is: …* line. Confirmed independently from this machine: `GET /` and `GET /ip` both return
  **HTTP 200**.
- **Why it matters beyond this plan:** VND-09 forbids signing off an acceptance pass while a
  departure from the recorded deviations is known and unrecorded. This was exactly that. Left
  alone it would have become the premise every later phase reasoned from — including the premise
  that the QR dialog is unreachable by clicking, which is false.
- **Fix:** `VENDORED.md` deviation 1 and `README.md`'s status section rewritten on the measurement.
  The plan to replace the flow is **unchanged and unweakened**: a third party still holds the OAuth
  exchange and still sees which account is being connected. Being alive is not the same as being
  something to depend on.
- **What was *not* established:** that a sign-in **completes**. That needs a human at a browser
  with a Microsoft account, and it was deliberately not attempted.
- **Files:** `VENDORED.md`, `README.md` — **Commit:** `49ad7f6`

### 3. [Rule 1 — Bug] The smoke action left its scratch store in the profile

- **Found during:** Task 3, reading the profile directory after the pass rather than trusting the code
- **Issue:** the throwaway export store persisted after every run. Two causes, both silent:
  Kodi's `rmdir` will not remove a directory that still holds files, and on Android it will not
  treat the argument as a directory at all without a trailing separator. Both report failure by
  returning `False` rather than by raising, so the error handler never fired.
- **Fix:** empty the directory first, pass a trailing separator, and **log what the removal
  returned** instead of assuming. Three attempts, each verified on the device; the third produced
  `dialog-smoke: scratch store removed: True` and a profile with no scratch directory left in it.
- **Files:** `resources/lib/addon.py` — **Commits:** `be4f9c8`, `831ac7e`

### 4. [Deviation — instrument] The Android pass ran before the Windows pass, not after

The plan sequences Windows first so that a Windows result is never read as evidence for Android.
The ordering could not be honoured because the Windows leg is blocked. The reasoning behind the
ordering is unharmed: **no Android result here is offered as evidence for Windows**, and the
Windows rows are recorded as unfilled rather than inferred.

### 5. [Scope — owner's decision] The Windows leg and the install matrix are dropped

- **Found during:** Task 3, while the Windows run was in progress
- **Change:** the owner stopped the Windows matrix and directed that the plan close on the Android
  row. Windows is not a target for this add-on; the target is a TCL television running Android TV
  12, and backwards compatibility across Kodi versions and desktop platforms is not being pursued.
- **Why this is not a quiet pass:** KODI-02 stays **unchecked**, the Windows rows stay **unfilled**,
  and the surviving logs are labelled uncontrolled rather than promoted to acceptance rows. Nothing
  became true by being descoped.
- **Consequence recorded elsewhere:** the TCL acceptance run moves to Phase 3, and ROADMAP.md is
  corrected to name the TCL as the primary acceptance device rather than a release-time checkbox.
- **Files:** `.planning/phases/01-vendor-lift/01-07-SUMMARY.md`, `.planning/ROADMAP.md`

## Findings for later phases

- **Kodi's `addoninformation` dialog crashes this emulator for every add-on**, including
  `service.xbmc.versioncheck`. It is an instrument limitation, not a defect in this add-on —
  established by reproducing it with an unrelated add-on rather than by assuming.
- **`ActivateWindow(addonsettings, <id>)` opens the settings dialog without the add-on bound to
  it** and renders empty with a garbled title. That is not a defect either; the working route is
  the add-on browser context menu, and it renders correctly.
- **Two `error` lines appear in the pass log from the vendored skin XMLs**: `Control has invalid
  animation type (no condition or no type)`, once each as `export-schedule-dialog.xml` and
  `export-main-dialog.xml` load. Inherited from upstream, harmless to rendering, worth a look when
  the skins are next touched.
- **Placing an add-on on Android by `adb push` as root is not enough.** The tree lands as
  `root:root` with the generic `storage_file` SELinux label, and Kodi then sees a broken add-on
  with no useful error. Ownership must be set to the app's uid and the label to
  `media_rw_data_file` with the app's categories. The same trap silently corrupted `guisettings.xml`
  and made Kodi fail with `unable to load settings`. Anyone repeating the Android leg needs this.
- **The `download` service binds an ephemeral port** (`44485` in this run) and writes it back as an
  undeclared `download.service.port` setting, exactly as VENDORED.md predicts. The harvested Windows
  logs show the same behaviour with different ports — `56216` on Kodi 20.5, `57005` on 22.0-BETA1,
  `51489` on 21.3 — so it is the design, not an Android artefact.
- **Kodi 22 logs a `SyntaxWarning` out of the vendored tree, at `error` level.** New, and visible
  only because Kodi 22 ships a newer Python:

  ```
  …\vendor\clouddrive_common\remote\oauth2.py:70: SyntaxWarning: "\/" is an invalid escape sequence.
  Such sequences will not work in the future. Did you mean "\\/"? A raw string is also an option.
  ```

  It is a warning, not a failure — the service started normally straight after it — but the wording
  says the sequence stops working in a future Python. It is an inherited upstream defect and a
  one-character fix; worth doing whenever the vendored tree is next touched.

## Deferred issues

- **The install matrix (four Kodi versions) and the Windows acceptance row** — **descoped by the
  owner's decision**, not deferred for later attention. Windows is not a target. KODI-02 stays
  unchecked. See *The Windows leg — closed by decision, not by evidence* above.
- **The first acceptance run on the TCL Android TV 12** — deferred to **Phase 3**, where it is
  recorded. Deferred on timing, not on priority: the TCL is the primary acceptance device, and
  Phase 3 is the first phase after which a run on it proves something the emulator could not.
- **The Kodi 19 refusal under a controlled run** — evidenced only by a harvested, unobserved log.
  The owner decides whether to accept it or re-run it once cleanly; see *Requirements* above.
- **`Request.HTTP_TIMEOUT_SECONDS = 30` is still unmeasured.** No network throttling was applied
  here either. 01-06 deferred it to this pass and this pass could not measure it: the instrument
  runs on a desktop's wired connection, and the value's entire justification is marginal Android TV
  Wi-Fi. **It must not be reported as validated.**
- **Whether a vendor ROM blocks shell access to `Android/data`** remains unanswerable on an AOSP
  image, unchanged from 01-01.
- **Packaging** must produce a directory named after the add-on id and must exclude `.gitignore`,
  `.project` and `.pydevproject`. Both are handled by a scratch staging script today and belong in
  a build script.

## Known stubs

The `_dialog_smoke` action is a **deliberate, documented debug affordance**, not a stub: it is a
complete implementation of what it claims to do. It is recorded in `VENDORED.md` under recorded
behaviour deviations and scheduled for removal or a debug-only gate before release, which is the
condition VND-10 attaches to it.

## Self-Check

- `VENDORED.md`, `CREDITS.md`, `README.md`, `resources/lib/addon.py`, `addon.xml` — all present
- `c9d9a0f3cf8cc5e124e8295db4acc0415d4b77af`, `b5065ab`, `9db3ae3`, `49ad7f6`, `be4f9c8`,
  `831ac7e` — all present in history
- `git show --name-only --format= c9d9a0f…` lists only `resources/lib/addon.py`
- No tracked file deleted by any commit in this plan
- `python -m pytest tests/test_vendor_gates.py -q` → **22 passed**
- `python -m compileall -q resources/ entrypoint.py service.py` → exit 0
- `D:\KodiPortable\_logs\android-acceptance\kodi-android-acceptance.log` exists, 146,341 bytes,
  0 tracebacks
- Working tree clean after every commit

**Closure pass, 2026-08-23:**

- All four harvested Kodi logs exist at the paths quoted, at the sizes quoted; each was read only
- No Kodi process was started, no add-on installed or removed, nothing under `%APPDATA%\Kodi` or
  `D:\KodiPortable` written — the closure touched `.planning/` only
- `python -m pytest tests/test_vendor_gates.py -q` → **22 passed**, no assertion edited
- KODI-02 confirmed still unchecked in REQUIREMENTS.md; no other checkbox altered

**Self-Check: PASSED**

## Status: COMPLETE — closed under a scope reduction

Tasks 1 and 2 are complete and committed. Task 3 is closed: its Android row is filled and stands as
this phase's acceptance evidence, and its Windows rows are **descoped by the owner's decision**
rather than filled. Windows is not a target for this add-on.

What that leaves open is written down rather than absorbed: **KODI-02 is not satisfied and stays
unchecked**, the Kodi 19 refusal has only uncontrolled evidence, the 30-second HTTP timeout is
still unmeasured, the vendor-ROM storage question is still unanswerable, and the acceptance row ran
on an Android 11 emulator rather than on the Android 12 TCL the add-on is actually for. The first
run on that hardware is recorded against Phase 3.

---
*Phase: 01-vendor-lift*
*Recorded: 2026-08-23*
