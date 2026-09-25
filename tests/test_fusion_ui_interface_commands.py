"""
Focused Fusion picker checks for Interface creation.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

from cable_bundler.domain import InterfaceTarget, InterfaceTargetKind


def test_interface_picker_reads_mixed_targets_and_requires_lone_occurrence(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep selected target order and reject a component mixed with geometry.
    """
    command = importlib.import_module("cable_bundler.fusion.ui.commands.interfaces")
    core = sys.modules["adsk.core"]
    fusion = command.adsk.fusion
    monkeypatch.setitem(
        vars(core), "SelectionCommandInput", SimpleNamespace(cast=lambda item: item)
    )
    monkeypatch.setitem(
        vars(fusion),
        "BRepBody",
        SimpleNamespace(cast=lambda item: item if item.kind == "body" else None),
    )
    monkeypatch.setitem(
        vars(fusion),
        "Sketch",
        SimpleNamespace(cast=lambda item: item if item.kind == "sketch" else None),
    )
    monkeypatch.setitem(
        vars(fusion),
        "Occurrence",
        SimpleNamespace(cast=lambda item: item if item.kind == "occurrence" else None),
    )
    body = SimpleNamespace(kind="body", entityToken="body-1")
    sketch = SimpleNamespace(kind="sketch", entityToken="sketch-1")
    occurrence = SimpleNamespace(kind="occurrence", entityToken="occurrence-1")
    selected = [body, sketch]
    picker = SimpleNamespace(
        selectionCount=2,
        selection=lambda index: SimpleNamespace(entity=selected[index]),
    )
    inputs = SimpleNamespace(itemById=lambda _identity: picker)

    assert tuple(target.kind for target in command._interface_targets(inputs)) == (
        InterfaceTargetKind.BODY,
        InterfaceTargetKind.SKETCH,
    )
    selected[1] = occurrence
    with pytest.raises(ValueError, match="by itself"):
        command._interface_targets(inputs)


def test_interface_picker_name_tracks_first_target_until_edited(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve a name typed by the user after subsequent selection changes.
    """
    command = importlib.import_module("cable_bundler.fusion.ui.commands.interfaces")
    core = sys.modules["adsk.core"]
    monkeypatch.setitem(
        vars(core), "SelectionCommandInput", SimpleNamespace(cast=lambda item: item)
    )
    monkeypatch.setitem(
        vars(core), "StringValueCommandInput", SimpleNamespace(cast=lambda item: item)
    )
    name = SimpleNamespace(value="Interface 01")
    first = SimpleNamespace(name="Connector A")
    picker = SimpleNamespace(
        selectionCount=1, selection=lambda _index: SimpleNamespace(entity=first)
    )
    inputs = SimpleNamespace(
        itemById=lambda identity: name if identity == command.INTERFACE_NAME_INPUT_ID else picker
    )
    handler = command._AddInterfaceInputChangedHandler()
    handler.notify(
        SimpleNamespace(input=SimpleNamespace(id=command.INTERFACE_TARGETS_INPUT_ID), inputs=inputs)
    )
    assert name.value == "Connector A"

    name.value = "Custom name"
    handler.notify(
        SimpleNamespace(input=SimpleNamespace(id=command.INTERFACE_NAME_INPUT_ID), inputs=inputs)
    )
    first.name = "Connector B"
    handler.notify(
        SimpleNamespace(input=SimpleNamespace(id=command.INTERFACE_TARGETS_INPUT_ID), inputs=inputs)
    )
    assert name.value == "Custom name"


def test_interface_resolution_checks_every_token_candidate(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Select the saved kind even when Fusion returns an earlier stale candidate.
    """
    targets = importlib.import_module("cable_bundler.fusion.interface_targets")
    fusion = targets.adsk.fusion
    monkeypatch.setitem(
        vars(fusion),
        "BRepBody",
        SimpleNamespace(cast=lambda item: item if getattr(item, "kind", None) == "body" else None),
    )
    monkeypatch.setitem(vars(fusion), "Sketch", SimpleNamespace(cast=lambda _item: None))
    monkeypatch.setitem(vars(fusion), "Occurrence", SimpleNamespace(cast=lambda _item: None))
    expected = SimpleNamespace(kind="body")
    design = SimpleNamespace(
        findEntityByToken=lambda _token: [SimpleNamespace(kind="face"), expected]
    )

    assert (
        targets.resolve_interface_target(
            design, InterfaceTarget(InterfaceTargetKind.BODY, "body-token")
        )
        is expected
    )
