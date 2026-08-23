---
schema_version: 1
open_count: 7
waived_count: 0
fixed_count: 0
total_count: 7
last_updated: 2026-08-23T09:03:50.403Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 3 | unrun-verify | tests/test_auth_gates.py |  | Five auth gate assertions are red by construction and owned by plans 03-08 through 03-12 | open |  | 2026-08-23T03:20:23.065Z |  |
| 2 | 03 | unrun-verify | .planning/phases/03-authentication/03-05-SUMMARY.md |  | AUTH-18 tenant-block behaviour is unverified against a genuinely blocking tenant; the tenant hosting this registration permits the device authorization grant so no blocking response can be produced on demand (D-08) | open |  | 2026-08-23T03:55:42.712Z |  |
| 3 | 03 | todo | resources/lib/vendor/clouddrive_common/ui/addon.py |  | import urllib does not bind urllib.parse; ten shipped modules rely on a transitive import to resolve urllib.parse.* — see .planning/phases/03-authentication/deferred-items.md item 1 | open |  | 2026-08-23T05:23:23.078Z |  |
| 4 | 03 | unrun-verify | .planning/phases/03-authentication/03-14-SUMMARY.md |  | Phase 3 acceptance on the TCL Android TV 12 is incomplete: the expiry-focus row, the d-pad reachability row, the context-menu re-authorise/remove rows, the three-dialog affordance check, the two-differing-image-paths check, the service-starts-at-login row and both session-log traceback sweeps were not run. AUTH-06 and AUTH-22 stay Pending because of it | open |  | 2026-08-23T09:03:37.982Z |  |
| 5 | 06 | todo | resources/lib/vendor/clouddrive_common/service/player.py |  | Reported during the 03-14 acceptance run, undiagnosed: subtitles from the cloud appeared once and the feature was inert afterwards. No log captured and no repeatable trigger; a session log showing the failure and a repeatable trigger are the two missing inputs. Likely Phase 6 (Play) - see deferred-items.md item 13 | open |  | 2026-08-23T09:03:43.185Z |  |
| 6 | 04 | todo | resources/lib/vendor/clouddrive_common/service/source.py |  | Reported during the 03-14 acceptance run, undiagnosed: mounting the cloud as a directory/source inside Kodi does not work. No detail on which screen fails or what appears instead, and no log. Likely Phase 4 (Browse), possibly Phase 6 - see deferred-items.md item 14 | open |  | 2026-08-23T09:03:50.042Z |  |
| 7 | 05 | todo | README.md |  | Installing this add-on by URL is not viable on Android TV: Kodi add-source browse needs a directory listing and a repository install is itself a zip install. Every re-test costs a USB round trip. Kodi 21.2 on Android 12 also shows no files on external storage until its Android file permission is set to always - undocumented in the install section. Phase 5 (Distribution) - see deferred-items.md items 15 and 16 | open |  | 2026-08-23T09:03:50.403Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "3",
    "file": "tests/test_auth_gates.py",
    "line": null,
    "description": "Five auth gate assertions are red by construction and owned by plans 03-08 through 03-12",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T03:20:23.065Z",
    "resolved_at": null
  },
  {
    "id": 2,
    "kind": "unrun-verify",
    "phase": "03",
    "file": ".planning/phases/03-authentication/03-05-SUMMARY.md",
    "line": null,
    "description": "AUTH-18 tenant-block behaviour is unverified against a genuinely blocking tenant; the tenant hosting this registration permits the device authorization grant so no blocking response can be produced on demand (D-08)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T03:55:42.712Z",
    "resolved_at": null
  },
  {
    "id": 3,
    "kind": "todo",
    "phase": "03",
    "file": "resources/lib/vendor/clouddrive_common/ui/addon.py",
    "line": null,
    "description": "import urllib does not bind urllib.parse; ten shipped modules rely on a transitive import to resolve urllib.parse.* — see .planning/phases/03-authentication/deferred-items.md item 1",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T05:23:23.078Z",
    "resolved_at": null
  },
  {
    "id": 4,
    "kind": "unrun-verify",
    "phase": "03",
    "file": ".planning/phases/03-authentication/03-14-SUMMARY.md",
    "line": null,
    "description": "Phase 3 acceptance on the TCL Android TV 12 is incomplete: the expiry-focus row, the d-pad reachability row, the context-menu re-authorise/remove rows, the three-dialog affordance check, the two-differing-image-paths check, the service-starts-at-login row and both session-log traceback sweeps were not run. AUTH-06 and AUTH-22 stay Pending because of it",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T09:03:37.982Z",
    "resolved_at": null
  },
  {
    "id": 5,
    "kind": "todo",
    "phase": "06",
    "file": "resources/lib/vendor/clouddrive_common/service/player.py",
    "line": null,
    "description": "Reported during the 03-14 acceptance run, undiagnosed: subtitles from the cloud appeared once and the feature was inert afterwards. No log captured and no repeatable trigger; a session log showing the failure and a repeatable trigger are the two missing inputs. Likely Phase 6 (Play) - see deferred-items.md item 13",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T09:03:43.185Z",
    "resolved_at": null
  },
  {
    "id": 6,
    "kind": "todo",
    "phase": "04",
    "file": "resources/lib/vendor/clouddrive_common/service/source.py",
    "line": null,
    "description": "Reported during the 03-14 acceptance run, undiagnosed: mounting the cloud as a directory/source inside Kodi does not work. No detail on which screen fails or what appears instead, and no log. Likely Phase 4 (Browse), possibly Phase 6 - see deferred-items.md item 14",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T09:03:50.042Z",
    "resolved_at": null
  },
  {
    "id": 7,
    "kind": "todo",
    "phase": "05",
    "file": "README.md",
    "line": null,
    "description": "Installing this add-on by URL is not viable on Android TV: Kodi add-source browse needs a directory listing and a repository install is itself a zip install. Every re-test costs a USB round trip. Kodi 21.2 on Android 12 also shows no files on external storage until its Android file permission is set to always - undocumented in the install section. Phase 5 (Distribution) - see deferred-items.md items 15 and 16",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T09:03:50.403Z",
    "resolved_at": null
  }
]
````
