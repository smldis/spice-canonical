"""Read-only structural inspection; ordinary fields remain the query interface.

Names match case-insensitively. Parameters remain ordered and unevaluated.
Graph edges mean terminal incidence, never conduction, signal flow, or coupling.
"""
from collections import deque
from dataclasses import dataclass, replace
from typing import Iterable

from .canonical_netlist import BlackBox, CanonicalNetlist, Circuit, Device, Diagnostic


@dataclass(frozen=True)
class Terminal:
    """One represented terminal; distinct terminals are never deduplicated."""
    device: str
    pin: str


@dataclass(frozen=True)
class Net:
    """First-seen net spelling and ordered incident terminals."""
    name: str
    terminals: tuple[Terminal, ...]


def net_incidence(circuit: Circuit) -> tuple[Net, ...]:
    """Return nets in declaration/first-use order, including unused pins."""
    rows = {}
    for pin in circuit.pins:
        rows.setdefault(pin.casefold(), (pin, []))
    for device in circuit.devices:
        for connection in device.connections:
            rows.setdefault(connection.net.casefold(), (connection.net, []))[1].append(
                Terminal(device.name, connection.pin))
    return tuple(Net(name, tuple(terminals)) for name, terminals in rows.values())


def definition(netlist: CanonicalNetlist, name: str) -> Circuit:
    """Select a subcircuit, never the file root; raise KeyError if absent."""
    for circuit in netlist.subcircuits:
        if circuit.name.casefold() == name.casefold():
            return circuit
    raise KeyError(name)


@dataclass(frozen=True)
class Call:
    """Call resolution, with defaults available on ``definition`` separately.

    Status is primitive, implemented, opaque, missing, or ambiguous. Authored
    source_type values can make old normalized artifacts intrinsically ambiguous;
    no helper can reconstruct normalization history absent from their data.
    """
    device: Device
    definition: Circuit | None
    status: str
    target: str | None


def resolve_call(netlist: CanonicalNetlist, device: Device) -> Call:
    """Resolve X instances, respecting explicit black boxes and source_type.

    Multiple differing source_type values or conflicting defined targets are
    ambiguous. A uniquely retained source_type is used for normalized calls.
    Formal pin sets must agree before a definition can be expanded.
    """
    if device.black_box is not None:
        return Call(device, None, 'opaque', device.black_box.cell)
    if not device.name.casefold().startswith('x') or device.type == 'unresolved':
        return Call(device, None, 'primitive', None)
    sources = {p.value.casefold(): p.value for p in device.parameters if p.name.casefold() == 'source_type'}
    if len(sources) > 1:
        return Call(device, None, 'ambiguous', None)
    target = next(iter(sources.values()), device.type)
    defs = {c.name.casefold(): c for c in netlist.subcircuits}
    body = defs.get(target.casefold())
    other = defs.get(device.type.casefold())
    if sources and other is not None and other is not body:
        return Call(device, None, 'ambiguous', target)
    if body is None:
        return Call(device, None, 'missing', target)
    pins = [c.pin.casefold() for c in device.connections]
    if len(pins) != len(set(pins)) or set(pins) != {p.casefold() for p in body.pins}:
        return Call(device, None, 'ambiguous', target)
    return Call(device, body, 'implemented', body.name)


def reachable_definitions(netlist: CanonicalNetlist, root: Circuit) -> tuple[Circuit, ...]:
    """Return each called definition once in depth-first order, excluding root.

    Opaque/missing/ambiguous calls are boundaries. Inspect ``resolve_call`` at
    their call sites to distinguish them. Recursive definitions terminate.
    """
    seen = {id(root)}
    result = []
    pending = list(reversed(root.devices))
    while pending:
        body = resolve_call(netlist, pending.pop()).definition
        if body is None or id(body) in seen:
            continue
        seen.add(id(body))
        result.append(body)
        pending.extend(reversed(body.devices))
    return tuple(result)


def top_level_netlist(netlist: CanonicalNetlist) -> CanonicalNetlist:
    """Project the root for saved tables, marking omitted implementations opaque.

    Calls to definitions in ``netlist`` retain their known formal pin names,
    nets, and raw overrides, but become named black boxes because their bodies
    are absent from the result. Existing external boundaries and unresolved or
    ambiguous device rows are left unmarked. An ambiguous call's resolved status
    can change when its candidate definitions are omitted. Diagnostics still
    describe the full input.
    """
    devices = []
    for device in netlist.top.devices:
        call = resolve_call(netlist, device)
        if call.status == 'implemented':
            device = replace(device, black_box=BlackBox(call.definition.name, 'named'))
        devices.append(device)
    return replace(netlist, top=replace(netlist.top, devices=tuple(devices)), subcircuits=())


def definition_library(netlist: CanonicalNetlist, name: str) -> CanonicalNetlist:
    """Project a selected definition and closure for ``render()``.

    Diagnostics remain input-wide, not scoped to this projection. The selected
    cell remains a definition, not a designated simulation root.
    """
    root = definition(netlist, name)
    return CanonicalNetlist(Circuit('TOP', (), ()),
                            (root, *reachable_definitions(netlist, root)), netlist.diagnostics)


@dataclass(frozen=True)
class CircuitReport:
    """Direct structure and call interfaces, without expanded implementations."""
    circuit: Circuit
    nets: tuple[Net, ...]
    calls: tuple[Call, ...]
    diagnostics: tuple[Diagnostic, ...]


def circuit_report(netlist: CanonicalNetlist, circuit: Circuit | None = None) -> CircuitReport:
    """Inspect the direct root by default, after includes; diagnostics are input-wide.

    ``circuit.devices`` holds raw parameters and black-box markers. ``calls``
    retains definition references for pins/defaults; bodies are not traversed.
    """
    circuit = netlist.top if circuit is None else circuit
    calls = tuple(resolve_call(netlist, d) for d in circuit.devices)
    return CircuitReport(circuit, net_incidence(circuit),
                         tuple(c for c in calls if c.status != 'primitive'), netlist.diagnostics)


# A scoped net is (occurrence path, case-folded name); () is root/global scope.
NetKey = tuple[tuple[str, ...], str]


@dataclass(frozen=True)
class Occurrence:
    """A device occurrence and its terminals bound to scoped net identities.

    Status: primitive, expanded, opaque, missing, ambiguous, recursive, depth.
    Expanded calls are context records, not leaves. Parameters/defaults remain
    on the original objects and are never evaluated or inherited.
    """
    path: tuple[str, ...]
    device: Device
    definition: Circuit | None
    connections: tuple[tuple[str, NetKey], ...]
    status: str


@dataclass(frozen=True)
class Expansion:
    """Bounded occurrence view; check ``truncated`` before claiming full counts."""
    occurrences: tuple[Occurrence, ...]
    nets: tuple[NetKey, ...]
    truncated: bool


def expand(netlist: CanonicalNetlist, root: Circuit | None = None, *,
           path: tuple[str, ...] = (), max_depth: int = 32,
           max_objects: int = 10000, global_nets: Iterable[str] = ()) -> Expansion:
    """Expand one circuit or selected instance path into a structural view.

    Paths exclude the root's display name and contain instance-name segments.
    Root and declared definitions never share a namespace. Ground 0 and explicit
    global_nets are global; other internal nets are occurrence-local. Port shorts
    are preserved. Missing interiors, recursion and depth limits remain boundary
    records. max_objects limits emitted devices; truncation is always explicit.
    A selected path must reach implemented, nonrecursive calls or raises ValueError.
    """
    if max_depth < 0 or max_objects < 1:
        raise ValueError('max_depth must be nonnegative and max_objects positive')
    root = netlist.top if root is None else root
    globals_ = {'0', *(n.casefold() for n in global_nets)}
    def net(name, scope, bindings):
        key = name.casefold()
        return ((), key) if key in globals_ else bindings.get(key, (scope, key))
    scope, bindings, active = (), {}, (id(root),)
    for segment in path:
        device = next((d for d in root.devices if d.name.casefold() == segment.casefold()), None)
        call = resolve_call(netlist, device) if device is not None else None
        if call is None or call.definition is None or id(call.definition) in active:
            raise ValueError(f'path does not reach an implemented nonrecursive call: {segment!r}')
        bindings = {c.pin.casefold(): net(c.net, scope, bindings) for c in device.connections}
        scope += (device.name,)
        root = call.definition
        active += (id(root),)
    rows, nets, truncated = [], {}, False
    # Iterators keep memory proportional to depth rather than expanded fanout.
    stack = [(root, scope, bindings, active, 0, iter(root.devices))]
    while stack:
        circuit, scope, bindings, active, depth, devices = stack[-1]
        for pin in circuit.pins:
            nets.setdefault(net(pin, scope, bindings), None)
        device = next(devices, None)
        if device is None:
            stack.pop()
            continue
        if len(rows) >= max_objects:
            truncated = True
            break
        call = resolve_call(netlist, device)
        connections = tuple((c.pin, net(c.net, scope, bindings)) for c in device.connections)
        nets.update((key, None) for _, key in connections)
        status = call.status
        if call.definition is not None:
            status = ('recursive' if id(call.definition) in active else
                      'depth' if depth >= max_depth else 'expanded')
        truncated |= status == 'depth'
        occurrence_path = scope + (device.name,)
        rows.append(Occurrence(occurrence_path, device, call.definition, connections, status))
        if status == 'expanded':
            stack.append((call.definition, occurrence_path,
                          {pin.casefold(): key for pin, key in connections},
                          active + (id(call.definition),), depth + 1, iter(call.definition.devices)))
    return Expansion(tuple(rows), tuple(nets), truncated)


@dataclass(frozen=True)
class Node:
    """Graph identity: kind 'net' or 'device', case-folded path and name.

    For devices, path is the enclosing occurrence path; for nets, their scoped
    identity. Use ``graph.nodes`` to discover exact identities for expanded views.
    """
    kind: str
    path: tuple[str, ...]
    name: str

    def __post_init__(self):
        if self.kind not in {'net', 'device'}:
            raise ValueError("node kind must be 'net' or 'device'")
        object.__setattr__(self, 'name', self.name.casefold())
        object.__setattr__(self, 'path', tuple(p.casefold() for p in self.path))


@dataclass(frozen=True)
class Neighborhood:
    """BFS result; truncated signals an object budget or depth frontier."""
    nodes: tuple[Node, ...]
    truncated: bool


class Connectivity:
    """Undirected terminal-incidence graph of a Circuit or Expansion.

    Expanded calls are omitted as vertices (their leaf connectivity is used).
    Opaque/recursive/depth boundaries remain vertices. Coupling/control references
    stored in parameters do not introduce edges. Exclusions are explicit names,
    case-insensitive across scopes. No source object is modified.
    """
    def __init__(self, source: Circuit | Expansion, *, exclude_nets: Iterable[str] = ()):
        excluded = {n.casefold() for n in exclude_nets}
        adjacency = {}
        def add(node):
            adjacency.setdefault(node, {})
        def edge(device, key):
            if key[1].casefold() in excluded:
                return
            node = Node('net', key[0], key[1].casefold())
            add(node)
            adjacency[device][node] = None
            adjacency[node][device] = None
        if isinstance(source, Circuit):
            net_keys = tuple(((), n.name.casefold()) for n in net_incidence(source))
            devices = (((), d.name, tuple(((), c.net.casefold()) for c in d.connections)) for d in source.devices)
            self.truncated = False
        else:
            net_keys = source.nets
            devices = ((o.path[:-1], o.device.name, tuple(key for _, key in o.connections))
                       for o in source.occurrences if o.status != 'expanded')
            self.truncated = source.truncated
        for key in net_keys:
            if key[1].casefold() not in excluded:
                add(Node('net', key[0], key[1].casefold()))
        for path, name, connections in devices:
            device = Node('device', path, name.casefold())
            add(device)
            for key in connections:
                edge(device, key)
        self._adjacency = {n: tuple(neighbors) for n, neighbors in adjacency.items()}

    @property
    def nodes(self) -> tuple[Node, ...]:
        """All graph nodes in deterministic source order."""
        return tuple(self._adjacency)

    def components(self) -> tuple[tuple[Node, ...], ...]:
        """Return represented connectivity islands, including isolated nodes."""
        unseen = dict.fromkeys(self.nodes)
        groups = []
        while unseen:
            start = next(iter(unseen))
            visited, _ = self._walk(start, None, len(unseen), None)
            groups.append(tuple(visited))
            for node in visited:
                unseen.pop(node, None)
        return tuple(groups)

    def _walk(self, start, max_depth, max_nodes, target):
        if start not in self._adjacency:
            raise KeyError(start)
        if max_nodes < 1 or (max_depth is not None and max_depth < 0):
            raise ValueError('max_nodes must be positive and max_depth nonnegative')
        parents, queue, truncated = {start: None}, deque([(start, 0)]), False
        while queue:
            node, depth = queue.popleft()
            if node == target:
                break
            for neighbor in self._adjacency[node]:
                if neighbor in parents:
                    continue
                if (max_depth is not None and depth >= max_depth) or len(parents) >= max_nodes:
                    truncated = True
                    continue
                parents[neighbor] = node
                queue.append((neighbor, depth + 1))
        return parents, truncated

    def neighborhood(self, start: Node, *, max_depth: int = 2, max_nodes: int = 1000) -> Neighborhood:
        """Return a bounded BFS neighborhood; limits and incomplete input are explicit."""
        parents, truncated = self._walk(start, max_depth, max_nodes, None)
        return Neighborhood(tuple(parents), truncated or self.truncated)

    def path(self, start: Node, end: Node, *, max_depth: int = 32, max_nodes: int = 10000) -> tuple[Node, ...] | None:
        """Return one shortest structural path, or None when proven unreachable.

        Raise ValueError if the target is not found before a search/input limit;
        a bounded failure is not proof of disconnectedness. Unknown nodes raise
        KeyError. A returned witness remains valid for an incomplete graph.
        """
        if end not in self._adjacency:
            raise KeyError(end)
        parents, truncated = self._walk(start, max_depth, max_nodes, end)
        if end not in parents:
            if truncated or self.truncated:
                raise ValueError('path search incomplete')
            return None
        result, current = [], end
        while current is not None:
            result.append(current)
            current = parents[current]
        return tuple(reversed(result))
