"""Artifact preservation and explicit snapshot boundaries, not producer semantics."""
from dataclasses import replace
from pathlib import Path

import pytest

from spice_canonical.canonical_netlist import (
    CanonicalNetlist, CanonicalParseError, Circuit, Connection, Device, Diagnostic,
    ExtensionColumns, ExtensionNamespace, ExtensionScope, ExtensionTable,
    Parameter, from_canonical_text, from_text, normalize_device_types,
)
from spice_canonical.inspect import definition_library, top_level_netlist, expand

ROOT = ExtensionScope("root", "TOP")
NS = "private.analysis"
PREAMBLE = "NAMESPACES\nnamespace | version\nprivate.analysis | 1\n\n"


def annotated():
    return from_text("R1 out 0 1k\n").with_namespace(NS, 1).with_column(
        NS, "role", table="DEVICE_TABLE", scope=ROOT, values={"R1": "load"})


def test_independent_unknown_schemas_and_namespace_local_edits(tmp_path):
    data = annotated().with_namespace("org.example.other", 999)
    other = ExtensionTable("org.example.other", "findings", ("id", "role"),
                           (("x", "external"),))
    data = data.with_table(other).with_table(ExtensionTable(NS, "findings", ("id",), (("load",),)))
    data = data.with_column("org.example.other", "role", table="DEVICE_TABLE",
                           scope=ROOT, values={"r1": "opaque"})
    path = tmp_path / "saved.canonical"
    path.write_text(data.render())
    restored = from_canonical_text(path.read_text())
    assert restored == data
    changed = restored.with_table(ExtensionTable(NS, "findings", ("id",), (("new",),)))
    assert changed.extensions.table("org.example.other", "findings") == other
    changed = changed.without_column(NS, "role", table="DEVICE_TABLE", scope=ROOT).without_table(NS, "findings")
    assert changed.extensions.column_host(ROOT, "DEVICE_TABLE").columns == ("org.example.other:role",)
    assert changed.extensions.table("org.example.other", "findings") == other
    removed = changed.without_namespace(NS)
    assert removed.extensions.namespaces == (ExtensionNamespace("org.example.other", 999),)
    assert from_canonical_text(removed.render()) == removed


@pytest.mark.parametrize("value", [" ", "  x  ", "a|b\\c\n\r\t", "🧪", "gain µV/V", "null",
                                  '{"url":"https://invalid.example/no-fetch","code":"__import__"}'])
def test_opaque_cells_round_trip_in_single_column_tables_and_host_columns(value):
    data = annotated().with_table(ExtensionTable(NS, "notes", ("text",), ((value,), (value,))))
    data = data.with_column(NS, "role", table="DEVICE_TABLE", scope=ROOT, values=[value])
    assert from_canonical_text(data.render()) == data


def test_zero_rows_and_empty_annotated_headers_survive():
    data = annotated().with_table(ExtensionTable(NS, "zero", ("text",), ()))
    data = data.with_column(NS, "note", table="PARAMETER_DEFAULTS", scope=ROOT, values=[])
    data = data.with_column(NS, "note", table="BLACK_BOX_TABLE", scope=ROOT, values=[])
    restored = from_canonical_text(data.render())
    assert restored == data
    assert restored.extensions.table(NS, "zero").rows == ()
    assert "PARAMETER_DEFAULTS TOP\nparameter | value | private.analysis:note" in data.render()


def test_annotated_net_row_order_survives_and_bindings_do_not_swap():
    text = PREAMBLE + from_text("R1 out 0 1k\n").render().replace(
        "net | incident_pins\nout | R1.p\n0 | R1.n",
        "net | incident_pins | private.analysis:role\n0 | R1.n | ground\nout | R1.p | signal")
    data = from_canonical_text(text)
    host = data.extensions.column_host(ROOT, "NET_INCIDENT_TABLE")
    assert host.row_order == ("0", "out")
    assert host.rows == (("ground",), ("signal",))
    data = data.with_column(NS, "label", table="NET_INCIDENT_TABLE", scope=ROOT,
                            values={"out": "output"})
    assert "0 | R1.n | ground | \nout | R1.p | signal | output" in data.render()
    assert from_canonical_text(data.render()) == data


def test_root_definition_and_document_scopes_and_inline_pin_columns():
    data = from_text(".subckt TOP A params: W=1 W=1\nR2 A 0 {W}\n.ends\n")
    data = data.with_namespace(NS, 1)
    definition = ExtensionScope("definition", "TOP")
    for scope, value in ((ROOT, "root"), (definition, "definition"), (ExtensionScope(), "document")):
        data = data.with_table(ExtensionTable(NS, "notes", ("value",), ((value,),), scope))
    data = data.with_column(NS, "direction", table="PINS", scope=definition, values={"a": "input"})
    data = data.with_column(NS, "note", table="PINS", scope=ROOT, values=[])
    data = data.with_column(NS, "origin", table="PARAMETER_DEFAULTS",
                            scope=definition, values={0: "first", 1: "second"})
    restored = from_canonical_text(data.render())
    assert restored == data
    assert restored.top.devices == ()
    assert restored.subcircuits[0].parameter_defaults == (Parameter("W", "1"), Parameter("W", "1"))
    assert "TOP_PORTS TOP\nport | private.analysis:note" in data.render()


def test_document_table_does_not_reset_current_circuit():
    data = annotated()
    text = data.render().replace("NETS TOP",
        "private.analysis:notes\ntext\nhello\n\nNETS TOP")
    loaded = from_canonical_text(text)
    assert loaded.extensions.table(NS, "notes").rows == (("hello",),)
    assert from_canonical_text(loaded.render()) == loaded


def test_diagnostics_occurrences_and_suppression_are_explicit():
    diagnostic = Diagnostic(2, "missing", Path("/never/open-this"))
    base = replace(from_text("R1 out 0 1k\n"), diagnostics=(diagnostic, diagnostic))
    assert "DIAGNOSTICS" not in base.render()
    data = base.with_namespace(NS, 1).with_column(NS, "note", table="DIAGNOSTICS",
                                               values={0: "first", 1: "second"})
    assert from_canonical_text(data.render()) == data
    with pytest.raises(ValueError, match="suppress diagnostics"):
        data.render(include_diagnostics=False)
    assert from_canonical_text(data.render(include_extensions=False)).diagnostics == ()
    assert from_canonical_text(data.render(include_extensions=False, include_diagnostics=True)) == base


def test_empty_annotated_diagnostics_table_survives():
    data = annotated().with_column(NS, "note", table="DIAGNOSTICS", values=[])
    assert "DIAGNOSTICS\nsource | line | message | private.analysis:note" in data.render()
    assert from_canonical_text(data.render()) == data
    with pytest.raises(ValueError, match="suppress diagnostics"):
        data.render(include_diagnostics=False)


@pytest.mark.parametrize("change", [
    lambda c: replace(c, name="renamed"),
    lambda c: replace(c, devices=()),
    lambda c: replace(c, parameter_defaults=(Parameter("W", "1"),)),
    lambda c: replace(c, devices=(replace(c.devices[0], name="Rnew"),)),
    lambda c: replace(c, devices=(replace(c.devices[0], connections=(Connection("p", "bias"), Connection("n", "0"))),)),
    lambda c: replace(c, devices=(replace(c.devices[0], parameters=(Parameter("value", "2k"),)),)),
])
def test_core_changes_reject_until_explicit_removal(change):
    data = annotated()
    changed = replace(data, top=change(data.top))
    with pytest.raises(ValueError, match="core snapshot changed"):
        changed.render()
    with pytest.raises(ValueError, match="core snapshot changed"):
        changed.with_namespace("private.other", 1)
    assert not changed.without_extensions().extensions
    assert "EXTENSION_NAMESPACES" not in changed.render(include_extensions=False)


def test_reordering_and_blackbox_changes_are_guarded():
    data = from_text("R1 out 0 1k\nR2 out 0 2k\n").with_namespace(NS, 1)
    changed = replace(data, top=replace(data.top, devices=tuple(reversed(data.top.devices))))
    with pytest.raises(ValueError, match="core snapshot changed"):
        changed.render()
    from spice_canonical.canonical_netlist import BlackBox
    changed = replace(data, top=replace(data.top, devices=(replace(data.top.devices[0], black_box=BlackBox("opaque", "named")), data.top.devices[1])))
    with pytest.raises(ValueError, match="core snapshot changed"):
        changed.render()


def test_noop_normalization_preserves_and_changed_normalization_projection_reject():
    data = annotated()
    assert normalize_device_types(data, {}) is data
    assert normalize_device_types(data, {"not-present": "nmos"}) == data
    with pytest.raises(ValueError, match="core snapshot changed"):
        normalize_device_types(data, {"resistor": "other"})
    for operation in (top_level_netlist, lambda n: definition_library(n, "absent")):
        with pytest.raises(ValueError, match="projection with extensions"):
            operation(data)
    assert top_level_netlist(data.without_extensions()) == data.without_extensions()
    assert expand(data) == expand(data.without_extensions())


@pytest.mark.parametrize("mutation,match", [
    (lambda s: s.replace("private.analysis | 1", "private.analysis | 1\nprivate.analysis | 1"), "duplicate namespace"),
    (lambda s: s.replace("private.analysis | 1", "private.analysis | 0"), "positive integer"),
    (lambda s: s.replace("private.analysis | 1", "analysis | 1"), "dotted"),
    (lambda s: s.replace("private.analysis:role", "private.unknown:role"), "undeclared"),
    (lambda s: s.replace("private.analysis:role", "role"), "qualified"),
    (lambda s: s.replace("| private.analysis:role", "| private.analysis:role | private.analysis:role"), "unique"),
    (lambda s: s.replace("out | R1.p", "out | R1.n"), "disagrees"),
    (lambda s: s.replace("DEVICES TOP", "UNKNOWN_TABLE TOP"), "unknown table"),
    (lambda s: s + "\nprivate.analysis:notes WRONG\ntext\nx\n", "current declared"),
    (lambda s: s + "\nprivate.analysis:notes\ntext\nx\n\nprivate.analysis:notes\ntext\ny\n", "duplicate extension"),
    (lambda s: s + "\nprivate.analysis:notes\ntext\nx | y\n", "column count"),
    (lambda s: s + "\nNAMESPACES\nnamespace | version\nprivate.other | 1\n", "first table"),
])
def test_malformed_envelopes_and_connectivity_still_fail(mutation, match):
    with pytest.raises(CanonicalParseError, match=match):
        from_canonical_text(mutation(annotated().render()))


def test_authored_invalid_hosts_core_and_payloads_are_rejected():
    with pytest.raises(ValueError, match="undeclared"):
        from_text("R1 out 0 1k\n").with_table(ExtensionTable(NS, "notes", ("text",), ()))
    with pytest.raises(ValueError, match="absent scope"):
        annotated().with_table(ExtensionTable(NS, "notes", ("text",), (),
                                             ExtensionScope("definition", "missing")))
    with pytest.raises(ValueError, match="unknown or duplicate"):
        annotated().with_column(NS, "note", table="DEVICE_TABLE", scope=ROOT, values={"missing": "x"})
    with pytest.raises(ValueError, match="invalid extension row key"):
        annotated().with_column(NS, "note", table="PARAMETER_DEFAULTS", scope=ROOT, values={True: "x"})
    with pytest.raises(ValueError, match="scalar"):
        ExtensionTable(NS, "notes", ("text",), (("\ud800",),))
    bad = CanonicalNetlist(Circuit("TOP", (), (Device("R", "resistor", ()), Device("r", "resistor", ()))), ())
    with pytest.raises(ValueError, match="duplicate device"):
        bad.with_namespace(NS, 1)
    host = annotated().extensions.column_host(ROOT, "DEVICE_TABLE")
    broken = replace(annotated(), extensions=replace(annotated().extensions,
        columns=(replace(host, row_order=("absent",)),)))
    with pytest.raises(ValueError, match="host rows"):
        broken.render()


def test_namespace_conflicts_unused_declarations_and_plain_core_export():
    base = from_text("R1 out 0 1k\n")
    data = base.with_namespace(NS, 17)
    assert data.with_namespace(NS, 17) is data
    with pytest.raises(ValueError, match="version conflict"):
        data.with_namespace(NS, 18)
    assert from_canonical_text(data.render()) == data
    assert data.render(include_extensions=False) == base.render()
    assert data.without_namespace(NS) == base


def test_authored_layout_cannot_reorder_ordered_core_rows():
    data = from_text("R1 out 0 1k\nR2 out 0 2k\n").with_namespace(NS, 1)
    data = data.with_column(NS, "role", table="DEVICE_TABLE", scope=ROOT, values=["first", "second"])
    host = data.extensions.column_host(ROOT, "DEVICE_TABLE")
    changed = replace(data, extensions=replace(data.extensions, columns=(
        replace(host, row_order=tuple(reversed(host.row_order))),)))
    with pytest.raises(ValueError, match="retain represented order"):
        changed.render()


def test_nonempty_blackbox_column_layout_preserves_its_independent_row_order():
    data = from_text("X1 a b Opaque\nX2 b 0 Opaque\n").with_namespace(NS, 1)
    data = data.with_column(NS, "note", table="BLACK_BOX_TABLE", scope=ROOT, values=["one", "two"])
    host = data.extensions.column_host(ROOT, "BLACK_BOX_TABLE")
    data = replace(data, extensions=replace(data.extensions, columns=(
        replace(host, row_order=("x2", "x1"), rows=(("two",), ("one",))),)))
    assert from_canonical_text(data.render()) == data
