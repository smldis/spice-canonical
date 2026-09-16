# SPICE Canonical Ontology

This is the ongoing self-study of the component rooted here. Briefly inhabit
its perspective as you work: what are you learning about what it is, why it
exists, and what it might become? Help this account evolve when you have
something useful to add.

## Purpose and scope

SPICE Canonical extracts a deterministic structural view of Eldo and ngspice
decks: circuits, devices, nets, hierarchy, and diagnostics suitable for graph
consumers. The simulator deck remains authoritative.

## Mode of being

**Development state:** `prototype`

Its runnable parser studies how much deterministic, graph-oriented structure
can be exposed across real Eldo and ngspice inputs while leaving the simulator
deck authoritative and unsupported meaning visible in diagnostics. Corpus
friction, consumer needs, and parsing failures are evidence for changing the
representation, syntax boundary, or ontology. Compatibility should grow from
concrete decks and consumers, with inspectable output and focused tests, not
from an attempt at speculative or exhaustive dialect coverage.

## Current contracts

- Python API: `spice_canonical.canonical_netlist`.
- CLI: `spice-canonical`.
- Inputs: netlist text/files, format selection, include boundaries, external
  subcircuit pin declarations, and device type mappings.
- Outputs: canonical circuit data and explicit diagnostics. Subcircuit declaration
  defaults are ordered `Parameter` values on `Circuit.parameter_defaults` and
  optional definition-scoped `PARAMETER_DEFAULTS` tables. Names and raw expressions
  survive extraction and device-type normalization; instance parameters remain
  explicit overrides. Default-free rendering and three-argument Circuit
  construction retain their previous behavior.
- Malformed declaration assignments raise structural errors; expression evaluation,
  default expansion, global `.PARAM` semantics, and model-body interpretation
  remain outside this extraction contract. There is no canonical-text parser.

A default-only edit previously disappeared from the structural view. Regression
fixtures now distinguish it without resolving simulator semantics. This evidence
supports preserving declared configuration beside connectivity: graph structure
alone cannot expose every meaningful input change, and retaining an expression
is a narrower commitment than interpreting it.

## Contribution to the parent

The unit contributes the structural input contract consumed explicitly by
`netlist-decomposition` and available to future analysis units.

## Exclusions

It is not a lossless netlist serializer, simulator, sidecar editor, functional
classifier, model-library interpreter, or project-wide study representation.

## Child composition

There are currently no child units.

## Incomplete library evidence

Missing includes already diagnose their source while preserving available devices;
undefined X calls retain target, raw positional nets and parameters without guessed
formal pins. External pin signatures provide an interface, never internals.
Undeclared MOS/diode models already retain syntax-defined terminals and generic
types without inferred polarity. Model availability is not validated, and deliberate
include/.LIB boundaries are silent; absence of diagnostics is not semantic completeness.
An undeclared BJT with extra positional tokens now uses the existing unresolved
representation with raw token content and a source diagnostic. This explicitly
supersedes the three-terminal guess: uncertain terminal/model boundaries must not
become represented incidence. Exactly three terminals plus an undeclared model
remain usable, as do syntax-defined MOS/diode roles. The API shape is unchanged;
ambiguous BJT rows change from guessed connections/model to unresolved raw evidence.

Observed consumer friction was downstream: an opaque call invalidated unrelated
certified comparison components. Available extraction and complete interpretation
are separate commitments; preserving one must not silently claim the other.
