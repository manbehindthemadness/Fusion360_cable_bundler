"""
Verify Add Pathway uses the harness routing mode without a picker.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import HarnessDefinition, RoutingMode, dumps


def test_add_pathway_dialog_has_no_routing_mode_input(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep pathway naming and profile selection with their event handlers.
    """
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.pathways")
    application = object()
    core = sys.modules["adsk.core"]
    core.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    monkeypatch.setitem(vars(commands), "_create_harness_gateway", lambda _app: object())
    monkeypatch.setitem(vars(commands), "suggest_pathway_name", Mock(return_value="Pathway_002"))
    harness_id = UUID(int=1)
    monkeypatch.setitem(
        vars(commands),
        "_runtime",
        SimpleNamespace(
            pending_pathway=SimpleNamespace(consume=lambda: harness_id),
            retain_command_handlers=Mock(),
        ),
    )
    gate_input = SimpleNamespace(
        addSelectionFilter=Mock(return_value=True),
        setSelectionLimits=Mock(return_value=True),
    )
    inputs = SimpleNamespace(
        addStringValueInput=Mock(return_value=object()),
        addDropDownCommandInput=Mock(),
        addSelectionInput=Mock(return_value=gate_input),
    )
    event = SimpleNamespace(add=Mock(return_value=True))
    command = SimpleNamespace(commandInputs=inputs, execute=event, validateInputs=event)

    commands._AddPathwayCreatedHandler().notify(SimpleNamespace(command=command))

    inputs.addStringValueInput.assert_called_once_with(
        commands.PATHWAY_NAME_INPUT_ID, "Pathway Name", "Pathway_002"
    )
    inputs.addDropDownCommandInput.assert_not_called()
    inputs.addSelectionInput.assert_called_once()
    gate_input.addSelectionFilter.assert_called_once_with("Profiles")
    gate_input.setSelectionLimits.assert_called_once_with(1, 0)
    assert event.add.call_count == 2


@pytest.mark.parametrize("routing_mode", tuple(RoutingMode))
def test_add_pathway_uses_harness_mode_at_execution(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    routing_mode: RoutingMode,
) -> None:
    """
    Use the owning harness mode when the user confirms the pathway.
    """
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.pathways")
    application = object()
    core = sys.modules["adsk.core"]
    core.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    gateway = SimpleNamespace(
        read_harness_definition=Mock(
            return_value=dumps(replace(valid_harness, routing_mode=routing_mode))
        )
    )
    monkeypatch.setitem(vars(commands), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(commands), "_read_pathway_name", lambda _inputs: "Pathway_002")
    monkeypatch.setitem(vars(commands), "_read_pathway_gate_tokens", lambda _inputs: ("gate",))
    add = Mock(return_value=SimpleNamespace(name="Pathway_002"))
    monkeypatch.setitem(vars(commands), "add_pathway", add)
    notice = Mock()
    monkeypatch.setitem(vars(commands), "_send_palette_state", notice)
    inputs = object()
    harness_id = UUID(int=1)

    commands._AddPathwayExecuteHandler(harness_id).notify(
        SimpleNamespace(command=SimpleNamespace(commandInputs=inputs))
    )

    gateway.read_harness_definition.assert_called_once_with(harness_id)
    add.assert_called_once_with(harness_id, "Pathway_002", routing_mode, ("gate",), gateway)
    notice.assert_called_once_with(application, "Created Pathway_002.")
