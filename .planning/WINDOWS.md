---
schema_version: 1
open_count: 3
waived_count: 0
fixed_count: 0
total_count: 3
last_updated: 2026-08-23T05:23:23.078Z
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
  }
]
````
