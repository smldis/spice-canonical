"""Incomplete library extraction keeps known syntax, not inferred model meaning."""
import pytest
from spice_canonical import canonical_netlist as cn


def test_missing_device_models_keep_primitive_roles_identifiers_and_parameters(tmp_path):
    path = tmp_path / 'models.sp'
    path.write_text('M1 d g s b UnavailableMOS W={W0*2}\n'
                    'D1 a k UnavailableDiode area=3\n'
                    'Q1 c base e UnavailableBJT\nR1 d 0 1k\n')
    data = cn.from_file(path)
    assert [(d.type, tuple(c.pin for c in d.connections)) for d in data.top.devices] == [
        ('mosfet', ('d', 'g', 's', 'b')), ('diode', ('a', 'k')),
        ('bjt', ('c', 'b', 'e')), ('resistor', ('p', 'n'))]
    for device, model in zip(data.top.devices, ('UnavailableMOS', 'UnavailableDiode', 'UnavailableBJT')):
        assert device.parameters[0] == cn.Parameter('model', model)
    assert data.top.devices[0].parameters[1] == cn.Parameter('W', '{W0*2}')
    assert data.diagnostics == ()  # absence of model bodies is not diagnosed
    assert cn.main([str(path), '--strict']) == 0


@pytest.mark.parametrize('tail', ['substrate MaybeModel area=2', 'MaybeModel 2 area={A*2}'])
def test_ambiguous_unknown_bjt_is_unresolved_and_preserves_raw_input(tmp_path, tail):
    path = tmp_path / 'ambiguous.sp'
    raw = 'c base e ' + tail
    path.write_text('Q1 ' + raw + '\nR1 c 0 1k\n')
    data = cn.from_file(path)
    device = data.top.devices[0]
    assert device.type == 'unresolved'
    assert device.connections == ()
    assert device.parameters == (cn.Parameter('raw', raw),)
    assert data.top.devices[1].type == 'resistor'
    assert 'ambiguous BJT terminal/model boundary' in data.diagnostics[0].message
    assert data.diagnostics[0].line == 1
    assert data.diagnostics[0].source == path
    assert cn.main([str(path), '--strict']) == 2


def test_declared_bjt_model_still_disambiguates_four_terminals():
    data = cn.from_text('.model Known NPN\nQ1 c base e substrate Known area=2')
    device = data.top.devices[0]
    assert tuple(c.pin for c in device.connections) == ('c', 'b', 'e', 's')
    assert device.parameters == (cn.Parameter('model', 'Known'), cn.Parameter('area', '2'))
    assert not data.diagnostics


def test_root_io_missing_include_and_intentional_boundaries_are_distinct(tmp_path, capsys):
    with pytest.raises(FileNotFoundError):
        cn.from_file(tmp_path / 'missing-root.sp')
    path = tmp_path / 'input.sp'
    path.write_text('.include unavailable.inc\n.LIB unavailable.lib TT\nR1 a 0 1k\n')
    data = cn.from_file(path)
    assert len(data.top.devices) == 1
    assert len(data.diagnostics) == 1
    assert data.diagnostics[0].source == path
    assert data.diagnostics[0].line == 1
    assert 'included file was not found' in data.diagnostics[0].message
    assert cn.main([str(path), '--strict']) == 2
    assert 'included file was not found' in capsys.readouterr().err
    stopped = cn.from_file(path, stop_include=['unavailable.inc'])
    assert not stopped.diagnostics  # deliberate boundaries are not I/O probes
    assert stopped.top.devices == data.top.devices


def test_external_signature_is_only_an_interface_and_checks_arity(tmp_path):
    path = tmp_path / 'input.sp'
    path.write_text('Xvendor out in 0 Missing gain={K*2}\nR1 out 0 1k')
    unknown = cn.from_file(path)
    assert unknown.top.devices[0].connections == (
        cn.Connection('@1', 'out'), cn.Connection('@2', 'in'), cn.Connection('@3', '0'))
    assert unknown.top.devices[0].black_box == cn.BlackBox('Missing', 'positional')
    assert unknown.top.devices[0].type == 'Missing'
    assert unknown.top.devices[0].parameters == (
        cn.Parameter('gain', '{K*2}'),)
    known_pins = cn.from_file(path, external_subcircuits={'Missing': ['O', 'I', 'G']})
    assert not known_pins.subcircuits
    assert known_pins.top.devices[0].black_box == cn.BlackBox('Missing', 'named')
    assert known_pins.top.devices[0].connections == (
        cn.Connection('O', 'out'), cn.Connection('I', 'in'), cn.Connection('G', '0'))
    with pytest.raises(ValueError):
        cn.from_file(path, external_subcircuits={'Missing': ['O', 'I']})
