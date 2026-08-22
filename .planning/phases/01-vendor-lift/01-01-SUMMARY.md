---
phase: 01-vendor-lift
plan: 01
subsystem: environment
tags: [kodi-addon-checker, fork-detach, adb, android-emulator, kodi-matrix, portable-install]

# Dependency graph
requires: []
provides:
  - "kodi-addon-checker 0.0.36 installed on the development machine, registry-confirmed rather than assumed"
  - "A detached repository: no upstream fork network, full history intact, root commit unchanged"
  - "A four-version Windows Kodi matrix (19.5, 20.5, 21.3, 22.0-BETA1), three of them portable and proven non-contaminating"
  - "An Android 11 / API 30 acceptance instrument reachable over adb, running Kodi 21.3, whose kodi.log can be retrieved"
  - "The measured boundary of adb log retrieval on Android 11+: app-private paths need root, public paths do not"
affects: [01-07, phase-02-ci]

# Tech tracking
tech-stack:
  added:
    - "kodi-addon-checker 0.0.36 (development-only; never shipped inside the add-on zip)"
  patterns:
    - "Verify the registry entry and the project home before installing, not after"
    - "Checksum every downloaded binary against the vendor-published digest, because the bytes arrive from a geo mirror and the digest does not"
    - "Prove environment isolation empirically; a clean profile asserted is not a clean profile"

key-files:
  created:
    - .planning/phases/01-vendor-lift/01-01-SUMMARY.md
  modified: []

key-decisions:
  - "Kodi 22 is pinned to 22.0 Piers beta1 from the releases mirror rather than a nightly: a fixed version string and a published checksum make a KODI-02 result reproducible, which a moving nightly cannot"
  - "The Android instrument is an emulator, not a physical phone; the phone was unavailable and the emulator is approved as its replacement, with its limits recorded rather than papered over"
  - "The Android TV image was tried first as the closer analogue and rejected on evidence: it is a production build, adb root is refused, and the log pull is therefore impossible on it"
  - "Portable Kodi installs live on D:\\KodiPortable, not under Program Files, because portable mode must write portable_data beside the executable and Program Files is not user-writable"

requirements-completed: [SETUP-06, ID-05]

metrics:
  duration: "~2h"
  completed: 2026-08-22
  tasks: 3

status: complete
---

# Phase 01 Plan 01: Environment and Identity Summary

Established the two facts the phase could not establish for itself: the repository is its own
project rather than a node in the upstream fork network, and a test environment exists in which a
clean-profile result means something.

## Task 1 — Manifest checker installed, pre-detach commit count recorded

`pip index versions kodi-addon-checker` reported, verbatim:

```
kodi-addon-checker (0.0.36)
Available versions: 0.0.36, 0.0.35, 0.0.34, 0.0.33, 0.0.32, 0.0.31, 0.0.30, 0.0.29, 0.0.28,
0.0.27, 0.0.26, 0.0.25, 0.0.24, 0.0.23, 0.0.22, 0.0.21, 0.0.20, 0.0.19, 0.0.18, 0.0.17, 0.0.16,
0.0.15, 0.0.14, 0.0.13, 0.0.12, 0.0.11, 0.0.10, 0.0.9, 0.0.8, 0.0.7, 0.0.6, 0.0.5, 0.0.4, 0.0.3,
0.0.2, 0.0.1
```

This settles research assumption **A7**, which recorded 0.0.36 as `[ASSUMED]` from earlier project
research rather than from a registry read. 0.0.36 is genuinely the current release.

Legitimacy was confirmed before installing, not after: PyPI metadata gives
`home_page = https://github.com/xbmc/addon-check` and `author = Team Kodi`, matching the research
Package Legitimacy Audit exactly.

- `kodi-addon-checker --version` → `kodi-addon-checker 0.0.36`, exit 0
- Pre-detach commit count: `git rev-list --count HEAD` = **129**
- Root commit: `2482723eae27a19c2b44655c82828172e1a1d846` — "Create README.md", Carlos Guzman,
  2015-02-22. This is the attribution record ID-05 exists to protect.

The checker was deliberately **not** run against the repository. At that point `addon.xml` still
carried the upstream identity and the external module import, so its output would have been noise.

## Task 2 — Repository detached from the upstream fork network

- **Status: detached.** The repository is no longer a fork.
- **Performed by: Kenny Nguyen**, the repository owner.
- **Verification method: visual confirmation in the browser by the owner.** No API verification was
  performed and none was possible: the repository is private, so
  `https://api.github.com/repos/anhyeuviolet/kodi.plugin.onedrive` returns 404 unauthenticated.
  This is stated plainly because claiming a machine check that did not happen would be worse than
  recording a human one that did.

History is intact. Nothing was squashed, rebased or force-pushed.

| Measurement | Before | After |
|---|---|---|
| `git rev-list --count HEAD` (local) | 129 | **152** |
| `git rev-list --count origin/matrix` | 113 | **113** |
| Root commit hash | `2482723e` | `2482723e` |

Both counts clear the 113 floor. The local rise from 129 to 152 is this phase's own plans 01-02
through 01-06 landing while Task 2 was blocked, not an artefact of the detach. `origin/matrix` is
39 behind HEAD and zero ahead, so there is no remote work to reconcile.

A subtlety worth carrying to 01-07: **113 is exactly the remote count**, which is the number GitHub
displays. A reader comparing the GitHub page against a local `git rev-list --count HEAD` will see
113 against 152 and should not read that gap as commit loss.

## Task 3 — Test environment

### Windows profile: clean, and re-confirmed after every launch

`%APPDATA%\Kodi\addons` listing, verbatim:

```
metadata.album.universal
metadata.artists.universal
metadata.common.fanart.tv
metadata.generic.albums
metadata.themoviedb.org.python
metadata.tvshows.themoviedb.org.python
packages
service.xbmc.versioncheck
temp
```

None of `plugin.onedrive`, `plugin.googledrive`, `plugin.dropbox`,
`script.module.clouddrive.common` is present. `%APPDATA%\Kodi\userdata\addon_data` holds only
`peripheral.joystick` and `skin.estuary`.

### The Kodi version matrix

| Kodi | Version string | Python | Location |
|---|---|---|---|
| 19 Matrix | `19.5` | 3.8 | `D:\KodiPortable\kodi-19.5` |
| 20 Nexus | `20.5` | 3.8 | `D:\KodiPortable\kodi-20.5` |
| 21 Omega | `21.3` | 3.8 | `C:\Program Files\Kodi` (pre-existing) |
| 22 Piers | `22.0-BETA1` | **3.14** | `D:\KodiPortable\kodi-22.0-beta1` |

Downloads, all from `https://mirrors.kodi.tv/releases/windows/win64/`, each verified against the
vendor-published `.sha256`:

| File | Bytes | SHA256 | Served by | Verify |
|---|---|---|---|---|
| `kodi-19.5-Matrix-x64.exe` | 80,055,401 | `5e2177703ab6b0ec8397ad209956a65898021352b983d2917862efe2b6556f4c` | `ftp.snt.utwente.nl` | OK |
| `kodi-20.5-Nexus-x64.exe` | 82,013,250 | `f5585bb12f5027eb86dcfac60a790faffd6ac7aa06cdc0d5c47b87ef0ee7a9ea` | `kodi.mirror.garr.it` | OK |
| `kodi-22.0-Piers_beta1-x64.exe` | 74,223,493 | `784a321db28d4a3176317b310c4df8601d195a187896266ea2f4b7567d10da8a` | `ftp.halifax.rwth-aachen.de` | OK |

Two operational notes for anyone repeating this. The canonical URL answers with a **302 to a geo
mirror** — each of the three downloads was served by a different third party, which is precisely
why the digest (fetched from `mirrors.kodi.tv`) is the thing that matters. And the `.sha256` files
**return 200 but are not listed in the directory index**, so they must be requested by name.

Installs were produced by extracting the NSIS installers with 7-Zip rather than running them, so
no registry entries were created and no installer could redirect a profile.

### Portable isolation: proven, not assumed

The clean Kodi 21.3 profile is the instrument SETUP-06 depends on, and a Kodi 19 binary opening a
Kodi 21 profile could have migrated its databases and destroyed it. So the profile was backed up
first, then each build launched with `-p`.

All three logged their own profile path, for example:

```
special://masterprofile/ is mapped to: D:\KodiPortable\kodi-19.5\portable_data\userdata
```

After all three launches, `%APPDATA%\Kodi` was byte-identical to its pre-test state: **581 files**,
listing SHA256 `b9dc12c15562b96aeac12343bb478288400aeddf63295df6cfc7bacbb02379ee` unchanged, and
nothing modified. A known-clean snapshot is retained at
`D:\KodiPortable\_backup\APPDATA-Kodi-pre-portable-test` as a restore point for the rest of the
phase.

### The Android instrument

| Fact | Value |
|---|---|
| `adb devices` | `emulator-5554	device` (`product:sdk_gphone_x86_64`, `transport_id:5`) |
| AVD name | `kodi_api30` |
| System image | `system-images;android-30;google_apis;x86_64` |
| `ro.build.version.release` | **11** |
| `ro.build.version.sdk` | 30 |
| `ro.build.type` | `userdebug` |
| Kodi installed | **21.3** (`primaryCpuAbi=x86`, from `kodi-21.3-Omega-x86.apk`) |
| `kodi.log` pull | **succeeded**, 33,693 bytes, 314 lines |
| Local path | `D:\KodiPortable\_logs\kodi-emulator-api30.log` |

APK provenance: `https://mirrors.kodi.tv/releases/android/x86/kodi-21.3-Omega-x86.apk`,
69,837,353 bytes, SHA256 `cf53a43522743f937ec0644991c625da0796d5705fb2081bd005430927fe7755`,
verified OK, served by `mirror.netcologne.de`. Kodi publishes `arm`, `arm64-v8a` and `x86` for
Android — there is no `x86_64` APK — and the x86 build installs and runs on the x86_64 image.

Log header confirming the instrument is real:

```
Starting Kodi (21.3 (21.3.0) Git:20251031-a3a448d26b). Platform: Android x86 32-bit
Running on Google sdk_gphone_x86_64 with Android 11.0.0 API level 30
```

Getting Kodi to first run is not a single command. It blocks on its own `Info` dialog
("Kodi requires access to your device media and files to function... or Kodi will exit"), then on
the system permission dialog, then on the *All files access* settings page. Granting
`READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE` and `RECORD_AUDIO` via `pm grant` plus
`appops set org.xbmc.kodi MANAGE_EXTERNAL_STORAGE allow` and dismissing the dialogs is what
finally produced `special://masterprofile` and the log. Plan 01-07 should budget for this rather
than expect `monkey` alone to yield a usable instance.

## Deviations from Plan

### 1. The Android instrument is an emulator, not a physical phone

**Plan text:** an Android phone running Kodi, reachable over adb.
**What happened:** no phone could be connected; an emulator was approved as its replacement.

What the emulator **legitimately establishes**: scoped-storage behaviour is an OS-level property of
the API level, identical on any Android 11 device. The Android 11 storage-regime argument behind
01-06's `eval()` removal — that from Android 11 an app's own `Android/data` bypasses FUSE, so
`chmod 0600` genuinely applies — is therefore genuinely exercised here. Storage paths, profile
mapping, file mode bits and `O_EXCL` all follow the API level.

What it **cannot** establish, and must not be read as establishing:

- **D-pad focus, ten-foot readability and low-end performance.** Unchanged from the existing CI-06
  exceptions; an emulator is no better than a phone here and in the TV case worse.
- **Real-hardware GPU, codec and decoder behaviour.** The emulator ran on `swiftshader_indirect`.

### 2. `Request.HTTP_TIMEOUT_SECONDS = 30` remains unmeasured — DEFERRED, not passed

01-06 recorded the value as coming from a recommended range rather than a measurement and deferred
validation to 01-07's acceptance pass. Its entire justification is marginal Android TV Wi-Fi. An
emulator on a desktop's wired connection cannot exercise that, and **no network throttling was
applied in this plan** — no `-netdelay`/`-netspeed` values were set, so not even a partial signal
was collected. The claim stands exactly where 01-06 left it: **unmeasured**.

### 3. Whether a vendor ROM blocks shell access to `Android/data` is now unanswerable — DEFERRED

The AOSP/`google_apis` image carries no vendor restrictions. The successful pull here proves the
retrieval **mechanism** works and gives 01-07 a working procedure, but proves nothing about any
real handset or TV box, where a vendor ROM may still restrict access. Both halves are true and
both are recorded.

### 4. A stronger and more general finding: on Android 11+, pulling an app-private log needs root

This was measured, not inferred, and it matters more than the vendor-ROM question because it
applies to **every** Android 11+ device, stock included:

| Shell identity | `adb pull /sdcard/Android/data/org.xbmc.kodi/.../kodi.log` |
|---|---|
| root (`adb root`, userdebug build) | succeeds — 33,693 bytes |
| `shell` (`adb unroot`, i.e. real hardware) | **`Permission denied`** |

The plan anticipated that "some vendor ROMs restrict shell access to `Android/data`". The reality
is broader: stock Android 11 restricts it for the `shell` user on all devices, and `adb root` is
refused on any production build. Plan 01-07's Android leg cannot rely on a direct pull from a
retail device.

A workaround was measured and works: `/sdcard/Download` **is** writable and pullable by the
non-root `shell` user. Copying the log to a public directory from inside Kodi, then pulling from
there, retrieves it without root. 01-07 should adopt that route.

### 5. The Android TV image was tried first and rejected on evidence

The TV image was the closer analogue to the deployment target and was attempted first:
`system-images;android-30;android-tv;x86` downloaded and installed cleanly, AVD `kodi_tv_api30`
booted as `AOSP TV on x86`, Android 11 / API 30. It was rejected because it is a **production
build** (`ro.build.type=user`, `ro.build.tags=dev-keys`): `adb root` returns
`adbd cannot run as root in production builds`, `/sdcard/Android/data/` is `Permission denied`, and
the log pull — the one capability 01-07 cannot work around — is therefore impossible on it. The
fallback to `google_apis;x86_64` was taken for that reason and no other. The AVD is left in place;
it remains the better instrument for any future question that does not require reading app-private
files.

### 6. Kodi 22 pinned to beta1 rather than a nightly

The plan asked for "a Kodi 22 nightly". `22.0-Piers_beta1` is the only 22.x on the releases mirror
and is the better instrument: a fixed version string and a published checksum make a KODI-02 result
reproducible, which a moving nightly target cannot.

### 7. `pip install` pulled a dependency closure

The acceptance criterion "No package other than `kodi-addon-checker` is installed by this task" is
not literally satisfiable, because the wheel declares dependencies. Captured by `pip freeze` diff,
the installed set was `kodi-addon-checker==0.0.36` plus its declared closure: `elementpath==5.1.4`,
`mando==0.7.1`, `polib==1.2.0`, `radon==6.0.1`, `xmlschema==4.3.2`. Nothing outside that closure was
installed; `requests`, `urllib3`, `certifi`, `six` and `colorama` were already satisfied. No
substitution or alternate-name install occurred.

## Findings for later phases

**Kodi 22 ships Python 3.14; Kodi 19, 20 and 21 all ship Python 3.8.** That is a six-release jump
inside the version matrix this add-on must span, and it lands directly on code being vendored right
now. It bears on the `eval()`→JSON swap in 01-06 and on anything in `clouddrive_common` that relies
on stdlib modules removed across 3.12–3.14. Worth an explicit compatibility gate before Phase 2
leans on the matrix.

## Verification

| Check | Result |
|---|---|
| `kodi-addon-checker --version` exits 0 | pass — `kodi-addon-checker 0.0.36` |
| `git rev-list --count HEAD` ≥ 113 before and after detach | pass — 129 before, 152 after |
| Root commit hash unchanged | pass — `2482723e` both sides |
| GitHub page carries no "forked from" line | pass — visual confirmation by owner (private repo; no API check possible) |
| `adb devices` lists the instrument in state `device` | pass — `emulator-5554	device` |
| Instrument runs Kodi, Android ≥ 11 | pass — Kodi 21.3, Android 11 (API 30) |
| `adb pull` retrieves `kodi.log` | pass with root; **fails as non-root** (see Deviation 4) |
| Windows addons directory free of the four forbidden ids | pass — before and after all launches |
| Four Kodi version strings recorded | pass — 19.5, 20.5, 21.3, 22.0-BETA1 |

## Prohibition

**SETUP-06 — resolved and held.** No sibling cloud-drive add-on was installed on the Windows test
profile at any point. The profile was verified clean before the work, and verified byte-identical
after three portable Kodi launches.

## Self-Check: PASSED

- `.planning/phases/01-vendor-lift/01-01-SUMMARY.md` exists
- Commit `40eea68` exists in history
- `D:\KodiPortable\_logs\kodi-emulator-api30.log` exists (33,693 bytes)
- `kodi.exe` present in each of `kodi-19.5`, `kodi-20.5`, `kodi-22.0-beta1`
- The SUMMARY commit deletes no tracked file
