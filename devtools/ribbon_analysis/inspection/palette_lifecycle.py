"""
Release active test resources when Fusion's palette close button is used.
"""

from __future__ import annotations

from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core


def closed_handler(viewer: Any) -> Any:
    """
    Create a retained SDK handler that stops only this viewer's active tester.

    Keep scene geometry and journals intact. Host cleanup failures remain visible
    in the viewer's event-error state even when its palette has already closed.
    """

    class Closed(adsk.core.UserInterfaceGeneralEventHandler):
        """
        Bind one palette close event to its explicit diagnostic owner.
        """

        def __init__(self) -> None:
            """
            Retain the viewer until its native close handler is released.
            """
            super().__init__()
            self.viewer = viewer

        def notify(self, args: Any) -> None:
            """
            Request cancellation and release the test's wake lease without another UI poll.
            """
            del args
            if self.viewer.tester is not None and self.viewer.tester.active:
                try:
                    self.viewer.tester.dispatch("stop", {})
                except (OSError, RuntimeError, ValueError) as error:
                    self.viewer.last_event_error = str(error)

    return Closed()
