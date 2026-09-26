---
name: spice-canonical
description: Extract, inspect, save, and reload canonical connectivity from Eldo or ngspice netlists with the spice-canonical CLI or Python API. Use for operating the extractor, not changing its implementation.
---

Use the `spice_canonical.canonical_netlist` public API or the `spice-canonical` CLI. Locate the input deck and its dialect first. The original SPICE deck remains authoritative for simulation; canonical output is a structural view of circuits, devices, nets, hierarchy, and extraction diagnostics.

**Extract a file.** Prefer `from_file` for a real deck: it recursively expands `.include` and `.inc` relative to each declaring file. The default dialect is `eldo`; select `ngspice` explicitly when appropriate. `from_text` parses one string and does not resolve includes or accept external subcircuit signatures. Neither API simulates the circuit.

```python
from spice_canonical.canonical_netlist import from_file

data = from_file("input.cir", spice_format="ngspice", top_name="TOP")
for diagnostic in data.diagnostics:
    print(diagnostic.source, diagnostic.line, diagnostic.message)
print(data.render())
```

For an isolated snippet, use `from_text("R1 in 0 1k\n", spice_format="eldo")`. Both functions accept `top_name` and `device_type_map`; only `from_file` accepts `stop_include` and `external_subcircuits`.

`data.top` and `data.subcircuits` are `Circuit` values. Each circuit has `name`, ordered `pins`, `devices`, and ordered `parameter_defaults`. Devices have `name`, `type`, `connections`, `parameters`, and optional `black_box`; connections have `pin` and `net`. Parameters retain raw, unevaluated values. An instance's parameters are explicit overrides, not expanded defaults. Inspect `data.diagnostics` before treating extracted connectivity as complete. `CanonicalParseError` means structurally inconsistent input; diagnostics report nonfatal omissions or assumptions.

**Inspect through Python.** Use direct dataclass fields for filtering devices, raw parameters, defaults, and black boxes. Reuse the public helpers for incidence and hierarchy:

```python
from spice_canonical.inspect import circuit_report, expand, Connectivity

report = circuit_report(data)             # direct root after includes; no descent
view = expand(data, max_depth=8, max_objects=10000)
leaves = [o for o in view.occurrences if o.status == "primitive"]
print(view.truncated)                     # check before reporting complete counts
graph = Connectivity(view)
islands = graph.components()
if graph.nodes:
    nearby = graph.neighborhood(graph.nodes[0], max_depth=2)
```

`definition(data, name)` selects only the subcircuit namespace; `resolve_call(data, device)` exposes a call's definition/defaults separately from overrides. `expand(..., path=("Xamp",))` selects an instance occurrence. `Connectivity.path(start, end)` finds a bounded structural witness using identities from `graph.nodes`; it raises `ValueError` when a limit prevents proving unreachability. Opaque and recursive boundaries have no represented interiors. Graph adjacency is terminal incidence, not signal flow; coupling/control references stored in parameters add no edges. Supply additional global nets explicitly to `expand`; only `0` is inherently global.

**Capture source evidence while extracting.**

```python
from spice_canonical.evidence import extract_with_evidence

result = extract_with_evidence("input.cir", spice_format="ngspice")
data = result.netlist
locations = result.evidence.objects       # device/definition source lines
includes = result.evidence.includes       # ordered occurrences and outcomes
raw_declarations = result.evidence.declarations  # root-scope PARAM/MODEL only
```

Evidence is an extraction snapshot, not part of saved canonical tables. Root-scope includes expanded files; it is not restricted to the physical root file. No general directives, title, or control script are captured. Consult public docstrings in `spice_canonical.inspect` and `spice_canonical.evidence` for record fields and limits, or the checkout's `docs/inspection.md` for recipes. These inspection features have no CLI counterpart.

**Use the CLI when a file artifact is wanted.**

```console
spice-canonical input.cir --format ngspice --output canonical.txt
spice-canonical input.cir --format ngspice --strict
```

Without `--output`, tables go to stdout; diagnostics go to stderr. `--strict` exits 2 if any diagnostic was emitted. Parse, I/O, or malformed JSON errors also exit 2. A clean strict result means the supported extraction emitted no diagnostics; it does not establish model availability, electrical equivalence, or simulator readiness.

**Keep incomplete libraries explicit.** `from_file(..., stop_include=["vendor-*.inc"])` or repeated `--stop-include GLOB` leaves matching include paths opaque. `.LIB` is also an opaque boundary. An undefined `X` target retains positional `@1`, `@2`, ... connections and a `BlackBox(cell, "positional")` marker. Supply ordered formal pins only when known:

```python
data = from_file("top.sp", external_subcircuits={"nch": ["d", "g", "s", "b"]})
```

The CLI equivalent is `--external-subcircuits interfaces.json`, with content such as `{"nch": ["d", "g", "s", "b"]}`. A supplied signature gives named pins and checks arity, but supplies no internals. A definition found in the expanded deck takes precedence. Missing includes and unresolved calls normally leave diagnostics; a deliberate stopped include or `.LIB` boundary itself does not.

**Normalize only with an explicit map.** `from_file(..., device_type_map={"library_cell": "nmos"})`, `normalize_device_types(data, mapping)`, or `--device-type-map types.json` maps source types case-insensitively. The JSON is a source-type-to-canonical-type object. Changed devices retain their old type as a `source_type` parameter and retain black-box identity. No map means no normalization.

**Reuse the saved representation.** `data.render()` emits the custom canonical tables. `from_canonical_file("canonical.txt")` and `from_canonical_text(text)` read them without reopening source files or re-extracting. The reader validates table shape and reciprocal net/device incidence; use it when a downstream tool consumes an existing artifact. The tables are not SPICE syntax or a lossless simulator deck.

For supported syntax and omitted directives, read the checkout's `docs/extraction.md`; for table columns, escaping, and incidence, read `docs/representation.md`. Check its `README.md` for installation and corpus verification. Consult current source and focused tests when a deck exposes an undocumented case; do not infer missing model semantics or formal pin names.
