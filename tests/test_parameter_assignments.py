"""Source-owned parameter context survives canonical handoffs without evaluation."""
from dataclasses import asdict, replace
import hashlib
import json

import pytest

from spice_canonical.canonical_netlist import (
    CanonicalParseError, Circuit, ExtensionScope, Parameter,
    from_canonical_file, from_canonical_text, from_file, from_text,
    normalize_device_types,
)
from spice_canonical.extensions import core_digest
from spice_canonical.inspect import definition_library, top_level_netlist


@pytest.mark.parametrize('spice_format', ['eldo', 'ngspice'])
@pytest.mark.parametrize('equals', ['=', ' = ', '= ', ' ='])
def test_assignments_keep_scope_order_duplicates_and_device_ties(spice_format, equals):
    deck = (
        f'* title\n.PARAM W{equals}2u gain={{W * 2}}\n'
        '+ off=\'gain / 2\'\n'
        '.SUBCKT TOP A PARAMS: W=1u\n'
        '.PARAM W=3u L={W / 4}\nR1 A 0 {L}\n.ENDS\n'
        '.PARAM W=4u\nX1 in TOP W={gain}\n'
    )
    data = from_text(deck, spice_format=spice_format)
    assert data.top.parameter_assignments == (
        Parameter('W', '2u'), Parameter('gain', '{W * 2}'),
        Parameter('off', "'gain / 2'"), Parameter('W', '4u'),
    )
    local = data.subcircuits[0]
    assert local.parameter_defaults == (Parameter('W', '1u'),)
    assert local.parameter_assignments == (Parameter('W', '3u'), Parameter('L', '{W / 4}'))
    assert local.devices[0].parameters == (Parameter('value', '{L}'),)
    assert data.top.devices[0].parameters == (Parameter('W', '{gain}'),)
    assert from_canonical_text(data.render()) == data


def test_include_scope_normalization_projections_and_file_roundtrip(tmp_path):
    (tmp_path / 'global.inc').write_text('.param W=2u\n')
    (tmp_path / 'local.inc').write_text('.param L={W / 4}\n')
    source = tmp_path / 'dut.sp'
    source.write_text('* title\n.include global.inc\n.subckt C A\n'
                      '.include local.inc\nR1 A 0 {L}\n.ends\n')
    data = from_file(source, spice_format='ngspice')
    assert data.top.devices == ()
    assert data.top.parameter_assignments == (Parameter('W', '2u'),)
    assert data.subcircuits[0].parameter_assignments == (Parameter('L', '{W / 4}'),)
    assert 'TOP_PORTS TOP' in data.render()  # A parameter-only root must be saved.
    normalized = normalize_device_types(data, {'resistor': 'r'})
    assert normalized.subcircuits[0].parameter_assignments == data.subcircuits[0].parameter_assignments
    assert normalized.top.parameter_assignments == data.top.parameter_assignments
    library = definition_library(data, 'C')
    assert library.top.parameter_assignments == data.top.parameter_assignments
    assert library.subcircuits == data.subcircuits
    projected = top_level_netlist(data)
    assert projected.top.parameter_assignments == data.top.parameter_assignments
    saved = tmp_path / 'saved.canonical'
    saved.write_text(library.render())
    source.unlink()
    (tmp_path / 'global.inc').unlink()
    (tmp_path / 'local.inc').unlink()
    assert from_canonical_file(saved) == library


def test_control_commands_are_not_deck_assignments():
    data = from_text('* title\n.param W=2u\n.control\n.param W=9u\n'
                     'alterparam W=10u\n.endc\n', spice_format='ngspice')
    assert data.top.parameter_assignments == (Parameter('W', '2u'),)


@pytest.mark.parametrize('tail', ['', 'W', 'W=', '=2u', 'W= X=2u',
                                  'W=2u stray', 'W={x + 2', "W='x + 2", 'W={x])}'])
@pytest.mark.parametrize('spice_format', ['eldo', 'ngspice'])
def test_malformed_assignments_fail_explicitly(tail, spice_format):
    with pytest.raises(CanonicalParseError, match=r'line 2: malformed .PARAM assignments'):
        from_text(f'* title\n.param {tail}\n', spice_format=spice_format)


def test_assignment_annotations_use_occurrences_and_core_projection_keeps_values():
    data = from_text('.param X={1 | 2} X="a\\b"\n.subckt C A\n.param X=3\n.ends\n')
    root = ExtensionScope('root', 'TOP')
    local = ExtensionScope('definition', 'C')
    data = data.with_namespace('private.sizing', 1)
    data = data.with_column('private.sizing', 'note', table='PARAMETER_ASSIGNMENTS',
                            scope=root, values={0: 'first', 1: 'second'})
    data = data.with_column('private.sizing', 'note', table='PARAMETER_ASSIGNMENTS',
                            scope=local, values=['local'])
    assert from_canonical_text(data.render()) == data
    host = data.extensions.column_host(root, 'PARAMETER_ASSIGNMENTS')
    assert host.row_order == (0, 1)
    assert host.rows == (('first',), ('second',))
    assert from_canonical_text(data.render(include_extensions=False)) == data.without_extensions()
    changed = replace(data, top=replace(data.top, parameter_assignments=(Parameter('X', '4'),)))
    with pytest.raises(ValueError, match='snapshot'):
        changed.render()


def test_empty_annotated_assignment_host_roundtrips():
    data = from_text('R1 a 0 1k\n').with_namespace('private.sizing', 1).with_column(
        'private.sizing', 'note', table='PARAMETER_ASSIGNMENTS',
        scope=ExtensionScope('root', 'TOP'), values=[])
    assert from_canonical_text(data.render()) == data


def test_parameter_free_snapshot_guards_and_constructor_remain_compatible():
    data = from_text('R1 a 0 1k\n')
    old_top = asdict(data.top)
    del old_top['parameter_assignments']
    old_snapshot = {'top': old_top, 'subcircuits': [], 'diagnostics': []}
    assert core_digest(data) == hashlib.sha256(json.dumps(old_snapshot, sort_keys=True).encode()).hexdigest()
    assert Circuit('C', (), (), (Parameter('W', '1u'),)).parameter_assignments == ()
    assert core_digest(replace(data, top=replace(data.top, parameter_assignments=(Parameter('W', '1u'),)))) != core_digest(data)


@pytest.mark.parametrize('row', [' | 2u', 'W | '])
def test_saved_assignment_table_rejects_missing_name_or_value(row):
    text = from_text('.param W=2u\n').render().replace('W | 2u', row)
    with pytest.raises(CanonicalParseError, match='nonempty names and values'):
        from_canonical_text(text)


def test_separate_declarations_render_one_root_parameter_table():
    data = from_text('.param W=2u\nR1 a 0 {W}\n.param L=1u\n.param M=2\n')
    assert data.render().count('PARAMETER_ASSIGNMENTS TOP\n') == 1
    assert 'parameter | value\nW | 2u\nL | 1u\nM | 2' in data.render()
