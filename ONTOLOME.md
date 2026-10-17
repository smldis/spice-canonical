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
  explicit overrides. Operative `.PARAM` declarations are ordered values on
  `Circuit.parameter_assignments`: all file-scope declarations share one root
  `PARAMETER_ASSIGNMENTS` table; local body declarations belong to their definition.
  Duplicate names and expressions survive, including parameter-only roots and
  definition-library export. Inputs without defaults/assignments and existing
  three-/four-argument Circuit construction retain their previous behavior.
- Malformed declaration assignments raise structural errors; expression evaluation,
  parameter precedence, default expansion, and model-body interpretation
  remain outside this extraction contract. `from_canonical_text` and
  `from_canonical_file` load the custom rendered tables without re-extraction.

A default-only edit previously disappeared from the structural view. Regression
fixtures now distinguish it without resolving simulator semantics. This evidence
supports preserving declared configuration beside connectivity: graph structure
alone cannot expose every meaningful input change, and retaining an expression
is a narrower commitment than interpreting it.

The sized-circuit handoff exposed the same boundary for operative `.PARAM`
assignments: excluding evaluation had also excluded declarations from saved core
objects. That omission is now revised explicitly. Source-owned parameter context
belongs in canonical core rather than a producer namespace, so dropping analysis
annotations cannot drop supplied sizing/bias values. A single root table groups
all top-level declarations; it preserves ordered raw ties, not a simulator's
resolved parameter environment. Old parameter-free snapshot guards retain their
identity; assignment changes participate in new guards. Selected `Circuit`
objects still need their enclosing netlist for global context.

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
Plain rendered canonical tables omit diagnostic rows by default; an explicit
render/CLI flag includes them. Extraction still retains diagnostics in Python,
CLI warnings remain a separate stderr stream, and strict mode still tests the
extraction result. This makes the structural artifact the default while leaving
the full diagnostic record available by choice.

## Namespaced artifact data

The owner requested project-defined tables and columns in a common canonical
artifact, then adopted the conservative direction of an independent Astra
review on 2026-10-06. Canonical now carries immutable versioned namespaces,
document/root/definition-scoped custom tables and columns on pin, default, net,
device, black-box and diagnostic hosts. Unknown producer schemas remain data;
canonical owns envelope and attachment validation, never functional meaning,
schema fetching or producer execution. Structural Circuit/Device objects remain
unchanged. Namespace identifiers reduce accidental collisions without proving
ownership. The original simulator deck remains authoritative.

The preservation commitment is decoded payload, ordered headers/rows and correct
attachment, including empty annotated hosts and unused declarations. Required
host layout is metadata, not a second connectivity authority. The codec now
distinguishes an empty cell/row and preserves Unicode whitespace and separators.
Extended export retains diagnostics; plain export retains its earlier default.
Core-only export and removal are explicit. An envelope is bound to the exact
ordered core snapshot: core-changing normalization fails and projection requires
removal. Read-only structural views do not claim to transport annotations.
This simple boundary avoids guessing how opaque references follow edits.

Attachment is not evidence validity. Loading binds the represented snapshot;
external edits before loading are not inferred. Producers retain their own basis,
assumptions and uncertainty. Automatic migration, annotation-aware expansion and
universal reference/schema semantics remain unbuilt. Focused preservation and
consumer checks exercise these boundaries; prototype maturity is unchanged.

Review of an extracted `.SUBCKT TOP` with top-level devices showed that table
loading must keep the top-level circuit outside the subcircuit-definition name
scope. The same distinction keeps an undefined external cell named `TOP`
unavailable even when `TOP_LEVEL TOP` exists. This refines artifact validation;
it does not add a new source-language interpretation.


## Read-only inspection and source evidence

The Python inspection surface now composes existing immutable circuit data with
shared incidence, call resolution, definition closure, bounded occurrence
expansion, and terminal-incidence graph queries. The renderer uses the same
incidence helper. Direct reports describe the root after include expansion;
root and definition namespaces stay separate. Defaults and overrides remain
ordered and unevaluated. Graph adjacency excludes coupling/control relationships
stored only as parameters and makes no electrical or functional claim.

An optional file-extraction result carries source locations, include occurrences
and outcomes, and raw lexical root-scope PARAM/MODEL declarations alongside the
canonical result. This revises the earlier blanket omission of global declaration
evidence, while retaining the exclusion on parameter/model interpretation.
Evidence is a snapshot, separate from canonical serialization: saved connectivity
alone cannot recover it. General directives, title and control scripts remain
excluded. Include evidence describes current extractor traversal, not simulator
control semantics. No new CLI surface or editing operation is provided.

Bounded expansion exposes opaque, recursive, ambiguous and truncated boundaries;
additional global nets are caller-supplied. Existing normalization stores original
types in raw source_type parameters, so authored collisions can leave identity
unrecoverable. Inspection reports observable ambiguity rather than inventing
missing history. This is a useful limit of the present representation, not proof
that normalization is a complete provenance mechanism. Prototype maturity is
unchanged.

Top-level canonical export is a projection with a changed availability boundary:
implemented calls whose definitions are omitted become named black boxes in the
saved artifact. Already external calls keep their existing markers; ambiguous
calls are not assigned a guessed identity. This keeps the artifact's explicit
boundary inventory aligned with the bodies it actually contains.
An authored `source_type` collision can still lose its ambiguous call status
when projection omits the candidate definitions; the current tables have no
explicit ambiguity marker. This is an observed limit, not a claim that the
call has a known missing target.
