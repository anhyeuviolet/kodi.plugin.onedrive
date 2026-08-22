# Phase 1 — API Coverage

**Declaration:** No external API integration. This phase copies and renames an existing module and
changes add-on identity; the Microsoft Graph client is carried unchanged and is first exercised in
Phase 3.

No coverage matrix is written because there is no external surface to enumerate. The one outbound
HTTP call site in the vendored tree is modified in plan 01-06 only to add an explicit `timeout=`;
neither its URL, its method, its headers nor its response handling changes in this phase.

The external surfaces this phase does touch are not APIs and are covered elsewhere:

| Surface | Where it is covered |
|---|---|
| Kodi add-on manifest and dependency resolver | `01-03-PLAN.md` (`test_addon_xml_imports`, `test_addon_xml_identity`) and the install matrix in `01-07-PLAN.md` |
| Kodi `WindowXMLDialog` skin path resolution | `01-05-PLAN.md` (`test_skin_assets_present`) and the dialog smoke action in `01-07-PLAN.md` |
| Kodi localized-string lookup | `01-03-PLAN.md` and `01-04-PLAN.md` (`test_string_ids_partitioned`) |
| SQLite key-value and cache stores | `01-06-PLAN.md` (`test_store_json_roundtrip`) |

Re-evaluate this declaration at Phase 3, where the device-code protocol introduces the first real
external API surface in the project.
