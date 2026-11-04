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
from ..end_profiles import retain_end_profiles
from ..inspection.archive import write_document
from ..performance import for_layout
from ..prepath import drawing as prepath_drawing
from .graphics import draw
from .placement import adjacent, allowed_pairs, generate_layout
from .scene import Config, Goal, Scene


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
        *,
        performance: Callable[[Scene], dict[str, Any]] | None = None,
    ) -> None:
        """
        Require an owned component and write-once archive directory before display.
        """
        directory.mkdir(parents=True, exist_ok=False)
        self.component, self.directory = component, directory
        self.avoid_adjacent_zones = True
        self.scene = scene or generate_layout()
        self.open_diagnostics = open_diagnostics
        self.performance = performance
        self.revision = 0
        self.received_requests = 0
        self.last_error: str | None = None
        self.palette: Any = None
        self.group: Any = None
        self._profiles: Any = None
        self._pending_profiles: Any = None
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
        if self._pending_profiles is not None:
            raise RuntimeError("Incomplete gym end profiles require review before redrawing.")
        group = draw(
            self.component,
            scene.payload()["drawing"],
            lambda: budget.check("gym drawing"),
            prepath=prepath_drawing(scene.targets),
        )
        self._pending_profiles = self.component.occurrences.addNewComponent(
            adsk.core.Matrix3D.create()
        )
        self._pending_profiles.component.name = "Sweep profiles - current gym targets"
        retain_end_profiles(
            self._pending_profiles.component,
            scene.targets,
            lambda: budget.check("gym end profiles"),
        )
        if self._profiles is not None and self._profiles.isValid:
            self._profiles.deleteMe()
        self._profiles, self._pending_profiles = self._pending_profiles, None
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
            candidate = generate_layout(
                Config(**data), avoid_adjacent_zones=getattr(self, "avoid_adjacent_zones", False)
            )
        elif action == "select":
            if set(data) == {"role", "zone", "face", "roll_degrees"}:
                goal = Goal.from_degrees(data["zone"], data["face"], data["roll_degrees"])
            elif set(data) == {"role", "zone", "face", "roll"}:
                goal = Goal(data["zone"], data["face"], data["roll"])
            else:
                raise ValueError("Supply a goal, zone, face and orientation.")
            candidate = self.scene.choose(data["role"], goal)
            if getattr(self, "avoid_adjacent_zones", False) and adjacent(
                candidate.a.zone, candidate.b.zone
            ):
                raise ValueError(
                    "Choose non-adjacent cubicles or disable Avoid adjacent cubicles. "
                    "Face, edge and corner contact count as adjacency."
                )
        elif action == "placement":
            if (
                set(data) != {"avoid_adjacent_zones"}
                or type(data["avoid_adjacent_zones"]) is not bool
            ):
                raise ValueError("Choose explicitly whether to avoid adjacent cubicles.")
            self.avoid_adjacent_zones = data["avoid_adjacent_zones"]
        elif action == "diagnostics":
            if data or self.open_diagnostics is None:
                raise ValueError("A linked diagnostic viewer is required.")
            self.open_diagnostics(self.scene)
        elif action == "performance":
            if data:
                raise ValueError("Performance refresh requires no layout edits.")
            return {"performance": self.counters()}
        elif action != "ready" or data:
            raise ValueError("Unknown gym action.")
        self.set_scene(candidate)
        state = self.state()
        if self.palette is not None:
            self.palette.sendInfoToHTML("gym_state", json.dumps(state, allow_nan=False))
        return state

    def set_scene(self, scene: Scene) -> None:
        """
        Replace the owned preview with one validated complete scene, preserving selected goals.
        """
        if not isinstance(scene, Scene):
            raise ValueError("Supply a validated gym scene.")
        if scene != self.scene:
            self.revision += 1
            self._record(scene)
            self._draw(scene)
            self.scene = scene

    def rebind_component(self, component: Any) -> None:
        """
        Recreate a deleted preview container from retained inputs without reviving deleted bodies.

        Drop only invalid native handles. Layout revision, archive, palette and
        user controls stay attached to this view; drawing failure propagates.
        """
        if self.component.isValid or not component.isValid:
            raise ValueError("Replace only a deleted gym component with a valid owned component.")
        self.component = component
        self.group = self._profiles = self._pending_profiles = None
        self._draw(self.scene)

    def counters(self) -> dict[str, Any]:
        """
        Refresh recorded counters without redrawing the scene or resetting editable controls.
        """
        return (
            self.performance(self.scene)
            if self.performance is not None
            else for_layout(self.scene.targets, self.scene.payload(), None)
        )

    def state(self) -> dict[str, Any]:
        """
        Expose layout data and the optional handoff capability without editing the scene.
        """
        return dict(
            self.scene.payload(),
            avoid_adjacent_zones=getattr(self, "avoid_adjacent_zones", False),
            eligible_a_zones=[
                a
                for a, _ in allowed_pairs(
                    tuple(range(26)),
                    (self.scene.b.zone,),
                    avoid_adjacent_zones=getattr(self, "avoid_adjacent_zones", False),
                )
            ],
            eligible_b_zones=[
                b
                for _, b in allowed_pairs(
                    (self.scene.a.zone,),
                    tuple(range(26)),
                    avoid_adjacent_zones=getattr(self, "avoid_adjacent_zones", False),
                )
            ],
            diagnostics_available=self.open_diagnostics is not None,
            prepath=prepath_drawing(self.scene.targets),
            performance=self.counters(),
        )

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
