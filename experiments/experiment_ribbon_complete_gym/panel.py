"""
Attach explicit complete-case diagnostic controls to an existing owned endpoint gym.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

from devtools.ribbon_analysis.inspection.run_contract import ProcedureRunner, TesterControls

if TYPE_CHECKING:
    from devtools.ribbon_analysis.inspection.fusion_view import DiagnosticViewer

from .controller import Controller
from .lock import ROOT

_owners: list[Panel] = []


class Incoming(adsk.core.HTMLEventHandler):
    """
    Return explicit dispatch failures without relaunching or hiding prior receipts.
    """

    def __init__(self, panel: Panel) -> None:
        """
        Retain the owned callback for the life of the palette.
        """
        super().__init__()
        self.panel = panel

    def notify(self, args: Any) -> None:
        """
        Process a single empty-payload control request and acknowledge its actual outcome.
        """
        try:
            if json.loads(args.data) != {} or not args.action.startswith("complete_ribbon_"):
                raise ValueError("Complete gym controls require a known action and empty payload")
            state = self.panel.dispatch(args.action[len("complete_ribbon_") :])
            self.panel.received_requests += 1
            self.panel.last_error = None
            args.returnData = json.dumps({"ok": True, "state": state}, allow_nan=False)
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
            self.panel.last_error = str(error)
            args.returnData = json.dumps({"ok": False, "error": str(error)})


class Panel:
    """
    Read the current draft on explicit start while preserving any in-flight frozen layout.
    """

    def __init__(self, workspace: Any, directory: Path, document_id: str) -> None:
        """
        Bind a caller-owned existing workspace without redrawing or replacing its geometry.
        """
        self.workspace, self.document_id = workspace, document_id
        self.controller = Controller(ROOT / ".venv/bin/python", directory)
        self.palette: Any = None
        self.received_requests = 0
        self.last_error: str | None = None
        self.handler = Incoming(self)

    def dispatch(self, action: str) -> dict[str, Any]:
        """
        Start only in the owned idle document and refuse overlap with the existing tester.
        """
        app = adsk.core.Application.get()
        if app.activeDocument.creationId != self.document_id:
            raise ValueError("Return to the owned complete-gym document")
        if action == "start":
            diagnostics: DiagnosticViewer | None = getattr(self.workspace, "diagnostics", None)
            runner: ProcedureRunner | None = diagnostics.runner if diagnostics is not None else None
            tester: TesterControls | None = getattr(self.workspace, "range_tester", None)
            if (
                app.userInterface.activeCommand != "SelectCommand"
                or (runner is not None and runner.state()["status"] in ("running", "cancelling"))
                or (tester is not None and tester.active)
            ):
                raise ValueError("Finish or stop the active command, solver and range tester first")
            self.controller.start(self.workspace.gym.scene, app.pointTolerance * 10)
        elif action == "cancel":
            self.controller.cancel()
        elif action != "poll":
            raise ValueError("Unknown complete gym action")
        return self.controller.poll()


def install(workspace: Any, directory: Path, document_id: str) -> Panel:
    """
    Create one retained experimental palette with no solver, native or geometry operation.

    The existing gym and selected solver remain independently owned. The caller
    must provide their workspace explicitly; no arbitrary document is discovered.
    """
    app = adsk.core.Application.get()
    if (
        app.activeDocument.creationId != document_id
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise ValueError("Install complete controls in the owned idle gym document")
    if any(owner.document_id == document_id and owner.palette.isValid for owner in _owners):
        raise ValueError("Complete gym controls are already installed in this document")
    panel = Panel(workspace, directory, document_id)
    panel.palette = app.userInterface.palettes.add(
        "complete_ribbon_" + uuid4().hex,
        "Complete ribbon gym · experimental",
        (Path(__file__).with_name("panel.html")).as_uri(),
        False,
        True,
        True,
        480,
        620,
        True,
    )
    if panel.palette is None or not panel.palette.incomingFromHTML.add(panel.handler):
        raise RuntimeError("Complete gym palette callback could not be attached")
    _owners.append(panel)
    panel.palette.isVisible = True
    return panel
