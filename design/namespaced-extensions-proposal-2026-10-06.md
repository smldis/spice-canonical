# Namespaced canonical extensions

**Status:** proposal, 2026-10-06; no implementation or adopted API yet.
**Request:** let any project declare custom tables and additional columns in
its own namespace and include them in a canonical file.

## Contract

Reuse the existing table syntax, escaping and structural validation. Canonical
owns transport and preservation; each producer owns the meaning and validation
of its extensions. Loading a file requires no producer package, schema download
or plugin execution. Existing circuit/device objects remain structural.

The essential guarantee is **read → write preserves all extension data,
including unfamiliar namespaces and schema versions**, with deterministic output.
This concerns values, row order and attachment, not byte-identical formatting.

## File format

A document-level declaration precedes the first use of each namespace:

```text
EXTENSION_NAMESPACES
namespace | version
netlist-decomposition | 1

TOP_LEVEL TOP

NET_INCIDENT_TABLE TOP
net | incident pins | netlist-decomposition:class
out | R1.p | signal
0 | R1.n | ground

DEVICE_TABLE TOP
name | type | connections | parameters | netlist-decomposition:findings
R1 | resistor | p=out, n=0 | value=1k | load:1

netlist-decomposition:findings TOP
id | kind | rule | status
load:1 | output_load | demonstration | candidate
```

This is a synthetic example, not an existing recognition result.

- Namespace names are lowercase project identifiers, optionally dotted; local
  names use letters, digits, underscores and hyphens. `:` separates them.
  The namespace is the project's schema identity; its positive integer version
  is project-owned. No central registry is required. One file has one version
  per namespace; conflicting declarations fail.
- Additional columns follow the unchanged required columns of any core table
  and have qualified names. Core fields cannot be overridden. A custom table's
  qualified marker establishes ownership; its header declares local columns.
- A custom table with a circuit argument belongs to the current declared circuit,
  just as core tables do. Root and definition scopes stay distinct even if their
  names match. Without a circuit argument, a custom table is document-scoped.
- Cells are opaque strings with existing escaping. Empty cells are empty strings;
  there is no implicit null, expression evaluation or reference resolution.
  Projects can use additional tables for memberships and evidence rather than
  packing nested objects into every device row.
- Reject undeclared prefixes, duplicate headers/table identities, malformed
  rows and unknown unqualified table names. Preserve unfamiliar declared
  extensions instead of silently discarding them.

## Python representation and attachment

Add one default-empty `extensions` field to `CanonicalNetlist`, carrying immutable
namespace declarations, custom tables and column attachments. Do not duplicate
connectivity into a parallel generic document model. Proposed operations declare
a namespace, add/replace its table or column, inspect it, and explicitly remove it.
Editing one namespace preserves all others; these operations are not file merges.

Attach named rows by their existing identity in a specific scope/table, not their
display position. For tables without unique row identities, retain an ordered
row reference guarded by a fingerprint of the core table. Reject orphaned or
changed guarded targets at serialization. A declaration default's duplicate
name must not cause annotations to attach to the wrong occurrence.

Canonical validates envelope shape and attachment, not project-specific claims
or cross-table references. Producers can provide explicit validators and record
a circuit digest/context in their tables. Preserved annotations can still be
semantically stale after a circuit edit; preservation does not certify them.

## Compatibility and implementation

Default-empty extensions preserve current constructors and plain-file rendering.
New readers accept old files; old readers will reject extended files. Provide an
explicit core-only export for those consumers. Normal export never silently
drops extensions; options removing an annotated target must require explicit
removal. Audit normalization and projection helpers: preserve attachments where
valid, otherwise reject or require an explicit discard. No automatic inference
of how annotations follow expansion, renaming or connectivity changes.

Implement in `canonical_netlist.py` (data and rendering), `canonical_text.py`
(qualified headers and tables), and focused artifact tests. Update
`docs/representation.md`, the unit ontology and the containing ontology's
cross-unit contract when adopted. Decomposition's annotation schema is a
separate consumer change; canonical must not import it.

## Acceptance checks

1. Two independent namespaces reuse local names without collision; both survive
   load/save without either project's package installed.
2. Extension columns and custom tables round-trip escaped punctuation, empty
   cells and ordered duplicate rows; plain artifacts retain existing behavior.
3. Existing reciprocal incidence checks still reject corrupt connectivity;
   extension declarations, headers and attachments fail clearly when malformed.
4. Exercise root/definition name collisions, duplicate defaults, target removal,
   unsupported projection and explicit core-only export.

First slice: generic transport, inspection and authoring API. Defer schema
registries, automatic migration, typed-cell machinery and general merge logic
until a consumer demonstrates the need.
