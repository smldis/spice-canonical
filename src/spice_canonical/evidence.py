"""Opt-in source evidence, separate from saved canonical connectivity.

Paths and starting physical lines describe the extraction snapshot. Logical
text has comments removed and continuations joined; it is not lossless source.
Evidence is not serialized by CanonicalNetlist.render and is not recovered by
from_canonical_file. No parameter/model evaluation or general directive capture
is performed.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .canonical_netlist import CanonicalNetlist, SpiceFormat, _extract_file


@dataclass(frozen=True)
class SourceLocation:
    """Source path, first physical line and include occurrence (None for root)."""
    source: Path | None
    line: int
    include: int | None = None


@dataclass(frozen=True)
class ObjectSource:
    """Location of a device or definition; circuit=None means file-root scope.

    device=None identifies a subcircuit declaration. Names retain source spelling;
    compare case-insensitively. No entry is invented for the synthetic root.
    """
    circuit: str | None
    device: str | None
    location: SourceLocation


@dataclass(frozen=True)
class Include:
    """One encountered include/library directive, never a deduplicated file.

    id is extraction-local; parent identifies the including occurrence. Outcomes:
    expanded, stopped, missing, cyclic, unreadable, malformed, opaque. Library
    raw text retains invocation/section evidence without guessing section meaning.
    Traversal describes this extractor, not a simulator's include/control rules.
    """
    id: int
    parent: int | None
    location: SourceLocation
    text: str
    target: Path | None
    outcome: str


@dataclass(frozen=True)
class Declaration:
    """Unevaluated root-scope PARAM or MODEL logical statement, in encounter order."""
    kind: str
    text: str
    location: SourceLocation


@dataclass(frozen=True)
class ExtractionEvidence:
    """Root provenance, object locations, include occurrences and declarations."""
    root: Path
    objects: tuple[ObjectSource, ...]
    includes: tuple[Include, ...]
    declarations: tuple[Declaration, ...]


@dataclass(frozen=True)
class ExtractionResult:
    """Canonical connectivity plus source evidence from the same extraction."""
    netlist: CanonicalNetlist
    evidence: ExtractionEvidence


@dataclass
class _Recorder:
    objects: list = field(default_factory=list)
    includes: list = field(default_factory=list)
    declarations: list = field(default_factory=list)
    orders: list = field(default_factory=list)
    ordinal: int = 0

    def advance(self):
        self.ordinal += 1
        return self.ordinal

    def location(self, statement):
        return SourceLocation(statement.source, statement.line, statement.include)

    def object(self, circuit, device, statement):
        self.objects.append(ObjectSource(circuit, device, self.location(statement)))

    def declaration(self, kind, statement):
        self.declarations.append(Declaration(kind, statement.text, self.location(statement)))

    def include(self, statement, target, outcome):
        event = Include(len(self.includes), statement.include, self.location(statement),
                        statement.text, target, outcome)
        self.includes.append(event)
        self.orders.append(statement.order)
        return event.id


def extract_with_evidence(path: str | Path, *, top_name: str = 'TOP',
                          spice_format: SpiceFormat = 'eldo',
                          stop_include: Sequence[str] = (),
                          external_subcircuits: Mapping[str, Sequence[str]] | None = None,
                          device_type_map: Mapping[str, str] | None = None) -> ExtractionResult:
    """Extract once with the same options/results as canonical_netlist.from_file.

    Root-scope means outside SUBCKT after include expansion, not physically in
    the root file. Only PARAM/MODEL declarations and include/LIB boundaries are
    retained; titles, control scripts and other directives remain omitted.
    Evidence is a source snapshot, not an object that tracks later edits.
    """
    recorder = _Recorder()
    netlist = _extract_file(path, top_name=top_name, spice_format=spice_format,
                           stop_include=stop_include, external_subcircuits=external_subcircuits,
                           device_type_map=device_type_map, evidence=recorder)
    return ExtractionResult(netlist, ExtractionEvidence(Path(path).expanduser().resolve(),
                            tuple(recorder.objects), tuple(sorted(recorder.includes, key=lambda e: recorder.orders[e.id])),
                            tuple(recorder.declarations)))
