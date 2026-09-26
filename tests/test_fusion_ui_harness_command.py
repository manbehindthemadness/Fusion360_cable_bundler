"""
Verify the native Create Harness dialog retains its former routing default.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cable_bundler.domain import RoutingMode


def test_create_harness_dialog_has_only_name_input(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Omit routing-mode selection while preserving command event registration.
    """
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.harness")
    application = object()
    gateway = object()
    core = sys.modules["adsk.core"]
    core.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    monkeypatch.setitem(vars(commands), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(commands), "suggest_harness_name", Mock(return_value="Harness_002"))
    retain = Mock()
    monkeypatch.setitem(vars(commands), "_runtime", SimpleNamespace(retain_command_handlers=retain))
    inputs = SimpleNamespace(
        addStringValueInput=Mock(return_value=object()),
        addDropDownCommandInput=Mock(),
    )
    event = SimpleNamespace(add=Mock(return_value=True))
    command = SimpleNamespace(commandInputs=inputs, execute=event, validateInputs=event)

    commands._CreateHarnessCreatedHandler().notify(SimpleNamespace(command=command))

    inputs.addStringValueInput.assert_called_once_with(
        commands.HARNESS_NAME_INPUT_ID, "Harness Name", "Harness_002"
    )
    inputs.addDropDownCommandInput.assert_not_called()
    assert event.add.call_count == 2
    retain.assert_called_once()


def test_create_harness_uses_routing_gates_without_a_selector(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Persist the previously selected-by-default mode using only the name input.
    """
    commands = importlib.import_module("cable_bundler.fusion.ui.commands.harness")
    application = object()
    gateway = object()
    core = sys.modules["adsk.core"]
    core.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    core.StringValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    monkeypatch.setitem(vars(commands), "_create_harness_gateway", lambda _app: gateway)
    create = Mock(return_value=SimpleNamespace(name="Harness_002"))
    monkeypatch.setitem(vars(commands), "create_empty_harness", create)
    notice = Mock()
    monkeypatch.setitem(vars(commands), "_send_palette_state", notice)
    name = SimpleNamespace(value=" Harness_002 ")
    inputs = SimpleNamespace(itemById=Mock(return_value=name))
    args = SimpleNamespace(command=SimpleNamespace(commandInputs=inputs))

    commands._HarnessBuilderExecuteHandler().notify(args)

    inputs.itemById.assert_called_once_with(commands.HARNESS_NAME_INPUT_ID)
    create.assert_called_once_with("Harness_002", RoutingMode.ROUTING_GATES, gateway)
    notice.assert_called_once_with(application, "Created Harness_002.")
    validation = SimpleNamespace(inputs=inputs, areInputsValid=False)
    commands._HarnessBuilderValidateInputsHandler().notify(validation)
    assert validation.areInputsValid is True
    name.value = "  "
    commands._HarnessBuilderValidateInputsHandler().notify(validation)
    assert validation.areInputsValid is False
