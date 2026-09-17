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
`PARAMETER_DEFAULTS` tables, separately from instance overrides. Global `.PARAM`
and model-body semantics are not implemented.

With ngspice installed, the optional network-backed corpus check is:

```bash
python scripts/verify_ngspice_corpus.py
```

It downloads only checksum-pinned upstream examples. Normal tests remain
offline.

Saved canonical tables can be read back with `from_canonical_file("canonical.txt")`
from `spice_canonical.canonical_netlist`. External cells retain explicit black-box
interfaces: `--external-subcircuits pins.json` supplies ordered formal names;
otherwise terminals are positional `@1`, `@2`, etc. Optional `BLACK_BOX_TABLE`
and `DIAGNOSTICS` tables preserve boundaries and warnings through saved files.

## Documentation

[`docs/`](docs/index.md) is the guide, built into the project's Sphinx site by
`python composition.py docs` from the repository root. Start with
[the canonical representation](docs/representation.md) if you consume the
output, [extracting a canonical netlist](docs/extraction.md) if you run the
parser, and the
[integrated-circuit netlist corpus](docs/netlist-corpus.md) for the open
netlists worth testing it against.

One neighbouring surface is deliberately not part of that site.
[`ONTOLOME.md`](ONTOLOME.md) states the contracts this unit currently
guarantees and what it excludes on purpose, and is where a change to a contract
must be recorded. There is no `design/` directory here: nothing in this unit's
documentation is spent working material.
