"""
Retain diagnostic cap profiles in one owned command transaction using the caller's original budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from .contracts import TargetPose
from .end_profiles import retain_end_profiles


@dataclass
class _Invocation:
    """
    Keep an asynchronous SDK command alive until destruction is authoritatively observed.
    """

    definition: Any
    document_id: str
    operation: Callable[[], dict[str, Any]]
    checkpoint: Callable[[], None]
    handlers: list[Any] = field(default_factory=list)
    executed: bool = False
    destroyed: bool = False
    error: Exception | None = None
    result: dict[str, Any] | None = None


_pending: list[_Invocation] = []


def collect_completed() -> tuple[str, ...]:
    """
    Delete only destroyed private command definitions; leave live ownership and geometry untouched.

    A pending timeout is not cancellation. Its eventual execute callback sees
    the latched error and cannot author geometry. Collection may be called again
    after that command's destroy event; no replacement command starts meanwhile.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    removed = []
    ui = adsk.core.Application.get().userInterface
    for invocation in tuple(_pending):
        identifier = invocation.definition.id
        if not invocation.destroyed or ui.activeCommand == identifier:
            continue
        if not invocation.definition.deleteMe():
            raise RuntimeError("Could not retire the owned profile command definition")
        _pending.remove(invocation)
        removed.append(identifier)
    return tuple(removed)


def pending_state() -> tuple[dict[str, Any], ...]:
    """
    Expose retained command handles without declaring a timeout terminal or changing the design.
    """
    return tuple(
        {
            "id": invocation.definition.id,
            "executed": invocation.executed,
            "destroyed": invocation.destroyed,
            "error": None if invocation.error is None else str(invocation.error),
        }
        for invocation in _pending
    )


def retain_transacted_profiles(
    component: Any,
    source: TargetPose,
    checkpoint: Callable[[], None],
) -> dict[str, Any]:
    """
    Run unchanged profile retention in one private execute transaction, returning only after destruction.

    The supplied checkpoint retains its original clock, RSS ceiling and stop
    latch across command registration, event waiting and both profile operations.
    Require the active idle design to own the component. This creates no toolbar
    control and never terminates another command, retries profiles or reloads a module.

    Event handlers intentionally transport exceptions instead of raising them
    across the SDK boundary: this commits the diagnostic prefix for inspection.
    The identical exception is re-raised at the outer boundary; failed work
    is never accepted. An error before destruction retains a fail-closed lease,
    preventing delayed geometry and another launch until authoritative collection.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    app = adsk.core.Application.get()
    ui = app.userInterface
    collect_completed()
    if _pending:
        raise RuntimeError("A previous profile command is still pending; no profiles launched")
    if (
        app.activeDocument is None
        or not component.isValid
        or component.parentDesign.parentDocument.creationId != app.activeDocument.creationId
        or ui.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Profile preparation requires its owned idle design")
    checkpoint()
    definition = ui.commandDefinitions.addButtonDefinition(
        "RibbonAnalysisProfiles" + uuid4().hex,
        "Prepare diagnostic end profiles",
        "Retain the unchanged joined profiles at the fixed diagnostic targets",
    )
    invocation = _Invocation(
        definition,
        app.activeDocument.creationId,
        lambda: retain_end_profiles(component, source, checkpoint),
        checkpoint,
    )

    class Execute(adsk.core.CommandEventHandler):
        """
        Commit even an unsuccessful diagnostic prefix, then let the outer boundary report its error.
        """

        _owner: _Invocation

        def notify(self, args: Any) -> None:
            """
            Execute once only, preserving stops and the original component/document ownership.
            """
            del args
            state = self._owner
            if state.error is not None:
                return
            try:
                state.checkpoint()
                if (
                    state.executed
                    or app.activeDocument is None
                    or app.activeDocument.creationId != state.document_id
                    or ui.activeCommand != definition.id
                    or not component.isValid
                ):
                    raise RuntimeError("Profile command ownership changed before execution")
                state.executed = True
                state.result = state.operation()
            except Exception as callback_error:
                # Transport every callback failure without the SDK rolling back its retained prefix.
                state.error = callback_error

    class Destroy(adsk.core.CommandEventHandler):
        """
        Observe actual command destruction without deleting its definition inside the event.
        """

        _owner: _Invocation

        def notify(self, args: Any) -> None:
            """
            Release waiting only when Fusion reports the command destroyed.
            """
            del args
            self._owner.destroyed = True

    class Created(adsk.core.CommandCreatedEventHandler):
        """
        Bind the private command's execution and destruction before automatic no-dialog execution.
        """

        _owner: _Invocation

        def notify(self, args: Any) -> None:
            """
            Retain both SDK handlers for the entire asynchronous command lifetime.
            """
            event = adsk.core.CommandCreatedEventArgs.cast(args)
            if event is None or event.command is None:
                self._owner.error = TypeError("Fusion did not provide the private profile command")
                return
            execute, destroy = Execute(), Destroy()
            execute._owner = destroy._owner = self._owner
            self._owner.handlers.extend((execute, destroy))
            execution_bound = event.command.execute.add(execute)
            destruction_bound = event.command.destroy.add(destroy)
            if not execution_bound or not destruction_bound:
                self._owner.error = RuntimeError(
                    "Could not bind the private profile command events"
                )

    created = Created()
    created._owner = invocation
    invocation.handlers.append(created)
    _pending.append(invocation)
    try:
        if not definition.commandCreated.add(created):
            invocation.destroyed = True
            raise RuntimeError("Could not bind private profile command creation")
        if not definition.execute():
            invocation.destroyed = True
            raise RuntimeError("Fusion did not queue the private profile command")
        while not invocation.destroyed:
            if invocation.error is not None:
                raise invocation.error
            checkpoint()
            adsk.doEvents()
        if ui.activeCommand != "SelectCommand":
            raise RuntimeError("Profile command did not return to idle selection")
    except Exception as error:
        # Retain a queued callback lease so a later event cannot author profiles after this stop.
        invocation.error = invocation.error or error
        raise
    finally:
        try:
            collect_completed()
        except RuntimeError as cleanup_error:
            if invocation.error is not None:
                raise invocation.error from cleanup_error
            raise
    if invocation.error is not None:
        raise invocation.error
    if not invocation.executed or invocation.result is None:
        raise RuntimeError("Profile command ended without completing retention")
    return invocation.result
