# SPICE Canonical agent guidance

Inherit the project guidance from `../AGENTS.md`. Before work here, read
`../MANIFESTO.md`, `../ONTOLOME.md`, local `ONTOLOME.md`, local `README.md`, and
local `unit.toml`, then inspect the relevant implementation and tests.

This unit owns deterministic extraction of circuits, devices, nets, hierarchy,
and diagnostics from supported netlist syntax while the simulator deck remains
authoritative. Keep functional classification, simulation-input editing, and
project policy outside this boundary. Update the local ontology when this being
changes; place a changed contract with another unit, including the canonical
data consumed by decomposition, in the closest containing ontology.

## Where to read, and what to trust

Two surfaces here, deliberately separate. Know which one you are in.

| Surface | Where | Maintained against the code? |
| --- | --- | --- |
| **Contracts** — what this unit guarantees now, and its exclusions | `ONTOLOME.md` | **Yes.** Update it in the same change that alters the contract. Not published. |
| **Documentation** — the format, the parser, and the corpus | `docs/` | **Yes.** Everything under `docs/` is published to the Sphinx site by `python composition.py docs` from the repository root. |

There is no third surface: this unit has **no `design/` directory**. If you
create one, the same rule applies as everywhere else in this repository — a
`design/` file is written on a date, never edited to stay true, never
published, and **never evidence of current behaviour**. Do not cite one, and do
not update one to match the code; promote what is still right into `docs/` or
`ONTOLOME.md` instead.

Nothing published may link to `ONTOLOME.md` or to any unpublished file. Sphinx
cannot resolve the target and it becomes a build warning; name such files as
inline code.

`docs/netlist-corpus.md` is the one page carrying a forward-looking proposal.
Its extraction results are findings; its tiers and priorities are unbuilt. Do
not read them as a description of what ships.

## Checks

```console
python -m pytest -q tests
python ../composition.py docs          # from the repository root: python composition.py docs
```

A successful Sphinx build can still report missing toctree entries and
unresolved cross-references, so read the warnings rather than the exit status.
