"""Reader for canonical tables. Connectivity is checked, never reconstructed from SPICE."""
from collections import Counter
from dataclasses import replace
from functools import partial
from pathlib import Path
import re

from .canonical_netlist import (
    BlackBox, CanonicalNetlist, CanonicalParseError, Circuit, Connection,
    Device, Diagnostic, Parameter,
)
from .extensions import (
    CORE_HEADERS, CanonicalExtensions, ExtensionColumns, ExtensionNamespace,
    ExtensionScope, ExtensionTable, core_digest, qualified_name,
)


# File spelling is independent of the stable Python annotation-host keys.
FILE_NAMES = {
    'PARAMETER_DEFAULTS': 'PARAMETER_DEFAULTS',
    'PARAMETER_ASSIGNMENTS': 'PARAMETER_ASSIGNMENTS',
    'NET_INCIDENT_TABLE': 'NETS', 'DEVICE_TABLE': 'DEVICES',
    'BLACK_BOX_TABLE': 'BLACK_BOXES', 'DIAGNOSTICS': 'DIAGNOSTICS',
}
FILE_HEADERS = {
    'PINS': ('port',),
    'PARAMETER_DEFAULTS': ('parameter', 'value'),
    'PARAMETER_ASSIGNMENTS': ('parameter', 'value'),
    'NET_INCIDENT_TABLE': ('net', 'incident_pins'),
    'DEVICE_TABLE': ('device', 'type', 'connections', 'parameters'),
    'BLACK_BOX_TABLE': ('device', 'cell', 'pin_basis'),
    'DIAGNOSTICS': ('source', 'line', 'message'),
}
ALIASES = {value: key for key, value in FILE_NAMES.items()}
ALIASES.update(TOP_PORTS='TOP_LEVEL', SUBCKT_PORTS='SUBCKT',
               NAMESPACES='EXTENSION_NAMESPACES')
NEW_MARKERS = {'TOP_PORTS', 'SUBCKT_PORTS', 'NETS', 'DEVICES', 'BLACK_BOXES', 'NAMESPACES'}


def _check_character(char, context):
    code = ord(char)
    if (0xD800 <= code <= 0xDFFF or code < 32 or 127 <= code <= 159
            or char != ' ' and char.isspace()):
        raise CanonicalParseError(f'{context}: unsupported character U+{code:04X}')


def _check_value(value, context):
    for char in value:
        if char not in '\n\r\t':
            _check_character(char, context)


def _encode(value, context):
    from .canonical_netlist import _cell
    _check_value(value, context)
    return _cell(value)


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
            parts.append(text[start:i].strip(' \t\r'))
            start = i + 1
            if maxsplit is not None and len(parts) == maxsplit:
                parts.append(text[start:].strip(' \t\r'))
                return parts
        i += 1
    parts.append(text[start:].strip(' \t\r'))
    return parts


def _decode(text, *, legacy=True):
    if legacy and text == r'\e':
        return ''
    result, i = [], 0
    while i < len(text):
        char = text[i]
        if char == '\\':
            i += 1
            if legacy and i < len(text) and text[i] == 'u':
                digits = text[i + 1:i + 5]
                if len(digits) != 4 or any(c not in '0123456789abcdefABCDEF' for c in digits):
                    raise CanonicalParseError(f'invalid canonical Unicode escape in {text!r}')
                code = int(digits, 16)
                if 0xD800 <= code <= 0xDFFF:
                    raise CanonicalParseError('canonical Unicode escapes require scalar values')
                result.append(chr(code))
                i += 5
                continue
            if i == len(text) or text[i] not in ('\\|nrts,=. ' if legacy else '\\|nrts,=.'):
                raise CanonicalParseError(f'invalid canonical escape in {text!r}')
            char = {'n': '\n', 'r': '\r', 't': '\t', 's': ' '}.get(text[i], text[i])
        elif not legacy:
            _check_character(char, 'canonical cell')
        result.append(char)
        i += 1
    return ''.join(result)


def _unique(values, label):
    keys = [value.casefold() for value in values]
    if len(keys) != len(set(keys)):
        raise CanonicalParseError(f'duplicate {label}')


def _assignments(text, cls, *, decode=_decode, legacy=True):
    if not text:
        return ()
    result = []
    for item in _split(text, ',', grouped=legacy and cls is Parameter):
        parts = _split(item, '=', maxsplit=1)
        if len(parts) < 2 or not parts[0]:
            raise CanonicalParseError(f'expected name=value, found {item!r}')
        result.append(cls(decode(parts[0]), decode(parts[1])))
    return tuple(result)


def parse(text: str) -> CanonicalNetlist:
    blocks, block = [], []
    for number, line in enumerate(text.split('\n'), 1):
        if line.strip(' \t\r'):
            block.append((number, line.strip(' \t\r')))
        elif block:
            blocks.append(block)
            block = []
    if block:
        blocks.append(block)
    # Distinct current markers select strict current lexical rules. Shared-only
    # artifacts (e.g. historical DIAGNOSTICS alone) remain legacy-readable.
    current_format = any(block[0][1].partition(' ')[0] in NEW_MARKERS for block in blocks)
    decode = partial(_decode, legacy=not current_format)
    circuits, order, top_data, diagnostics = {}, [], None, []
    diagnostic_table = False
    current = None
    namespaces, custom_tables, column_hosts = [], [], []
    declared = set()
    headers = {kind: header for kind, header in CORE_HEADERS.items() if kind != 'PINS'}

    def read_rows(block, required=None):
        if len(block) < 2:
            raise CanonicalParseError('table requires a header')
        header = tuple(decode(x) for x in _split(block[1][1], '|'))
        if not header or any(not name for name in header) or len(header) != len(set(header)):
            raise CanonicalParseError('table headers must be nonempty and unique')
        if required is not None:
            if header[:len(required)] != required:
                raise CanonicalParseError(f'incorrect header for {block[0][1].partition(" ")[0]}')
            for name in header[len(required):]:
                namespace, _ = qualified_name(name)
                if namespace not in declared:
                    raise CanonicalParseError('undeclared extension namespace')
        rows = []
        for number, row in block[2:]:
            cells = tuple(_split(row, '|'))
            # Validate every encoded cell, including structured fields and
            # unknown producer payloads, before their schema-specific decoding.
            for cell in cells:
                decode(cell)
            if len(cells) != len(header):
                raise CanonicalParseError(f'canonical line {number}: incorrect column count')
            rows.append(cells)
        return header, rows

    def retain_columns(scope, kind, header, rows, width):
        if len(header) > width:
            positional = kind in ('PARAMETER_DEFAULTS', 'PARAMETER_ASSIGNMENTS', 'DIAGNOSTICS')
            keys = tuple(range(len(rows))) if positional else tuple(decode(row[0]).casefold() for row in rows)
            column_hosts.append(ExtensionColumns(
                scope, kind, header[width:], keys,
                tuple(tuple(decode(value) for value in row[width:]) for row in rows)))
        return [list(row[:width]) for row in rows]

    for index, block in enumerate(blocks):
        number, marker = block[0]
        try:
            spelling, _, raw_name = marker.partition(' ')
            kind = ALIASES.get(spelling, spelling)
            if kind == 'EXTENSION_NAMESPACES':
                if index != 0 or raw_name:
                    raise CanonicalParseError('namespace preamble must be the first table')
                header, rows = read_rows(block)
                if header != ('namespace', 'version') or not rows:
                    raise CanonicalParseError('namespace preamble requires namespace/version declarations')
                for name, version in rows:
                    name, version = decode(name), decode(version)
                    if not version.isascii() or not version.isdigit() or version.startswith('0'):
                        raise CanonicalParseError('namespace version must be a positive integer')
                    namespace = ExtensionNamespace(name, int(version))
                    if name in declared:
                        raise CanonicalParseError('duplicate namespace declaration')
                    namespaces.append(namespace)
                    declared.add(name)
                continue
            if kind in ('TOP_LEVEL', 'SUBCKT'):
                name = decode(raw_name.strip(' \t\r'))
                if not name:
                    raise CanonicalParseError('empty circuit name')
                if kind == 'TOP_LEVEL':
                    if top_data is not None:
                        raise CanonicalParseError('duplicate TOP_LEVEL')
                else:
                    if name.casefold() in circuits:
                        raise CanonicalParseError('duplicate subcircuit name')
                    if len(block) < 2:
                        raise CanonicalParseError('SUBCKT requires a pin table')
                scope = ExtensionScope('root' if kind == 'TOP_LEVEL' else 'definition', name)
                pins = ()
                if spelling in NEW_MARKERS and len(block) < 2:
                    raise CanonicalParseError('table requires a header')
                if len(block) > 1:
                    header, rows = read_rows(block, FILE_HEADERS['PINS'] if spelling in NEW_MARKERS else ('pin',))
                    rows = retain_columns(scope, 'PINS', header, rows, 1)
                    pins = tuple(decode(row[0]) for row in rows)
                if any(not pin for pin in pins):
                    raise CanonicalParseError('circuit ports must be nonempty')
                _unique(pins, 'circuit pins')
                current = {'name': name, 'pins': pins, 'tables': {}, 'scope': scope}
                if kind == 'TOP_LEVEL':
                    top_data = current
                else:
                    circuits[name.casefold()] = current
                    order.append(name.casefold())
                continue
            if ':' in kind:
                namespace, local = qualified_name(kind)
                if namespace not in declared:
                    raise CanonicalParseError('undeclared extension namespace')
                scope = ExtensionScope()
                if raw_name:
                    if current is None or decode(raw_name.strip(' \t\r')).casefold() != current['name'].casefold():
                        raise CanonicalParseError('custom table must belong to the current declared circuit')
                    scope = current['scope']
                header, rows = read_rows(block)
                custom_tables.append(ExtensionTable(namespace, local, header,
                    tuple(tuple(decode(value) for value in row) for row in rows), scope))
                continue
            if kind not in headers or (kind == 'DIAGNOSTICS' and raw_name):
                raise CanonicalParseError(f'unknown table {marker!r}')
            # Shared parameter/diagnostic labels can carry legacy headers.
            if len(block) < 2:
                raise CanonicalParseError('table requires a header')
            required = headers[kind]
            if spelling in NEW_MARKERS:
                required = FILE_HEADERS[kind]
            elif current_format and spelling == FILE_NAMES[kind]:
                observed = tuple(_split(block[1][1], '|'))[:len(required)]
                if observed != required:
                    required = FILE_HEADERS[kind]
            header, rows = read_rows(block, required)
            if kind == 'DIAGNOSTICS':
                if diagnostic_table:
                    raise CanonicalParseError('duplicate DIAGNOSTICS')
                diagnostic_table = True
            else:
                if current is None or decode(raw_name.strip(' \t\r')).casefold() != current['name'].casefold():
                    raise CanonicalParseError('table must belong to the current declared circuit')
                if kind in current['tables']:
                    raise CanonicalParseError(f'duplicate {kind}')
            scope = ExtensionScope() if kind == 'DIAGNOSTICS' else current['scope']
            rows = retain_columns(scope, kind, header, rows, len(headers[kind]))
            if kind == 'DIAGNOSTICS':
                for source, line, message in rows:
                    if not re.fullmatch(r'0|[1-9][0-9]*', line):
                        raise CanonicalParseError('diagnostic line must be a non-negative integer')
                    decoded_source = decode(source)
                    diagnostics.append(Diagnostic(int(line), decode(message), Path(decoded_source) if decoded_source else None))
            else:
                current['tables'][kind] = rows
        except ValueError as exc:
            raise CanonicalParseError(f'canonical line {number}: {exc}') from exc

    def build(data):
        tables = data['tables']
        if 'DEVICE_TABLE' not in tables or 'NET_INCIDENT_TABLE' not in tables:
            raise CanonicalParseError(f'{data["name"]}: missing device or net-incident table')
        devices = [Device(decode(name), decode(kind), _assignments(connections, Connection, decode=decode, legacy=not current_format),
                          _assignments(parameters, Parameter, decode=decode, legacy=not current_format))
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
            net = decode(net).casefold()
            if net in actual:
                raise CanonicalParseError('duplicate net-incident row')
            endpoints = Counter()
            for ref in _split(references, ',') if references else []:
                parts = _split(ref, '.')
                if len(parts) != 2:
                    raise CanonicalParseError(f'ambiguous incident reference {ref!r}; escape literal dots')
                endpoints[tuple(decode(p).casefold() for p in parts)] += 1
            actual[net] = endpoints
        if actual != expected:
            raise CanonicalParseError(f'{data["name"]}: net-incident table disagrees with device connections or declared pins')
        defaults = tuple(Parameter(decode(n), decode(v))
                         for n, v in tables.get('PARAMETER_DEFAULTS', []))
        if any(not p.name for p in defaults):
            raise CanonicalParseError('parameter defaults require nonempty names')
        assignments = tuple(Parameter(decode(n), decode(v))
                            for n, v in tables.get('PARAMETER_ASSIGNMENTS', []))
        if any(not p.name or not p.value for p in assignments):
            raise CanonicalParseError('parameter assignments require nonempty names and values')
        return Circuit(data['name'], data['pins'], tuple(devices), defaults, assignments)

    top = build(top_data) if top_data is not None else Circuit('TOP', (), ())
    result = CanonicalNetlist(top, tuple(build(circuits[name]) for name in order), tuple(diagnostics))
    if namespaces:
        try:
            envelope = CanonicalExtensions(tuple(namespaces), tuple(custom_tables), tuple(column_hosts), core_digest(result))
            result = replace(result, extensions=envelope)
            envelope.validate(result, check_core=False)
        except ValueError as exc:
            raise CanonicalParseError(str(exc)) from exc
    return result


def render(netlist: CanonicalNetlist, *, include_diagnostics: bool | None = None,
           include_extensions: bool = True) -> str:
    """Emit the UTF-8/LF table format; legacy spellings are input-only."""
    from .extensions import _core_hosts, _row_keys
    if not isinstance(netlist.extensions, CanonicalExtensions):
        raise ValueError('expected a CanonicalExtensions envelope')
    envelope = netlist.extensions if include_extensions else CanonicalExtensions()
    if envelope:
        envelope.validate(netlist)
    diagnostic_columns = envelope.column_host(ExtensionScope(), 'DIAGNOSTICS')
    if envelope and include_diagnostics is False and (netlist.diagnostics or diagnostic_columns is not None):
        raise ValueError('cannot suppress diagnostics with attached extensions; use explicit core-only export')
    hosts = _core_hosts(netlist)
    sections = []

    def emit(label, headers, rows, *, encoded=False):
        lines = [label, ' | '.join(headers)]
        for index, row in enumerate(rows, 1):
            if len(row) == 1 and not row[0]:
                raise CanonicalParseError(f'{label}, row {index}: empty one-column row is not representable')
            values = []
            for column, value in zip(headers, row):
                context = f'{label}, row {index}, column {column}'
                if encoded:
                    _check_value(_decode(value), context)
                    values.append(value)
                else:
                    values.append(_encode(value, context))
            lines.append(' | '.join(values))
        sections.append('\n'.join(lines))

    def emit_host(scope, table, label):
        host = hosts[scope, table]
        extra = envelope.column_host(scope, table)
        headers, rows = FILE_HEADERS[table], host.rows
        if extra is not None:
            by_key = dict(zip(_row_keys(host), rows))
            rows = tuple((*by_key[key], *(_encode(value, f'{label}, row {index}, column {column}')
                         for column, value in zip(extra.columns, values)))
                         for index, (key, values) in enumerate(zip(extra.row_order, extra.rows), 1))
            headers = (*headers, *extra.columns)
        emit(label, headers, rows, encoded=True)

    def emit_producers(scope, argument=''):
        for item in envelope.tables:
            if item.scope == scope:
                emit(f'{item.namespace}:{item.name}{argument}', item.columns, item.rows)

    if envelope.namespaces:
        emit('NAMESPACES', ('namespace', 'version'),
             ((item.name, str(item.version)) for item in envelope.namespaces))
    emit_producers(ExtensionScope())
    circuits = ((ExtensionScope('root', netlist.top.name), netlist.top), *(
                (ExtensionScope('definition', c.name), c) for c in netlist.subcircuits))
    for scope, circuit in circuits:
        targeted = any(item.scope == scope for item in (*envelope.columns, *envelope.tables))
        if scope.kind == 'root' and not (targeted or circuit.devices or circuit.pins or
                circuit.parameter_defaults or circuit.parameter_assignments or circuit.name != 'TOP'):
            continue
        name = _encode(circuit.name, 'circuit name')
        marker = 'TOP_PORTS' if scope.kind == 'root' else 'SUBCKT_PORTS'
        emit_host(scope, 'PINS', f'{marker} {name}')
        for table in FILE_NAMES:
            if table == 'DIAGNOSTICS':
                continue
            if (hosts[scope, table].rows or table in ('NET_INCIDENT_TABLE', 'DEVICE_TABLE')
                    or envelope.column_host(scope, table) is not None):
                emit_host(scope, table, f'{FILE_NAMES[table]} {name}')
        emit_producers(scope, f' {name}')
    if ((include_diagnostics or envelope and include_diagnostics is None) and netlist.diagnostics
            or diagnostic_columns is not None):
        emit_host(ExtensionScope(), 'DIAGNOSTICS', 'DIAGNOSTICS')
    return '\n\n'.join(sections) + ('\n' if sections else '')
