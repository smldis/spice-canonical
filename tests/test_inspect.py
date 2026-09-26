from collections import Counter

import pytest

from spice_canonical.canonical_netlist import from_text, normalize_device_types, from_canonical_text
from spice_canonical.inspect import (net_incidence, definition, resolve_call, reachable_definitions,
                                     definition_library, circuit_report, expand, Connectivity, Node)


def fixture():
    return from_text('.subckt CELL A B UNUSED W=1 W=2\nR1 A B {W}\n.ends\n'
                     'X1 in out CELL W=3\nX2 out 0 spare CELL\n'.replace('X1 in out CELL', 'X1 in out spare CELL'))


def test_direct_inventory_recipes_and_projection():
    data = fixture()
    report = circuit_report(data)
    assert report.circuit is data.top
    assert [n.name for n in report.nets] == ['in', 'out', 'spare', '0']
    body = definition(data, 'cell')
    assert [p.value for p in body.parameter_defaults] == ['1', '2']
    assert report.calls[0].definition is body
    assert [p.value for p in report.calls[0].device.parameters] == ['3']
    assert [n.name for n in net_incidence(body) if not n.terminals] == ['UNUSED']
    library = definition_library(data, 'cell')
    assert from_canonical_text(library.render()) == library
    assert library.top.devices == ()
    assert reachable_definitions(data, data.top) == (body,)
    with pytest.raises(KeyError):
        definition(data, 'absent')


def test_incidence_case_spelling_and_terminal_multiplicity():
    data = from_text('.subckt C A\nM1 a A a A NM\n.ends\n')
    row, = net_incidence(data.subcircuits[0])
    assert row.name == 'A'
    assert [r.pin for r in row.terminals] == ['d', 'g', 's', 'b']


def test_call_namespaces_normalization_and_boundaries():
    data = from_text('.subckt TOP A\nR1 A 0 1k\n.ends\nX1 in TOP\nX2 out ABSENT\n')
    normalized = normalize_device_types(data, {'TOP': 'cell'})
    assert resolve_call(normalized, normalized.top.devices[0]).definition is normalized.subcircuits[0]
    assert resolve_call(data, data.top.devices[1]).status == 'opaque'
    colliding = from_text('.subckt A P\n.ends\n.subckt B P\n.ends\nX1 p A source_type=B\n')
    assert resolve_call(colliding, colliding.top.devices[0]).status == 'ambiguous'
    assert expand(data).occurrences[1].path == ('X1', 'R1')


def test_occurrences_shorts_globals_selection_and_counts():
    data = from_text('.subckt C A B\nR1 A local 1k\nR2 local B 2k\nR3 local VDD 3k\n.ends\n'
                     'X1 in in C\nX2 out 0 C\n')
    view = expand(data, global_nets=['vdd'])
    assert Counter(o.device.type for o in view.occurrences if o.status == 'primitive') == {'resistor': 6}
    first, second = view.occurrences[1:3]
    assert first.connections[0][1] == second.connections[1][1] == ((), 'in')
    assert first.connections[1][1] == (('X1',), 'local')
    assert view.occurrences[3].connections[1][1] == ((), 'vdd')
    selected = expand(data, path=('x2',))
    assert selected.occurrences[0].path == ('X2', 'R1')
    assert selected.occurrences[0].connections[0][1] == ((), 'out')
    with pytest.raises(ValueError):
        expand(data, path=('R1',))
    graph = Connectivity(view)
    assert graph.path(Node('net', (), 'in'), Node('net', (), 'out')) is not None


def test_limits_recursion_and_repeated_cells():
    data = from_text('.subckt C A\nXself A C\nR1 A 0 1k\n.ends\nX1 a C\nX2 b C\n')
    view = expand(data)
    assert [o.status for o in view.occurrences].count('recursive') == 2
    assert [o.status for o in view.occurrences].count('primitive') == 2
    assert not view.truncated
    assert expand(data, max_objects=2).truncated
    assert expand(data, max_depth=0).truncated
    with pytest.raises(ValueError):
        expand(data, path=('X1', 'Xself'))
    assert reachable_definitions(data, data.top) == data.subcircuits


def test_graph_islands_paths_exclusions_and_unknown_incidence():
    data = from_text('.subckt C UNUSED\nR1 a b 1k\nR2 b c 1k\nR3 d e 1k\nK1 L1 L2 .9\n.ends\n')
    graph = Connectivity(data.subcircuits[0])
    assert len(graph.components()) == 4  # resistor chain, R3, unused pin, coupling-only K1
    start, end = Node('net', (), 'a'), Node('net', (), 'c')
    assert len(graph.path(start, end)) == 5
    assert graph.path(start, Node('net', (), 'd')) is None
    with pytest.raises(ValueError, match='incomplete'):
        graph.path(start, end, max_depth=1)
    assert graph.neighborhood(start, max_depth=1).truncated
    assert Connectivity(data.subcircuits[0], exclude_nets=['B']).path(start, end) is None
    with pytest.raises(KeyError):
        graph.path(start, Node('net', (), 'absent'))


def test_node_names_do_not_conflate_devices_and_nets():
    graph = Connectivity(from_text('R1 R1 0 1k\n').top)
    assert len(graph.nodes) == 3
    assert len(graph.components()) == 1


def test_graph_queries_casefold_names_and_expanded_paths():
    data = from_text('.subckt C A\nR1 A Internal 1k\n.ends\nXUP a C\n')
    graph = Connectivity(expand(data))
    assert graph.path(Node('net', (), 'A'), Node('net', ('xup',), 'INTERNAL'))
    with pytest.raises(ValueError):
        Node('invented', (), 'a')


def test_budgeted_graph_does_not_claim_unreachable():
    data = from_text('R1 a b 1k\nR2 b c 1k\nR3 c d 1k\n')
    graph = Connectivity(data.top)
    with pytest.raises(ValueError, match='incomplete'):
        graph.path(Node('net', (), 'a'), Node('net', (), 'd'), max_nodes=2)
    assert graph.neighborhood(Node('net', (), 'a'), max_nodes=2).truncated
