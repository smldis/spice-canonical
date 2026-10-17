# Canonical format: explicit port tables and a simple grammar

**Status:** draft for owner review, 2026-10-17. Not implemented or adopted.
The existing renderer, parser, agent instructions and saved files are unchanged.

## Proposed naming

Separate a circuit-scope declaration from its ordered external-port table:

```text
SUBCKT amplifier

PORT_TABLE amplifier
port
IN
OUT
VDD
VSS
```

`SUBCKT amplifier` declares a reusable definition. `PORT_TABLE amplifier` names
the table; `port` is its column header. Only its data rows declare ports, in
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

The shorter alternative is `SUBCKT_PORT_TABLE amplifier` followed by the header
and rows. That changes fewer lines but keeps scope declaration and table
declaration combined. **Recommendation: use separate `SUBCKT` and `PORT_TABLE`
blocks**, consistent with the explicit names of the other tables and usable for
both root and definition interfaces. The header name alone cannot prevent a
reader mistake; the grammar and example must identify headers as syntax.

## Simple grammar

This describes the proposed normal emitted form. It is not a claim that the
current parser accepts it. Read literal strings in quotes; `[]` means optional,
`{}` means zero or more repetitions, and `|` outside quotes means alternatives.
`LF` is a line-feed character. Tables are separated by at least one empty line.

```ebnf
file              = [ block, { gap, block } ], [ LF ];
gap               = LF, LF, { LF };

block             = scope-declaration | table;
scope-declaration = ("TOP_LEVEL" | "SUBCKT"), " ", name;

table             = table-marker, LF, header, { LF, row };
table-marker      = core-table, " ", name
                  | "EXTENSION_NAMESPACES"
                  | "DIAGNOSTICS"
                  | qualified-name, [ " ", name ];

core-table        = "PORT_TABLE"
                  | "PARAMETER_DEFAULTS"
                  | "PARAMETER_ASSIGNMENTS"
                  | "NET_INCIDENT_TABLE"
                  | "DEVICE_TABLE"
                  | "BLACK_BOX_TABLE";

header            = column, { " | ", column };
row               = cell, { " | ", cell };

connections       = [ assignment, { ", ", assignment } ];
parameters        = [ assignment, { ", ", assignment } ];
assignment        = key, "=", value;
incidents         = [ incident, { ", ", incident } ];
incident          = device-name, ".", pin-name;

qualified-name    = namespace, ":", local-name;
```

Lexical rules, deliberately separate from circuit interpretation:

- `name`, `column`, `device-name`, `pin-name` and `key` are nonempty encoded
  strings. `cell` and `value` may be empty where their field permits it.
- Split delimiters **before** decoding escapes. A raw `|` separates columns;
  `\|` is a literal character inside a cell. The spaces shown around separators
  are the normal writer style; a reader can trim ordinary surrounding formatting
  whitespace without altering escaped spaces.
- Preserve the existing escapes: `\\`, `\|`, `\n`, `\r`, `\t`, `\s` and
  `\uHHHH`. Escape literal commas inside list items as `\,`, literal equals in
  assignment keys as `\=`, and literal dots in incident device/pin names as
  `\.`. `\s` preserves significant spaces. Escape raw control/separator
  characters instead of allowing them to become record boundaries.
- A cell containing exactly `\e` represents an empty string. In a one-column
  custom table this distinguishes one empty row from no rows. An empty required
  port or identifier is invalid. A multi-column empty field may remain empty
  between separators, including at the end of a device row.
- A namespace has at least two dot-separated segments, each matching
  `[a-z][a-z0-9_-]*`. A local name matches `[A-Za-z][A-Za-z0-9_-]*`.
  Namespace declarations use positive ASCII decimal versions without leading
  zeros. These are producer-schema versions, not a new core-file version.

### Table schemas

Core columns are fixed, in the order below. Optional namespaced columns follow
them. Each row must have exactly as many cells as its header. A header is always
present even when the table has no rows.

| Table marker | Required header | Scope |
| --- | --- | --- |
| `PORT_TABLE name` | `port` | Current root or definition |
| `PARAMETER_DEFAULTS name` | `name \| value` | Current root or definition |
| `PARAMETER_ASSIGNMENTS name` | `name \| value` | Current root or definition |
| `NET_INCIDENT_TABLE name` | `net \| incident pins` | Current root or definition |
| `DEVICE_TABLE name` | `name \| type \| connections \| parameters` | Current root or definition |
| `BLACK_BOX_TABLE name` | `name \| cell \| pin_basis` | Current root or definition |
| `EXTENSION_NAMESPACES` | `namespace \| version` | Document; first block if present |
| `DIAGNOSTICS` | `source \| line \| message` | Document |
| `namespace:table name` | Producer-defined unique column names | Current root or definition |
| `namespace:table` | Producer-defined unique column names | Document |

`EXTENSION_NAMESPACES` itself has no additional columns. Qualified tables and
columns require a preceding declaration; unfamiliar declared schemas remain
opaque data. Unknown unqualified markers are errors.

### Scope and meaning

The grammar identifies records. These short constraints establish their meaning:

1. `TOP_LEVEL` declares the root, at most once. `SUBCKT` declares a definition;
   definitions do not instantiate hardware. Root and definition name spaces
   remain distinct, even when both names are `TOP`. Definition names are unique
   case-insensitively.
2. Each circuit table names the current root/definition. The name must match
   that declaration. A document-scoped table does not change the current circuit.
3. Every definition has exactly one `PORT_TABLE`, including an empty table for
   a zero-port definition. Root ports are normally absent in extracted SPICE;
   an explicit root interface, including extension columns, uses the same table.
4. Each declared circuit has exactly one `NET_INCIDENT_TABLE` and one
   `DEVICE_TABLE`. Other core tables are optional and cannot be duplicated in
   one scope. The writer places ports first, then defaults, assignments, nets,
   devices, black boxes and circuit extensions. Diagnostics are written last.
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

## Complete definition-only example

This file declares a reusable three-port divider; it contains no root instance:

```text
SUBCKT divider

PORT_TABLE divider
port
IN
OUT
RET

NET_INCIDENT_TABLE divider
net | incident pins
IN | R1.p
OUT | R1.n, R2.p
RET | R2.n

DEVICE_TABLE divider
name | type | connections | parameters
R1 | resistor | p=IN, n=OUT | value=10k
R2 | resistor | p=OUT, n=RET | value=10k
```

The ordered ports are exactly `IN`, `OUT`, `RET`. `port`, `net`, `name` and
`parameters` are headers. Instantiation requires a device row in another scope;
this example alone asserts no supply, load, operating state or simulation result.

## Compatibility and implementation after review

- New writers would emit explicit `PORT_TABLE` blocks and the `port` header.
  New readers would also accept the existing combined `SUBCKT`/`pin` form and
  legacy inline root pin tables. Reject a duplicate inline-plus-explicit
  interface rather than guessing which wins. Old readers will not accept the
  new syntax; update consumers before exchanging newly rendered files.
- Preserve existing table/escape compatibility and namespaced annotations.
  Changing the public text marker need not rename the Python `Circuit.pins`
  field or the existing `PINS` extension-host API. Audit that boundary during
  implementation instead of adding unnecessary API migration.
- Leave frozen evaluation inputs, instructions, answers and scores unchanged.
  Updated agent instructions should embed the compact grammar, schemas and
  worked example, with essential scope semantics. A grammar link alone cannot
  serve an input-only reader that cannot open files.
- Keep the proposal and later implementation in focused remote PRs. The local
  checkout has other unmerged commits and dirty changes; do not silently bundle
  them into this format change. The proposal can be reviewed independently;
  implementation prerequisites require their own explicit review or PR stack.

**Review requested before implementation:** the explicit `PORT_TABLE` name,
separating it from `SUBCKT`, the `port` column header, and whether this grammar
plus the short scope rules is clear enough to give an agent. No syntax changes
are adopted merely by opening the proposal PR.
