# Using the SPICE Canonical skill

The checkout keeps the skill in the visible `skills/spice-canonical/SKILL.md`
for extracting, inspecting, saving, and reloading canonical connectivity from Eldo or ngspice
netlists. It gives an agent the Python and CLI syntax, artifact handoff, and
diagnostic boundaries. It also covers Python-only incidence, hierarchy/graph
inspection, and optional source evidence. Parser development is outside its scope.

The `.agents/skills/spice-canonical/SKILL.md` discovery path is a symlink to
that visible file.

Start Codex in the SPICE Canonical checkout or one of its directories, then
select the skill in the request:

```text
$spice-canonical Extract this ngspice deck, keep vendor.inc opaque, use the
ordered pins in interfaces.json, and inspect diagnostics before saving the
canonical tables.
```

Include the input deck path and dialect. Supply external pin signatures or a
type map only when you have those facts. For work from another checkout, copy
`skills/spice-canonical` to your configured personal skills directory or that
project's `.agents/skills`; keep this checkout and its Python package available.

The skill covers the maintained public syntax. See [extraction](extraction.md)
for dialect and include details, [Python inspection](inspection.md) for query
recipes and source evidence, and [representation](representation.md) for the
saved table contract.
