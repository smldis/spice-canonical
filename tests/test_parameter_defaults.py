from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from spice_canonical.canonical_netlist import (  # noqa: E402
    CanonicalParseError, Circuit, Parameter, from_file, from_text, main,
    normalize_device_types,
)


@pytest.mark.parametrize("spice_format", ["eldo", "ngspice"])
@pytest.mark.parametrize("marker", ["", "PARAMS: ", "param: "])
@pytest.mark.parametrize("equals", ["=", " = ", "= ", " ="])
def test_defaults_preserve_names_expressions_order_and_scope(spice_format, marker, equals):
    deck = (
        f"* title\n.SUBCKT INV A Y {marker}WP{equals}2u\n"
        f"+ wN{equals}{{WP / 2}} Q{equals}'WP + 1u' D{equals}\"wN * 2\"\n"
        "R1 A Y {wN}\n.ENDS INV\n"
        "X1 in out INV WP=3u\nX2 in other INV\n"
    )
    netlist = from_text(deck, spice_format=spice_format)
    circuit = netlist.subcircuits[0]
    assert netlist.diagnostics == ()
    assert circuit.pins == ("A", "Y")
    assert circuit.parameter_defaults == (
        Parameter("WP", "2u"), Parameter("wN", "{WP / 2}"),
        Parameter("Q", "'WP + 1u'"), Parameter("D", '"wN * 2"'),
    )
    assert netlist.top.parameter_defaults == ()
    assert netlist.top.devices[0].parameters == (Parameter("WP", "3u"),)
    assert netlist.top.devices[1].parameters == ()
    assert "PARAMETER_DEFAULTS INV\nname | value\nWP | 2u\nwN | {WP / 2}" in netlist.render()
    assert from_text(deck.replace(f"WP{equals}2u", f"WP{equals}4u"), spice_format=spice_format).render() != netlist.render()


def test_normalization_and_includes_preserve_defaults(tmp_path):
    (tmp_path / "cell.inc").write_text(
        ".SUBCKT CELL A B W=2u\nR1 A B 1k\n.ENDS\n"
    )
    top = tmp_path / "top.sp"
    top.write_text(".include cell.inc\nX1 a b CELL W=3u\n")
    original = from_file(top)
    normalized = normalize_device_types(original, {"resistor": "r", "cell": "c"})
    assert normalized.subcircuits[0].parameter_defaults == (Parameter("W", "2u"),)
    assert normalized.subcircuits[0].devices[0].type == "r"
    assert normalized.top.devices[0].type == "c"
    assert from_file(top, device_type_map={"resistor": "r", "cell": "c"}) == normalized
    assert normalize_device_types(original, {}) is original


def test_default_free_render_and_old_constructor():
    assert Circuit("EMPTY", (), ()).parameter_defaults == ()
    assert from_text(".SUBCKT EMPTY A\n.ENDS\n").render() == (
        "SUBCKT EMPTY\npin\nA\n\nNET_INCIDENT_TABLE EMPTY\n"
        "net | incident pins\nA | \n\nDEVICE_TABLE EMPTY\n"
        "name | type | connections | parameters\n"
    )


def test_defaults_reuse_cell_escaping_and_do_not_interpret_expressions():
    netlist = from_text(
        '.PARAM GLOBAL=5\n.MODEL N NMOS LEVEL=1\n'
        '.SUBCKT C A PARAMS: Expr={GLOBAL == 5 | 2} Path="a\\b"\n'
        '+ Expr=(f([1, 2]) + 3)\n.ENDS\n'
    )
    assert netlist.subcircuits[0].parameter_defaults == (
        Parameter("Expr", "{GLOBAL == 5 | 2}"), Parameter("Path", '"a\\b"'),
        Parameter("Expr", "(f([1, 2]) + 3)"),
    )
    assert 'Expr | {GLOBAL == 5 \\| 2}\nPath | "a\\\\b"' in netlist.render()
    assert "LEVEL" not in netlist.render()
    assert netlist.top.parameter_defaults == ()


@pytest.mark.parametrize("tail", [
    "PARAMS:", "PARAMS: W", "W=", "W =", "PARAMS: =2u", "W= X=2u",
    "W = X = 2u", "W=2u stray", "W={x + 2", "W='x + 2",
    'W="x + 2', "W={x])}", "W=2u}", "PARAMS: W=2u PARAMS: X=3u",
])
@pytest.mark.parametrize("spice_format", ["eldo", "ngspice"])
def test_malformed_defaults_raise_instead_of_disappearing(tail, spice_format):
    with pytest.raises(CanonicalParseError, match=r"line 2: malformed .SUBCKT defaults"):
        from_text(f"* title\n.SUBCKT C A {tail}\n.ENDS\n", spice_format=spice_format)


def test_cli_reports_malformed_defaults(tmp_path, capsys):
    deck = tmp_path / "bad.sp"
    deck.write_text(".SUBCKT C A W=\n.ENDS\n")
    with pytest.raises(SystemExit) as error:
        main([str(deck)])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "error: line 1: malformed .SUBCKT defaults" in captured.err
    assert captured.out == ""
