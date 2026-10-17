# SPICE Canonical

This unit extracts an LLM-oriented canonical connectivity representation from
Eldo or ngspice netlists. It is independently installable:

```bash
python -m pip install -e .
python -m pytest -q tests
spice-canonical input.cir --format ngspice --output canonical.txt
```

The Python API is `spice_canonical.canonical_netlist`. Includes are expanded
recursively; model libraries can remain opaque; strict mode turns unresolved or
unsupported structures into failures. Subcircuit declaration defaults are retained
as ordered, unevaluated `Circuit.parameter_defaults` and optional
`PARAMETER_DEFAULTS` tables, separately from instance overrides. Operative `.PARAM`
assignments are retained in `Circuit.parameter_assignments`: all file-scope
assignments share one `PARAMETER_ASSIGNMENTS` table on the root, even when the
root has no devices. Subcircuit-body assignments belong to that definition.
Expressions remain raw; parameter evaluation and model-body semantics are not
implemented.

With ngspice installed, the optional network-backed corpus check is:

```bash
python scripts/verify_ngspice_corpus.py
```

It downloads only checksum-pinned upstream examples. Normal tests remain
offline.

Saved canonical tables can be read back with `from_canonical_file("canonical.txt")`
from `spice_canonical.canonical_netlist`. Files use UTF-8 with LF line endings;
the [formal grammar](docs/format.md) defines the current table names, headers
and escaping. Historical files remain readable, and writers emit the current form. External cells retain explicit black-box
interfaces: `--external-subcircuits pins.json` supplies ordered formal names;
otherwise terminals are positional `@1`, `@2`, etc. `BLACK_BOXES` rows
preserve boundaries through saved files. Diagnostic rows are omitted by
default; use `render(include_diagnostics=True)` or CLI
`--include-diagnostics` to retain them in the artifact. CLI warnings remain on
stderr.

Projects can declare versioned namespaces and attach custom tables or additional
columns to canonical artifacts through immutable `with_namespace`, `with_table`
and `with_column` operations. Unknown project schemas survive load/save without
producer dependencies. Envelopes bind to the exact core snapshot; transformations
require explicit removal or reauthoring. Extended exports preserve diagnostics;
`render(include_extensions=False)` explicitly exports core-only text for older
readers. See [the extension contract](docs/representation.md#namespaced-tables-and-columns).

## Documentation

[`docs/`](docs/index.md) is the guide, built into the project's Sphinx site by
`python composition.py docs` from the repository root. Start with
[the canonical representation](docs/representation.md) if you consume the
output, [extracting a canonical netlist](docs/extraction.md) if you run the
parser, [the agent skill](docs/agent-skill.md) if you use Codex to operate it,
and the
[integrated-circuit netlist corpus](docs/netlist-corpus.md) for the open
netlists worth testing it against.

The [package use-case recipes](examples/use_cases.py) show Python calls for
common netlist questions and canonical-file exports. The implemented recipes
currently cover read-only work; deferred editing cases are listed there too.

One neighbouring surface is deliberately not part of that site.
[`ONTOLOME.md`](ONTOLOME.md) states the contracts this unit currently
guarantees and what it excludes on purpose, and is where a change to a contract
must be recorded. The unpublished `design/` directory holds dated proposals,
not descriptions of current behavior.
