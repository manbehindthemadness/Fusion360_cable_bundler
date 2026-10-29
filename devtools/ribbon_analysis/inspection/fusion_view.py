"""
Replay frozen diagnostic geometry and an interactive section frame in Fusion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..budget import NativeBudget
from ..graphics import draw_lines, draw_text, draw_trace, set_color
from .archive import _integer, _text
from .display import visible_section_indices
from .native_guides import retain
from .run_contract import ProcedureRunner
from .session import Session
from .solver_graphics import render as render_solver_graphics

SECTION_COLORS = ((30, 140, 200), (215, 105, 30), (145, 65, 180), (30, 150, 100))


class PaletteIncomingHandler(adsk.core.HTMLEventHandler):
    """
    Keep the event handler alive with its owning diagnostic viewer.
    """

    def __init__(self, viewer: DiagnosticViewer) -> None:
        """
        Retain the explicit viewer rather than a process-global current experiment.
        """
        super().__init__()
        self.viewer = viewer

    def notify(self, args: Any) -> None:
        """
        Return a concrete error; the source archive survives an incomplete new scene.
        """
        html_args = None
        self.viewer.received_events += 1
        try:
            html_args = adsk.core.HTMLEventArgs.cast(args)
            if html_args is None:
                raise TypeError("Fusion did not provide HTML event arguments.")
            if html_args.action == "response":
                return
            prefix = "ribbon_inspection_"
            if not html_args.action.startswith(prefix):
                raise ValueError("Unknown diagnostic palette message.")
            action = html_args.action[len(prefix) :]
            data = json.loads(html_args.data)
            if not isinstance(data, dict):
                raise ValueError("Inspection request must be an object.")
            self.viewer.received_requests += 1
            self.viewer.last_request = action
            state = self.viewer.dispatch(action, data)
            html_args.returnData = json.dumps({"ok": True, "state": state}, allow_nan=False)
            self.viewer.last_event_error = None
        except (AttributeError, RuntimeError, TypeError, ValueError, OSError) as error:
            self.viewer.last_event_error = str(error)
            if html_args is not None:
                html_args.returnData = json.dumps({"ok": False, "error": str(error)})
            self.viewer.palette.sendInfoToHTML("error", str(error))


class DiagnosticViewer:
    """
    Own one replay root; no solver, conductor bodies or unrelated documents are edited.

    Method components retain every disposition in the browser. Only the selected
    method's disposable scene is displayed, with independently selectable sections.
    The palette reads indexed frozen history; replay does not invoke the solver.
    """

    def __init__(
        self,
        owned_component: Any,
        document: Any,
        manifest: Path,
        runner: ProcedureRunner | None = None,
    ) -> None:
        """
        Validate an archive before creating components within the supplied owned root.
        """
        self.session = Session(manifest)
        self.document = document
        self.root = owned_component
        self.runner = runner
        self.palette: Any = None
        self._handler: PaletteIncomingHandler | None = None
        self._scene: Any = None
        self._frame: Any = None
        self._triad: Any = None
        self._envelope: Any = None
        self._visibility = {
            "outlines": True,
            "envelope": True,
            "axes": True,
            "solver": True,
            "constraints": False,
            "baseline": True,
        }
        self._solver_groups: list[Any] = []
        self._constraint_groups: list[Any] = []
        self._solver_sketch: Any = None
        self._baseline_group: Any = None
        self._details_visibility: dict[tuple[str, str], bool] = {}
        self._solver_sketch_key = (str(self.session.manifest), self.session.solver)
        self._follow_comparison = False
        self._methods: dict[str, Any] = {}
        self._sessions: dict[Path, tuple[Session, dict[str, Any]]] = {
            manifest.resolve(): (self.session, self._methods)
        }
        self._sections: list[Any] = []
        self.received_requests = 0
        self.received_events = 0
        self.last_event_error: str | None = None
        self.last_request: str | None = None
        budget = self._budget()
        for method in self.session.methods:
            budget.check("solver inventory")
            self._register_method(method)
        self._draw()

    def _register_method(self, method: dict[str, Any]) -> None:
        """
        Retain one named method disposition in this viewer's owned browser hierarchy.
        """
        occurrence = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occurrence.component.name = f"{method['label']} [{method['status']}]"
        occurrence.isLightBulbOn = False
        self._methods[method["id"]] = occurrence

    @staticmethod
    def _budget() -> NativeBudget:
        """
        Start a bounded display operation under the ongoing investigation RSS cap.
        """
        return NativeBudget(maximum_seconds=30, maximum_rss_kib=4 * 1024 * 1024)

    def _draw(self) -> None:
        """
        Replace only this viewer's selected scene, preserving the archived proposals.
        """
        budget = self._budget()
        budget.check("replay launch")
        if budget.memory() >= int(3.8 * 1024 * 1024):
            raise RuntimeError("Diagnostic replay lacks 3.8GiB launch headroom.")
        if self._solver_sketch is not None and self._solver_sketch.isValid:
            self._details_visibility[self._solver_sketch_key] = self._solver_sketch.isLightBulbOn
            self._solver_sketch.isLightBulbOn = False
        self._solver_sketch = None
        self._solver_groups, self._constraint_groups, self._baseline_group = [], [], None
        if self._scene is not None and self._scene.isValid:
            self._scene.deleteMe()
        self._scene, self._frame, self._triad, self._envelope, self._sections = (
            None,
            None,
            None,
            None,
            [],
        )
        for identifier, occurrence in tuple(self._methods.items()):
            if not occurrence.isValid:
                method = next(item for item in self.session.methods if item["id"] == identifier)
                self._register_method(method)
                occurrence = self._methods[identifier]
            occurrence.isLightBulbOn = identifier == self.session.solver
        snapshot = self.session.snapshot
        if snapshot is None:
            return
        component = self._methods[self.session.solver].component
        self._scene = component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        self._scene.component.name = f"Recorded geometry / proposal {self.session.proposal}"
        retain(self._scene.component, snapshot, lambda: budget.check("original frozen guide"))
        paths = self._scene.component.customGraphicsGroups.add()
        for trace in snapshot.guides:
            if snapshot.lines == 1 and trace.number != 0:
                continue
            budget.check("frozen guide")
            draw_trace(paths, trace, (35, 90, 170) if trace.number == 0 else (150, 110, 65))
        for section in snapshot.sections:
            budget.check("distinct section")
            occurrence = self._scene.component.occurrences.addNewComponent(
                adsk.core.Matrix3D.create()
            )
            occurrence.component.name = (
                f"Section {section.index:02} / u={section.u:.5f} / {section.kind}"
            )
            group = occurrence.component.customGraphicsGroups.add()
            draw_lines(
                group,
                section.outline,
                SECTION_COLORS[section.index % len(SECTION_COLORS)],
                occurrence.component.name,
            )
            self._sections.append(occurrence)
        # A wireframe envelope shows diameter without inventing native solids.
        if all(section.kind == "circle" for section in snapshot.sections):
            self._envelope = self._scene.component.customGraphicsGroups.add()
            for index in range(0, 32, 4):
                draw_lines(
                    self._envelope,
                    tuple(section.outline[index] for section in snapshot.sections),
                    (140, 150, 160),
                    "Sampled circular envelope",
                )
        self._draw_frame()
        budget.check("solver panels")
        self._solver_groups, self._constraint_groups, self._solver_sketch, self._baseline_group = (
            render_solver_graphics(
                self._scene.component,
                component,
                self.session,
                lambda: budget.check("solver detail/witness"),
            )
        )
        self._solver_sketch_key = (str(self.session.manifest), self.session.solver)
        if self._solver_sketch is not None:
            self._solver_sketch.isLightBulbOn = self._details_visibility.get(
                self._solver_sketch_key, self._solver_sketch.isLightBulbOn
            )
        self._apply_visibility()

    def _draw_frame(self) -> None:
        """
        Move a right-handed XYZ triad to the selected recorded section.
        """
        self._budget().check("section frame")
        if self._frame is not None and self._frame.isValid:
            self._frame.deleteMe()
            self._frame = None
        if self._triad is not None and self._triad.isValid:
            self._triad.deleteMe()
            self._triad = None
        snapshot = self.session.snapshot
        if snapshot is None:
            return
        section = snapshot.sections[self.session.section]
        self._frame = self._scene.component.customGraphicsGroups.add()
        self._triad = self._scene.component.customGraphicsGroups.add()
        draw_lines(self._frame, section.outline, (245, 35, 180), "Selected section")
        length = snapshot.diameter_mm * 2.5
        for label, axis, rgb in (
            ("X", section.frame.x, (215, 40, 40)),
            ("Y", section.frame.y, (20, 155, 60)),
            ("+Z", section.frame.z, (35, 80, 230)),
        ):
            tip = section.frame.origin.translated(axis, length)
            draw_lines(self._triad, (section.frame.origin, tip), rgb, f"Local {label}")
            draw_text(self._triad, label, tip, rgb, snapshot.diameter_mm * 0.35)
        self._triad.isVisible = self._visibility["axes"]

    def _apply_visibility(self) -> None:
        """
        Synchronize palette layer controls with this viewer's native graphics only.
        """
        visible = visible_section_indices(len(self._sections), self.session.section)
        for group in self._solver_groups:
            group.isVisible = self._visibility["solver"]
        for group in self._constraint_groups:
            group.isVisible = self._visibility["constraints"]
        if self._baseline_group is not None:
            self._baseline_group.isVisible = self._visibility["baseline"]
        for index, occurrence in enumerate(self._sections):
            occurrence.isLightBulbOn = self._visibility["outlines"] and index in visible
            if index in visible:
                outline = occurrence.component.customGraphicsGroups.item(0).item(0)
                set_color(outline, SECTION_COLORS[visible.index(index) % len(SECTION_COLORS)])
        if self._envelope is not None:
            self._envelope.isVisible = self._visibility["envelope"]
        if self._triad is not None:
            self._triad.isVisible = self._visibility["axes"]

    def show(self) -> None:
        """
        Open the local palette; its section controls drive this retained viewer.
        """
        ui = adsk.core.Application.get().userInterface
        identifier = f"ribbon_diagnostic_{id(self)}"
        self.palette = ui.palettes.add(
            identifier,
            "Routing diagnostics",
            str(Path(__file__).with_name("viewer.html").resolve()),
            False,
            True,
            True,
            620,
            800,
            True,
        )
        if self.palette is None:
            raise RuntimeError("Fusion did not create the diagnostic palette.")
        self._handler = PaletteIncomingHandler(self)
        if not self.palette.incomingFromHTML.add(self._handler):
            self.palette.deleteMe()
            raise RuntimeError("Fusion did not register the diagnostic palette handler.")
        self.palette.dockingOption = (
            adsk.core.PaletteDockingOptions.PaletteDockOptionsToVerticalOnly
        )
        self.palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        self.palette.isVisible = True

    def close(self) -> None:
        """
        Release only this viewer's recreatable scenes and palette; keep its archive.
        """
        if self.runner is not None:
            self.runner.cancel()
        if self.palette is not None and self.palette.isValid:
            self.palette.deleteMe()
        self.palette = None
        self._handler = None
        for _, inventory in self._sessions.values():
            for occurrence in inventory.values():
                if occurrence.isValid:
                    occurrence.deleteMe()
        self._methods.clear()
        self._sessions.clear()

    def _open_example(self, identifier: str) -> None:
        """
        Switch authored inputs while retaining each example's session and run history.
        """
        if self.runner is None:
            raise ValueError("Diagnostic examples are not configured.")
        manifest = self.runner.open_example(identifier).resolve()
        incoming = self._sessions.get(manifest)
        if incoming is None:
            incoming = (Session(manifest), {})
        for occurrence in self._methods.values():
            if occurrence.isValid:
                occurrence.isLightBulbOn = False
        self.session, self._methods = incoming
        self._sessions[manifest] = incoming
        for method in self.session.methods:
            if method["id"] not in self._methods:
                self._register_method(method)
        self._draw()

    def dispatch(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Apply a validated selection and send matching frozen geometry to the palette.
        """
        if action == "example":
            self._open_example(_text(data.get("id")))
        elif action == "compare":
            if self.runner is None or set(data) != {"disabled_rules"}:
                raise ValueError(
                    "Comparison requires explicit disabled rules and a configured worker."
                )
            method = next(
                item for item in self.session.methods if item["id"] == self.session.solver
            )
            if not method["settings"] or not method["procedure"]:
                raise ValueError("Choose a recorded numerical procedure with archived settings.")
            if len(self.session.methods) + 2 > 64:
                raise ValueError("The comparison would exceed 64 recorded entries.")
            self.runner.start(
                {
                    "procedures": [{"id": method["procedure"], "settings": method["settings"]}],
                    "comparison": {
                        "origin": method["id"],
                        "disabled_rules": data["disabled_rules"],
                    },
                },
                self.session.targets,
            )
            self._follow_comparison = True
        elif action in ("run", "poll", "cancel"):
            if self.runner is None:
                raise ValueError("Numerical procedure execution is not configured for this replay.")
            if action == "run":
                choices = data.get("procedures")
                if not isinstance(choices, list) or len(self.session.methods) + len(choices) > 64:
                    raise ValueError("Run selection would exceed this session's 64 method entries.")
                self.runner.start(data, self.session.targets)
            elif action == "cancel":
                self.runner.cancel()
            else:
                manifest = self.runner.poll()
                if manifest is None:
                    return {"execution_update": True, "execution": self.runner.state()}
                added = self.session.import_results(manifest)
                budget = self._budget()
                for method in self.session.methods:
                    if method["id"] in added:
                        budget.check("new numerical result")
                        self._register_method(method)
                if self._follow_comparison:
                    self.session.select(added[-1])
                    self._draw()
                    self._follow_comparison = False
        elif action == "select":
            self.session.select(_text(data.get("solver")), _integer(data.get("proposal", -1)))
            self._draw()
        elif action == "section":
            self.session.select_section(_integer(data.get("index")))
            self._draw_frame()
            self._apply_visibility()
        elif action == "visibility":
            if set(data) != set(self._visibility) or any(
                not isinstance(value, bool) for value in data.values()
            ):
                raise ValueError("Diagnostic visibility needs every explicit boolean layer.")
            self._visibility.update(data)
            self._apply_visibility()
        elif action != "ready":
            raise ValueError("Unknown diagnostic action.")
        state = self.session.state()
        state["visibility"] = self._visibility.copy()
        state["visible_sections"] = visible_section_indices(
            len(self._sections), self.session.section
        )
        state["execution"] = self.runner.state() if self.runner is not None else None
        self.palette.sendInfoToHTML("state", json.dumps(state, allow_nan=False))
        return state
