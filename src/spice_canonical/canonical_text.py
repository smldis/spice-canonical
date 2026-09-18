"""Reader for canonical tables. Connectivity is checked, never reconstructed from SPICE."""
from collections import Counter
from dataclasses import replace
from pathlib import Path

from .canonical_netlist import (
    BlackBox, CanonicalNetlist, CanonicalParseError, Circuit, Connection,
    Device, Diagnostic, Parameter,
)


def _split(text, separator, *, grouped=False, maxsplit=None):
    """Split before unescaping; grouped values support earlier rendered expressions."""
    parts, start, i, stack, quote = [], 0, 0, [], None
    while i < len(text):
        char = text[i]
        if char == '\\':
            i += 2
            continue
        if grouped:
            if quote:
                if char == quote:
                    quote = None
            elif char in '\"\'':
                quote = char
            elif char in '({[':
                stack.append(char)
            elif char in ')}]' and stack:
                stack.pop()
        if char == separator and not quote and not stack:
            parts.append(text[start:i].strip())
            start = i + 1
            if maxsplit is not None and len(parts) == maxsplit:
                parts.append(text[start:].strip())
                return parts
        i += 1
    parts.append(text[start:].strip())
    return parts


def _decode(text):
    result, i = [], 0
    while i < len(text):
        char = text[i]
        if char == '\\':
            i += 1
            if i == len(text) or text[i] not in '\\|nrts,=. ':
                raise CanonicalParseError(f'invalid canonical escape in {text!r}')
            char = {'n': '\n', 'r': '\r', 't': '\t', 's': ' '}.get(text[i], text[i])
        result.append(char)
        i += 1
    return ''.join(result)


def _unique(values, label):
    keys = [value.casefold() for value in values]
    if len(keys) != len(set(keys)):
        raise CanonicalParseError(f'duplicate {label}')


def _assignments(text, cls):
    if not text:
        return ()
    result = []
    for item in _split(text, ',', grouped=cls is Parameter):
        parts = _split(item, '=', maxsplit=1)
        if len(parts) < 2 or not parts[0]:
            raise CanonicalParseError(f'expected name=value, found {item!r}')
        result.append(cls(_decode(parts[0]), _decode(parts[1])))
    return tuple(result)


def parse(text: str) -> CanonicalNetlist:
    blocks, block = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            block.append((number, line.strip()))
        elif block:
            blocks.append(block)
            block = []
    if block:
        blocks.append(block)
    circuits, order, top_data, diagnostics = {}, [], None, []
    diagnostic_table = False
    current = None
    headers = {'PARAMETER_DEFAULTS': 'name | value',
               'NET_INCIDENT_TABLE': 'net | incident pins',
               'DEVICE_TABLE': 'name | type | connections | parameters',
               'BLACK_BOX_TABLE': 'name | cell | pin_basis',
               'DIAGNOSTICS': 'source | line | message'}
    for block in blocks:
        number, marker = block[0]
        try:
            kind, _, raw_name = marker.partition(' ')
            if kind in ('TOP_LEVEL', 'SUBCKT'):
                name = _decode(raw_name.strip())
                if not name:
                    raise CanonicalParseError('empty circuit name')
                if kind == 'TOP_LEVEL':
                    if top_data is not None:
                        raise CanonicalParseError('duplicate TOP_LEVEL')
                else:
                    if name.casefold() in circuits:
                        raise CanonicalParseError('duplicate subcircuit name')
                    if len(block) < 2 or block[1][1] != 'pin':
                        raise CanonicalParseError('SUBCKT requires a pin table')
                if len(block) > 1 and block[1][1] != 'pin':
                    raise CanonicalParseError('expected pin table after circuit marker')
                pins = tuple(_decode(row) for _, row in block[2:])
                _unique(pins, 'circuit pins')
                current = {'name': name, 'pins': pins, 'tables': {}}
                if kind == 'TOP_LEVEL':
                    top_data = current
                else:
                    circuits[name.casefold()] = current
                    order.append(name.casefold())
                continue
            if kind not in headers or (kind == 'DIAGNOSTICS' and raw_name):
                raise CanonicalParseError(f'unknown table {marker!r}')
            if len(block) < 2 or [x.strip() for x in block[1][1].split('|')] != headers[kind].split(' | '):
                raise CanonicalParseError(f'incorrect header for {kind}')
            if kind == 'DIAGNOSTICS':
                if diagnostic_table:
                    raise CanonicalParseError('duplicate DIAGNOSTICS')
                diagnostic_table = True
            else:
                if current is None or _decode(raw_name.strip()).casefold() != current['name'].casefold():
                    raise CanonicalParseError('table must belong to the current declared circuit')
                if kind in current['tables']:
                    raise CanonicalParseError(f'duplicate {kind}')
            rows = []
            for number, row in block[2:]:
                cells = _split(row, '|')
                if len(cells) != len(headers[kind].split(' | ')):
                    raise CanonicalParseError(f'incorrect column count in {kind}')
                rows.append(cells)
            if kind == 'DIAGNOSTICS':
                for source, line, message in rows:
                    if not line.isdigit():
                        raise CanonicalParseError('diagnostic line must be a non-negative integer')
                    diagnostics.append(Diagnostic(int(line), _decode(message), Path(_decode(source)) if source else None))
            else:
                current['tables'][kind] = rows
        except CanonicalParseError as exc:
            raise CanonicalParseError(f'canonical line {number}: {exc}') from exc

    def build(data):
        tables = data['tables']
        if 'DEVICE_TABLE' not in tables or 'NET_INCIDENT_TABLE' not in tables:
            raise CanonicalParseError(f'{data["name"]}: missing device or net-incident table')
        devices = [Device(_decode(name), _decode(kind), _assignments(connections, Connection),
                          _assignments(parameters, Parameter))
                   for name, kind, connections, parameters in tables['DEVICE_TABLE']]
        _unique((d.name for d in devices), 'device names')
        by_name = {d.name.casefold(): i for i, d in enumerate(devices)}
        seen_boxes = set()
        for name, cell, basis in tables.get('BLACK_BOX_TABLE', []):
            name, cell, basis = map(_decode, (name, cell, basis))
            if name.casefold() not in by_name or name.casefold() in seen_boxes:
                raise CanonicalParseError('black-box row names an unknown or duplicate device')
            seen_boxes.add(name.casefold())
            if not cell or basis not in ('named', 'positional'):
                raise CanonicalParseError('black-box cell required; pin_basis must be named or positional')
            if cell.casefold() in circuits:
                raise CanonicalParseError('black-box cell also has an implementation in this artifact')
            i = by_name[name.casefold()]
            device = devices[i]
            if basis == 'positional' and tuple(c.pin for c in device.connections) != tuple(
                    f'@{j}' for j in range(1, len(device.connections) + 1)):
                raise CanonicalParseError('positional black-box pins must be @1, @2, ... in order')
            devices[i] = replace(device, black_box=BlackBox(cell, basis))
        expected = {pin.casefold(): Counter() for pin in data['pins']}
        for device in devices:
            if not device.name or not device.type:
                raise CanonicalParseError('device name and type must be non-empty')
            _unique((c.pin for c in device.connections), 'device terminal roles')
            for connection in device.connections:
                if not connection.pin or not connection.net:
                    raise CanonicalParseError('connection pin and net must be non-empty')
                expected.setdefault(connection.net.casefold(), Counter())[
                    (device.name.casefold(), connection.pin.casefold())] += 1
        actual = {}
        for net, references in tables['NET_INCIDENT_TABLE']:
            net = _decode(net).casefold()
            if net in actual:
                raise CanonicalParseError('duplicate net-incident row')
            endpoints = Counter()
            for ref in _split(references, ',') if references else []:
                parts = _split(ref, '.')
                if len(parts) != 2:
                    raise CanonicalParseError(f'ambiguous incident reference {ref!r}; escape literal dots')
                endpoints[tuple(_decode(p).casefold() for p in parts)] += 1
            actual[net] = endpoints
        if actual != expected:
            raise CanonicalParseError(f'{data["name"]}: net-incident table disagrees with device connections or declared pins')
        defaults = tuple(Parameter(_decode(n), _decode(v))
                         for n, v in tables.get('PARAMETER_DEFAULTS', []))
        return Circuit(data['name'], data['pins'], tuple(devices), defaults)

    top = build(top_data) if top_data is not None else Circuit('TOP', (), ())
    return CanonicalNetlist(top, tuple(build(circuits[name]) for name in order), tuple(diagnostics))
