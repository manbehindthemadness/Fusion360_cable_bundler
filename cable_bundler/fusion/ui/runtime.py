"""
Session state retained across Fusion UI event callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

from ...application import HarnessLoadResult

T = TypeVar("T")


@dataclass
class PendingSlot(Generic[T]):
    """
    Hold one command request until its command-created callback consumes it.
    """

    _value: Optional[T] = None

    @property
    def value(self) -> Optional[T]:
        """
        Return the queued request without consuming it.
        """
        return self._value

    def prepare(self, value: T) -> None:
        """
        Queue one request, rejecting overlapping launches for the same command.
        """
        if self._value is not None:
            raise RuntimeError("Another request for this command is already starting.")
        self._value = value

    def consume(self) -> Optional[T]:
        """
        Return and clear the queued request exactly once.
        """
        value = self._value
        self._value = None
        return value

    def clear(self) -> None:
        """
        Discard a queued request after cancellation or launch failure.
        """
        self._value = None


@dataclass
class HandlerRegistry:
    """
    Retain Fusion event handlers for as long as their event sources need them.
    """

    handlers: list[object] = field(default_factory=list)

    def retain(self, *handlers: object) -> None:
        """
        Retain one or more handlers in registration order.
        """
        self.handlers.extend(handlers)

    def release(self, *handlers: object) -> None:
        """
        Release handlers that have reached the end of their command lifetime.
        """
        for handler in handlers:
            if handler in self.handlers:
                self.handlers.remove(handler)

    def clear(self) -> None:
        """
        Release all retained handlers when the add-in stops.
        """
        self.handlers.clear()


class _CommandHandlerCleanup(adsk.core.CommandEventHandler):
    """
    Release ordinary command handlers when Fusion destroys their command.
    """

    def __init__(self, registry: HandlerRegistry, handlers: tuple[object, ...]) -> None:
        """
        Retain the registry and paired handlers through command destruction.
        """
        super().__init__()
        self._registry = registry
        self._handlers = handlers

    def notify(self, _args: adsk.core.CommandEventArgs) -> None:
        """
        Release the paired handlers and this cleanup callback.
        """
        self._registry.release(*self._handlers, self)


@dataclass
class UiRuntime:
    """
    Own mutable add-in state that must outlive individual Fusion callbacks.
    """

    handler_registry: HandlerRegistry = field(default_factory=HandlerRegistry)
    pending_pathway: PendingSlot[UUID] = field(default_factory=PendingSlot)
    pending_junction: PendingSlot[UUID] = field(default_factory=PendingSlot)
    pending_junction_relationship: PendingSlot[tuple[UUID, UUID]] = field(
        default_factory=PendingSlot
    )
    pending_standalone_end: PendingSlot[UUID] = field(default_factory=PendingSlot)
    pending_cable_end_attachment: PendingSlot[tuple[UUID, UUID]] = field(
        default_factory=PendingSlot
    )
    pending_append_gates: PendingSlot[tuple[str, UUID, UUID]] = field(default_factory=PendingSlot)
    pending_refine: PendingSlot[tuple[str, UUID, UUID]] = field(default_factory=PendingSlot)
    pending_segment: PendingSlot[tuple[UUID, UUID]] = field(default_factory=PendingSlot)
    pending_refine_edit: PendingSlot[tuple[UUID, UUID]] = field(default_factory=PendingSlot)
    pending_palette_edit: PendingSlot[tuple[str, str, object]] = field(default_factory=PendingSlot)
    last_command_error: str = ""
    last_diagram_qa_observation: Optional[dict[str, object]] = None
    damaged_harness_results: dict[str, HarnessLoadResult] = field(default_factory=dict)
    history_handler: Optional[object] = None
    deferred_stripe_restore_event: Optional[object] = None
    deferred_stripe_restore_handler: Optional[object] = None
    stripe_restore_pending: bool = False
    active_selection_handler: Optional[object] = None
    document_saving_handler: Optional[object] = None
    document_saved_handler: Optional[object] = None
    graphics_cache_restore_value: Optional[bool] = None
    graphics_cache_save_document: Optional[object] = None

    @property
    def handlers(self) -> list[object]:
        """
        Expose retained handlers for diagnostics and lifecycle regression tests.
        """
        return self.handler_registry.handlers

    def reset_pending_requests(self) -> None:
        """
        Clear all one-shot native-command launch context.
        """
        self.pending_pathway.clear()
        self.pending_junction.clear()
        self.pending_junction_relationship.clear()
        self.pending_standalone_end.clear()
        self.pending_cable_end_attachment.clear()
        self.pending_append_gates.clear()
        self.pending_refine.clear()
        self.pending_segment.clear()
        self.pending_refine_edit.clear()
        self.pending_palette_edit.clear()

    def capture_graphics_cache_preference(self, value: bool) -> None:
        """
        Capture the user's preference once across a protected save sequence.
        """
        if self.graphics_cache_restore_value is None:
            self.graphics_cache_restore_value = value

    def retain_command_handlers(
        self,
        command: adsk.core.Command,
        *handlers: object,
    ) -> None:
        """
        Retain ordinary command handlers until the command is destroyed.

        Raises:
            RuntimeError: If Fusion rejects the cleanup callback.
        """
        cleanup = _CommandHandlerCleanup(self.handler_registry, handlers)
        if not command.destroy.add(cleanup):
            raise RuntimeError("Fusion could not register command-handler cleanup.")
        self.handler_registry.retain(*handlers, cleanup)


runtime = UiRuntime()
