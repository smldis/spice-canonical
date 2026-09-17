"""Saved canonical artifacts preserve evidence and reject inconsistent tables."""
from dataclasses import replace
from pathlib import Path

import pytest

from spice_canonical.canonical_netlist import (
    BlackBox, CanonicalNetlist, CanonicalParseError, Circuit, Connection, Device,
    Diagnostic, Parameter, from_canonical_text, from_canonical_file, from_file,
    from_text, main, normalize_device_types,
)


def test_extract_save_read_preserves_named_and_positional_boundaries(tmp_path, capsys):
    source = tmp_path / 'design.sp'
    source.write_text('.include absent.inc\n.lib absent.lib TT\n'
                      '.subckt AMP I O W={max(1u, 2u)}\n'
                      'XM O I 0 0 nmos_lvt W=1u\nXR O 0 res_cell R=1k\n.ends\n'
                      'Xamp in out AMP W=3u\n')
    data = from_file(source, external_subcircuits={'nmos_lvt': ['d', 'g', 's', 'b']})
    data = normalize_device_types(data, {'nmos_lvt': 'nmos'})
    mos, resistor = data.subcircuits[0].devices
    assert mos.black_box == BlackBox('nmos_lvt', 'named')
    assert resistor.black_box == BlackBox('res_cell', 'positional')
    assert mos.parameters[-1] == Parameter('source_type', 'nmos_lvt')
    artifact = tmp_path / 'saved.canonical'
    artifact.write_text(data.render())
    source.unlink()
    assert from_canonical_file(artifact) == data
    assert len(data.diagnostics) == 2  # missing include and unnamed resistor; .LIB is a boundary
    assert 'BLACK_BOX_TABLE AMP' in artifact.read_text()


def test_cli_emits_reusable_custom_tables(tmp_path, capsys):
    source, target = tmp_path / 'a.sp', tmp_path / 'a.canonical'
    source.write_text('X1 out in 0 0 Missing W=1u\n')
    expected = from_file(source)
    assert main([str(source), '--output', str(target)]) == 0
    assert 'warning:' in capsys.readouterr().err
    assert from_canonical_file(target) == expected


def test_escaped_delimiters_defaults_diagnostics_and_unused_pins_round_trip():
    device = Device('X.a,1', 'vendor|cell',
                    (Connection('p.=,', 'net|,\\x'), Connection('other', 'line\nbreak')),
                    (Parameter('a=b', '{max(1, 2) == 2}'), Parameter('raw', 'a|b\\c\nd'),
                     Parameter('same', '1'), Parameter('same', '2')),
                    BlackBox('vendor|cell', 'named'))
    circuit = Circuit('C|x', ('unused',), (device,), (Parameter('W', '{A / 2}'),))
    data = CanonicalNetlist(Circuit('custom_root', (), ()), (circuit,),
                           (Diagnostic(7, 'a|b\\c\nmessage', Path('/missing/a|b')),))
    assert from_canonical_text(data.render()) == data


@pytest.mark.parametrize('source', ['', '.subckt C A B\n.ends\n', 'R1 a 0 1k\n'])
def test_empty_library_and_ordinary_legacy_tables(source):
    data = from_text(source)
    assert from_canonical_text(data.render()) == data


@pytest.mark.parametrize('mutation, match', [
    (lambda s: s.replace('a | R1.p', 'a | R1.n'), 'disagrees'),
    (lambda s: s.replace('resistor |', 'resistor | extra |'), 'column count'),
    (lambda s: s.replace('DEVICE_TABLE TOP', 'DEVICE_TABLE WRONG'), 'current declared'),
    (lambda s: s.replace('NET_INCIDENT_TABLE', 'UNKNOWN_TABLE'), 'unknown table'),
    (lambda s: s + '\nDEVICE_TABLE TOP\nname | type | connections | parameters\n', 'duplicate'),
])
def test_invalid_tables_fail_instead_of_silently_losing_evidence(mutation, match):
    with pytest.raises(CanonicalParseError, match=match):
        from_canonical_text(mutation(from_text('R1 a 0 1k\n').render()))


def test_bad_black_box_basis_and_duplicate_roles_fail():
    text = from_text('X1 a b Missing\n').render()
    with pytest.raises(CanonicalParseError, match='pin_basis'):
        from_canonical_text(text.replace('| positional', '| invented'))
    with pytest.raises(CanonicalParseError, match='positional black-box pins'):
        from_canonical_text(text.replace('@2', '@1'))


def test_older_grouped_parameter_expressions_remain_readable():
    data = from_text('R1 a 0 {max(A, B)}\n')
    older = data.render().replace('\\,', ',')
    assert from_canonical_text(older) == data


def test_top_name_is_not_a_subcircuit_definition_or_external_cell(tmp_path):
    defined = from_text('.subckt TOP A W={max(1u, 2u)}\n'
                        'R1 A 0 {W}\n.ends\nX1 out TOP W={max(2u, 3u)}\n')
    assert from_canonical_text(defined.render()) == defined

    source = tmp_path / 'external.sp'
    source.write_text('X1 out TOP gain={max(1, 2)}\nR1 out 0 1k\n')
    external = from_file(source)
    assert external.top.devices[0].black_box == BlackBox('TOP', 'positional')
    assert from_canonical_text(external.render()) == external
