# The Canonical Representation

The canonical netlist representation is an LLM-oriented structural view of an
Eldo or ngspice netlist. It complements the original netlist; it is not a
replacement for simulator input or a lossless serialization of every simulator
directive.

The representation gives two reciprocal views of circuit connectivity:

- the devices and pins incident on each net;
- the named nets connected to each device.

Subcircuit interfaces are represented separately so an instance can use formal
pin names instead of positional pin numbers.

This page is the format itself — what a consumer, or a reverse converter, reads.
For the formal EBNF, table schemas and UTF-8/escaping contract, see
[canonical file format](format.md). For the parser that produces it, see [extracting a canonical netlist](extraction.md).

## Tables

Each subcircuit has a one-column interface table. Pin order is the declaration
order from the original `.SUBCKT` statement, but numeric pin identifiers are not
introduced.

```text
SUBCKT_PORTS INV
port
A
Y
VDD
VSS
```

A subcircuit with declaration defaults has an optional two-column table directly
after its interface and before its net and device tables:

```text
PARAMETER_DEFAULTS INV
parameter | value
WP | 2u
WN | {WP / 2}
```

This represents `.SUBCKT INV A Y VDD VSS PARAMS: WP=2u WN={WP / 2}`.
Rows retain declaration order, parameter-name spelling, and unevaluated value
spelling (including quotes or braces). Repeated names remain separate rows;
the extractor does not choose simulator precedence. Assignment spacing is not
retained, and continuation lines are joined by the existing logical-line parser.
Cells use the same escaping as the other tables. No table is emitted when there
are no defaults or default-host annotations.

Defaults belong to the definition. An instance's device parameters contain only
its explicit overrides; the extractor neither copies defaults into instances nor
evaluates expressions or resolves parameter scope. This is canonical table
syntax, not simulator syntax. `from_canonical_text` and `from_canonical_file`
read these tables back into canonical objects without evaluating expressions.

Each circuit, including `TOP`, has a net-incident table with one row per net.

```text
NETS INV
net | incident_pins
A | M1.g, M2.g
Y | M1.d, M2.d
VDD | M1.s, M1.b
VSS | M2.s, M2.b
```

An incident pin uses `instance.pin`. Primitive devices use semantic terminal
names such as `d`, `g`, `s`, and `b`. Subcircuit instances use the formal pin
names from the corresponding `SUBCKT_PORTS` table.

Each circuit also has a device table.

```text
DEVICES INV
device | type | connections | parameters
M1 | pmos | d=Y, g=A, s=VDD, b=VDD | model=PCH, W=2u, L=180n
M2 | nmos | d=Y, g=A, s=VSS, b=VSS | model=NCH, W=1u, L=180n
```

Columns are separated by a single ` | `. Cells are not padded to a common
width, so a reader must strip surrounding whitespace rather than rely on
alignment, and an empty trailing cell leaves the row ending in `| `.

A subcircuit instance uses its subcircuit name as its type and maps formal pins
to nets by name.

```text
DEVICES TOP
device | type | connections | parameters
X1 | INV | A=in, Y=out, VDD=vdd, VSS=0 |
```

The corresponding net rows are:

```text
NETS TOP
net | incident_pins
in | X1.A
out | X1.Y
vdd | X1.VDD
0 | X1.VSS
```

## Top Level

The root uses the same interface-table syntax as definitions:

```text
TOP_PORTS TOP
port
```

It declares the root identity and ordered external ports. Ordinary SPICE roots
have zero port rows; authored canonical roots can have explicit ports. This is
followed by `NETS` and `DEVICES` tables. A definition-only library omits the
root tables. The root display name follows `top_name`, defaulting to `TOP`.
An empty default root is omitted unless it carries data or annotation layout.

## Connectivity Invariant

Every device connection has exactly one reciprocal net incident. If a device row
contains:

```text
X1 | INV | A=in |
```

then the `in` net row contains `X1.A`. The Python renderer derives the incident
table from parsed device connections so these views cannot diverge.

Subcircuit pins with no internal connection are still emitted as empty net rows.
This preserves the complete declared interface.

Nets are matched case-insensitively, and the first spelling encountered is the
one rendered.

## Buses

Bus indices and ranges use angle brackets and retain the spelling from the source
netlist.

```text
SUBCKT_PORTS REGISTER
port
D<9:0>
Q<9:0>
CLK
VDD
VSS
```

Uniform whole-bus connectivity may remain compact:

```text
XREG | REGISTER | D<9:0>=DATA<9:0>, Q<9:0>=RESULT<9:0>, CLK=clk, VDD=vdd, VSS=0 |
```

```text
DATA<9:0> | XREG.D<9:0>
RESULT<9:0> | XREG.Q<9:0>
```

When bits have different connectivity, the source netlist should expose those
bits separately and the canonical form emits one row per bit:

```text
DATA<3> | XREG.D<3>, U1.Y
DATA<2> | XREG.D<2>, U2.Y
```

The extractor does not infer or expand bus semantics that are not present in the
source. A whole-bus name and a bit of that bus are distinct net names, and
nothing relates them.

## Operative parameter assignments

All top-level `.PARAM` declarations are grouped into one root table, even if
that root has no devices:

```text
TOP_PORTS TOP
port

PARAMETER_ASSIGNMENTS TOP
parameter | value
PAIR_W | 2u
PAIR_L | {PAIR_W / 4}
BIAS | 10u
```

This is `netlist.top.parameter_assignments` in Python. A subcircuit-body `.PARAM`
uses the same optional table in its definition scope. `.SUBCKT` header defaults
remain in `PARAMETER_DEFAULTS`; explicit instance overrides remain in device
rows. These are different sources of parameter context, not interchangeable
fallback defaults. Instance expressions retain their symbols, so a MOS row may
still contain `w={PAIR_W}, l={PAIR_L}` alongside those declarations.

Rows preserve source traversal order, duplicates and raw expression strings.
No dictionary collapse or numerical substitution is performed. Declaration-line
grouping, comments and placement relative to device statements are not retained;
this artifact does not reproduce simulator execution or resolve precedence.
Opaque or unavailable libraries can leave additional bindings unknown.
A selected definition alone does not carry file-scope assignments:
`definition_library` preserves them on its otherwise empty root when exporting
the definition and its reachable children.

## Delimiters

The structural punctuation is deliberately small:

```text
|     separates table columns
,     separates items within a cell
.     separates an instance name from its pin
=     maps a pin to a net or a parameter to a value
:     qualifies extension identifiers; inside core cells it remains available for bus ranges
< >   enclose bus indices and ranges
```

A literal `|`, backslash, or newline inside a rendered cell uses `\|`, `\\`,
or `\n`. Carriage returns and tabs use `\r` and `\t`; significant edge spaces
use `\s`. Inside comma-separated lists, literal commas use `\,`; literal equals
in assignment names use `\=`. Incident references escape literal dots in either
the instance or pin name as `\.`. Reading restores the original strings.
Earlier grouped/quoted parameter expressions with unescaped commas remain
readable in legacy files. Ambiguous old incident references containing literal dots must be
escaped or re-extracted; the reader does not guess their boundaries.

Files use UTF-8 with LF records. Printable Unicode stays literal. Newline,
carriage return, tab and significant spaces use their named escapes; other
controls and unsupported whitespace/separators are rejected. Empty cells stay
blank. A table with no entries retains its label and header; an empty one-column
data row is not representable. Multi-column empty cells and rows remain valid.
JSON, `null`, URLs and paths remain strings. See the complete
[grammar and legacy-reading rules](format.md).

## External cells and saved diagnostics

Unavailable subcircuit implementations are explicit boundaries. Their device
rows retain the cell type, connections and raw instance overrides. Supplied
external signatures give named pins; otherwise `@1`, `@2`, etc. retain ordered
terminal tokens without claiming formal names. Missing primitive model bodies
do not create this marker: primitive syntax already defines their terminals.

```text
BLACK_BOXES TOP
device | cell | pin_basis
XM | nmos_lvt | named
XR | vendor_res | positional
```

This optional per-circuit table follows its device table. `cell` preserves the
original library identity even after type normalization. `pin_basis` is `named`
or `positional`. The Python equivalent is `Device.black_box = BlackBox(cell,
pin_basis)`; ordinary devices and implemented calls have `black_box=None`.
This states neither an implementation nor electrical equivalence.

An optional final table preserves extraction diagnostics. Plain `render()` omits it by
default; `render(include_diagnostics=True)` or the CLI's
`--include-diagnostics` flag adds it:

```text
DIAGNOSTICS
source | line | message
/work/design.sp | 1 | included file was not found: /work/vendor.inc
```

An empty source cell represents no source path. Paths are evidence only: loading
a canonical artifact never opens its original source, includes or libraries.
Extended artifacts retain diagnostics by default, as described below.
The reader preserves defaults, scoped assignments, duplicate parameter entries, unused interface
pins, black-box markers and any included diagnostics. It requires blank lines
between table blocks, rejects unknown unqualified/duplicate tables and invalid fields, and
checks reciprocal net/device incidence. The top-level circuit and subcircuit definitions have
separate name scopes: a `.SUBCKT TOP` may coexist with `TOP_PORTS TOP`, and a
black-box cell called `TOP` does not imply an implementation in the top-level
circuit. Device/net row ordering need not agree. Files rendered by
older versions without metadata tables remain readable when unambiguous, but
diagnostics absent from a saved file cannot be recovered from that file.

## Namespaced tables and columns

Projects can carry their own information in the same artifact without changing
structural fields or installing the producer. A single preamble precedes all
circuits and declares every namespace used, including otherwise unused ones:

```text
NAMESPACES
namespace | version
org.example.analysis | 1

TOP_PORTS TOP
port

NETS TOP
net | incident_pins
out | R1.p
0 | R1.n

DEVICES TOP
device | type | connections | parameters | org.example.analysis:role
R1 | resistor | p=out, n=0 | value=1k | load_candidate

org.example.analysis:findings TOP
id | kind | rule
load1 | output_load | demonstration
```

This synthetic example illustrates transport, not a recognized electrical fact.
Projects can define separate findings, membership, net-role and evidence tables
for overlapping interpretations; an element need not belong exclusively to one
block. Canonical does not standardize those schemas.

Namespace segments match `[a-z][a-z0-9_-]*`, separated by dots, with at least
two segments. Use an authority/project ID under your control for public schemas,
or a documented `private.<project>` convention locally. Names do not authenticate
ownership and no registry is consulted. A positive ASCII decimal integer, without
leading zeros, identifies the complete namespace schema rather than its package
release. One version per namespace is allowed in a file; duplicate declarations
fail. A fork or uncoordinated schema uses its own namespace.

Table markers and appended core-column headers use `namespace:local`; local
identifiers match `[A-Za-z][A-Za-z0-9_-]*` and are case-sensitive. Namespace
identifiers are lowercase. Required core headers retain their spelling/order;
extra headers follow them. Custom table headers are nonempty unique local
identifiers. Rows must have the declared width. Namespace metadata itself is
not extensible. Unknown declared namespaces and versions are preserved;
unknown unqualified markers and undeclared prefixes fail. Preserving an unknown
version does not authorize interpreting it or imply future core-grammar support.

A custom table with a circuit argument belongs to the current root/definition;
its argument uses ordinary cell escaping and must match that circuit. With no
argument it is document-scoped and does not reset the current circuit scope.
Table identity includes scope, namespace and local name. A root `TOP` and a
definition `TOP` are distinct. Additional columns are supported on interface pin
tables, parameter defaults and assignments, net incidence, devices, black boxes and diagnostics.

### Python authoring and inspection

The public types are available from `spice_canonical.canonical_netlist`:

```python
from spice_canonical.canonical_netlist import (
    ExtensionScope, ExtensionTable, from_text, from_canonical_text,
)

netlist = from_text("R1 out 0 1k\n")
scope = ExtensionScope("root", "TOP")
namespace = "org.example.analysis"
netlist = netlist.with_namespace(namespace, 1)
netlist = netlist.with_column(
    namespace, "role", scope=scope, table="DEVICE_TABLE",
    values={"R1": "load_candidate"},
)
netlist = netlist.with_table(ExtensionTable(
    namespace, "findings", ("id", "kind"),
    (("load1", "output_load"),), scope,
))
assert from_canonical_text(netlist.render()) == netlist
columns = netlist.extensions.column_host(scope, "DEVICE_TABLE")
findings = netlist.extensions.table(namespace, "findings", scope)
```

Functional methods return new immutable values. Declaring the same namespace
version is idempotent; changing its version requires explicit removal/conversion.
Adding a table or column replaces only the same qualified identity. Other
namespaces survive. Use `without_table`, `without_column`, `without_namespace`
or `without_extensions` for explicit removal. Headers, rows and declaration
collections are tuples; cells are strings.

`ExtensionScope()` is document scope; root and definition scopes require a name,
stored case-folded to match structural identity rules. Column host names are
`PINS`, `PARAMETER_DEFAULTS`, `PARAMETER_ASSIGNMENTS`, `NET_INCIDENT_TABLE`, `DEVICE_TABLE`,
`BLACK_BOX_TABLE` and `DIAGNOSTICS`. These are stable Python host keys; file
labels use the [current grammar](format.md). `PINS` identifies the combined
root/definition interface table.
Diagnostics require document scope; other column hosts require a circuit scope.

Column value mappings use case-insensitive device/net/pin names for named hosts,
and zero-based occurrence indices for ordered defaults, assignments and diagnostics. Omitted
mapping keys yield empty cells; unknown or duplicate normalized keys fail.
Sequence values follow the host's retained row order. Duplicate defaults,
assignments and diagnostics remain separate positional occurrences, not durable entity IDs.

### Preservation and mutation boundaries

The envelope retains decoded extension cells, header/row order, duplicates,
unused declarations and empty annotated hosts. Annotated core hosts retain their
row order and attachment, including regenerated net tables. Output canonicalizes
table-block order and formatting; byte identity and core spelling aliases are
not promised. Empty targeted roots/optional hosts are emitted.

An envelope binds to the exact ordered represented core, including parameters,
definitions, black-box boundaries and diagnostics. Rendering or authoring after
a core change fails: explicitly remove extensions before transforming, then
reauthor them if appropriate. No-op normalization preserves the envelope; changed
normalization fails. Top-only and definition-closure export reject extensions
until explicitly removed because opaque tables may reference removed scopes.
Read-only structural reports and expansion remain views; their results do not
claim annotation-preserving export.

Plain files omit diagnostics by default. For an extended snapshot, default
`render()` includes its diagnostics, even when only another table is annotated.
`include_diagnostics=False` fails if it would remove diagnostics or an annotated
diagnostic host. Explicit `render(include_extensions=False)` produces core-only
text with the old diagnostic default; pass `include_diagnostics=True` separately
if needed. This projection uses the current file grammar; older readers require updating.

Attachment and preservation do not establish truth or freshness. The in-memory
guard captures the snapshot at loading/authoring; it cannot discover external
edits predating a load. Producers must retain and validate their original basis,
assumptions and uncertainty where that matters. Canonical never refreshes those
fields, runs namespace code, fetches schemas or follows evidence paths.
Document equality includes annotations; `Circuit`/`Device` equality remains
structural. The exact envelope guard digest is not a universal connectivity or
consumer identity contract.

## What the representation omits

Analysis commands, options, model bodies, and other simulator
directives apart from represented `.PARAM` assignments are intentionally omitted
from the structural representation. The original Eldo or ngspice deck remains
the authoritative source for simulation.
