# Canonical netlist manipulation use cases

**Status:** reconstructed index, not a verbatim copy of the original Astra
candidate list. Prepared 2026-09-26 from the selected scope and descriptions in
[the read-only implementation plan](read-only-inspection-plan-2026-09-26.md).
It records proposed user tasks, not shipped capabilities or adopted API shapes.

The operator selected **1–18, 27, 28, and 30** for the read-only implementation.
Editing cases **19–26** are deferred. Cases **29** and **31** were discarded.

| # | Use case | Decision |
| --- | --- | --- |
| 1 | Inventory the direct top-level devices, nets, definitions, and diagnostics. | Read-only |
| 2 | Inspect one named subcircuit definition and its interface. | Read-only |
| 3 | Inspect one instance, including its pins, call target, and explicit parameters. | Read-only |
| 4 | List the device terminals attached to one net. | Read-only |
| 5 | Find devices by type or model identifier. | Read-only |
| 6 | Inspect raw ordered instance parameters and subcircuit defaults. | Read-only |
| 7 | Inventory external or black-box cells and their known interfaces. | Read-only |
| 8 | Find unresolved structures and extraction diagnostics. | Read-only |
| 9 | Find the call sites of a subcircuit. | Read-only |
| 10 | Find subcircuit definitions reachable through calls. | Read-only |
| 11 | Count devices or calls directly or across bounded occurrences. | Read-only |
| 12 | Find nets with low represented terminal incidence. | Read-only |
| 13 | Find declared subcircuit pins with no represented attachment. | Read-only |
| 14 | Find connectivity islands in the represented device/net graph. | Read-only |
| 15 | Inspect a bounded graph neighborhood or structural path between nodes. | Read-only |
| 16 | Produce a top-only inspection report without descending into implementations. | Read-only |
| 17 | Extract one selected definition together with its reachable definition closure. | Read-only |
| 18 | Expand hierarchy into a bounded, occurrence-level structural view. | Read-only |
| 19 | Rename a net in canonical data. | Deferred editing |
| 20 | Rename a device in canonical data. | Deferred editing |
| 21 | Reconnect a device terminal in canonical data. | Deferred editing |
| 22 | Merge nets in canonical data. | Deferred editing |
| 23 | Change a raw parameter value in canonical data. | Deferred editing |
| 24 | Clone an instance in canonical data. | Deferred editing |
| 25 | Remove an instance from canonical data. | Deferred editing |
| 26 | Retarget a subcircuit call in canonical data. | Deferred editing |
| 27 | Locate source lines for devices and subcircuit definitions. | Read-only |
| 28 | Inspect include occurrences, outcomes, and opaque library boundaries. | Read-only |
| 29 | Inventory general top-level directives. | Discarded |
| 30 | Inventory raw root-scope `.PARAM` and `.MODEL` declarations. | Read-only |
| 31 | Capture ngspice title and `.CONTROL` text. | Discarded |

“Top-level” in these descriptions means represented root structure after the
selected include expansion. Graph findings concern represented terminal
incidence, not electrical function. The [implementation plan](read-only-inspection-plan-2026-09-26.md)
holds the current proposal and code census for the selected read-only cases.
