---
phase: 1
slug: vendor-lift
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` 8.3.5 on CPython 3.11.9 — already installed; matches the 3.11 Kodi 20/21 bundle |
| **Config file** | none — Wave 0 adds `pytest.ini` (`testpaths = tests`, nothing else) |
| **Quick run command** | `python -m pytest tests/test_vendor_gates.py -q` |
| **Full suite command** | `python -m pytest tests -q && python -m compileall -q resources/ entrypoint.py service.py` |
| **Estimated runtime** | < 2 seconds (quick), < 10 seconds (full) |

Every assertion in this phase is over the repository as text or as XML. No Kodi stub library is
needed and none is introduced here — Phase 2 owns `Kodistubs`, fixtures and the layering test.
Adding them now is scaffolding this phase does not use.

---

## Sampling Rate

- **After every task commit:** `python -m pytest tests/test_vendor_gates.py -q` — under 2 s, so
  there is no excuse to skip it. Every commit in this phase must leave the add-on installable and
  the gate green, because the phase's entire value is attributability.
- **After every plan wave:** quick run + `python -m compileall -q` + `kodi-addon-checker . --branch=omega`
  once it is installed.
- **Before `/gsd-verify-work`:** full gate green, install matrix complete, and one full manual
  acceptance pass on Windows and on the Android phone, on a clean profile, both logs archived.
- **Max feedback latency:** 2 seconds

---

## Per-Requirement Verification Map

Task-level IDs are assigned when the plans are written; this map is the requirement-level contract
the plans must satisfy.

| Req | Behaviour | Threat Ref | Test Type | Automated Command | File Exists | Status |
|-----|-----------|------------|-----------|-------------------|-------------|--------|
| VND-01 | Vendored tree matches upstream `matrix` @ `df68e9a` | — | unit | `pytest tests/test_vendor_gates.py::test_vendored_sha_recorded -q` | ❌ W0 | ⬜ pending |
| VND-02 | No `clouddrive.common` reference outside the vendored path | — | unit | `::test_no_legacy_package_prefix` | ❌ W0 | ⬜ pending |
| VND-03 | No second top-level `resources` package; skins and strings merged | — | unit | `::test_resources_merged` | ❌ W0 | ⬜ pending |
| VND-04 | Zero `script.module.clouddrive.common` literals | — | unit | `::test_no_hardcoded_module_id` | ❌ W0 | ⬜ pending |
| VND-05 | Zero `eval(`/`exec(`; store round-trips through JSON | T-1-01 | unit | `::test_no_eval` + `::test_store_json_roundtrip` | ❌ W0 | ⬜ pending |
| VND-06 | Every outbound HTTP call carries `timeout=` | T-1-02 | unit | `::test_all_http_calls_have_timeout` | ❌ W0 | ⬜ pending |
| VND-07 | Module service disposition recorded in `VENDORED.md` | — | unit | `::test_vendored_md_sections` | ❌ W0 | ⬜ pending |
| VND-08 | Skin XML and media present; textures resolve | — | unit | `::test_skin_assets_present` | ❌ W0 | ⬜ pending |
| VND-09 | `VENDORED.md` fields; both licence files present | — | unit | `::test_licences_present` | ❌ W0 | ⬜ pending |
| VND-10 | Loads, renders, opens every dialog, no traceback, on a clean profile — minus the two recorded deviations (dead broker; `allow_directory_listing` defaulted off) | — | **manual** | Manual acceptance matrix | n/a | ⬜ pending |
| VND-11 | Exactly one `<import>`, `xbmc.python` 3.0.1 | — | unit | `::test_addon_xml_imports` | ❌ W0 | ⬜ pending |
| ID-01 | No `plugin.onedrive` outside `plugin.onedrive.kn` | — | unit | `::test_addon_id_everywhere` | ❌ W0 | ⬜ pending |
| ID-02 | `provider-name` and display name changed | — | unit | `::test_addon_xml_identity` | ❌ W0 | ⬜ pending |
| ID-03 | `LICENSE.txt` unchanged; GPL headers intact | — | unit | `::test_license_unmodified` (hash) + `::test_gpl_headers_intact` | ❌ W0 | ⬜ pending |
| ID-04 | `CREDITS.md` names origin, module, pyqrcode, pypng | — | unit | `::test_credits_content` | ❌ W0 | ⬜ pending |
| ID-05 | Repo detached from fork network; history preserved | — | **manual** | GitHub settings + `git rev-list --count HEAD` ≥ 113 | partial | ⬜ pending |
| KODI-01 | Kodi 19 refuses; 20/21/22 accept | — | **manual** | Install matrix (manifest logic proven from source) | n/a | ⬜ pending |
| KODI-02 | Runs on 20, 21, 22 | — | **manual** | Install matrix + log assertions | n/a | ⬜ pending |
| SETUP-06 | Clean profile + Android phone reachable over `adb` | — | **manual** | Windows half verified; Android half outstanding | partial | ⬜ pending |
| CI-06 | Manual acceptance on Windows and the Android phone | — | **manual** | Manual acceptance matrix | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_vendor_gates.py` — every automated assertion above
- [ ] `pytest.ini` (or `[tool.pytest.ini_options]`) — `testpaths = tests`, nothing else
- [ ] A phase-local `_dialog_smoke` plugin action, so Success Criterion 3 is testable at all
- [ ] `pip install kodi-addon-checker` on the development machine
- [ ] Kodi 19, 20 and 22 portable installs (21.3 already present)
- [ ] Confirm the Android phone has Kodi installed and is reachable over `adb`

Nothing else. Do not build a Kodi-stub harness in this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Every dialog opens without a traceback | VND-10, CI-06 | The broker is dead, so sign-in cannot complete and no dialog is reachable by navigating the UI | Invoke each dialog through the phase-local `_dialog_smoke` action on a clean profile; assert no traceback in `kodi.log`. Includes the QR dialog, which writes a per-invocation `qr-<hex>.png` into a profile directory it creates first; two constructions in one session must log two different paths |
| Kodi 19 refuses installation | KODI-01 | Requires a real Kodi 19 install; the manifest logic is proven from source but the refusal is an installer behaviour | Attempt install of the built zip on a portable Kodi 19; expect rejection on the `xbmc.python` version |
| Installs and runs on Kodi 20 / 21 / 22 | KODI-02 | Three real installs; entry-point loading is a runtime behaviour | Install on each; confirm both the plugin and the service entry points load, from `kodi.log` |
| Android acceptance on the phone | CI-06, SETUP-06 | Kodi behaviour on Android — storage regime, mode bits, loopback — is not reproducible from a desktop | Clean profile on the Android phone over `adb`; install, load both entry points, run the smoke action; pull and archive `kodi.log`. The Android TV box is the deployment target, not a test device, and is checked before release |
| Repository detached from the fork network | ID-05 | GitHub UI operation with no API-free equivalent available here (`gh` is not installed) | Repository settings → leave fork network; then `git rev-list --count HEAD` to confirm history is intact |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
