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
For the parser that produces it, see [extracting a canonical netlist](extraction.md).

## Tables

Each subcircuit has a one-column interface table. Pin order is the declaration
order from the original `.SUBCKT` statement, but numeric pin identifiers are not
introduced.

```text
SUBCKT INV
pin
A
Y
VDD
VSS
```

Each circuit, including `TOP`, has a net-incident table with one row per net.

```text
NET_INCIDENT_TABLE INV
net | incident pins
A | M1.g, M2.g
Y | M1.d, M2.d
VDD | M1.s, M1.b
VSS | M2.s, M2.b
```

An incident pin uses `instance.pin`. Primitive devices use semantic terminal
names such as `d`, `g`, `s`, and `b`. Subcircuit instances use the formal pin
names from the corresponding `SUBCKT` table.

Each circuit also has a device table.

```text
DEVICE_TABLE INV
name | type | connections | parameters
M1 | pmos | d=Y, g=A, s=VDD, b=VDD | model=PCH, W=2u, L=180n
M2 | nmos | d=Y, g=A, s=VSS, b=VSS | model=NCH, W=1u, L=180n
```

Columns are separated by a single ` | `. Cells are not padded to a common
width, so a reader must strip surrounding whitespace rather than rely on
alignment, and an empty trailing cell leaves the row ending in `| `.

A subcircuit instance uses its subcircuit name as its type and maps formal pins
to nets by name.

```text
DEVICE_TABLE TOP
name | type | connections | parameters
X1 | INV | A=in, Y=out, VDD=vdd, VSS=0 |
```

The corresponding net rows are:

```text
NET_INCIDENT_TABLE TOP
net | incident pins
in | X1.A
out | X1.Y
vdd | X1.VDD
0 | X1.VSS
```

## Top Level

The root circuit starts with a reserved marker:

```text
TOP_LEVEL TOP
```

It is followed by the root `NET_INCIDENT_TABLE` and `DEVICE_TABLE`. There is no
root pin table because a SPICE input deck has no declared external pin list.
`TOP_LEVEL` lets a reverse converter locate the root directly without traversing
subcircuit hierarchy or being told the root circuit's display name.
For a library file containing only subcircuit definitions, the marker and both
root tables are omitted; such a representation intentionally has no designated
simulation root.

The root circuit's display name follows the extractor's `top_name`, which
defaults to `TOP`.

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
SUBCKT REGISTER
pin
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

## Delimiters

The structural punctuation is deliberately small:

```text
|     separates table columns
,     separates items within a cell
.     separates an instance name from its pin
=     maps a pin to a net or a parameter to a value
:     is not a structural delimiter; it remains available for bus ranges
< >   enclose bus indices and ranges
```

A literal `|`, backslash, or newline inside a rendered cell is backslash-escaped.
Parameter expressions otherwise retain their source spelling.

## Annotations

The core form is structural. Information not explicitly encoded by ordinary
SPICE, such as pin direction or signal class, can be added later as columns:

```text
SUBCKT INV
pin | direction | class
A | input | signal
Y | output | signal
VDD | input | power
VSS | input | ground
```

Inferred annotations should carry provenance or confidence separately from the
structural extraction. Nothing emits these columns today; the shape is reserved,
not implemented.

## What the representation omits

Analysis commands, options, model bodies, global parameters, and other simulator
directives are intentionally omitted from the structural representation. The
original Eldo or ngspice deck remains the authoritative source for simulation.
