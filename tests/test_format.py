"""The reviewed file grammar, legacy reading and explicit export limits."""
from pathlib import Path
import re

import pytest

from spice_canonical.canonical_netlist import (
    CanonicalNetlist, CanonicalParseError, Circuit, Diagnostic, ExtensionScope,
    ExtensionTable, Parameter, from_canonical_file, from_canonical_text, from_text, main,
)

NS = 'org.example.analysis'
LEGACY = '''EXTENSION_NAMESPACES
namespace | version
org.example.analysis | 1

TOP_LEVEL TOP

NET_INCIDENT_TABLE TOP
net | incident pins
a | R1.p
0 | R1.n

DEVICE_TABLE TOP
name | type | connections | parameters | org.example.analysis:role
R1 | resistor | p=a, n=0 | value=1k | \\e

org.example.analysis:notes
text
hello
'''


def test_maintained_grammar_example_is_directly_readable_and_has_closed_productions():
    doc = (Path(__file__).parents[1] / 'docs/format.md').read_text(encoding='utf-8')
    grammar = re.search(r'```ebnf\n(.*?)```', doc, re.S).group(1)
    lexical = re.sub(r'"[^"\n]*"|\?.*?\?', '', grammar, flags=re.S)
    defined = set(re.findall(r'^([a-zA-Z_]+)\s*=', lexical, re.M))
    assert set(re.findall(r'\b[a-zA-Z_]+\b', lexical)) <= defined
    assert 'hex' not in defined and 'empty_row' not in defined
    text = doc.split('## Complete example\n', 1)[1].split('```text\n', 1)[1].split('```', 1)[0]
    data = from_canonical_text(text)
    assert data.top.devices[0].parameters == ()
    assert data.subcircuits[0].pins == ('IN', 'OUT', 'RET')
    assert data.subcircuits[0].parameter_defaults == (Parameter('R', '10k'),)
    assert data.extensions.column_host(ExtensionScope('root', 'TOP'), 'DEVICE_TABLE').rows == (('divider_instance',),)
    assert from_canonical_text(data.render()) == data


def test_legacy_aliases_headers_and_empty_cells_read_then_emit_current_names():
    data = from_canonical_text(LEGACY)
    rendered = data.render()
    assert rendered.startswith('NAMESPACES\n')
    assert 'TOP_PORTS TOP\nport\n' in rendered
    assert 'DEVICES TOP\ndevice | type | connections | parameters | ' in rendered
    assert 'value=1k | \n' in rendered
    assert '\\e' not in rendered
    assert from_canonical_text(rendered) == data


@pytest.mark.parametrize('encoded, decoded, exportable', [
    (r'\u03bc', 'μ', True), (r'\u000a', '\n', True),
    (r'\u000b', '\v', False), (r'\u2028', '\u2028', False),
    (r'\e', '', False),
])
def test_legacy_payload_is_preserved_on_read_and_never_silently_dropped(encoded, decoded, exportable):
    data = from_canonical_text(LEGACY.replace('\nhello\n', '\n' + encoded + '\n'))
    assert data.extensions.table(NS, 'notes').rows == ((decoded,),)
    if exportable:
        assert from_canonical_text(data.render()) == data
    else:
        with pytest.raises(CanonicalParseError, match=NS + ':notes.*row 1'):
            data.render()


@pytest.mark.parametrize('encoded', [r'\u0041', r'\e', r'\q', '\0', '\v', '\u2028', '\u00a0', 'a\tb'])
def test_current_payload_rejects_legacy_escapes_and_raw_forbidden_characters(encoded):
    current = from_canonical_text(LEGACY).render().replace('\nhello\n', '\n' + encoded + '\n')
    with pytest.raises(CanonicalParseError):
        from_canonical_text(current)


@pytest.mark.parametrize('value', ['\0', '\v', '\u2029', '\u00a0', '\ud800'])
def test_export_errors_identify_core_table_and_column(value):
    data = CanonicalNetlist(Circuit('TOP', (), (), (Parameter('raw', value),)), ())
    with pytest.raises(CanonicalParseError, match='PARAMETER_DEFAULTS TOP, row 1, column value'):
        data.render()


def test_blank_cells_all_empty_multicolumn_rows_and_zero_rows_are_preserved():
    data = from_text('R1 a 0 1k\n').with_namespace(NS, 1)
    data = data.with_table(ExtensionTable(NS, 'notes', ('left', 'right'), (('', ''),)))
    data = data.with_table(ExtensionTable(NS, 'zero', ('text',), ()))
    data = data.with_column(NS, 'role', table='DEVICE_TABLE', scope=ExtensionScope('root', 'TOP'), values=[''])
    assert '\n | \n' in data.render()
    assert from_canonical_text(data.render()) == data


def test_utf8_cli_file_and_named_escapes_survive(tmp_path):
    source, target = tmp_path / 'source.cir', tmp_path / 'saved.canonical'
    source.write_text('Rµ a 0 1k\n', encoding='utf-8')
    assert main([str(source), '--output', str(target)]) == 0
    assert b'R\xc2\xb5' in target.read_bytes() and b'\r\n' not in target.read_bytes()
    data = from_canonical_file(target).with_namespace(NS, 1)
    values = ('gain µV/V', 'first\nsecond\rthird\tend', ' leading ', r'a|b\u0041')
    data = data.with_table(ExtensionTable(NS, 'notes', ('text',), tuple((v,) for v in values)))
    target.write_text(data.render(), encoding='utf-8')
    assert from_canonical_file(target) == data


def test_scope_and_logical_table_duplicates_are_checked_across_aliases():
    text = from_text('R1 a 0 1k\n').render()
    duplicate = '\nDEVICE_TABLE TOP\nname | type | connections | parameters\n'
    with pytest.raises(CanonicalParseError, match='duplicate DEVICE_TABLE'):
        from_canonical_text(text + duplicate)
    with pytest.raises(CanonicalParseError, match='current declared'):
        from_canonical_text(text.replace('NETS TOP', 'NETS wrong'))
    with pytest.raises(CanonicalParseError, match='header'):
        from_canonical_text('TOP_PORTS TOP\n')


def test_zero_port_definition_explicit_unused_root_port_and_same_name_scope():
    data = CanonicalNetlist(Circuit('TOP', ('sense',), ()), (Circuit('TOP', (), ()),))
    text = data.render()
    assert 'SUBCKT_PORTS TOP\nport\n\nNETS TOP' in text
    assert 'sense | \n' in text
    assert from_canonical_text(text) == data


def test_legacy_diagnostics_only_artifact_remains_readable():
    data = from_canonical_text('DIAGNOSTICS\nsource | line | message\n | 1 | old\\u03bc\n')
    assert data.diagnostics == (Diagnostic(1, 'oldμ'),)
    assert 'oldμ' in data.render(include_diagnostics=True)


def test_missing_default_name_is_invalid_but_empty_device_parameter_value_survives():
    data = CanonicalNetlist(Circuit('TOP', (), (), (Parameter('W', '1u'),)), ())
    with pytest.raises(CanonicalParseError, match='defaults require nonempty names'):
        from_canonical_text(data.render().replace('W | 1u', ' | 1u'))
    text = from_text('R1 a 0 1k\n').render().replace('value=1k', 'value=')
    loaded = from_canonical_text(text)
    assert loaded.top.devices[0].parameters == (Parameter('value', ''),)
    assert from_canonical_text(loaded.render()) == loaded
