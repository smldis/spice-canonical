# Read-only canonical inspection: proposed implementation plan

**Status:** proposal for later implementation, not an adopted contract. Prepared
2026-09-26 from the operator's selected use cases and an Astra review of
`src/spice_canonical/canonical_netlist.py`, `canonical_text.py`, maintained docs,
and focused tests. No code change is authorized by this document alone.

## Scope and boundary

Plan read-only items **1–18, 27, 28, and 30** from the
[numbered use-case index](canonical-manipulation-use-cases-2026-09-26.md).
Editing items **19–26** are deferred. Items **29** (general top-level
directives) and **31** (ngspice title/control text) are discarded. The operator
will call Python directly; add no CLI options. Do not change the simulator deck,
evaluate expressions, interpret model bodies, infer pin directions or signal
flow, or build a generic query language.

| IDs | Retained read-only use cases |
| --- | --- |
| 1–4 | Root inventory; named cell; one instance; attachments to one net. |
| 5–8 | Device/model search; raw parameter table; external cells; unresolved structures and diagnostics. |
| 9–11 | Call sites; reachable definitions; direct or occurrence-level counts. |
| 12–15 | Low-incidence nets; unused pins; connectivity islands; bounded neighborhood or path. |
| 16–18 | Top-only report; selected cell with definition closure; bounded occurrence expansion. |
| 27, 28, 30 | Device/definition source locations; include/boundary tree; root-scope raw `.PARAM`/`.MODEL` inventory. |

The deferred editing set is net/device rename, terminal reconnect, net merge,
raw parameter change, instance clone/removal, and call retargeting. These are
canonical-data transformations, not part of this read-only plan.

The immediate top-level view is the direct contents of `CanonicalNetlist.top`
**after the selected include expansion**. It includes top-level devices from
expanded files and does not descend into X-call implementations. This is all
*represented* root structure, not every statement physically in the root file.
The root circuit and a `.SUBCKT TOP` are separate scopes even if their display
names coincide. A library-only input can have no populated root.

Existing immutable `CanonicalNetlist`, `Circuit`, `Device`, `Connection`,
`Parameter`, `BlackBox`, and `Diagnostic` values are the default Python
interface. Agents should use fields and small comprehensions where they are
clear. New helpers earn their place only for repeated, error-prone incidence,
call-resolution, hierarchy, or graph logic. A small `spice_canonical.inspect`
module is one reasonable home for them; choose the smallest clear boundary
after examining the existing code. Keep `spice-canonical` independent of
`netlist-comparison`'s comparison-specific expansion code.

The current code is a starting point, not a constraint on implementation.
Refactor or modify existing parser, normalizer, renderer, data types, or public
Python functions when that yields a simpler and more reliable read-only
capability. In particular, the `source_type` provenance limit below may be
better fixed in existing normalization code than worked around in inspection.
The suggested `inspect.py` and optional-recorder seams are proposals to test
against the code, not required architecture. Keep the selected use-case scope
and Python-only access; when an adopted change alters observable behavior or a
public contract, update focused tests, maintained docs, and the affected
ontology explicitly.

## Slices

1. **Direct structure and incidence (1, 2, 4–8, 12, 13, 16).** Document recipes
   for root and named-definition selection, type/model and raw-parameter scans,
   black-box inventory, and unresolved devices/diagnostics. Add one
   `net_incidence(circuit)` helper, and have the renderer reuse its incidence
   construction. Return first-seen net spelling and structured device/terminal
   references, including unused declared pins. Keep multiple terminals of one
   device distinct. Use this for net attachments, low-incidence review, and
   unused pins. Counts are observations of represented incidence, not floating
   net verdicts. Make a top-only report easy to obtain from Python, whether
   through direct composition or a small convenience function over
   `netlist.top`, incidence, referenced cell interfaces, and explicitly
   whole-input diagnostics. Do not label an omitted implementation as an
   unavailable library or pretend the projection is a complete standalone
   canonical artifact.

2. **Calls, hierarchy, and selected definitions (3, 9–11, 17, 18).** Add one
   call-resolution helper using only the subcircuit-definition namespace;
   preserve explicit black-box boundaries and the original cell identity when
   it remains available after device-type normalization. Report visible
   ambiguity rather than guessing: the current normalizer skips adding
   `source_type` when an authored parameter already has that name, so original
   identity cannot always be recovered from a normalized `Device`. Use it to
   explain a call's formal bindings, explicit overrides, and ordered definition
   defaults separately; never calculate an effective parameter value. Add a
   definition walk for callers and reachable-definition closure. A selected
   cell plus its closure may be assembled as a library-only `CanonicalNetlist`
   and rendered with the existing serializer, with input-wide diagnostics
   clearly labeled as such. For occurrence-level counts and expansion, add a
   bounded walk returning occurrence-path tuples, original objects, port
   bindings, and explicit stop reasons. Active-path cycle detection must allow
   repeated instances while stopping recursive calls. Scope internal nets by
   occurrence; treat `0` explicitly and accept additional global names from
   the caller because `.GLOBAL` is not retained. Unknown interiors stay opaque.
   This is a structural view, not a flattened runnable SPICE deck.

3. **Graph inspection (14, 15).** Reuse incidence for one undirected
   device/net graph. Provide connected components, a bounded neighborhood,
   and a bounded shortest-path witness. Include isolated declared nets and
   devices with no known connections. Let callers exclude named high-degree
   nets; do not guess supply nets. Mutual-inductor and controlling-device
   references currently live in parameters, not `Connection` rows, so this
   graph excludes those relationships. A path shows structural adjacency, not
   conduction or signal direction. Keep graph inputs scoped to one circuit or
   an explicitly expanded occurrence view.

4. **Optional source evidence (27, 28, 30).** Add a Python entry point such as
   `extract_with_evidence(path, ...) -> ExtractionResult(netlist, evidence)`.
   Prefer sharing extraction work when practical, but choose an internal
   recorder, a focused second pass, or a simpler revision to existing code
   based on clarity and consistent results. Preserve the ordinary
   `from_file` call and return behavior. Evidence contains
   device/definition source locations keyed by explicit root-versus-definition
   scope and name; ordered include *occurrences* with parent occurrence,
   directive location, target when known, and outcomes such as expanded,
   stopped, missing, cyclic, or unreadable; and ordered raw logical `.PARAM`
   and `.MODEL` declarations lexically outside `.SUBCKT`. Retain duplicate
   declarations and source locations. `.LIB` can be recorded as an opaque
   boundary without loading it or guessing section semantics. The joined
   logical text is not a lossless physical-source serializer. An evidence
   result represents one extraction; it does not automatically track later
   canonical edits.

   Include expansion currently precedes ngspice `.CONTROL` filtering. Record
   the extractor's actual traversal, not inferred simulator include semantics;
   do not capture control or title text as new evidence. A stopped include is
   not probed for existence, and the evidence path must preserve that behavior.

   The proposed evidence result is separate from canonical connectivity; this
   avoids adding fields, canonical tables, or schema migrations merely to
   expose source navigation. Revisit that mechanism if modifying existing
   code gives a clearer contract. Under this separate-evidence design, evidence
   is unavailable after loading a saved canonical artifact alone; a caller
   must still have the source files and extract again. Add persistence only if
   a concrete use case calls for it. Do not smuggle discarded general
   directives or ngspice control/title capture into the evidence container.

## Code census and implementation seams

These are observed source seams and proposed edits, not a shipped API. Paths in
this section are relative to `spice-canonical/`; line numbers locate the code
as inspected on 2026-09-26 and may move during implementation.

| Use cases | Current code and minimal next step |
| --- | --- |
| 1, 2 | `CanonicalNetlist.top/subcircuits` and `Circuit` in `src/spice_canonical/canonical_netlist.py:67-81` already provide the inventory. Document direct field access and a case-insensitive lookup among definitions; keep root scope separate even when a definition is named `TOP`. |
| 4, 12, 13 | `_render_circuit_tables` at `canonical_netlist.py:873` seeds declared pins, then scans every device connection into a case-folded incidence index. Move this loop to `inspect.net_incidence(circuit)` with structured device/terminal references; render its result back into the same strings. Keep duplicate terminal incidences and first-seen net spelling. |
| 5, 6 | Scan `Device.type`, all ordered `Device.parameters`, and `Circuit.parameter_defaults` directly. `_parameters_for_tail` at `canonical_netlist.py:760` creates model parameters; `_split_parameters` at `:794` preserves duplicate raw assignments. Do not collapse these into dictionaries or mistake an absent model body for an unresolved device. |
| 7, 8 | `BlackBox` and `_parse_subcircuit_instance` at `canonical_netlist.py:48,636` expose external identities and named/positional interfaces. `_unresolved_device` at `:746` preserves raw tokens and diagnostics without invented connections. Inspect those objects directly; never parse diagnostic prose as a data API. |
| 16 | Assemble the root report in Python from `top`, incidence, called interfaces, and explicitly input-wide diagnostics. Included top-level statements are already spliced into `top` by `_statements_from_file` at `:393`. This report is a projection, not a standalone complete netlist. |
| 3, 9, 10 | Add `resolve_call(netlist, device)` in `inspect.py` using the subcircuit namespace, `Device.black_box`, and visible `source_type` provenance. Reuse it for direct call-site listing and a deterministic reachable-definition walk; report opaque, recursive, or ambiguous boundaries. `_parse_subcircuit_instance` at `:636` is the extraction-side reference. |
| 11, 17, 18 | Count direct devices with ordinary Python aggregation; qualify partial occurrence counts. Export a selected definition plus reachable definitions as a library-only `CanonicalNetlist` through existing `render`, clearly labeling whole-input diagnostics. A single bounded occurrence walker can emit tuple paths, original objects, pin bindings, and stop reasons; detect cycles on the active path, not globally. |
| 14, 15 | Build one private bipartite adjacency index from incidence in `inspect.py`, using typed net/device keys so equal names cannot collide. Share bounded breadth-first traversal between components, neighborhood, and shortest-path witnesses; represent isolated pins and devices. For expanded occurrences, adapt the slice-2 walker internally instead of creating another public graph protocol. |
| 27 | `_LogicalStatement` and `_RawDevice` at `canonical_netlist.py:117,124` already carry source and starting line, but `_build_circuit` at `:555` drops them. An optional extraction recorder can capture `.SUBCKT` locations in `_from_statements` at `:287` and device locations alongside circuit construction, with an explicit root-versus-definition scope key. |
| 28 | `_statements_from_file` at `canonical_netlist.py:393` has branches for malformed, stopped, cyclic, missing, expanded, and unreadable includes. Record each include occurrence and its parent at those branches. Add a private occurrence ID to statements only if repeated includes require it to associate source objects with their traversal. `.LIB` stays an opaque boundary; its operands are not uniformly file paths. |
| 30 | In `_from_statements`, after ngspice control filtering and before directive handling, capture `.PARAM` and `.MODEL` logical statements only when `current is top`. The `models` lookup at `canonical_netlist.py:545` loses duplicate declarations and bodies and must not supply this inventory. Do not change its existing model-resolution behavior as a side effect. |

One possible implementation places the opt-in file entry point beside
`from_file` at `canonical_netlist.py:204` and factors shared extraction work
behind an optional recorder; whichever mechanism is chosen, its canonical
result must match ordinary extraction. `from_text` does not
expand includes; `from_canonical_text` at `:105` loads saved tables without
source files. The separate-evidence proposal needs no change to
`src/spice_canonical/canonical_text.py` or the canonical table grammar.
`normalize_device_types` at `canonical_netlist.py:245` only adds `source_type`
when the name is absent, so an authored collision may look valid and cannot
always be detected by inspection. This is a candidate for a focused change to
normalization during implementation; until then, unnormalized extraction is
the clearer route when call identity matters.

If `inspect.py` is used, let it depend on the public dataclasses. If the
renderer imports its incidence helper, a local import inside
`_render_circuit_tables` is one way to avoid a module import cycle, as
`from_canonical_text` already does for its reader. A
private graph index can be shared by the graph operations without adding a
graph library. Existing `K` mutual-inductor references (`_parse_mutual_inductor`
at `:727`) and controlling-device references (`_parameters_for_tail` at `:760`)
are parameter values, not graph edges; an isolated graph node is therefore not
an electrical fault finding.

## Concrete test anchors

Add focused `tests/test_inspect.py` cases for repeated terminals, unused pins,
first net spelling, root/definition name collision, normalized and opaque
calls, recursion versus repeated instances, port shorts, explicit globals,
bounded truncation, isolated graph nodes, equal net/device names, excluded
nets, and deterministic path witnesses. Keep current extraction assertions in
`tests/test_canonical_netlist.py` for incidence rendering, top-level include
ordering, case-insensitive definitions, and include outcomes;
`tests/test_parameter_defaults.py` already checks ordered raw expressions.

Add `tests/test_extraction_evidence.py` for source locations across
continuations, nested/repeated includes, every include outcome, lexical root
declarations across includes, and opaque `.LIB` forms. Compare its canonical
result with `from_file` on the same fixtures. Reuse boundaries from
`tests/test_incomplete_extraction.py` and ngspice title/control/include-fragment
behavior from `tests/test_canonical_netlist_ngspice.py`. Confirm discarded
general-directive and control/title capture remain absent.

## Verification and documentation for implementation

Test incidence spelling, repeated terminals, unused pins, case-insensitive
lookups, raw parameter order/duplicates, root-versus-definition `TOP`, normalized
and opaque calls, repeated and recursive occurrences, port shorts, explicit
globals, truncation, isolated graph nodes, and path witnesses. Test source
locations across continuations/includes, repeated include occurrences,
stopped/missing/cyclic includes, opaque `.LIB`, root-scope declarations versus
subcircuit defaults, and absence of items 29/31. Keep existing render/read
round trips unchanged. Use focused tests per slice, then the full canonical
suite and affected downstream integration checks; build docs and inspect
warnings.

Likely implementation sites are `canonical_netlist.py`, a small new
`inspect.py`, and focused tests. Update the Python API and inspection guide,
visible agent skill, and local `ONTOLOME.md` when behavior is implemented. The
root ontology needs revision only if the promoted cross-unit contract changes.
This plan itself changes no ontology commitment or development state.
