# SPICE Canonical

Read the structure out of a SPICE deck without becoming a simulator.

SPICE Canonical parses an Eldo or ngspice netlist and emits a deterministic,
tabular view of what is connected to what: circuits, devices, nets, hierarchy,
and — where the deck says something it cannot resolve — diagnostics. The
simulator deck stays authoritative. Nothing here executes, edits, or interprets
a design; it makes the connectivity legible to a graph consumer or a language
model.

```bash
spice-canonical inverter.cir --output canonical.txt
```

An inverter instantiated at the top of a deck comes back as two reciprocal
tables per circuit, plus a pin table for each subcircuit:

```text
TOP_LEVEL TOP

NET_INCIDENT_TABLE TOP
net | incident pins
vdd | VDD1.p, X1.VDD
0 | VDD1.n, VIN.n, X1.VSS, CL.n
in | VIN.p, X1.A
out | X1.Y, CL.p

DEVICE_TABLE TOP
name | type | connections | parameters
VDD1 | vsource | p=vdd, n=0 | dc=1.8
VIN | vsource | p=in, n=0 | waveform=PULSE(0 1.8 0 1n 1n 5n 10n)
X1 | INV | A=in, Y=out, VDD=vdd, VSS=0 |
CL | capacitor | p=out, n=0 | value=10f

SUBCKT INV
pin
A
Y
VDD
VSS

NET_INCIDENT_TABLE INV
net | incident pins
A | M1.g, M2.g
Y | M1.d, M2.d
VDD | M1.s, M1.b
VSS | M2.s, M2.b

DEVICE_TABLE INV
name | type | connections | parameters
M1 | pmos | d=Y, g=A, s=VDD, b=VDD | model=PCH, W=2u, L=180n
M2 | nmos | d=Y, g=A, s=VSS, b=VSS | model=NCH, W=1u, L=180n
```

`X1` uses the formal pin names `A`, `Y`, `VDD`, `VSS` rather than pin numbers,
and the `INV` body is typed `pmos` and `nmos` from its `.MODEL` declarations.

Two ideas carry the rest:

- **The two views cannot disagree.** The net-incident table is derived from the
  parsed device connections, so every device connection has exactly one
  reciprocal net incident, by construction rather than by discipline.
- **Unsupported is said, not guessed.** A device the parser cannot resolve keeps
  its raw text and produces a diagnostic. Inventing terminal names would create
  false graph edges, which is worse than an admitted gap.

## Start here

| If you want to | Read |
| --- | --- |
| consume the output, or write a reverse converter | [The canonical representation](representation.md) |
| run the extractor from Python or the command line | [Extracting a canonical netlist](extraction.md) |
| know which dialects and devices are handled | [Supported extraction](extraction.md#supported-extraction) |
| keep a vendor model library opaque | [Includes and boundaries](extraction.md#includes-and-boundaries) |
| find real netlists to test or extend it against | [Integrated-circuit netlist R&D corpus](netlist-corpus.md) |

## What state this is in

This unit is a **prototype**, and its scope is deliberately evidence-led rather
than exhaustive. Two dialects are supported — Eldo and ngspice — and
compatibility is meant to grow from concrete decks and consumers that fail,
not from speculative dialect coverage. Corpus friction, parsing failures, and
what a downstream consumer actually needs are the arguments for changing the
representation.

So expect gaps, and expect them to be visible. The
[corpus page](netlist-corpus.md) is where the known ones are named: trailing
backslash continuations, Spectre-style syntax, `.LIB` section selection, and
PDK primitive schemas are all identified, none are implemented. The unit's
`ONTOLOME.md` states the contracts it does guarantee today, and what it
excludes on purpose.

```{toctree}
:maxdepth: 2

representation
extraction
netlist-corpus
```
