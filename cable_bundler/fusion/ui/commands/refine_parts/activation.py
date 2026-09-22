"""
Shared command activation for add and edit refine previews.
"""

from __future__ import annotations

from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.core

from ...support import _report_failure
from .types import SelectionInput


class RefineActivateHandler(adsk.core.CommandEventHandler):
    """
    Request the initial preview after a refine command becomes interactive.
    """

    def __init__(self, selection_input: Optional[SelectionInput] = None) -> None:
        """
        Optionally require placement selection after the initial preview exists.
        """
        super().__init__()
        self._selection_input = selection_input

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Draw command graphics, then let Fusion disable OK until placement.
        """
        try:
            if not args.command.doExecutePreview():
                raise RuntimeError("Fusion could not start the refine preview.")
            if self._selection_input is not None:
                if not self._selection_input.setSelectionLimits(1, 1):
                    raise RuntimeError("Fusion could not require refine-path selection.")
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("start refine preview")
