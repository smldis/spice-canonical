# Independent architectural review: namespaced canonical extensions

Date: 2026-10-06. Reviewed: [namespaced-extensions-proposal-2026-10-06.md](namespaced-extensions-proposal-2026-10-06.md), working-tree version. Requested routing: `gpt-6-astra`, high effort; actual model/effort were not exposed by the available interface and could not be independently verified.

## Verdict: revise before implementation

The concept is sound and meets a real requirement: arbitrary projects need both custom tables and additional columns in one reusable canonical artifact. The draft correctly separates structural extraction from interpretation and makes unknown-extension preservation fundamental. However, its strongest guarantee exceeds what its grammar, attachment model and existing transformations currently explain. Settle those semantics before making files or APIs that others depend on.

Confidence is high in the implementation findings below, moderate in the preferred design. Evidence includes actual working-tree readers, writers, inspection helpers, tests and two representative consumers. No extension implementation exists to assess, and this review does not establish all consumers' requirements. Recommendations below are proposals, not adopted contracts.

The [manifesto](../../MANIFESTO.md) supports preserving inspectable evidence while keeping prototypes proportionate. Canonical's [ontology](../ONTOLOME.md) keeps the simulator deck authoritative. Extensions should broaden what an artifact can carry without granting functional labels authority to rewrite literal connectivity.

## SWOT

| | Assessment specific to this design |
|---|---|
| Strengths | One inspectable artifact; arbitrary producer schemas; both compact columns and relational tables; unknown versions load without dependencies; explicit rejection rather than silent loss; structural API can remain useful independently. |
| Weaknesses | Project names are weak ownership identifiers; unspecified empty-row grammar; preservation conflicts with regenerated/omitted tables; attachment validity is easier to promise than semantic freshness; transformation and digest impacts are understated. |
| Opportunities | Carry overlapping findings, memberships and provenance without exclusive device classifications; make preservation boundaries explicit across tools; establish separate circuit/document identities; prototype transport before standardizing consumer semantics. |
| Threats | Two producers claim the same namespace/version; a label survives a reconnect and looks current; projections strand opaque references; annotations unexpectedly alter comparison identities; local source/context evidence travels farther than its producer intended. |

## Must settle before implementation

### 1. Make the preservation guarantee executable

**Trigger:** An accepted net table lists `0` before `a`, while device connections encounter `a` first. The reader validates incidence but discards the original net-row representation; rendering regenerates first-use order. An appended annotation column therefore cannot preserve both its input sequence and attachment using only the existing circuit model.

**Evidence:** [reader](../src/spice_canonical/canonical_text.py#L172), lines 172–198; [incidence](../src/spice_canonical/inspect.py#L27), lines 27–36; [renderer](../src/spice_canonical/canonical_netlist.py#L963), lines 963–993. A synthetic probe confirmed accepted reordered input renders differently. Another confirmed empty `PARAMETER_DEFAULTS` and `BLACK_BOX_TABLE` headers disappear. Default [rendering](../src/spice_canonical/canonical_netlist.py#L84), lines 84–107, also omits diagnostics and an empty default root.

**Consequence:** The promise to preserve values, row order and attachment needs retained layout information. An empty annotated table still contains meaningful headers. An annotation on a diagnostic cannot survive omission of its host. This is a fixable draft gap, not a reason to abandon columns.

**Recommendation:** Define preservation as decoded cell values, ordered headers, ordered rows including duplicates, scope, declarations including unused ones, and presence of empty extension-bearing tables. Preserve host-row order wherever columns are attached, including generated net rows. Permit canonical ordering of table blocks and declarations; do not promise original whitespace or core spelling aliases. Retain only necessary layout metadata, not another connectivity authority. An extension-bearing empty root must be emitted. Artifact saving must retain annotated diagnostics; explicitly suppressing them must fail or explicitly remove their annotations. Resolve how that policy relates to today's `render(include_diagnostics=False)` before coding.

### 2. Specify a complete envelope grammar, including small awkward cases

**Trigger:** A custom one-column table has one row containing the empty string. Existing `_cell('')` emits nothing, which the block parser treats as a separator. Opaque strings containing U+2028 or vertical tab introduce unintended line boundaries; edge U+00A0 is stripped.

**Evidence:** [codec](../src/spice_canonical/canonical_netlist.py#L997), lines 997–1008, and [parser](../src/spice_canonical/canonical_text.py#L12), lines 12–52 and 73–90. Read-only probes reproduced these results using current diagnostic cells and the shared codec. They are current codec findings, not tests of an unbuilt extension parser.

**Consequence:** “Opaque strings with existing escaping” does not define a lossless string domain. The proposal also says “any core table” without explaining the inline `pin` table after `SUBCKT`/`TOP_LEVEL`, or whether namespace declarations themselves are extensible.

**Recommendation:** Add an explicit whole-cell empty-string encoding, distinguish zero rows from one empty row, and make splitting/trimming operate on the documented separators. Either escape additional line/whitespace characters or reject them explicitly at authoring; never silently normalize them. Require at least one header, fixed row widths and no duplicate headers. JSON is an ordinary string unless the producer's schema says otherwise; `null` remains literal text.

Use one namespace preamble before all circuits. Specify ASCII identifier patterns, case rules, whitespace, marker argument escaping, and duplicate-declaration policy. Enumerate eligible hosts: pin interface, defaults, nets, devices, black boxes and diagnostics. Treat declarations as envelope metadata, not recursively extensible tables. Internally identify scopes as document, root, or definition plus case-folded name. A circuit argument must match the current circuit, while a document table neither acquires nor resets that scope. Root `TOP` and definition `TOP` are distinct. Table uniqueness is `(scope, namespace, local-name)`, not merely marker text. Unknown unqualified core markers must still fail; unknown namespace versions do not imply support for a future core grammar.

### 3. Separate attachment identity from evidence validity

**Trigger:** `R1` is reconnected from `out` to `bias`, retaining its name. A `demo:role=output_load` column remains attached under the proposed named-row rule, although its assertion may now be false. A table `demo:members` can mention deleted `R2` only inside an opaque cell; generic attachment validation cannot discover that reference.

**Consequence:** Valid attachment proves where a value is stored, not why it remains applicable. Detecting dangling column hosts cannot justify “valid” custom-table claims. Moreover, two identical declaration defaults `W=1, W=1` can exchange human intent without changing any core-table fingerprint. Neither ordinals nor hashes recover edit history.

**Evidence:** Duplicate defaults intentionally remain ordered ([representation](../docs/representation.md#L44), lines 44–54; [tests](../tests/test_parameter_defaults.py#L64), lines 64–73). Core device, pin and net uniqueness is case-insensitive in the [reader](../src/spice_canonical/canonical_text.py#L55), lines 55–58, 154–176 and 183–195. Construction of frozen [model objects](../src/spice_canonical/canonical_netlist.py#L22), lines 22–82, does not itself enforce those invariants.

**Recommendation:** Define host keys precisely and validate programmatically authored envelopes too. Scope/table-qualified case-folded names suit unique named rows; defaults and diagnostics require ordered occurrences. Fingerprints must specify an ordered, decoded core representation, exclude extension values, and avoid dependence on incidental renderer whitespace. Identical occurrences have positional identity only. Delete/rename/reorder behavior must be explicit; do not advertise durable entity identity.

For a simpler first slice, bind the entire extension bundle to the exact core snapshot captured at load/attachment. Refuse core-changing transforms until the caller explicitly removes or reauthors the bundle. This conservative policy costs editing convenience but eliminates mixed implicit migration rules. It cannot detect an externally edited file whose annotation basis was not saved. Producers needing validity checks must retain their original basis digest and assumptions; loading must never silently refresh that evidence.

### 4. Namespace spelling is not ownership or compatibility

**Trigger:** Two unrelated teams choose `analysis`, version `1`, with incompatible `analysis:findings` schemas. The file is internally consistent; the declaration cannot expose the collision. Likewise, a newer schema may retain familiar headers while changing their meaning.

**Consequence:** Rejecting conflicting version declarations only catches one collision class. Package installation, producer identity and schema identity are different things.

**Recommendation:** Use a stable authority-qualified schema identifier, such as an owned reverse-domain/project name, with explicitly documented private-name conventions. This reduces accidental collision without a registry or online resolution; it does not authenticate authorship. Namespace ownership covers tables and columns together. The integer identifies the complete namespace schema, not the emitting package release. Breaking semantics require a new version; forks choose a new namespace unless coordinated. Explicit consumers interpret only versions they support; everyone else preserves the payload. Unknown-version replacement or relabeling must be an explicit producer action. Keeping one version per namespace per file is a reasonable initial limitation; incompatible datasets require conversion, separate files or distinct schema identities.

### 5. Audit actual transformation and identity boundaries in the first slice

**Trigger/evidence:** Adding a default field alone leaves several different behaviors:

| Existing path | Consequence of a naive field addition |
|---|---|
| [Normalization](../src/spice_canonical/canonical_netlist.py#L261), lines 261–300 | Reconstructs `CanonicalNetlist`; a new field defaults away, even with a nonempty map that changes no devices. |
| [Top projection](../src/spice_canonical/inspect.py#L108), lines 108–124 | `replace` retains extensions while deleting definitions and converting implemented calls to black boxes. |
| [Definition closure](../src/spice_canonical/inspect.py#L127), lines 127–135 | Constructs a fresh netlist, changes root/definition availability and otherwise loses extensions. |
| [Comparison identity](../../netlist-comparison/src/netlist_comparison/report.py#L10), lines 10–15 | Hashes `asdict(netlist)`: even an empty new field changes identities; populated annotations also affect them. [Batch preparation](../../netlist-comparison/src/netlist_comparison/operator_scoped.py#L293), lines 293–302, uses these identities. |

**Recommendation:** Publish an operation matrix: preserve, reject, explicit discard, or structural read-only view. Unknown payloads may reference any removed scope, so projection cannot safely prune only apparently local attachments. Refusing extension-bearing projection initially is simpler and honest. No-op normalization should preserve exactly; changed normalization follows the chosen mutation policy.

Separate document equality/hash, represented-core identity and producer evidence-basis identity. Keeping structural `Circuit` equality unchanged is valuable. Do not casually call a hash “connectivity”: defaults, raw parameters and black-box boundaries also matter. Comparison's current hash includes diagnostics and sorts devices; decomposition's [circuit digest](../../netlist-decomposition/src/netlist_decomposition/logic.py#L253), lines 253–256, preserves exact circuit order. These are different contracts, not one universal digest. Decide the comparison identity change deliberately and test it, rather than inheriting it from dataclass serialization.

Comparison [loads through canonical](../../netlist-comparison/src/netlist_comparison/cli.py#L247), lines 247–251, but emits its own [catalog](../../netlist-comparison/src/netlist_comparison/report.py#L56), lines 56–74. Canonical [expansion](../src/spice_canonical/inspect.py#L163), lines 163–195, produces a structural view. Neither must become an annotation-preserving document exporter. Document that distinction. Comparison already [rejects root/definition name collisions](../../netlist-comparison/src/netlist_comparison/expand.py#L12), lines 12–20; extension support need not solve that separate limitation, but must not imply otherwise.

## Recommended minimal design and alternatives

Keep `Circuit` and `Device` structural. Add a small immutable envelope on `CanonicalNetlist`: namespace declarations, scoped custom tables, column payloads, necessary host layout/presence, and a core-snapshot guard. Parsing validates envelope shape and reciprocal incidence; the ordinary preservation writer validates attachments. Namespace edits preserve all other payloads, including unknown versions. Provide explicit core-only export. Initially reject core-changing transformations with attached extensions, as described above. This is an artifact transport prototype with both requested extension forms, not a generic graph engine.

| Alternative | Tradeoff |
|---|---|
| Draft's named-row attachments plus guarded positional rows | More convenient device reorder/edit behavior; requires table-specific identity and invalidation rules immediately, while still not solving semantic staleness. Viable after those rules are specified. |
| Recommended snapshot-bound envelope | Simpler first implementation and predictable preservation; conservative rejection makes subsequent circuit editing less convenient. Producers can reauthor explicitly. |
| Generic table document as authoritative artifact, typed circuit projection | Naturally retains all table layout and unknown content; creates a document/circuit editing boundary. Viable if faithful arbitrary-table editing is the dominant use case. Avoid independently mutable copies of connectivity. |
| Per-`Circuit` extensions | Easier attachments when passing a circuit alone, but still needs a document layer for declarations/diagnostics and changes existing snapshot serialization and hashes. Poorer fit for this first slice. |

The draft's ban on a parallel model should target duplicate authority, not forbid the small document metadata required by its guarantee. Conversely, sidecars or tables-only transport do not satisfy the owner's same-file columns requirement.

Shared findings need no universal schema: a producer can define `findings(id, kind, basis)`, `members(finding, device, role)`, `net_relations(finding, net, role)` and `evidence(finding, source, detail)`. Two findings may share a member; direction/class columns are optional conveniences, never rewrites of incidence. Cross-scope references need producer-defined scope discriminators, not naked names.

Decomposition's [CircuitAnalysis](../../netlist-decomposition/src/netlist_decomposition/analysis.py#L110), lines 110–194, already carries snapshots, overlapping findings, explanations, measurements, context and correspondence. Its [loader](../../netlist-decomposition/src/netlist_decomposition/analysis.py#L307), lines 307–347, is closed and validates references. An eventual namespace adapter must declare whether it exports a summary or a reconstructible analysis; do not invent a second analysis engine inside canonical or imply arbitrary tables inherit that validation.

Useful later work includes such an adapter, selective migration and producer validators. Canonical must never import a namespace package, execute plugins, fetch schemas, dereference evidence paths or treat strings as trusted markup. Producer validation remains opt-in and explicitly scoped. Preserved provenance can include local paths or private context: preservation is not publication approval. No server, authentication system or generalized resource framework is justified by this task.

Remaining owner decisions are the strict initial mutation policy, namespace authority convention, exact ordering/string guarantees, and the preservation writer's diagnostics/API behavior. These should be recorded before implementation; they require no speculative migration infrastructure.

## Acceptance cases

1. Two independent namespaces reuse local names; unknown versions survive without producer imports. Conflicting declarations and unsupported interpretation fail distinctly.
2. Zero rows, one empty one-column row, duplicate rows, empty trailing cells, ordered headers, escaped punctuation and documented Unicode strings round-trip exactly as decoded values.
3. Annotated reordered net rows retain order and attachment; empty optional hosts, an empty root and annotated diagnostics survive. Explicit suppression cannot silently discard them.
4. Root and definition both named `TOP`, interface-pin columns, case-folded host collisions, duplicate defaults and duplicate diagnostics behave according to explicit scope/occurrence rules.
5. Namespace-only edits preserve other namespaces. Reconnect, rename, deletion, reorder, default changes and black-box changes exercise the chosen guard policy. Identical-row history is explicitly unrecoverable.
6. No-op normalization preserves; changed normalization and top/closure projection either follow supported rules or reject. Core-only export strips explicitly and remains readable by old readers.
7. Annotation-only changes affect document identity but not the chosen core digest or structural comparison findings. Existing plain-input identity behavior is preserved or deliberately revised, including empty envelopes.
8. Malformed reciprocity still fails. Unknown core syntax fails rather than being laundered as an extension. Opaque JSON, URLs and paths cause no evaluation, imports or I/O.

Deferred: annotation-aware expansion, cross-file merge, schema migration, historical identity, general reference validation and semantic freshness inference. A read-only structural view may omit annotations in its own result while leaving the source document untouched.

## Checks and limits

Read mandatory guidance, ontologies and representative implementation/tests; inspected root and child Git status. Ran one in-memory probe under ASS `.venv/bin/python -B` (Python 3.11.16), confirming the working-tree import, net-row normalization, empty-host omission, string-codec failures and fixed-header rejection. Inspected tests but ran no pytest, decomposition verifier, simulation, rendering, network access or evaluation workflows. No corpus/ovnote content was used. Only this report was created; no implementation or contract changes are claimed.
