# Canonical file format

Files use **UTF-8 with LF line endings**. This is the maintained grammar for
the reader and writer. The simulator deck remains authoritative; these tables
carry structural data and producer annotations.

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
another root table. Do not add a fictitious empty port row.

`SUBCKT_PORTS amplifier` similarly declares a reusable definition and its ordered
ports. It does not instantiate it. There is no separate `SUBCKT` declaration.
The two tables have identical schemas and differ only in the circuit role they
establish. A definition-only library omits `TOP_PORTS`.

## Grammar

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
       | nonempty_cell;
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
plain         = ? Unicode scalar except backslash, vertical bar,
                  control characters and whitespace other than ASCII space ?;
escape        = BS, ( BS | "|" | "n" | "r" | "t" | "s"
                    | "," | "=" | "." );
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
empty. A one-column row must contain a nonempty encoding. Blank physical lines
separate tables and never count as rows. An empty one-column data row is not
representable; a table with no entries retains its label and header with zero
rows. This deliberately gives up the former distinction between zero rows and
one empty row in a one-column extension table. No current engineering consumer
requiring that distinction was found; generic preservation tests alone do not
justify a special syntax rule.

Structured-field productions refine `cell` for the named core columns. Split
unescaped delimiters before decoding. A connection's key and value are a pin
and a nonempty net name; a parameter key is nonempty but its raw value may be
empty (`key=`). Incident components are nonempty device/pin names. An empty
structured cell means an empty list. Significant edge spaces must be escaped,
so whitespace alone is not a nonempty encoding. Printable Unicode text remains
literal; unsupported control and whitespace characters are errors.

The schema determines whether a scope argument is required or forbidden, the
required columns and their meaning. Root tables, definition tables, metadata
and producer tables all use the same syntax. Table types need different
semantic validation, not different record grammars.

## Names and schemas

Core names are uppercase, descriptive and omit `_TABLE`. Headers use lowercase
`snake_case`, with explicit row subjects rather than an ambiguous `name`.

| Table label | Required header |
| --- | --- |
| `TOP_PORTS name` | `port` |
| `SUBCKT_PORTS name` | `port` |
| `PARAMETER_DEFAULTS name` | `parameter \| value` |
| `PARAMETER_ASSIGNMENTS name` | `parameter \| value` |
| `NETS name` | `net \| incident_pins` |
| `DEVICES name` | `device \| type \| connections \| parameters` |
| `BLACK_BOXES name` | `device \| cell \| pin_basis` |
| `NAMESPACES` | `namespace \| version` |
| `DIAGNOSTICS` | `source \| line \| message` |
| `namespace:local [name]` | Producer-defined local column names |

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
  There is no special empty-value escape. A literal backslash followed by e
  is encoded `\\e`, using the ordinary backslash escape.
- Split delimiters before decoding. Supported escapes are `\\`, `\|`,
  `\n`, `\r`, `\t`, `\s` and the field-specific escapes below. Significant
  edge spaces use `\s`. Printable Unicode text, such as `gain µV/V`, stays
  literal. There is no Unicode escape syntax. Newline, carriage return and tab
  use their named escapes; other control characters and whitespace other than
  ASCII space are rejected, including Unicode line/paragraph separators.
  Unsupported characters and escape sequences are explicit errors, never
  silently removed or replaced. Raw cell and record delimiters cannot occur
  inside a cell. Cells contain Unicode scalar values.
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

The two adjacent separators in X1's row enclose an empty `parameters` cell.
A one-column producer table with no entries contains only its label and header;
an invisible empty row is not another entry. Empty values remain supported in
multi-column rows, including rows whose cells are all empty: their delimiters
make the row visible.


## Reading older files

The reader accepts the historical labels `TOP_LEVEL`, `SUBCKT`,
`NET_INCIDENT_TABLE`, `DEVICE_TABLE`, `BLACK_BOX_TABLE` and
`EXTENSION_NAMESPACES`, with their historical headers (`pin`, `name`,
`incident pins`). Their logical tables share duplicate checks with current names.
Old root declarations may omit their interface header. Earlier grouped/quoted
parameter expressions with unescaped commas are accepted in the legacy dialect.

Distinct current table labels select current lexical rules for the artifact.
Shared-only artifacts, such as a standalone `DIAGNOSTICS` table, remain
legacy-readable because their syntax cannot distinguish the two dialects.
Legacy `\e` and `\uHHHH` encodings are decoded when reading those older files;
they are not emitted. New-format exports encode permitted values literally or
with supported named escapes. A one-column empty data row or a forbidden
character causes an explicit export error with table/row/column context; no
row or character is silently discarded. A literal backslash followed by `u`
remains ordinary data when its backslash is escaped.

Writers emit only the current form. Older readers cannot consume this form,
even when extensions are omitted. The file grammar does not rename Python
fields or annotation-host keys: those remain `PINS`, `PARAMETER_DEFAULTS`,
`PARAMETER_ASSIGNMENTS`, `NET_INCIDENT_TABLE`, `DEVICE_TABLE`, `BLACK_BOX_TABLE`
and `DIAGNOSTICS`. Producer-owned identifiers retain their spelling.

An empty default root has no separate presence bit in the Python model; writers
omit it unless it carries data, a nondefault name or an annotation layout.
Definition-only libraries therefore have no designated root in their files.
Defaults require nonempty parameter names; operative assignments require both
nonempty names and values. Raw device parameter values may be empty. None of
these fields establishes simulator precedence or evaluates an expression.
