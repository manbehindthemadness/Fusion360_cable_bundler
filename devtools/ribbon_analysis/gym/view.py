"""
Show an endpoint-only gym in one explicitly owned Fusion component and palette.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..budget import NativeBudget
from ..end_profiles import checkpoint_interrupted, retain_end_profiles
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
        self.last_preparation: dict[str, Any] | None = None
        self.handler: Incoming | None = None
        self._record(self.scene)
        self._draw(self.scene)

    def _record(self, scene: Scene) -> None:
        """
        Freeze each requested layout without solver results or post-result filtering.
        """
        write_document(self.directory / f"layout-{self.revision:04}.json", scene.payload())

    def _draw(self, scene: Scene, *, maximum_seconds: int = 10) -> None:
        """
        Apply the chosen setup cap and retain stage measurements on an interrupted preparation.
        """
        if self._pending_profiles is not None:
            raise RuntimeError("Incomplete gym end profiles require review before redrawing.")
        budget = NativeBudget(maximum_seconds=maximum_seconds, maximum_rss_kib=4 * 1024 * 1024)
        budget.check("gym drawing launch")
        if budget.memory() >= int(3.8 * 1024 * 1024):
            raise RuntimeError("Gym drawing lacks launch headroom.")
        try:
            self._replace(scene, budget)
        finally:
            report = {
                "seed": scene.config.seed,
                "maximum_seconds": maximum_seconds,
                "elapsed_seconds": budget.clock() - budget.started,
                "timings": dict(budget.timings),
                "samples": list(budget.samples),
                "stop_reason": budget.stopped,
            }
            self.last_preparation = report
            if budget.stopped is not None:
                path = self.directory / f"preparation-stop-{uuid4().hex}.json"
                report["log"] = str(path)
                try:
                    write_document(path, report)
                except OSError as error:
                    # Preserve the scheduling error even if its optional detailed log cannot be written.
                    report["log_error"] = str(error)

    def _replace(self, scene: Scene, budget: NativeBudget) -> None:
        """
        Measure replacement graphics, cap profiles, old-scene retirement and viewport refresh separately.
        """
        group = budget.measure("graphics", draw)(
            self.component,
            scene.payload()["drawing"],
            lambda: budget.check("gym drawing"),
            prepath=prepath_drawing(scene.targets),
        )
        budget.check("gym profile container")
        self._pending_profiles = budget.measure(
            "profile_container", self.component.occurrences.addNewComponent
        )(adsk.core.Matrix3D.create())
        self._pending_profiles.component.name = "Sweep profiles - current gym targets"
        budget.measure("end_profiles", retain_end_profiles)(
            self._pending_profiles.component,
            scene.targets,
            lambda: budget.check("gym end profiles"),
        )
        if self._profiles is not None and self._profiles.isValid:
            budget.measure("retire_profiles", self._profiles.deleteMe)()
        self._profiles, self._pending_profiles = self._pending_profiles, None
        if self.group is not None and self.group.isValid:
            budget.measure("retire_graphics", self.group.deleteMe)()
        self.group = group
        budget.measure("viewport_refresh", adsk.core.Application.get().activeViewport.refresh)()

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

    def set_scene(self, scene: Scene, *, maximum_seconds: int = 10) -> None:
        """
        Replace the owned preview with one validated complete scene, preserving selected goals.
        """
        if not isinstance(scene, Scene):
            raise ValueError("Supply a validated gym scene.")
        if type(maximum_seconds) is not int or not 10 <= maximum_seconds <= 120:
            raise ValueError("Preview setup limit must be an integer from 10 to 120 seconds.")
        if scene != self.scene:
            self.revision += 1
            self._record(scene)
            self._draw(scene, maximum_seconds=maximum_seconds)
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

    def archive_interrupted_profiles(self) -> None:
        """
        Release a scheduling-interrupted prefix only for a newly requested test run.

        Keep the original component and its native geometry for inspection. Actual
        native-authoring failures and damaged prefixes retain the blocking guard.
        This never redraws, retries a profile or deletes failed work.
        """
        pending = self._pending_profiles
        if pending is not None and pending.isValid and checkpoint_interrupted(pending.component):
            pending.component.name = "Sweep profiles - interrupted preparation (retained)"
            pending.isLightBulbOn = False
            self._pending_profiles = None

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
