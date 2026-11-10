"""
Verify owned command lifetimes and partial-profile retention without Fusion or geometry execution.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis import end_profile_command as command
from tests.test_ribbon_end_profiles import _targets


class _Event:
    """
    Retain SDK handlers and deliver one explicitly supplied argument object.
    """

    def __init__(self) -> None:
        """
        Start with no command subscribers.
        """
        self.handlers: list[Any] = []

    def add(self, handler: Any) -> bool:
        """
        Keep the same handler instance alive until event delivery.
        """
        self.handlers.append(handler)
        return True

    def fire(self, args: Any) -> None:
        """
        Deliver native-style events synchronously within the fake event pump.
        """
        for handler in self.handlers:
            handler.notify(args)


class _Host:
    """
    Queue a private command without executing it until the simulated Fusion event pump.
    """

    def __init__(self) -> None:
        """
        Expose one owned idle document and configurable failure boundaries.
        """
        self.document = SimpleNamespace(creationId="owned")
        self.ui = SimpleNamespace(activeCommand="SelectCommand")
        self.app = SimpleNamespace(activeDocument=self.document, userInterface=self.ui)
        self.component = SimpleNamespace(
            isValid=True, parentDesign=SimpleNamespace(parentDocument=self.document)
        )
        self.definitions: list[Any] = []
        self.pending: list[Any] = []
        self.accept_queue = True
        self.after_queue: Any = lambda: None
        self.execute_count = 1
        self.delete_allowed = True
        self.after_destroy_command = "SelectCommand"
        self.execution_args = SimpleNamespace(executeFailed=False)
        self.ui.commandDefinitions = SimpleNamespace(addButtonDefinition=self.add_definition)

    def add_definition(self, identifier: str, name: str, description: str) -> Any:
        """
        Return an owned definition with observable queueing and cleanup.
        """
        del name, description
        definition = SimpleNamespace(
            id=identifier, commandCreated=_Event(), deleted=False, queued=False
        )

        def execute() -> bool:
            """
            Queue exactly once without firing creation or profile work yet.
            """
            if self.accept_queue:
                definition.queued = True
                self.pending.append(definition)
            self.after_queue()
            return self.accept_queue

        def delete() -> bool:
            """
            Retain failed deletion for explicit subsequent collection.
            """
            definition.deleted = self.delete_allowed
            return self.delete_allowed

        definition.execute, definition.deleteMe = execute, Mock(side_effect=delete)
        self.definitions.append(definition)
        return definition

    def pump(self) -> None:
        """
        Run creation, execution and destruction without rolling back retained callback state.
        """
        if not self.pending:
            raise AssertionError("Unexpected event pumping without a queued command")
        definition = self.pending.pop(0)
        native = SimpleNamespace(execute=_Event(), destroy=_Event())
        definition.commandCreated.fire(SimpleNamespace(command=native))
        self.ui.activeCommand = definition.id
        for _ in range(self.execute_count):
            native.execute.fire(self.execution_args)
        native.destroy.fire(SimpleNamespace())
        self.ui.activeCommand = self.after_destroy_command


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> _Host:
    """
    Replace only SDK events and the native retainer boundary; use the real command ownership logic.
    """
    host = _Host()
    core = ModuleType("adsk.core")
    core.Application = SimpleNamespace(get=lambda: host.app)
    core.CommandEventHandler = object
    core.CommandCreatedEventHandler = object
    core.CommandCreatedEventArgs = SimpleNamespace(cast=lambda args: args)
    adsk = ModuleType("adsk")
    adsk.core, adsk.doEvents = core, host.pump
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.core", core)
    monkeypatch.setattr(command, "_pending", [])
    return host


def test_exact_targets_and_original_checkpoint_survive_the_asynchronous_command(
    sdk: _Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Return the original retainer result only after destruction and remove the private definition.
    """
    result = {"start": object(), "end": object()}
    checkpoint = Mock()
    source = _targets()

    def retain(component: Any, targets: Any, guard: Any) -> dict[str, Any]:
        """
        Assert actual command ownership without substituting targets or a fresh budget.
        """
        assert component is sdk.component and targets is source and guard is checkpoint
        assert sdk.ui.activeCommand == sdk.definitions[0].id
        assert not sdk.definitions[0].deleted
        return result

    author = Mock(side_effect=retain)
    monkeypatch.setitem(vars(command), "retain_end_profiles", author)
    sdk.after_queue = lambda: author.assert_not_called()
    assert command.retain_transacted_profiles(sdk.component, source, checkpoint) is result
    assert author.call_count == 1 and checkpoint.call_count >= 3
    assert sdk.ui.activeCommand == "SelectCommand" and sdk.definitions[0].deleted
    assert command.pending_state() == ()


def test_callback_error_retains_its_prefix_and_is_reraised_without_sdk_rollback(
    sdk: _Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve even an unexpected programming error and never silently accept partial retention.
    """
    prefix: list[str] = []
    failure = LookupError("retained native prefix")

    def retain(*args: Any) -> dict[str, Any]:
        """
        Model a completed first cap followed by a failed second native operation.
        """
        del args
        prefix.append("start")
        raise failure

    monkeypatch.setitem(vars(command), "retain_end_profiles", retain)
    with pytest.raises(LookupError) as error:
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    assert error.value is failure and prefix == ["start"]
    assert not sdk.execution_args.executeFailed and sdk.definitions[0].deleted
    assert command.pending_state() == ()


def test_timeout_keeps_pending_ownership_and_suppresses_late_geometry(
    sdk: _Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A wait timeout cannot renew the queue or make its later event author abandoned profiles.
    """
    failure = RuntimeError("original budget exhausted")
    stopped = [False]

    def checkpoint() -> None:
        """
        Keep the same stop latch after queueing rather than starting another clock.
        """
        if stopped[0]:
            raise failure

    sdk.after_queue = lambda: stopped.__setitem__(0, True)
    author = Mock()
    monkeypatch.setitem(vars(command), "retain_end_profiles", author)
    with pytest.raises(RuntimeError) as error:
        command.retain_transacted_profiles(sdk.component, _targets(), checkpoint)
    assert error.value is failure and not sdk.definitions[0].deleted
    assert len(command.pending_state()) == 1
    with pytest.raises(RuntimeError, match="still pending"):
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    assert len(sdk.definitions) == 1
    sdk.pump()
    author.assert_not_called()
    assert command.collect_completed() == (sdk.definitions[0].id,)
    assert command.pending_state() == ()


@pytest.mark.parametrize("execute_count", (0, 2))
def test_missing_or_duplicate_execution_cannot_produce_success(
    sdk: _Host, monkeypatch: pytest.MonkeyPatch, execute_count: int
) -> None:
    """
    Require exactly one completed retainer call, even when the SDK event sequence is malformed.
    """
    sdk.execute_count = execute_count
    author = Mock(return_value={"start": object(), "end": object()})
    monkeypatch.setitem(vars(command), "retain_end_profiles", author)
    with pytest.raises(RuntimeError, match="without completing|ownership changed"):
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    assert author.call_count == min(execute_count, 1)
    assert command.pending_state() == ()


def test_refused_queue_is_retired_without_geometry_or_retry(sdk: _Host) -> None:
    """
    Distinguish the SDK's explicit launch refusal from a merely delayed command.
    """
    sdk.accept_queue = False
    with pytest.raises(RuntimeError, match="did not queue"):
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    assert not sdk.pending and sdk.definitions[0].deleted
    assert command.pending_state() == ()


def test_failed_definition_cleanup_remains_owned_until_explicit_collection(
    sdk: _Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A cleanup failure cannot silently lose its native definition or permit a duplicate launch.
    """
    sdk.delete_allowed = False
    monkeypatch.setitem(vars(command), "retain_end_profiles", Mock(return_value={}))
    with pytest.raises(RuntimeError, match="retire"):
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    state = command.pending_state()
    assert len(state) == 1 and state[0]["destroyed"]
    sdk.delete_allowed = True
    assert command.collect_completed() == (sdk.definitions[0].id,)
    assert command.pending_state() == ()


def test_unrelated_command_is_never_terminated_after_owned_command_destruction(
    sdk: _Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reject changed UI ownership without cancelling the user's new command.
    """
    sdk.after_destroy_command = "UserCommand"
    monkeypatch.setitem(vars(command), "retain_end_profiles", Mock(return_value={}))
    with pytest.raises(RuntimeError, match="return to idle"):
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    assert sdk.ui.activeCommand == "UserCommand" and sdk.definitions[0].deleted
    assert command.pending_state() == ()


def test_cleanup_failure_cannot_mask_the_original_native_callback_error(
    sdk: _Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve the first failure and pending ownership even when retiring its definition also fails.
    """
    failure = LookupError("original native failure")
    sdk.delete_allowed = False
    monkeypatch.setitem(vars(command), "retain_end_profiles", Mock(side_effect=failure))
    with pytest.raises(LookupError) as error:
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    assert error.value is failure
    assert isinstance(error.value.__cause__, RuntimeError)
    assert "retire" in str(error.value.__cause__)
    assert command.pending_state()[0]["error"] == str(failure)
    sdk.delete_allowed = True
    assert command.collect_completed() == (sdk.definitions[0].id,)


@pytest.mark.parametrize("changed", ("document", "command", "component"))
def test_wrong_ownership_never_launches_a_command(sdk: _Host, changed: str) -> None:
    """
    Protect unrelated designs and user commands before any native preparation or registration.
    """
    if changed == "document":
        sdk.app.activeDocument = SimpleNamespace(creationId="unrelated")
    elif changed == "command":
        sdk.ui.activeCommand = "UserCommand"
    else:
        sdk.component.isValid = False
    with pytest.raises(RuntimeError, match="owned idle"):
        command.retain_transacted_profiles(sdk.component, _targets(), lambda: None)
    assert not sdk.definitions and sdk.ui.activeCommand in ("SelectCommand", "UserCommand")
