"""Namespaced artifact data, bound to an exact structural snapshot.

No namespace selects Python code. Core cells are generated from the structural
model; only extension values and necessary host layout are retained here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Literal, Mapping, Sequence

if TYPE_CHECKING:
    from .canonical_netlist import CanonicalNetlist

_SEGMENT = r"[a-z][a-z0-9_-]*"
_NAMESPACE = re.compile(rf"{_SEGMENT}(?:\.{_SEGMENT})+")
_LOCAL = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
CORE_HEADERS = {
    "PINS": ("pin",),
    "PARAMETER_DEFAULTS": ("name", "value"),
    "NET_INCIDENT_TABLE": ("net", "incident pins"),
    "DEVICE_TABLE": ("name", "type", "connections", "parameters"),
    "BLACK_BOX_TABLE": ("name", "cell", "pin_basis"),
    "DIAGNOSTICS": ("source", "line", "message"),
}


def _text(value: str) -> None:
    if type(value) is not str:
        raise ValueError("extension cells must be strings")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("extension cells must contain Unicode scalar values") from exc


def _strings(values: tuple[str, ...], *, headers: bool = False) -> None:
    if type(values) is not tuple:
        raise ValueError("extension sequences must be immutable tuples")
    for value in values:
        _text(value)
    if headers and (not values or len(set(values)) != len(values)):
        raise ValueError("extension headers must be nonempty and unique")


def _rows(rows: tuple[tuple[str, ...], ...], width: int) -> None:
    if type(rows) is not tuple:
        raise ValueError("extension rows must be an immutable tuple")
    for row in rows:
        _strings(row)
        if len(row) != width:
            raise ValueError("incorrect extension column count")


def qualified_name(value: str) -> tuple[str, str]:
    if type(value) is not str:
        raise ValueError("qualified extension name must be a string")
    namespace, separator, local = value.partition(":")
    if not separator or not _NAMESPACE.fullmatch(namespace) or not _LOCAL.fullmatch(local):
        raise ValueError(f"invalid qualified extension name: {value!r}")
    return namespace, local


@dataclass(frozen=True)
class ExtensionNamespace:
    name: str
    version: int

    def __post_init__(self) -> None:
        if type(self.name) is not str or not _NAMESPACE.fullmatch(self.name):
            raise ValueError("namespace must be a lowercase dotted authority/project identifier")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("namespace version must be a positive integer")


@dataclass(frozen=True)
class ExtensionScope:
    kind: Literal["document", "root", "definition"] = "document"
    name: str = ""

    def __post_init__(self) -> None:
        _text(self.name)
        if self.kind not in ("document", "root", "definition"):
            raise ValueError("invalid extension scope")
        if (self.kind == "document") != (self.name == ""):
            raise ValueError("document scope has no name; circuit scopes require a name")
        object.__setattr__(self, "name", self.name.casefold())


@dataclass(frozen=True)
class ExtensionTable:
    namespace: str
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    scope: ExtensionScope = ExtensionScope()

    def __post_init__(self) -> None:
        if type(self.namespace) is not str or type(self.name) is not str:
            raise ValueError("custom table names must be strings")
        qualified_name(f"{self.namespace}:{self.name}")
        if not isinstance(self.scope, ExtensionScope):
            raise ValueError("invalid extension table scope")
        _strings(self.columns, headers=True)
        if any(not _LOCAL.fullmatch(column) for column in self.columns):
            raise ValueError("custom table headers must be local identifiers")
        _rows(self.rows, len(self.columns))


@dataclass(frozen=True)
class ExtensionColumns:
    scope: ExtensionScope
    table: str
    columns: tuple[str, ...]
    row_order: tuple[str | int, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ExtensionScope) or self.table not in CORE_HEADERS:
            raise ValueError("invalid extension column host")
        if (self.table == "DIAGNOSTICS") != (self.scope.kind == "document"):
            raise ValueError("diagnostics use document scope; other hosts use circuit scope")
        _strings(self.columns, headers=True)
        for column in self.columns:
            qualified_name(column)
        if type(self.row_order) is not tuple:
            raise ValueError("extension row order must be an immutable tuple")
        positional = self.table in ("PARAMETER_DEFAULTS", "DIAGNOSTICS")
        for key in self.row_order:
            if positional:
                if type(key) is not int or key < 0:
                    raise ValueError("ordered host rows require nonnegative occurrence indices")
            elif type(key) is not str or not key:
                raise ValueError("named host rows require nonempty names")
        keys = tuple(key.casefold() if isinstance(key, str) else key for key in self.row_order)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate extension host row")
        object.__setattr__(self, "row_order", keys)
        _rows(self.rows, len(self.columns))
        if len(self.rows) != len(keys):
            raise ValueError("extension host row/value count disagrees")


@dataclass(frozen=True)
class CanonicalExtensions:
    namespaces: tuple[ExtensionNamespace, ...] = ()
    tables: tuple[ExtensionTable, ...] = ()
    columns: tuple[ExtensionColumns, ...] = ()
    core_sha256: str = ""

    def __post_init__(self) -> None:
        for sequence, cls in ((self.namespaces, ExtensionNamespace),
                              (self.tables, ExtensionTable), (self.columns, ExtensionColumns)):
            if type(sequence) is not tuple or any(not isinstance(item, cls) for item in sequence):
                raise ValueError("extension envelope requires immutable typed tuples")
        names = [item.name for item in self.namespaces]
        if len(names) != len(set(names)):
            raise ValueError("duplicate namespace declaration")
        declared = set(names)
        table_keys = [(item.scope, item.namespace, item.name) for item in self.tables]
        host_keys = [(item.scope, item.table) for item in self.columns]
        if len(table_keys) != len(set(table_keys)) or len(host_keys) != len(set(host_keys)):
            raise ValueError("duplicate extension table or column host")
        used = {item.namespace for item in self.tables}
        used.update(qualified_name(column)[0] for host in self.columns for column in host.columns)
        if not used <= declared:
            raise ValueError("undeclared extension namespace")
        if type(self.core_sha256) is not str:
            raise ValueError("invalid extension snapshot digest")
        if self.core_sha256 and not re.fullmatch(r"[0-9a-f]{64}", self.core_sha256):
            raise ValueError("invalid extension snapshot digest")
        # Block order is canonical; column and row order are payload.
        object.__setattr__(self, "namespaces", tuple(sorted(self.namespaces, key=lambda item: item.name)))
        object.__setattr__(self, "tables", tuple(sorted(self.tables, key=lambda item:
            (item.scope.kind, item.scope.name, item.namespace, item.name))))
        object.__setattr__(self, "columns", tuple(sorted(self.columns, key=lambda item:
            (item.scope.kind, item.scope.name, item.table))))

    def __bool__(self) -> bool:
        return bool(self.namespaces or self.tables or self.columns)

    def column_host(self, scope: ExtensionScope, table: str) -> ExtensionColumns | None:
        return next((item for item in self.columns if item.scope == scope and item.table == table), None)

    def table(self, namespace: str, name: str, scope: ExtensionScope = ExtensionScope()) -> ExtensionTable | None:
        return next((item for item in self.tables if
                     (item.namespace, item.name, item.scope) == (namespace, name, scope)), None)

    def validate(self, netlist: CanonicalNetlist, *, check_core: bool = True) -> None:
        if not self:
            if self.core_sha256:
                raise ValueError("empty extension envelope cannot retain a snapshot guard")
            return
        if self.core_sha256 != core_digest(netlist):
            raise ValueError("extension core snapshot changed; explicitly remove or reauthor extensions")
        hosts = _core_hosts(netlist)
        scopes = {ExtensionScope(), ExtensionScope("root", netlist.top.name),
                  *(ExtensionScope("definition", c.name) for c in netlist.subcircuits)}
        for table in self.tables:
            if table.scope not in scopes:
                raise ValueError("extension table refers to an absent scope")
        for column in self.columns:
            host = hosts.get((column.scope, column.table))
            if host is None or set(column.row_order) != set(_row_keys(host)):
                raise ValueError("extension columns disagree with their host rows")
            if column.table in ("PINS", "DEVICE_TABLE", "PARAMETER_DEFAULTS", "DIAGNOSTICS") and column.row_order != _row_keys(host):
                raise ValueError("ordered core host rows must retain represented order")
        if check_core:
            # Validate authored core objects too; loading never opens source paths.
            from .canonical_netlist import from_canonical_text
            from_canonical_text(netlist.render(include_extensions=False, include_diagnostics=True))


def core_digest(netlist: CanonicalNetlist) -> str:
    """Exact ordered represented snapshot, including diagnostics; no annotations."""
    document = {"top": asdict(netlist.top), "subcircuits": [asdict(c) for c in netlist.subcircuits],
                "diagnostics": [asdict(d) for d in netlist.diagnostics]}
    def encode(value):
        if isinstance(value, Path):
            return str(value)
        raise TypeError(f"unexpected core value: {type(value).__name__}")
    return hashlib.sha256(json.dumps(document, sort_keys=True, default=encode).encode()).hexdigest()


@dataclass(frozen=True)
class _Host:
    scope: ExtensionScope
    table: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]  # generated, already escaped core cells


def _core_hosts(netlist: CanonicalNetlist) -> dict[tuple[ExtensionScope, str], _Host]:
    from .canonical_netlist import _cell, _render_circuit_tables, _render_defaults
    from .canonical_text import _split
    result = {}
    for scope, circuit in ((ExtensionScope("root", netlist.top.name), netlist.top),
                           *((ExtensionScope("definition", c.name), c) for c in netlist.subcircuits)):
        for table in ("PINS", "PARAMETER_DEFAULTS", "NET_INCIDENT_TABLE", "DEVICE_TABLE", "BLACK_BOX_TABLE"):
            result[scope, table] = _Host(scope, table, CORE_HEADERS[table], ())
        result[scope, "PINS"] = _Host(scope, "PINS", ("pin",), tuple((_cell(pin),) for pin in circuit.pins))
        text = _render_defaults(circuit) + _render_circuit_tables(circuit)
        for block in text.strip("\n").split("\n\n"):
            lines = block.split("\n")
            table = lines[0].partition(" ")[0]
            rows = tuple(tuple(_split(row, "|")) for row in lines[2:])
            result[scope, table] = _Host(scope, table, CORE_HEADERS[table], rows)
    scope = ExtensionScope()
    rows = tuple((_cell(str(d.source)) if d.source is not None else "", str(d.line), _cell(d.message))
                 for d in netlist.diagnostics)
    result[scope, "DIAGNOSTICS"] = _Host(scope, "DIAGNOSTICS", CORE_HEADERS["DIAGNOSTICS"], rows)
    return result


def _row_keys(host: _Host) -> tuple[str | int, ...]:
    from .canonical_text import _decode
    if host.table in ("PARAMETER_DEFAULTS", "DIAGNOSTICS"):
        return tuple(range(len(host.rows)))
    return tuple(_decode(row[0]).casefold() for row in host.rows)


def _bind(netlist: CanonicalNetlist, envelope: CanonicalExtensions) -> CanonicalNetlist:
    result = replace(netlist, extensions=replace(envelope, core_sha256=core_digest(netlist)) if envelope else CanonicalExtensions())
    result.extensions.validate(result)
    return result


def declare_namespace(netlist: CanonicalNetlist, name: str, version: int) -> CanonicalNetlist:
    netlist.extensions.validate(netlist)
    namespace = ExtensionNamespace(name, version)
    previous = next((item for item in netlist.extensions.namespaces if item.name == name), None)
    if previous is not None:
        if previous != namespace:
            raise ValueError("namespace version conflict; explicit removal/conversion is required")
        return netlist
    return _bind(netlist, replace(netlist.extensions, namespaces=(*netlist.extensions.namespaces, namespace)))


def put_table(netlist: CanonicalNetlist, table: ExtensionTable) -> CanonicalNetlist:
    netlist.extensions.validate(netlist)
    if not isinstance(table, ExtensionTable):
        raise ValueError("expected an ExtensionTable")
    existing = tuple(item for item in netlist.extensions.tables if
                     (item.scope, item.namespace, item.name) != (table.scope, table.namespace, table.name))
    return _bind(netlist, replace(netlist.extensions, tables=(*existing, table)))


def put_column(netlist: CanonicalNetlist, namespace: str, name: str, *,
               table: str, values: Mapping[str | int, str] | Sequence[str],
               scope: ExtensionScope = ExtensionScope()) -> CanonicalNetlist:
    netlist.extensions.validate(netlist)
    qualified = f"{namespace}:{name}"
    qualified_name(qualified)
    host = _core_hosts(netlist).get((scope, table))
    if host is None:
        raise ValueError("unknown extension column host")
    previous = netlist.extensions.column_host(scope, table)
    order = previous.row_order if previous else _row_keys(host)
    if isinstance(values, Mapping):
        if any(not (type(key) is str or type(key) is int and key >= 0) for key in values):
            raise ValueError("invalid extension row key")
        normalized = {key.casefold() if isinstance(key, str) else key: value for key, value in values.items()}
        if len(normalized) != len(values) or not set(normalized) <= set(order):
            raise ValueError("unknown or duplicate extension row key")
        additions = tuple(normalized.get(key, "") for key in order)
    else:
        if isinstance(values, (str, bytes)):
            raise ValueError("column values must be a sequence of cells")
        additions = tuple(values)
    if len(additions) != len(order):
        raise ValueError("extension host row/value count disagrees")
    for cell in additions:
        _text(cell)
    headers = previous.columns if previous else ()
    rows = previous.rows if previous else tuple(() for _ in order)
    if qualified in headers:
        index = headers.index(qualified)
        rows = tuple((*row[:index], cell, *row[index + 1:]) for row, cell in zip(rows, additions))
    else:
        headers = (*headers, qualified)
        rows = tuple((*row, cell) for row, cell in zip(rows, additions))
    columns = ExtensionColumns(scope, table, headers, order, rows)
    existing = tuple(item for item in netlist.extensions.columns if (item.scope, item.table) != (scope, table))
    return _bind(netlist, replace(netlist.extensions, columns=(*existing, columns)))


def remove_namespace(netlist: CanonicalNetlist, namespace: str) -> CanonicalNetlist:
    netlist.extensions.validate(netlist)
    ExtensionNamespace(namespace, 1)
    columns = []
    for host in netlist.extensions.columns:
        indices = [i for i, name in enumerate(host.columns) if qualified_name(name)[0] != namespace]
        if indices:
            columns.append(replace(host, columns=tuple(host.columns[i] for i in indices),
                                   rows=tuple(tuple(row[i] for i in indices) for row in host.rows)))
    return _bind(netlist, replace(netlist.extensions,
        namespaces=tuple(item for item in netlist.extensions.namespaces if item.name != namespace),
        tables=tuple(item for item in netlist.extensions.tables if item.namespace != namespace),
        columns=tuple(columns)))


def remove_table(netlist: CanonicalNetlist, namespace: str, name: str,
                 scope: ExtensionScope = ExtensionScope()) -> CanonicalNetlist:
    netlist.extensions.validate(netlist)
    qualified_name(f"{namespace}:{name}")
    return _bind(netlist, replace(netlist.extensions, tables=tuple(item for item in netlist.extensions.tables
        if (item.scope, item.namespace, item.name) != (scope, namespace, name))))


def remove_column(netlist: CanonicalNetlist, namespace: str, name: str, *,
                  table: str, scope: ExtensionScope = ExtensionScope()) -> CanonicalNetlist:
    netlist.extensions.validate(netlist)
    qualified = f"{namespace}:{name}"
    qualified_name(qualified)
    columns = []
    for host in netlist.extensions.columns:
        if (host.scope, host.table) != (scope, table) or qualified not in host.columns:
            columns.append(host)
            continue
        indices = [i for i, column in enumerate(host.columns) if column != qualified]
        if indices:
            columns.append(replace(host, columns=tuple(host.columns[i] for i in indices),
                rows=tuple(tuple(row[i] for i in indices) for row in host.rows)))
    return _bind(netlist, replace(netlist.extensions, columns=tuple(columns)))


def render_extended(netlist: CanonicalNetlist, *, include_diagnostics: bool | None) -> str:
    from .canonical_netlist import _cell
    netlist.extensions.validate(netlist)
    envelope = netlist.extensions
    hosts = _core_hosts(netlist)
    diagnostic_columns = envelope.column_host(ExtensionScope(), "DIAGNOSTICS")
    if include_diagnostics is False and (netlist.diagnostics or diagnostic_columns is not None):
        raise ValueError("cannot suppress diagnostics with attached extensions; use explicit core-only export")

    def cell(value):
        return _cell(value) or r"\e"

    def emit_host(scope, table, marker):
        host = hosts[scope, table]
        extra = envelope.column_host(scope, table)
        headers, rows = host.headers, host.rows
        if extra is not None:
            by_key = dict(zip(_row_keys(host), rows))
            rows = tuple((*by_key[key], *(cell(value) for value in values))
                         for key, values in zip(extra.row_order, extra.rows))
            headers = (*headers, *extra.columns)
        return "\n".join((marker, " | ".join(headers), *(" | ".join(row) for row in rows)))

    def emit_tables(scope, argument=""):
        return ["\n".join((f"{item.namespace}:{item.name}{argument}",
                          " | ".join(item.columns),
                          *(" | ".join(cell(value) for value in row) for row in item.rows)))
                for item in envelope.tables if item.scope == scope]

    sections = ["\n".join(("EXTENSION_NAMESPACES", "namespace | version",
                           *(f"{item.name} | {item.version}" for item in envelope.namespaces)))]
    sections.extend(emit_tables(ExtensionScope()))
    circuits = ((ExtensionScope("root", netlist.top.name), netlist.top), *(
                (ExtensionScope("definition", c.name), c) for c in netlist.subcircuits))
    for scope, circuit in circuits:
        targeted = any(item.scope == scope for item in (*envelope.columns, *envelope.tables))
        if scope.kind == "root" and not (targeted or circuit.devices or circuit.pins or
                                        circuit.parameter_defaults or circuit.name != "TOP"):
            continue
        name = _cell(circuit.name)
        marker = "TOP_LEVEL" if scope.kind == "root" else "SUBCKT"
        sections.append(emit_host(scope, "PINS", f"{marker} {name}"))
        for table in ("PARAMETER_DEFAULTS", "NET_INCIDENT_TABLE", "DEVICE_TABLE", "BLACK_BOX_TABLE"):
            if (hosts[scope, table].rows or table in ("NET_INCIDENT_TABLE", "DEVICE_TABLE")
                    or envelope.column_host(scope, table) is not None):
                sections.append(emit_host(scope, table, f"{table} {name}"))
        sections.extend(emit_tables(scope, f" {name}"))
    if netlist.diagnostics or diagnostic_columns is not None:
        sections.append(emit_host(ExtensionScope(), "DIAGNOSTICS", "DIAGNOSTICS"))
    return "\n\n".join(sections) + "\n"
