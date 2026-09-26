from pathlib import Path

import pytest

from spice_canonical.canonical_netlist import from_file
from spice_canonical.evidence import extract_with_evidence


def test_source_locations_scope_continuations_and_discarded_text(tmp_path):
    root = tmp_path / 'root.cir'
    child = tmp_path / 'child.inc'
    child.write_text('.param child=2\n.subckt TOP A\n.param local=3\nR1 A 0 1k\n.ends\n')
    root.write_text('title not retained\n.param W=1\n+ W=2\n.include child.inc\n'
                    '.model N NMOS\nX1 a TOP W=3\n.control\n.param ignored=4\n.endc\n.tran 1n 1u\n')
    result = extract_with_evidence(root, spice_format='ngspice', device_type_map={'TOP': 'cell'})
    assert result.netlist == from_file(root, spice_format='ngspice', device_type_map={'TOP': 'cell'})
    assert [(d.kind, d.text) for d in result.evidence.declarations] == [
        ('PARAM', '.param W=1 W=2'), ('PARAM', '.param child=2'), ('MODEL', '.model N NMOS')]
    assert result.evidence.declarations[0].location.line == 2
    locations = {(o.circuit, o.device): o.location for o in result.evidence.objects}
    assert locations[('TOP', None)].source == child
    assert locations[('TOP', 'R1')].line == 4
    assert locations[('TOP', 'R1')].include == 0
    assert locations[(None, 'X1')].line == 6
    assert locations[(None, 'X1')].include is None


def test_nested_repeated_and_boundary_outcomes(tmp_path):
    root, child = tmp_path / 'root.sp', tmp_path / 'child.inc'
    child.write_text('.param repeated=1\n.include root.sp\n')
    root.write_text('.include child.inc\n.include child.inc\n.include absent\n'
                    '.include stopped\n.include\n.lib section\n.lib "vendor.lib" tt\nR1 a 0 1k\n')
    result = extract_with_evidence(root, stop_include=['stopped'])
    events = result.evidence.includes
    assert [e.outcome for e in events] == ['expanded', 'cyclic', 'expanded', 'cyclic', 'missing', 'stopped', 'malformed', 'opaque', 'opaque']
    assert events[1].parent == events[0].id
    assert events[3].parent == events[2].id
    assert [d.location.include for d in result.evidence.declarations] == [0, 2]
    assert events[-1].target is None  # no guessed library-file/section semantics
    assert result.netlist == from_file(root, stop_include=['stopped'])


def test_unreadable_include_and_missing_root(tmp_path, monkeypatch):
    root, child = tmp_path / 'root.sp', tmp_path / 'bad.inc'
    root.write_text('.include bad.inc\nR1 a 0 1k\n')
    child.write_bytes(b'\xff')
    result = extract_with_evidence(root)
    assert result.evidence.includes[0].outcome == 'unreadable'
    assert result.netlist.top.devices[0].name == 'R1'
    with pytest.raises(FileNotFoundError):
        extract_with_evidence(tmp_path / 'absent')


def test_libraries_keep_encounter_order_without_control_capture(tmp_path):
    root, child = tmp_path / 'root.sp', tmp_path / 'child.inc'
    root.write_text('title\n.lib "first.lib" tt\n.include child.inc\n.control\n.lib secret\n.endc\n')
    child.write_text('.lib "nested.lib" ff\n')
    result = extract_with_evidence(root, spice_format='ngspice')
    assert [e.text for e in result.evidence.includes] == [
        '.lib "first.lib" tt', '.include child.inc', '.lib "nested.lib" ff']
    assert result.evidence.includes[2].parent == result.evidence.includes[1].id


def test_stopped_include_is_not_probed(tmp_path, monkeypatch):
    root = tmp_path / 'root.sp'
    stopped = tmp_path / 'stopped.inc'
    root.write_text('.include stopped.inc\n')
    original = Path.is_file
    def guarded(path):
        if path == stopped:
            raise AssertionError('stopped target was probed')
        return original(path)
    monkeypatch.setattr(Path, 'is_file', guarded)
    result = extract_with_evidence(root, stop_include=['stopped.inc'])
    assert result.evidence.includes[0].outcome == 'stopped'
    assert result.netlist.diagnostics == ()
