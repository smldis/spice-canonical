# Canonical format: one table syntax

**Status:** revised proposal for owner review, 2026-10-17; not implemented.
The owner accepted combining definition identity and ports, rejected a separate
empty declaration, and now rejects redundant `_TABLE` suffixes. This revision
keeps that combined design and proposes making the root a table too. Exact new
names and the remaining conventions still await review. Runtime code, agent
instructions and frozen evaluations remain unchanged.

## Uniform structure

Every record is a table: a label, a column header, then zero or more data rows.
There are no standalone scope markers or optional-header tables.

```text
TOP_PORTS TOP
port

SUBCKT_PORTS amplifier
port
IN
OUT
VDD
VSS
```

`TOP_PORTS TOP` declares the root and lists its external ports. An ordinary
SPICE root has no declared ports, hence no data rows. The table still carries
the root's identity and interface; it is not an extra declaration alongside
another root table. Do not add a fictitious `\e` port row.

`SUBCKT_PORTS amplifier` similarly declares a reusable definition and its ordered
ports. It does not instantiate it. There is no separate `SUBCKT` declaration.
The two tables have identical schemas and differ only in the circuit role they
establish. A definition-only library omits `TOP_PORTS`.

## Simple grammar

Quoted text is literal; `[]` means optional, `{}` means zero or more
repetitions, and `? ... ?` describes a character class. Productions describe the
normal writer form, before escape decoding. The schema below adds column types,
scope requirements and validity rules.

```ebnf
file   = [ table, { gap, table } ], [ LF ];
table  = label, LF, header, { LF, row };
label  = table_name, [ " ", scope_name ];
header = column, { " | ", column };
row    = cell, " | ", cell, { " | ", cell }
       | nonempty_cell | empty_row;
gap    = LF, LF, { LF };

table_name = core_table | qualified_name;
core_table = "TOP_PORTS" | "SUBCKT_PORTS"
           | "PARAMETER_DEFAULTS" | "PARAMETER_ASSIGNMENTS"
           | "NETS" | "DEVICES" | "BLACK_BOXES"
           | "NAMESPACES" | "DIAGNOSTICS";
column         = local_name | qualified_name;
qualified_name = namespace, ":", local_name;
namespace      = segment, ".", segment, { ".", segment };
segment        = lower, { lower | digit | "_" | "-" };
local_name     = letter, { letter | digit | "_" | "-" };
letter         = lower | ? ASCII A through Z ?;
lower          = ? ASCII a through z ?;
digit          = "0" | nonzero_digit;
nonzero_digit  = ? ASCII 1 through 9 ?;
version        = nonzero_digit, { digit };
line_number    = "0" | version;

scope_name    = nonempty_cell;
cell          = { plain | escape };
nonempty_cell = ( plain | escape ), cell;
empty_row     = BS, "e";
plain         = ? Unicode scalar except backslash, vertical bar,
                  control characters and whitespace other than ASCII space ?;
escape        = BS, ( BS | "|" | "n" | "r" | "t" | "s"
                    | "," | "=" | "." | "u", hex, hex, hex, hex );
hex           = digit | ? ASCII A through F or a through f ?;
BS            = ? U+005C backslash ?;
LF            = ? U+000A line feed ?;

connections   = [ assignment, { ", ", assignment } ];
parameters    = [ assignment, { ", ", assignment } ];
assignment    = key, "=", value;
key           = key_char, { key_char };
key_char      = escape | ? plain character except comma or equals ?;
value         = { value_char };
value_char    = escape | ? plain character except comma ?;
incident_pins = [ incident, { ", ", incident } ];
incident      = incident_name, ".", incident_name;
incident_name = incident_char, { incident_char };
incident_char = escape | ? plain character except comma or dot ?;
```

A row with two or more columns contains delimiters even when all cells are
empty. A one-column row must contain a nonempty encoding; `empty_row` is the
exceptional spelling for one empty value. Blank physical lines separate tables
and never count as rows. Thus zero rows and one empty row remain distinct.
`empty_row` is legal only for a one-column table whose schema permits an empty
value; it is not an escape to insert inside other text.

Structured-field productions refine `cell` for the named core columns. Split
unescaped delimiters before decoding. A connection's key and value are a pin
and a nonempty net name; a parameter key is nonempty but its raw value may be
empty (`key=`). Incident components are nonempty device/pin names. An empty
structured cell means an empty list. Significant edge spaces must be escaped,
so whitespace alone is not a nonempty encoding. A Unicode escape must decode
to a scalar value, excluding surrogate code points.

The schema determines whether a scope argument is required or forbidden, the
required columns and their meaning. Root tables, definition tables, metadata
and producer tables all use the same syntax. Table types need different
semantic validation, not different record grammars.

## Names and schemas

Core names are uppercase, descriptive and omit `_TABLE`. Headers use lowercase
`snake_case`, with explicit row subjects rather than an ambiguous `name`.

| Current form | Proposed label | Required header |
| --- | --- | --- |
| `TOP_LEVEL name`, with optional inline pins | `TOP_PORTS name` | `port` |
| `SUBCKT name` with inline pins | `SUBCKT_PORTS name` | `port` |
| `PARAMETER_DEFAULTS name` | `PARAMETER_DEFAULTS name` | `parameter \| value` |
| `PARAMETER_ASSIGNMENTS name` | `PARAMETER_ASSIGNMENTS name` | `parameter \| value` |
| `NET_INCIDENT_TABLE name` | `NETS name` | `net \| incident_pins` |
| `DEVICE_TABLE name` | `DEVICES name` | `device \| type \| connections \| parameters` |
| `BLACK_BOX_TABLE name` | `BLACK_BOXES name` | `device \| cell \| pin_basis` |
| `EXTENSION_NAMESPACES` | `NAMESPACES` | `namespace \| version` |
| `DIAGNOSTICS` | `DIAGNOSTICS` | `source \| line \| message` |
| Producer table | `namespace:local [name]` | Producer-defined local column names |

`NAMESPACES` and `DIAGNOSTICS` have document scope and take no circuit-name
argument. Other core tables require one. New producer names should prefer
lowercase `snake_case`, without a redundant suffix. Existing legal producer
names are preserved; the transport does not rename someone else's schema.

Every table has a header, even with zero rows. Rows must match its width and
headers must be unique. Core headers are fixed and case-sensitive. Namespaced
columns may follow the core columns, except on `NAMESPACES` itself. Declared
unfamiliar producer schemas remain opaque data; unknown unqualified core names
and undeclared namespace prefixes are errors.

## Cells and fields

- The writer uses LF records, one empty line between tables, ` | ` between
  columns and `, ` between list items. There are no alignment spaces, Markdown
  separator rows or inline comments. A reader can tolerate ordinary surrounding
  formatting whitespace without changing escaped spaces.
- Leave ordinary empty cells blank: `X1 | divider | IN=input | ` has no
  parameter overrides. Empty list-valued cells mean empty lists, not null,
  unknown or an omitted prerequisite. Empty required names and ports are invalid.
  Reserve `\e` for an otherwise invisible empty row in a one-column producer
  table. A literal backslash followed by e is encoded `\\e`.
- Split delimiters before decoding. Preserve existing escapes: `\\`, `\|`,
  `\n`, `\r`, `\t`, `\s`, `\uHHHH`. Significant edge spaces use `\s`;
  control characters and Unicode separators are escaped. Raw cell and record
  delimiters cannot occur inside a cell. Cells contain Unicode scalar values.
- `connections` and `parameters` contain `key=value` items separated by commas.
  `incident_pins` contains `device.pin` items. Escape literal commas within
  items as `\,`, equals in keys as `\=`, and dots within incident device/pin
  names as `\.`. Split only unescaped delimiters, using the first unescaped
  equals for an assignment. Expressions and quoted values remain raw strings.
- Circuit, device, net and pin identities match case-insensitively while retaining
  spelling; raw values are not lowercased. Bus spellings are identities, not
  instructions to infer bit relationships.
- Namespace segments match `[a-z][a-z0-9_-]*`, with at least two dot-separated
  segments. Local identifiers match `[A-Za-z][A-Za-z0-9_-]*`. Namespace versions
  are positive ASCII decimal integers without leading zeros. Diagnostic line
  numbers are nonnegative decimal integers. An absent diagnostic source is a
  blank cell.

## Scope, order and validity

1. `TOP_PORTS` starts the root scope, at most once; `SUBCKT_PORTS` starts a
   definition scope. Root and definition name spaces remain distinct even if
   both names are `TOP`. Definitions are unique case-insensitively.
2. Following circuit tables belong to that scope and repeat its name. A name
   mismatch is an error. The next root/definition port table starts a new scope.
   A producer table with a name argument belongs to the current circuit;
   without one it belongs to the document and does not reset circuit scope.
3. Writer order: namespace declarations, document producer tables, root if
   present, definitions, diagnostics. Each circuit starts with its port table,
   then defaults, assignments, nets, devices, black boxes and producer tables.
   Preserve meaningful port, parameter and annotation row order. Readers may
   accept other within-scope table ordering without changing meaning.
4. Each circuit has one port table, one `NETS` table and one `DEVICES` table.
   Other core tables are optional and unique in their scope. Required tables
   may have zero rows; omit optional tables with no data or annotation layout.
   Parameter entries may repeat, preserving their order. Defaults, assignments
   and call overrides are separate raw information, without inferred precedence.
5. Every device connection has exactly one reciprocal net incident. Unused
   declared ports remain net rows with empty incident lists. The two views
   describe the same wiring; they do not add hardware or signal direction.
6. A known call's type identifies its definition and named connections bind
   formal ports to parent nets. Distinct occurrences keep their internal nets
   separate. `BLACK_BOXES` retains missing cell identity and named or positional
   pin basis without inventing interiors. Annotations do not establish electrical
   function, operating state or measurement validity.

## Complete example

```text
NAMESPACES
namespace | version
org.example.analysis | 1

TOP_PORTS TOP
port

NETS TOP
net | incident_pins
input | X1.IN
output | X1.OUT
0 | X1.RET

DEVICES TOP
device | type | connections | parameters | org.example.analysis:role
X1 | divider | IN=input, OUT=output, RET=0 |  | divider_instance

SUBCKT_PORTS divider
port
IN
OUT
RET

PARAMETER_DEFAULTS divider
parameter | value
R | 10k

NETS divider
net | incident_pins
IN | R1.p
OUT | R1.n, R2.p
RET | R2.n

DEVICES divider
device | type | connections | parameters
R1 | resistor | p=IN, n=OUT | value={R}
R2 | resistor | p=OUT, n=RET | value={R}

org.example.analysis:notes divider
text
Synthetic producer annotation
```

The root has no declared external ports; the definition has exactly three.
X1 binds them to `input`, `output`, `0` and supplies no parameter overrides.
The header `port` is never an extra terminal. The file retains the raw default
`R=10k`, without asserting an operating state, output load or simulation result.
The same port-table shape also supports explicit root ports and namespaced
port columns; no separate root-port table or special header rule is needed.
`NAMESPACES` declares producer schema version 1. The qualified `role` column
annotates X1; the qualified `notes` table belongs to the divider definition.
These are synthetic producer data, not built-in electrical facts. Omitting the
scope argument from a producer table makes it document-scoped. The declaration
must precede use, and unknown declared schemas must still be preserved.

An empty ordinary cell needs no marker. For example, the two adjacent
separators in X1's row enclose an empty `parameters` cell. The only exceptional
case is a one-column producer table:

```text
org.example.analysis:notes divider
text
\e
```

This contains one empty note. The same label and header with no data line
contains zero notes. Leaving that one row blank would erase the distinction
because blank lines separate tables. Existing preservation coverage explicitly
checks this distinction in `tests/test_extensions.py`, including opaque producer
data. Eliminating `\e` entirely would require another row boundary convention
(such as enclosing every row in pipes) or dropping the distinction. Neither
change is needed just to allow ordinary blank cells.

## Other simplifications considered

| Change | Assessment |
| --- | --- |
| Remove suffixes and make the root a port table | Recommend. Removes a special record production, optional root headers and a second root-interface table. |
| Keep historical aliases out of the normal grammar | Recommend. Agents get one normal form; legacy reading belongs in a separate compatibility description. |
| Remove repeated scope arguments on circuit tables | Saves text, but relies entirely on placement and removes a useful mismatch check. Current extension tables use presence/absence of this argument to distinguish circuit/document scope. Do not silently change that contract; leave open as a separate design choice. |
| Use one circuit registry with kind/name/ports columns | Unifies declarations, but adds indirection and needs an explicit way to distinguish equally named root/definition scopes. No advantage over two same-schema port tables for this change. |
| Merge defaults and assignments | Requires a kind column repeated on every row and remapping distinct annotation hosts. Fewer table types would not simplify the already uniform syntax; retain the meaningful distinction. |
| Put black-box fields in every device row | Removes a table type but adds mostly empty columns. The normalized device type alone does not recover original cell/interface authority. No demonstrated net simplification. |
| Make the reciprocal net view optional | Its core connectivity is derivable from devices and ports; the existing net_incidence helper proves this mechanism is available. But net annotations and reader usefulness need consideration. Evaluate as an information-presentation choice rather than silently dropping it during a syntax cleanup. |
| Replace nested connection/parameter lists with atomic relation tables | Could reduce field-level delimiter/escape rules, but repeats device identities and adds rows. Worth a small side-by-side example if escape complexity remains a problem; not presumed better or implemented here. |

The first changes simplify the specification without changing what circuit
information can be expressed. The latter choices need an explicit tradeoff,
not a claim that shorter text or fewer table names automatically helps agents.

## Compatibility and review boundary

New writers would emit one normal form. New readers would retain the current
markers, headers and empty-cell spellings as a legacy input dialect, mapping to
the same circuit objects and rejecting duplicate logical tables even across
aliases. Old readers cannot read the proposed new form; coordinate reader
rollout before emitting it. An absent library root, zero-port definitions,
explicit root ports, root/definition name collisions and unknown namespaces
must retain their existing meanings. No source or evaluation artifacts are
rewritten by this proposal.

Keep existing Python object fields and extension-host keys through explicit
file-to-model mappings. Do not rename producer-owned tables or fields. This
proposal adds no core version preamble, schema framework, parser dependency or
expression evaluator. Namespace versions still describe producer schemas.

The proposal remains in one remote review PR, based on main. Existing local
unmerged extension commits and dirty parameter-assignment work are excluded;
implementation prerequisites need their own review or PR stack. After review,
update the reader, renderer, maintained specification, ontology and embedded
agent guide together. Frozen input-only evaluations retain their old guide.

**Review focus:** the two port-table names, all-table syntax, short table names,
and whether any of the open representation choices above should join this
change. No runtime implementation has started.
