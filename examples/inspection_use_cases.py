"""Executable recipes for the numbered SPICE Canonical use cases.

This is one file of examples, not another library API. From the
``spice-canonical`` checkout, after installing the package, use it like this::

    from examples.inspection_use_cases import case_01, case_17, case_27
    from spice_canonical.evidence import extract_with_evidence

    result = extract_with_evidence("design.sp", spice_format="ngspice")
    root_inventory = case_01(result.netlist)
    source_locations = case_27(result)

For a top-level-only canonical file, see the complete example in ``case_01``.

To save the complete extracted structure as canonical tables::

    from pathlib import Path

    Path("design.canonical").write_text(result.netlist.render(), encoding="utf-8")

For use case 17, the selected definition and its reachable definitions already
form a ``CanonicalNetlist`` and can be saved the same way::

    selected = case_17(result.netlist, "AMP")
    Path("amp.canonical").write_text(selected.render(), encoding="utf-8")

These files contain structural netlists, not the inventory or source-location
answers returned by other cases.

Cases 1-18, 27, 28, and 30 use the implemented read-only Python API. Cases
19-26 are deferred canonical-data edits; 29 and 31 were discarded. Their
descriptions remain below so no unsupported code is mistaken for a working
operation. The wording follows the reconstructed use-case index, not a
verbatim record of the original brainstorming session.

All graph results describe represented terminal incidence, not electrical
behavior. Source evidence describes the extraction snapshot and is unavailable
from saved canonical tables alone.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from spice_canonical.canonical_netlist import CanonicalNetlist, Circuit, Device
from spice_canonical.evidence import ExtractionResult
from spice_canonical.inspect import (
    Connectivity,
    Expansion,
    Node,
    circuit_report,
    definition,
    definition_library,
    expand,
    net_incidence,
    reachable_definitions,
    resolve_call,
)


def _circuits(netlist: CanonicalNetlist) -> tuple[Circuit, ...]:
    return (netlist.top, *netlist.subcircuits)


def _device(circuit: Circuit, name: str) -> Device:
    for device in circuit.devices:
        if device.name.casefold() == name.casefold():
            return device
    raise KeyError(name)


def case_01(netlist: CanonicalNetlist) -> dict:
    """1. Inventory direct top-level devices, nets, definitions, diagnostics.

    To save just the represented top-level structure as a canonical netlist::

        from dataclasses import replace
        from pathlib import Path
        from spice_canonical.canonical_netlist import from_file

        netlist = from_file("design.sp", spice_format="ngspice")
        top_only = replace(netlist, subcircuits=())
        Path("top.canonical").write_text(top_only.render(), encoding="utf-8")

    This preserves top-level devices, net incidence, instance pin mappings and
    raw parameters after include expansion. Subcircuit instances remain, but
    their definitions (including declaration defaults) are omitted. Diagnostics
    still describe the complete extraction. The source object is unchanged.

    Canonical tables do not contain raw root-scope PARAM/MODEL declarations;
    those remain available through ``extract_with_evidence`` and ``case_30``.
    The inventory returned below also lists definition interfaces; that list
    is not included in the top-only file.
    """
    return {
        "top": netlist.top,
        "devices": netlist.top.devices,
        "nets": net_incidence(netlist.top),
        "definitions": tuple((c.name, c.pins) for c in netlist.subcircuits),
        "diagnostics": netlist.diagnostics,
    }


def case_02(netlist: CanonicalNetlist, cell_name: str) -> Circuit:
    """2. Inspect one named subcircuit definition and its interface."""
    return definition(netlist, cell_name)  # .pins, .devices, .parameter_defaults


def case_03(netlist: CanonicalNetlist, circuit: Circuit, instance_name: str) -> dict:
    """3. Inspect one instance: pins, call target, explicit parameters."""
    device = _device(circuit, instance_name)
    call = resolve_call(netlist, device)
    return {
        "device": device,
        "connections": device.connections,
        "target": call.target,
        "status": call.status,
        "parameters": device.parameters,
    }


def case_04(circuit: Circuit, net_name: str) -> tuple:
    """4. List the device terminals attached to one net."""
    for net in net_incidence(circuit):
        if net.name.casefold() == net_name.casefold():
            return net.terminals
    raise KeyError(net_name)


def case_05(
    netlist: CanonicalNetlist, *, device_type: str | None = None,
    model_name: str | None = None,
) -> tuple[tuple[Circuit, Device], ...]:
    """5. Find devices by type or model identifier; both filters mean AND."""
    if device_type is None and model_name is None:
        raise ValueError("provide device_type or model_name")
    return tuple(
        (circuit, device)
        for circuit in _circuits(netlist)
        for device in circuit.devices
        if (device_type is None or device.type.casefold() == device_type.casefold())
        and (
            model_name is None
            or any(
                parameter.name.casefold() == "model"
                and parameter.value.casefold() == model_name.casefold()
                for parameter in device.parameters
            )
        )
    )


def case_06(netlist: CanonicalNetlist, circuit: Circuit, instance_name: str) -> dict:
    """6. Inspect ordered raw instance parameters and definition defaults."""
    device = _device(circuit, instance_name)
    call = resolve_call(netlist, device)
    return {
        "instance_parameters": device.parameters,
        "definition_defaults": (
            call.definition.parameter_defaults if call.definition is not None else ()
        ),
    }


def case_07(netlist: CanonicalNetlist) -> tuple:
    """7. Inventory external or black-box cells and their known interfaces."""
    return tuple(
        (circuit.name, device.name, device.black_box, device.connections)
        for circuit in _circuits(netlist)
        for device in circuit.devices
        if device.black_box is not None
    )


def case_08(netlist: CanonicalNetlist) -> dict:
    """8. Find unresolved structures and extraction diagnostics."""
    return {
        "unresolved": tuple(
            (circuit.name, device)
            for circuit in _circuits(netlist)
            for device in circuit.devices
            if device.type == "unresolved"
        ),
        "diagnostics": netlist.diagnostics,
    }


def case_09(netlist: CanonicalNetlist, cell_name: str) -> tuple:
    """9. Find call sites of a subcircuit, including opaque call targets."""
    return tuple(
        (circuit, device, call)
        for circuit in _circuits(netlist)
        for device in circuit.devices
        if (call := resolve_call(netlist, device)).target is not None
        and call.target.casefold() == cell_name.casefold()
    )


def case_10(netlist: CanonicalNetlist, root: Circuit | None = None) -> tuple[Circuit, ...]:
    """10. Find definitions reachable through calls from one circuit."""
    return reachable_definitions(netlist, netlist.top if root is None else root)


def case_11(
    netlist: CanonicalNetlist, *, occurrence_level: bool = False,
    root: Circuit | None = None, max_depth: int = 32, max_objects: int = 10000,
    global_nets: Iterable[str] = (),
) -> dict:
    """11. Count direct devices/calls or bounded occurrence leaves/calls.

    ``budget_complete`` only reports whether the expansion hit a limit.
    Opaque, missing, ambiguous, and recursive interiors remain unavailable.
    """
    if not occurrence_level:
        circuit = netlist.top if root is None else root
        calls = (resolve_call(netlist, device) for device in circuit.devices)
        return {
            "device_types": Counter(device.type for device in circuit.devices),
            "call_statuses": Counter(
                call.status for call in calls if call.status != "primitive"
            ),
            "budget_complete": True,
        }
    view = expand(
        netlist, root, max_depth=max_depth, max_objects=max_objects,
        global_nets=global_nets,
    )
    return {
        "device_types": Counter(
            occurrence.device.type
            for occurrence in view.occurrences
            if occurrence.status != "expanded"
        ),
        "call_statuses": Counter(
            occurrence.status
            for occurrence in view.occurrences
            if occurrence.status != "primitive"
        ),
        "budget_complete": not view.truncated,
    }


def case_12(circuit: Circuit, *, max_terminals: int = 1) -> tuple:
    """12. Find nets with low represented terminal incidence."""
    if max_terminals < 0:
        raise ValueError("max_terminals must be nonnegative")
    return tuple(net for net in net_incidence(circuit)
                 if len(net.terminals) <= max_terminals)


def case_13(circuit: Circuit) -> tuple[str, ...]:
    """13. Find declared subcircuit pins with no represented attachment."""
    incidence = {net.name.casefold(): net for net in net_incidence(circuit)}
    return tuple(pin for pin in circuit.pins
                 if not incidence[pin.casefold()].terminals)


def case_14(source: Circuit | Expansion, *, exclude_nets: Iterable[str] = ()) -> dict:
    """14. Find connectivity islands in the represented device/net graph."""
    graph = Connectivity(source, exclude_nets=exclude_nets)
    return {"components": graph.components(), "input_truncated": graph.truncated}


def case_15(
    source: Circuit | Expansion, start: Node, end: Node | None = None, *,
    max_depth: int = 2, max_nodes: int = 1000,
    exclude_nets: Iterable[str] = (),
) -> dict:
    """15. Inspect a bounded graph neighborhood or structural path.

    Pass ``end`` to request a path. An unreachable path returns None only when
    the search completed; ValueError means a limit prevented that conclusion.
    """
    graph = Connectivity(source, exclude_nets=exclude_nets)
    nearby = graph.neighborhood(start, max_depth=max_depth, max_nodes=max_nodes)
    return {
        "neighborhood": nearby,
        "path": (
            graph.path(start, end, max_depth=max_depth, max_nodes=max_nodes)
            if end is not None else None
        ),
        "input_truncated": graph.truncated,
    }


def case_16(netlist: CanonicalNetlist):
    """16. Produce a top-only report without descending into implementations."""
    return circuit_report(netlist)


def case_17(netlist: CanonicalNetlist, cell_name: str) -> CanonicalNetlist:
    """17. Extract a selected definition and its reachable definition closure.

    Save with ``Path(path).write_text(case_17(netlist, name).render(),
    encoding="utf-8")``. Diagnostics on the projected object still describe
    the whole original input.
    """
    return definition_library(netlist, cell_name)


def case_18(
    netlist: CanonicalNetlist, *, root: Circuit | None = None,
    path: tuple[str, ...] = (), max_depth: int = 32,
    max_objects: int = 10000, global_nets: Iterable[str] = (),
) -> Expansion:
    """18. Expand hierarchy into a bounded occurrence-level structural view."""
    return expand(
        netlist, root, path=path, max_depth=max_depth,
        max_objects=max_objects, global_nets=global_nets,
    )


# 19. Rename a net in canonical data. Deferred editing; no executable API.
# 20. Rename a device in canonical data. Deferred editing; no executable API.
# 21. Reconnect a device terminal in canonical data. Deferred editing; no API.
# 22. Merge nets in canonical data. Deferred editing; no executable API.
# 23. Change a raw parameter value in canonical data. Deferred editing; no API.
# 24. Clone an instance in canonical data. Deferred editing; no executable API.
# 25. Remove an instance from canonical data. Deferred editing; no executable API.
# 26. Retarget a subcircuit call in canonical data. Deferred editing; no API.


def case_27(result: ExtractionResult) -> tuple:
    """27. Locate source lines for devices and subcircuit definitions."""
    return result.evidence.objects


def case_28(result: ExtractionResult) -> tuple:
    """28. Inspect include occurrences, outcomes, and opaque LIB boundaries."""
    return result.evidence.includes


# 29. Inventory general top-level directives. Discarded; no executable API.


def case_30(result: ExtractionResult) -> tuple:
    """30. Inventory raw root-scope .PARAM and .MODEL declarations."""
    return result.evidence.declarations


# 31. Capture ngspice title and .CONTROL text. Discarded; no executable API.
