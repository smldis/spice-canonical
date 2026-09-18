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
  remain outside this extraction contract. `from_canonical_text` and
  `from_canonical_file` load the custom rendered tables without re-extraction.

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
undefined X calls now retain target, positional `@N` connections and raw overrides
without guessed formal names. Explicit `Device.black_box` metadata records cell
identity and named/positional pin basis. External pin signatures provide an
interface, never internals. This supersedes packing positional nets into an
`unresolved_nets` parameter: extraction owns token boundaries, consumers need not
recover them from a joined string. Type normalization preserves the boundary.
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

## Reusable canonical artifacts

The user requires extraction to be reusable independently of comparison. Canonical
therefore owns a reader for its existing custom tables, rather than adding a second
JSON format or making comparison parse SPICE/external interface configuration.
Optional black-box and diagnostic tables preserve boundaries and evidence. A
reader checks reciprocal net/device incidence and rejects inconsistent tables;
structural punctuation is escaped before rendering and decoded after splitting.
Missing library bodies stay unavailable. This is a data handoff, not simulator
serialization, inferred pin semantics or an algorithm-quality improvement.
Prototype maturity is unchanged.

Review of an extracted `.SUBCKT TOP` with top-level devices showed that table
loading must keep the top-level circuit outside the subcircuit-definition name
scope. The same distinction keeps an undefined external cell named `TOP`
unavailable even when `TOP_LEVEL TOP` exists. This refines artifact validation;
it does not add a new source-language interpretation.
