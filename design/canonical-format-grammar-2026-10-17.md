# Canonical format: consistent conventions and a simple grammar

**Status:** revised draft for owner review, 2026-10-17. The owner accepted the
combined `SUBCKT_PORT_TABLE` definition/interface block. The further consistency
conventions below remain proposals. Nothing here is implemented: the renderer,
parser, agent instructions and saved files are unchanged.

## Accepted subcircuit interface

Use one explicitly named table to declare a definition and its ordered ports:

```text
SUBCKT_PORT_TABLE amplifier
port
IN
OUT
VDD
VSS
```

`SUBCKT_PORT_TABLE amplifier` declares the reusable definition and names its
interface table; `port` is its column header. Its data rows declare ports, in
positional call order. Device terminals such as `d`, `g`, `s`, `p` and `n` remain
pins in device connections. Naming distinguishes a circuit boundary port from
an individual device pin.

This replaces the current combined declaration/interface block:

```text
SUBCKT amplifier
pin
IN
OUT
VDD
VSS
```

There is no separate `SUBCKT` block. The interface table already carries the
definition name and establishes scope for the following circuit tables. A
zero-port definition still needs that table to declare its existence; an
additional empty declaration would add nothing.

## Consistency review

The current format mixes table names with and without `_TABLE`, prose headers
with identifier headers, generic `name` columns with subject-specific columns,
two spellings of empty cells, and a root marker that can double as a port table.
The proposed normal form applies these conventions:

| Concern | Convention and rationale |
| --- | --- |
| Core table names | `UPPER_SNAKE_CASE_TABLE`, with a singular subject or relation name. The suffix identifies every built-in table. |
| Non-table records | `TOP_LEVEL name` is the sole scope-only record. It has no column header or data rows and does not gain `_TABLE`. |
| Column headers | Lowercase `snake_case`; identify the row subject as `port`, `net`, `device`, `parameter` or `namespace`, rather than an ambiguous `name`. |
| Definitions and instances | The subcircuit port table declares a reusable definition. A device row instantiates it. No extra empty declaration is added. |
| Root interfaces | Optional `TOP_LEVEL_PORT_TABLE name` carries actual root ports or port-table annotations. Omit it when neither exists; do not manufacture an empty table for ordinary SPICE roots. |
| Empty cells | Writers emit `\e` consistently, including empty connection/parameter lists. This avoids blank rows and fragile trailing-space cells. Empty string is not null or unknown. |
| Whitespace | LF records, one empty line between blocks, ` | ` between columns and `, ` between list items; no alignment padding or Markdown separator rows. |
| Extensions | New producer schemas should prefer `namespace:lower_snake_case_table` for tables and `namespace:lower_snake_case` for columns. Existing legal producer names remain readable and are never renamed by the core transport. |
| Source identities | Preserve names and raw values. Formatting conventions do not lowercase data, reinterpret punctuation, expand buses or evaluate expressions. |
| Ordering | Define one writer order, while retaining meaningful port/parameter/annotation row order. Do not sort rows merely for cosmetic consistency. |

### Complete naming and header mapping

These are proposed file spellings, not Python API renames. The accepted
subcircuit-table name is included for completeness.

| Current spelling | Proposed normal spelling | Proposed required header |
| --- | --- | --- |
| `SUBCKT name` with inline pins | `SUBCKT_PORT_TABLE name` | `port` |
| `TOP_LEVEL name` | `TOP_LEVEL name` | None; marker only |
| Optional inline root pins | `TOP_LEVEL_PORT_TABLE name` | `port` |
| `PARAMETER_DEFAULTS name` | `PARAMETER_DEFAULT_TABLE name` | `parameter \| value` |
| `PARAMETER_ASSIGNMENTS name` | `PARAMETER_ASSIGNMENT_TABLE name` | `parameter \| value` |
| `NET_INCIDENT_TABLE name` | `NET_INCIDENCE_TABLE name` | `net \| incident_pins` |
| `DEVICE_TABLE name` | `DEVICE_TABLE name` | `device \| type \| connections \| parameters` |
| `BLACK_BOX_TABLE name` | `BLACK_BOX_TABLE name` | `device \| cell \| pin_basis` |
| `EXTENSION_NAMESPACES` | `EXTENSION_NAMESPACE_TABLE` | `namespace \| version` |
| `DIAGNOSTICS` | `DIAGNOSTIC_TABLE` | `source \| line \| message` |

`incidence` names the connection relation; an entry such as `R1.p` names one
incident device pin. `port` names an external circuit terminal, whereas `pin`
names a terminal on a device or call. `type`, `cell` and `pin_basis` retain
their existing meanings rather than being renamed for cosmetic symmetry.

Adding `_table` to extension names is a style recommendation for new or
deliberately revised producer schemas, not a new rejection rule. For example,
the core must still preserve an existing `private.ndecomp:tags` table. Renaming
that producer-owned table would require its own schema/API decision; the
canonical parser cannot make it on the producer's behalf.

## Simple grammar

This describes the proposed normal emitted form. It is not a claim that the
current parser accepts it. Read literal strings in quotes; `[]` means optional,
`{}` means zero or more repetitions, and `|` outside quotes means alternatives.
`LF` is a line-feed character. Tables are separated by at least one empty line.

```ebnf
file              = [ block, { gap, block } ], [ LF ];
gap               = LF, LF, { LF };

block             = root | table;
root              = "TOP_LEVEL", " ", name;

table             = table-marker, LF, header, { LF, row };
table-marker      = core-table, " ", name
                  | "EXTENSION_NAMESPACE_TABLE"
                  | "DIAGNOSTIC_TABLE"
                  | qualified-name, [ " ", name ];

core-table        = "SUBCKT_PORT_TABLE"
                  | "TOP_LEVEL_PORT_TABLE"
                  | "PARAMETER_DEFAULT_TABLE"
                  | "PARAMETER_ASSIGNMENT_TABLE"
                  | "NET_INCIDENCE_TABLE"
                  | "DEVICE_TABLE"
                  | "BLACK_BOX_TABLE";

header            = column, { " | ", column };
row               = cell, { " | ", cell };

connections       = empty | assignment, { ", ", assignment };
parameters        = empty | assignment, { ", ", assignment };
assignment        = key, "=", value;
incidents         = empty | incident, { ", ", incident };
incident          = device-name, ".", pin-name;
empty             = "\e";

qualified-name    = namespace, ":", local-name;
```

Lexical rules, deliberately separate from circuit interpretation:

- `name`, `column`, `device-name`, `pin-name` and `key` are nonempty encoded
  strings. An encoded `cell` is either an ordinary string or the explicit empty
  spelling `\e`. `value` may denote an empty string only where its field permits
  it. Raw record/column separators cannot appear unescaped within a cell.
- Split delimiters **before** decoding escapes. A raw `|` separates columns;
  `\|` is a literal character inside a cell. The spaces shown around separators
  are the normal writer style; a reader can trim ordinary surrounding formatting
  whitespace without altering escaped spaces.
- Preserve the existing escapes: `\\`, `\|`, `\n`, `\r`, `\t`, `\s` and
  `\uHHHH`. Escape literal commas inside list items as `\,`, literal equals in
  assignment keys as `\=`, and literal dots in incident device/pin names as
  `\.`. `\s` preserves significant spaces. Escape raw control/separator
  characters instead of allowing them to become record boundaries.
- A cell containing exactly `\e` represents an empty string. This spelling is
  uniform across core and extension cells. In a one-column custom table it
  distinguishes one empty row from no rows; in list-valued fields it denotes
  an empty list. An empty required port or identifier is invalid. The literal
  two-character string backslash-plus-e is encoded `\\e`, not `\e`.
- A namespace has at least two dot-separated segments, each matching
  `[a-z][a-z0-9_-]*`. A local name matches `[A-Za-z][A-Za-z0-9_-]*`.
  Namespace declarations use positive ASCII decimal versions without leading
  zeros. These are producer-schema versions, not a new core-file version.

### Table schemas and field types

The mapping above specifies fixed core headers. Optional namespaced columns
follow them. Each row has exactly as many cells as its header, including explicit
empty cells. Every table has a header even with zero rows; `TOP_LEVEL` is not a
table. Header names are unique and case-sensitive.

Device `connections` and `parameters` fields use the corresponding grammar
productions; `incident_pins` uses `incidents`. These fields are encoded structured
lists, not arbitrary comma-delimited prose. Other fields are scalar cells.
Diagnostic `line` is a nonnegative decimal integer; namespace `version` is a
positive decimal integer. Parameter names/values in assignment rows are nonempty.
An absent diagnostic source is `\e`, not a fabricated path.

`EXTENSION_NAMESPACE_TABLE` has no additional columns. Qualified tables and
columns require a preceding namespace declaration. A qualified table with a
circuit-name argument belongs to that current root/definition; without an
argument it belongs to the document and does not reset circuit scope. Producer
table headers are unique nonempty local identifiers. Unfamiliar declared schemas
remain opaque data. Unknown unqualified markers are errors.

### Scope and meaning

The grammar identifies records. These short constraints establish their meaning:

1. `TOP_LEVEL` declares the root, at most once. `SUBCKT_PORT_TABLE` declares a
   definition and its interface in one block; definitions do not instantiate
   hardware. Root and definition name spaces
   remain distinct, even when both names are `TOP`. Definition names are unique
   case-insensitively.
2. `TOP_LEVEL` and `SUBCKT_PORT_TABLE` establish the current circuit. Every
   subsequent circuit table names that same root/definition until the next scope
   starts. A document-scoped table does not change the current circuit.
3. A zero-port definition has a `SUBCKT_PORT_TABLE` header with no data rows;
   it still declares a real definition. `TOP_LEVEL` always remains a marker
   without a table body. Actual root ports or root-interface annotation layout
   use an optional `TOP_LEVEL_PORT_TABLE` inside that root scope. This table
   cannot appear in a definition. Neither port table is emitted just to repeat
   an already represented interface.
4. Each declared circuit has exactly one `NET_INCIDENCE_TABLE` and one
   `DEVICE_TABLE`. Other core tables are optional and cannot be duplicated in
   one scope. The writer places ports first, then defaults, assignments, nets,
   devices, black boxes and circuit extensions. Namespace declarations come
   first, then document extensions, root (if present), definitions and finally
   diagnostics. Tables stay in their declared scope. Readers may accept other
   within-scope table ordering without changing meaning; writers emit one form.
5. A device row creates one represented device or call. A net row is the
   reciprocal view of the same connections, not additional hardware. Each
   `device.pin` incident must match exactly one device connection. Declared ports
   remain present as net rows even when unused.
6. A known call's type identifies a definition. Its named connections bind child
   formal ports to parent nets. Equally spelled internal nets in different
   occurrences are not joined. A missing body stays unavailable; black-box
   `pin_basis` is `named` or positional `@1`, `@2`, etc.
7. Names are matched case-insensitively for represented circuit identity, while
   preserving spelling. Port row order matters. Parameter entries preserve
   order and may repeat; assignments, definition defaults and call overrides
   are distinct raw values. No expression evaluation or simulator precedence
   follows from the file grammar.
8. Extension tables/columns annotate represented structure. Their schemas own
   their interpretation. Connectivity syntax establishes neither intended
   function, operating state nor electrically valid measurements.

## Complete example

This file instantiates a reusable three-port divider. The root marker has no
port table because no root interface is declared:

```text
TOP_LEVEL TOP

NET_INCIDENCE_TABLE TOP
net | incident_pins
input | X1.IN
output | X1.OUT
0 | X1.RET

DEVICE_TABLE TOP
device | type | connections | parameters
X1 | divider | IN=input, OUT=output, RET=0 | \e

SUBCKT_PORT_TABLE divider
port
IN
OUT
RET

PARAMETER_DEFAULT_TABLE divider
parameter | value
R | 10k

NET_INCIDENCE_TABLE divider
net | incident_pins
IN | R1.p
OUT | R1.n, R2.p
RET | R2.n

DEVICE_TABLE divider
device | type | connections | parameters
R1 | resistor | p=IN, n=OUT | value={R}
R2 | resistor | p=OUT, n=RET | value={R}
```

The definition's ordered ports are exactly `IN`, `OUT`, `RET`. `X1` binds them
to root nets `input`, `output`, `0`. Headers are syntax, not extra circuit
objects. `\e` records that X1 supplies no parameter overrides; the definition
retains the raw default `R=10k`. This file asserts no operating state, load or
simulation result.

## Compatibility and implementation after review

- New writers would emit only the proposed normal spellings: uniform table
  suffixes/headers, explicit empty cells and separate optional root-port data.
  New readers would also accept current table/header aliases, blank empty
  fields, the combined `SUBCKT`/`pin` form and legacy inline root pin tables.
  Normalize aliases to the same objects and reject duplicate logical tables
  or definitions even if they use different spellings. Old readers cannot read
  the new form; coordinate reader rollout before emitting new files.
- Preserve existing table/escape compatibility and namespaced annotations.
  Changing file spellings does not require renaming Python `Circuit.pins`,
  `Device.name` or existing extension-host keys such as `PINS` and
  `PARAMETER_DEFAULTS`. Keep the public object APIs stable through explicit
  file-to-model mapping. Do not rewrite third-party namespace identifiers,
  local table names, schemas or values to impose a core naming style.
- This bounded change proposes no new file-version preamble, semantic schema,
  quoting language, comment syntax or dependency. Alias recognition suffices
  for these spelling changes. A future incompatible meaning needs its own
  explicit format decision, not inference from a producer namespace version.
- Leave frozen evaluation inputs, instructions, answers and scores unchanged.
  Updated agent instructions should embed the compact grammar, schemas and
  worked example, with essential scope semantics. A grammar link alone cannot
  serve an input-only reader that cannot open files.
- Keep the proposal and later implementation in focused remote PRs. The local
  checkout has other unmerged commits and dirty changes; do not silently bundle
  them into this format change. The proposal can be reviewed independently;
  implementation prerequisites require their own explicit review or PR stack.

**Accepted:** one combined `SUBCKT_PORT_TABLE` definition/interface block, with
no separate empty declaration. **Review requested:** the remaining naming/header
mapping, explicit empty cells, optional named root-port table, and extension style
recommendation. These conventions revise the draft, not runtime behavior.
