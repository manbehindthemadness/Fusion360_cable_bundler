"""
Show an endpoint-only gym in one explicitly owned Fusion component and palette.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..budget import NativeBudget
from ..inspection.archive import write_document
from .graphics import draw
from .scene import Config, Goal, Scene, generate


class Incoming(adsk.core.HTMLEventHandler):
    """
    Keep palette changes scoped to a retained endpoint preview.
    """

    def __init__(self, view: GymView) -> None:
        """
        Retain the owner while Fusion holds the callback.
        """
        super().__init__()
        self.view = view

    def notify(self, args: Any) -> None:
        """
        Acknowledge only valid gym requests and report errors without changing inputs.
        """
        event = adsk.core.HTMLEventArgs.cast(args)
        if event is None or event.action == "response":
            return
        try:
            if not event.action.startswith("ribbon_gym_"):
                raise ValueError("Unknown gym message.")
            data = json.loads(event.data)
            if not isinstance(data, dict):
                raise ValueError("Gym request must be an object.")
            state = self.view.dispatch(event.action[len("ribbon_gym_") :], data)
            self.view.received_requests += 1
            self.view.last_error = None
            event.returnData = json.dumps({"ok": True, "state": state}, allow_nan=False)
        except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as error:
            self.view.last_error = str(error)
            event.returnData = json.dumps({"ok": False, "error": str(error)})
            self.view.palette.sendInfoToHTML("gym_error", str(error))


class GymView:
    """
    Retain reproducible layouts; render virtual solids without constructing cable bodies.
    """

    def __init__(
        self,
        component: Any,
        directory: Path,
        scene: Scene | None = None,
        open_diagnostics: Callable[[Scene], None] | None = None,
    ) -> None:
        """
        Require an owned component and write-once archive directory before display.
        """
        directory.mkdir(parents=True, exist_ok=False)
        self.component, self.directory = component, directory
        self.scene = scene or generate()
        self.open_diagnostics = open_diagnostics
        self.revision = 0
        self.received_requests = 0
        self.last_error: str | None = None
        self.palette: Any = None
        self.group: Any = None
        self.handler: Incoming | None = None
        self._record(self.scene)
        self._draw(self.scene)

    def _record(self, scene: Scene) -> None:
        """
        Freeze each requested layout without solver results or post-result filtering.
        """
        write_document(self.directory / f"layout-{self.revision:04}.json", scene.payload())

    def _draw(self, scene: Scene) -> None:
        """
        Build replacement graphics before removing the prior owned scene.
        """
        budget = NativeBudget(maximum_seconds=10, maximum_rss_kib=4 * 1024 * 1024)
        budget.check("gym drawing launch")
        if budget.memory() >= int(3.8 * 1024 * 1024):
            raise RuntimeError("Gym drawing lacks launch headroom.")
        group = draw(
            self.component, scene.payload()["drawing"], lambda: budget.check("gym drawing")
        )
        if self.group is not None and self.group.isValid:
            self.group.deleteMe()
        self.group = group
        adsk.core.Application.get().activeViewport.refresh()

    def dispatch(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and archive input edits; never call a routing solver or add its rules.
        """
        candidate = self.scene
        if action == "generate":
            if set(data) != {"seed", "lines", "diameter_mm", "void_percent", "zone_percent"}:
                raise ValueError("Supply the seed, cable dimensions, and void/zone percentages.")
            candidate = generate(Config(**data))
        elif action == "select":
            if set(data) != {"role", "zone", "face", "roll"}:
                raise ValueError("Supply a goal, zone, face and orientation.")
            candidate = self.scene.choose(
                data["role"], Goal(data["zone"], data["face"], data["roll"])
            )
        elif action == "diagnostics":
            if data or self.open_diagnostics is None:
                raise ValueError("A linked diagnostic viewer is required.")
            self.open_diagnostics(self.scene)
        elif action != "ready":
            raise ValueError("Unknown gym action.")
        if candidate != self.scene:
            self.revision += 1
            self._record(candidate)
            self._draw(candidate)
            self.scene = candidate
        state = self.state()
        if self.palette is not None:
            self.palette.sendInfoToHTML("gym_state", json.dumps(state, allow_nan=False))
        return state

    def state(self) -> dict[str, Any]:
        """
        Expose layout data and the optional handoff capability without editing the scene.
        """
        return dict(self.scene.payload(), diagnostics_available=self.open_diagnostics is not None)

    def show(self) -> None:
        """
        Open an interactive local palette with matching native and canvas geometry.
        """
        template = Path(__file__).with_name("viewer.html").read_text(encoding="utf-8")
        initial = json.dumps(self.state(), allow_nan=False).replace("<", "\\u003c")
        html = self.directory / "viewer.html"
        html.write_text(template.replace("__INITIAL_GYM__", initial), encoding="utf-8")
        ui = adsk.core.Application.get().userInterface
        self.palette = ui.palettes.add(
            f"ribbon_gym_{id(self)}",
            "Endpoint test gym",
            str(html.resolve()),
            False,
            True,
            True,
            680,
            850,
            True,
        )
        if self.palette is None:
            raise RuntimeError("Fusion did not create the gym palette.")
        self.handler = Incoming(self)
        if not self.palette.incomingFromHTML.add(self.handler):
            self.palette.deleteMe()
            raise RuntimeError("Fusion did not register gym controls.")
        self.palette.dockingOption = (
            adsk.core.PaletteDockingOptions.PaletteDockOptionsToVerticalOnly
        )
        self.palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        self.palette.isVisible = True
