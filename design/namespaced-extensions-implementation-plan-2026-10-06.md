# Namespaced extensions implementation plan

Date: 2026-10-06. Status: canonical implementation complete under the owner's instruction to proceed
with the [Astra review](namespaced-extensions-astra-review-2026-10-06.md).
This records the selected design and execution evidence, not a replacement for
maintained API documentation. The supervisor verified Astra/high in the herdr UI;
the reviewer could not inspect its own UI. Original proposal and review stay intact.

## Selected invariants

- Keep `Circuit`/`Device` structural. Add an immutable envelope to
  `CanonicalNetlist`, with declarations, scoped custom tables, column payloads,
  necessary host-row order/presence, and an exact ordered core-snapshot digest.
- Support additional columns on interface pins, defaults, nets, devices,
  black boxes and diagnostics. Namespace declarations are envelope metadata,
  not recursively extensible.
- Namespace IDs are lowercase dotted authority/project identifiers. Public
  producers should use an authority they control; `private.<project>` identifies
  private conventions. This reduces collisions without authenticating ownership
  or requiring a registry. Versions identify the whole namespace schema.
- Use one preamble, qualified `namespace:local` names and opaque Unicode scalar
  string cells. Encode a whole-cell empty string explicitly; trim only documented
  ASCII formatting and escape control/line-separator characters. Fixed-width
  rows, duplicate headers and undeclared namespaces fail clearly.
- Preserve decoded extension values, ordered columns/rows, duplicates, unused
  declarations and empty annotated hosts. Annotated host rows retain order and
  attachment. Table-block order/formatting is canonicalized. Root and definition
  scopes are distinct; document tables do not reset the current circuit scope.
- Ordinary extended export retains diagnostics and an annotated empty root.
  Explicit suppression of needed data fails. Core-only export is explicit and
  follows existing diagnostic defaults. Unknown namespaces/versions remain data;
  canonical performs no imports, evaluation, schema fetching or evidence I/O.
- Bind the envelope to the full represented core, including order, parameters,
  black-box boundaries and diagnostics. Reject core changes while it is attached;
  no-op normalization preserves it. Projection requires explicit removal.
  Loading checks attachment, not semantic freshness: producer basis/context
  fields are never silently refreshed.
- Document equality includes extensions. Comparator identity continues to hash
  its existing core projection, excluding the new envelope, including when empty.
  Decomposition's circuit digest remains a separate unchanged contract.

## Execution

1. **Envelope and codec.** Add immutable namespace/scope/table/column models,
   validation and functional declare/add/replace/remove/inspect operations.
   Capture a snapshot guard and preserve unrelated namespaces.
2. **Reader/writer.** Implement the preamble and qualified headers/markers;
   preserve necessary annotated-host layout without a second mutable connectivity
   model. Cover inline pin tables, empty hosts and annotated diagnostics.
3. **Consumer boundaries.** Audit normalization, top/closure projections and
   comparator hashing. Reject unsupported transformations explicitly; structural
   read-only expansion remains a view, not a preserving exporter.
4. **Checks and maintained contracts.** Test actual preservation/codec failures,
   independent namespaces, unknown versions, ambiguous scopes/occurrences,
   invalid incidence and guards. Run canonical checks in ASS `.venv`; do not run
   decomposition pytest or its OTA verifier. Update representation/API docs,
   README and affected ontologies. Keep pre-existing changes and local evaluation
   untouched; no commit, publication or history rewrite is part of this work.

Acceptance includes: zero versus one empty row; Unicode whitespace/separators;
ordered/repeated rows; reordered annotated nets; empty optional hosts/root;
diagnostic retention/suppression; root/definition `TOP`; duplicate defaults and
diagnostics; unknown versions and colliding declarations; namespace-only edits;
reconnect/rename/delete/reorder rejection; no-op normalization; projection;
explicit core-only export; annotation-independent comparator identity; and
unchanged reciprocal incidence validation.

## Execution evidence

Steps 1–4 completed in the working tree. The public authoring/inspection types
are re-exported through `spice_canonical.canonical_netlist`; the implementation
lives in `extensions.py`. Reader/writer support both extension forms, inline
pin hosts, opaque strings, unknown schemas and required host layout. Named
rows use case-folded identity; default/diagnostic occurrences are positional.
Ordered structural hosts cannot be reordered through layout metadata; net and
black-box host layouts can preserve their independently supplied order.

Normalization now retains the envelope on no-ops and rejects actual core changes.
Both document projections require explicit removal. Comparator hashing excludes
the envelope while keeping its prior core/diagnostic ordering semantics.
Maintained representation, API, inspection and README docs plus canonical,
comparison and containing ontologies describe the adopted contract.

Verification: touched Python files compile; 173 checks passed across the complete
canonical suite and focused comparison identity/canonical-input/context tests.
The composed Sphinx build succeeds with eight existing warnings in decomposition
links/highlighting and no new canonical warning. No decomposition pytest, OTA
verifier, simulation, corpus evaluation, commit or publication was performed.
The supervisor verified all 159 pre-review modified/untracked file hashes before
implementation; task changes were then inspected by scoped diffs. The temporary
hash manifest became unavailable after the environment's sandbox change, so no
post-implementation full hash audit is claimed.

Durable-memory synchronization could not run after the environment change:
the basic-memory MCP methods were no longer exposed and server discovery found
no basic-memory resource. Earlier project notes were successfully retrieved
before that change. This plan and maintained contracts retain the outcome for
later synchronization; no direct write outside the permitted workspace was used.

Remaining limits: namespace authority is convention, unknown producer references
and evidence validity are not verified, the snapshot guard is in-memory, and
automatic annotation migration/projection remains unsupported. Explicit producer
basis/context is necessary to detect external edits preceding a load. Renderer
work below remains planned, not implemented.

## Renderer implementation plan — subsequent consumer work

The renderer will consume the completed transport contract. This section plans
that work; it does not introduce another analysis model or implement it now.

1. **Declare the decomposition schema.** Define a namespace/version and an
   adapter from saved `CircuitAnalysis` to canonical plus findings, membership
   roles, bound net roles, rules/tagging levels, explanations and unresolved
   conditions. Preserve overlapping findings. Start with an explicitly labeled
   inspection export; retain the existing analysis artifact for reconstruction.
   Record snapshot identity, producer provenance and supplied-versus-derived
   status. Never invent precise producing-pass history from tagging levels.
2. **Define reading options.** Choose full/compact views, deterministic ordering,
   reversible aliases and optional human grouping with its own provenance.
   Render each physical element once and link all interpretations; preserve
   opaque devices/boundaries and context limitations. Human symmetry grouping
   remains distinguishable from recognition.
3. **Centralize readable SPICE export.** Serialize supported device families from
   exact interfaces/model authority and retain identity mappings. Parameter
   binding is an explicit separate input: show raw expressions and sourced
   bindings, never silently substitute absent defaults. Mark omitted simulator
   directives and unsupported serialization; original decks remain authority.
4. **Exercise real witnesses locally.** Use saved analog_pmic (literal values),
   amp_030 (symbolic defaults/overlapping symmetric outputs) and ldo_008
   (zero-volt probe/context gap). Check complete device/terminal/model mapping,
   alias collisions, uncertain findings and unknown namespaces. Keep evaluation
   ignored and do not publish source artifacts or personal notes. These checks
   establish a reading view, not electrical equivalence.
5. **Expose and document one operation.** Provide a Python export/render entry
   point and, if useful, a thin CLI over the same operation. Document inspection
   versus reconstructible interchange, extension preservation, snapshot guards
   and explicit renderer limits. Update decomposition and containing ontologies
   if these become adopted cross-unit contracts.
