"""
Bind range testing to the selected workspace's owned preview, controller and native output.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

# noinspection PyUnresolvedReferences
import adsk.core

from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.gym.handoff import freeze
from devtools.ribbon_analysis.gym.scene import Scene

from .. import lock
from ..controller import Controller
from ..native import NativeOwner
from .engine import Tester
from .ranges import FIELDS
from .sequence import defaults

if TYPE_CHECKING:
    from ..gym import SelectedWorkspace


class Runtime:
    """
    Use the ordinary runner without accumulating successful replay sessions or native bodies.
    """

    def __init__(self, workspace: SelectedWorkspace) -> None:
        """
        Attach only to an explicitly owned selected-solver workspace with an idle controller.
        """
        self.workspace = workspace
        runner = workspace.diagnostics.runner
        if not isinstance(runner, Controller):
            raise ValueError("Range testing needs the selected solver controller.")
        self.runner = runner
        self.document_id = workspace.native.document_id
        self.native: NativeOwner | None = None
        self.engine = Tester(
            workspace.directory / "range-tests",
            runner,
            lock.verify,
            self._guard,
            self._prepare,
            self._cleanup,
            self._present,
            self._setup,
        )

    @property
    def active(self) -> bool:
        """
        Keep manual controls locked until the current operation has been safely collected.
        """
        return self.engine.active

    def _guard(self) -> None:
        """
        Refuse changed documents, user commands, preview edits or insufficient launch headroom.
        """
        app = adsk.core.Application.get()
        if (
            app.activeDocument is None
            or app.activeDocument.creationId != self.document_id
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Range tester requires its owned idle Fusion design.")
        if (
            self.active
            and self.engine.phase == "running"
            and self.engine.scene != self.workspace.gym.scene
        ):
            raise RuntimeError("Gym inputs changed during the active test case.")
        budget = NativeBudget(maximum_seconds=10, maximum_rss_kib=4194304)
        budget.check("range tester boundary")
        if budget.memory() >= 3984588:
            raise RuntimeError("Range tester reached its 3.8GiB launch-headroom limit.")

    def _setup(self) -> None:
        """
        Preserve prior user output and give automatic cleanup a fresh, exclusively owned body handle.
        """
        workspace = self.workspace
        previous = workspace.native
        previous.hide()
        native = NativeOwner(
            self.document_id, previous.display_x_cm, flat_surfaces=previous.flat_surfaces
        )
        self.native = native
        native.on_progress = workspace.diagnostics.report_progress
        workspace.native = native
        self.runner.build = native.build
        workspace.diagnostics.enable_geometry_clear(native.clear, native.has_geometry)

    def _cleanup(self) -> None:
        """
        Delete only the previous successful body produced by this tester instance.
        """
        if self.native is not None:
            self.native.clear()

    def _prepare(self, scene: Scene) -> None:
        """
        Show one current endpoint preview while keeping the diagnostics controls available.
        """
        workspace = self.workspace
        workspace.gym.set_scene(scene)
        workspace.gym_occurrence.isLightBulbOn = True
        workspace.diagnostic_occurrence.isLightBulbOn = False
        workspace.gym.palette.isVisible = False

    def _present(self, scene: Scene, result: Path | None) -> None:
        """
        Select the stopped case and its latest recorded route without resetting its build log.
        """
        self._guard()
        workspace = self.workspace
        workspace.gym.set_scene(scene)
        assert self.engine.journal is not None
        layout = freeze(scene, self.engine.journal.directory / "inspection")
        workspace.diagnostics.open_results(
            layout, f"Range test · case {self.engine.attempted} · seed {scene.config.seed}", result
        )
        workspace.gym_occurrence.isLightBulbOn = False
        workspace.diagnostic_occurrence.isLightBulbOn = True
        workspace.diagnostics.palette.isVisible = True
        adsk.core.Application.get().activeViewport.fit()

    def dispatch(self, action: str, data: dict[str, Any]) -> None:
        """
        Accept only explicit start/poll/stop/inspect actions from the diagnostic panel.
        """
        if action == "start":
            if set(data) != {"specification", "selection"}:
                raise ValueError("Supply tester specification and one solver selection.")
            self.engine.start(data["specification"], data["selection"])
        elif data:
            raise ValueError("Tester poll, stop and inspect actions do not accept input edits.")
        elif action == "poll":
            self.engine.poll()
        elif action == "stop":
            self.engine.stop()
        elif action == "inspect":
            self.engine.inspect()
        else:
            raise ValueError("Unknown range tester action.")

    def state(self) -> dict[str, Any]:
        """
        Expose available ranges and current progress without regenerating a drawing.
        """
        return {
            **self.engine.state(),
            "available": True,
            "defaults": defaults(self.workspace.gym.scene),
            "fields": [asdict(field) for field in FIELDS],
        }
