"""
Show the frozen spatial packet in a Fusion palette and owned Custom Graphics without building bodies.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.end_profiles import retain_end_profiles
from devtools.ribbon_analysis.graphics import draw_lines
from devtools.ribbon_analysis.inspection.archive import parse_snapshot
from devtools.ribbon_analysis.inspection.native_guides import retain

from .ledger import Ledger, create
from .palette_layout import LayoutIncoming
from .palette_layout import show as show_palette

VIEWS: list[Inspector] = []


class Incoming(adsk.core.HTMLEventHandler):
    """
    Retain one acknowledged, explicitly scoped palette bridge.
    """

    def __init__(self, viewer: Inspector) -> None:
        """
        Keep the explicit inspector alive with its native callback.
        """
        super().__init__()
        self.viewer = viewer

    def notify(self, args: Any) -> None:
        """
        Return an action result or visible error without repeating a mutation.
        """
        native = adsk.core.HTMLEventArgs.cast(args)
        if native is None or native.action == "response":
            return
        try:
            if native.action != "ribbon_spatial":
                raise ValueError("Unknown spatial inspection message")
            request = json.loads(native.data)
            self.viewer.received_requests += 1
            native.returnData = json.dumps(
                self.viewer.dispatch(request["action"], request["data"]), allow_nan=False
            )
        except (KeyError, TypeError, ValueError, RuntimeError, OSError, ArithmeticError) as error:
            self.viewer.last_error = str(error)
            native.returnData = json.dumps({"error": str(error)})


class Inspector:
    """
    Own only an explicit diagnostic component, palette and immutable single-probe ledger.
    """

    def __init__(
        self, component: Any, document_id: str, directory: Path, python_executable: Path
    ) -> None:
        """
        Bind an already-owned display component without inspecting unrelated scene geometry.
        """
        self.component, self.document_id = component, document_id
        self.ledger = Ledger(directory)
        self.palette: Any = None
        self.handler: Any = None
        self.section_group: Any = None
        self.received_requests = 0
        self.last_error: str | None = None
        self.python_executable = python_executable
        self.process: subprocess.Popen[bytes] | None = None
        self.probe_log: Any = None
        self.after_drawn = False
        self.worker_error: str | None = None

    def guard(self) -> None:
        """
        Require the same owned idle document and original4GiB resource ceiling.
        """
        app = adsk.core.Application.get()
        if (
            app.activeDocument is None
            or app.activeDocument.creationId != self.document_id
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Inspect only in the owned idle document")
        NativeBudget(maximum_seconds=2, maximum_rss_kib=4194304).check("spatial inspection")

    def section(self, index: int) -> None:
        """
        Highlight exactly the same frozen material section in Fusion as in all four palette views.
        """
        sections = self.ledger.baseline["sections"]
        if type(index) is not int or not 0 <= index < len(sections):
            raise ValueError("Section is outside the frozen packet")
        if self.section_group is not None:
            self.section_group.deleteMe()
        self.section_group = self.component.customGraphicsGroups.add()
        points = tuple(Vector3(*p) for p in sections[index]["outline"])
        draw_lines(self.section_group, points, (245, 245, 245), "Selected exact material section")

    def dispatch(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Navigate geometry, commit a prediction, or consume the one probe allowance.
        """
        self.guard()
        if action == "section" and set(data) == {"index"}:
            self.section(data["index"])
        elif action == "commit":
            self.ledger.commit(data)
        elif action == "probe" and not data:
            if self.process is not None:
                raise RuntimeError("The single probe is already running")
            create(
                self.ledger.directory / "probe-launch.json",
                {"python": str(self.python_executable), "operation": "single cold numerical probe"},
            )
            self.probe_log = (self.ledger.directory / "probe-worker.log").open("xb")
            environment = dict(os.environ)
            environment.pop("PYTHONHOME", None)
            environment.pop("PYTHONPATH", None)
            self.process = subprocess.Popen(
                [
                    str(self.python_executable),
                    "-m",
                    "experiments.experiment_ribbon_spatial_inspection.worker",
                    "probe",
                    str(self.ledger.directory),
                ],
                cwd=Path(__file__).resolve().parents[2],
                stdout=self.probe_log,
                stderr=subprocess.STDOUT,
                env=environment,
            )
        elif action != "ready" or data:
            raise ValueError("Unknown inspection action or payload")
        state = self.ledger.state()
        running = self.process is not None and self.process.poll() is None
        if self.process is not None and not running:
            self.probe_log.close()
            state["worker_exit_code"] = self.process.returncode
            if self.process.returncode != 0:
                self.worker_error = "Probe process stopped without a completed result. The attempt remains recorded; no automatic retry."
            self.process = None
        if (
            state.get("probe_result") is not None
            and state["probe_result"].get("after") is not None
            and not self.after_drawn
        ):
            self.draw(state["probe_result"]["after"], after=True)
            self.after_drawn = True
        state["execution"] = {
            "active": running,
            "launch_consumed": (self.ledger.directory / "probe-launch.json").exists(),
            "error": self.worker_error,
        }
        return state

    def draw(self, packet: dict[str, Any], *, after: bool = False) -> None:
        """
        Draw shared millimeter coordinates as labelled curves and joined-profile outlines.
        """
        budget = NativeBudget(maximum_seconds=30, maximum_rss_kib=4194304)
        group = self.component.customGraphicsGroups.add()
        group.name = "Probe diagnostic overlay" if after else "Frozen spatial inspection"
        for i, trace in enumerate(packet["traces"]):
            budget.check("inspection guide")
            color = (
                (250, 160, 90)
                if after
                else ((244, 202, 112), (80, 219, 220), (177, 148, 235))[i]
                if i < 3
                else (88, 169, 141)
            )
            draw_lines(group, tuple(Vector3(*p) for p in trace["points"]), color, trace["name"])
        if not after:
            count = len(packet["sections"])
            for index in range(0, count, max(1, count // 30)):
                budget.check("material section")
                draw_lines(
                    group,
                    tuple(Vector3(*p) for p in packet["sections"][index]["outline"]),
                    (55, 105, 120),
                    f"Material section {index}",
                )
            for box in packet["hardware"]:
                corners = box["corners"]
                for i in range(8):
                    for bit in (1, 2, 4):
                        if not i & bit:
                            draw_lines(
                                group,
                                (Vector3(*corners[i]), Vector3(*corners[i | bit])),
                                (110, 140, 160),
                                "Fixed " + box["terminal"] + " hardware proxy",
                            )
            for witness in packet["witnesses"]:
                point = Vector3(*witness["point"])
                for member in witness["members"]:
                    end = point.translated(
                        Vector3(*member["normal"]), packet["targets"]["diameter_mm"] * 3
                    )
                    draw_lines(
                        group, (point, end), (255, 70, 60), witness["kind"] + " material normal"
                    )

    def show(self) -> None:
        """
        Retain original cap profiles/guides and expose the independent inspection palette.
        """
        self.guard()
        budget = NativeBudget(maximum_seconds=30, maximum_rss_kib=4194304)
        target_payload = self.ledger.baseline["targets"]
        targets = Targets(
            **{
                key: Vector3(**value) if isinstance(value, dict) else value
                for key, value in target_payload.items()
            }
        )
        retain_end_profiles(self.component, targets, lambda: budget.check("fixed cap profiles"))
        retain(
            self.component,
            parse_snapshot(self.ledger.baseline["original_guides_snapshot"]),
            lambda: budget.check("original material guides"),
        )
        self.draw(self.ledger.baseline)
        self.section(0)
        ui = adsk.core.Application.get().userInterface
        self.palette = ui.palettes.add(
            "ribbon_spatial_" + str(id(self)),
            "Ribbon spatial inspection",
            str(Path(__file__).with_name("viewer.html").resolve()),
            False,
            True,
            True,
            1100,
            900,
            True,
        )
        if self.palette is None:
            raise RuntimeError("Fusion could not create the inspection palette")
        self.handler = LayoutIncoming(Incoming(self), self.palette)
        if not self.palette.incomingFromHTML.add(self.handler):
            raise RuntimeError("Fusion could not register the inspection bridge")
        self.palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateFloating
        self.palette.setPosition(60, 100)
        show_palette(self.palette, 1000, 850)
        VIEWS.append(self)
