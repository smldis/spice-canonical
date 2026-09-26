# Inspecting from Python

`spice_canonical.inspect` reads the existing dataclasses. The direct root is
`netlist.top` after include expansion, without descending into called cells.
It does not contain every statement physically in the root file.

```python
from collections import Counter
from spice_canonical.canonical_netlist import from_file
from spice_canonical.inspect import (
    circuit_report, definition, definition_library, top_level_netlist, net_incidence,
    resolve_call, reachable_definitions, expand, Connectivity, Node,
)

netlist = from_file("design.sp")
report = circuit_report(netlist)          # direct root, nets, calls, diagnostics
cell = definition(netlist, "AMP")         # only the definition namespace
incident = net_incidence(cell)
unused = [n.name for n in incident if not n.terminals]
small = [n for n in incident if len(n.terminals) <= 1]

# Ordinary Python keeps raw parameters and duplicate names intact.
circuits = (netlist.top, *netlist.subcircuits)
mos = [(c.name, d) for c in circuits for d in c.devices
       if d.type.casefold() == "nmos"]
model_hits = [(c.name, d) for c in circuits for d in c.devices
              if any(p.name.casefold() == "model" and p.value.casefold() == "nch"
                     for p in d.parameters)]
parameters = [(c.name, d.name, p.name, p.value)
              for c in circuits for d in c.devices for p in d.parameters]
widths = [(d.name, tuple(p.value for p in d.parameters if p.name.casefold() == "w"))
          for d in cell.devices]         # () means missing; duplicates survive
external = [(c.name, d) for c in circuits for d in c.devices if d.black_box]
unresolved = [(c.name, d) for c in circuits for d in c.devices if d.type == "unresolved"]
call_sites = [(c, d) for c in circuits for d in c.devices
              if resolve_call(netlist, d).definition is cell]
closure = reachable_definitions(netlist, cell)
library_text = definition_library(netlist, "AMP").render()
top_text = top_level_netlist(netlist).render()

view = expand(netlist, max_depth=8, max_objects=10000)
counts = Counter(o.device.type for o in view.occurrences if o.status == "primitive")
assert not view.truncated               # otherwise these are partial counts
# Opaque/recursive boundaries still have no represented interiors.
selected = expand(netlist, path=("Xamp",), max_depth=8)
graph = Connectivity(cell, exclude_nets=("VDD", "0"))
islands = graph.components()
# Discover exact node identities through graph.nodes.
near = graph.neighborhood(Node("net", (), "in"), max_depth=2)
path = graph.path(Node("net", (), "in"), Node("net", (), "out"))
```

The examples use illustrative cell/net names. `circuit_report` is a Python
report, not a new file format. Its call references expose interfaces/defaults;
it does not traverse their bodies. Diagnostics remain input-wide. Parameter
values are never evaluated, and defaults remain separate from overrides.
`top_level_netlist` omits definition bodies and marks calls to those omitted
definitions as named black boxes. Existing external black boxes retain their
pin basis; unresolved and ambiguous calls are not given guessed identities.

Graph paths are structural incidence, not conduction or signal flow. Coupling
and control references stored in parameters add no graph edges. A graph of an
expansion omits expanded call vertices and uses leaf connectivity; opaque and
limited calls remain boundary vertices. Ground `0` is global during expansion;
additional global names must be supplied explicitly. Bus names are not expanded.

Normalized calls use retained `source_type`. Authored values can collide with
this convention; observable conflicts are reported as ambiguous, but missing
normalization history cannot be recovered. Prefer unnormalized inputs for
hierarchy inspection when such collisions exist.

For source locations and include outcomes, opt in while extracting:

```python
from spice_canonical.evidence import extract_with_evidence
result = extract_with_evidence("design.sp", stop_include=("vendor-*.inc",))
result.netlist                 # same canonical result as from_file
result.evidence.objects        # explicit root/definition scope and source lines
result.evidence.includes       # occurrences, parent IDs, outcomes, raw LIB boundaries
result.evidence.declarations   # ordered root-scope raw PARAM and MODEL statements
```

Evidence describes the extraction snapshot. It is not saved in canonical
text or recovered from saved canonical files. Logical text joins continuation
lines and omits comments; only starting physical lines are recorded. Root-scope
declarations include expanded files but exclude subcircuit-local declarations.
Includes describe extractor traversal, which precedes ngspice control filtering;
they are not a simulator execution trace. No general directives, title, or
control script are captured. The [API reference](api.rst) documents limits and
return records.
