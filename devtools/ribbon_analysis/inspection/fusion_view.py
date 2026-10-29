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
from .session import Session

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

    def __init__(self, owned_component: Any, document: Any, manifest: Path) -> None:
        """
        Validate an archive before creating components within the supplied owned root.
        """
        self.session = Session(manifest)
        self.document = document
        self.root = owned_component
        self.palette: Any = None
        self._handler: PaletteIncomingHandler | None = None
        self._scene: Any = None
        self._frame: Any = None
        self._triad: Any = None
        self._envelope: Any = None
        self._visibility = {"outlines": True, "envelope": True, "axes": True}
        self._methods: dict[str, Any] = {}
        self._sections: list[Any] = []
        self.received_requests = 0
        self.received_events = 0
        self.last_event_error: str | None = None
        self.last_request: str | None = None
        budget = self._budget()
        for method in self.session.methods:
            budget.check("solver inventory")
            occurrence = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            occurrence.component.name = f"{method['label']} [{method['status']}]"
            occurrence.isLightBulbOn = False
            self._methods[method["id"]] = occurrence
        self._draw()

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
        if self._scene is not None:
            self._scene.deleteMe()
        self._scene, self._frame, self._triad, self._envelope, self._sections = (
            None,
            None,
            None,
            None,
            [],
        )
        for identifier, occurrence in self._methods.items():
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
        self._apply_visibility()

    def _draw_frame(self) -> None:
        """
        Move a right-handed XYZ triad to the selected recorded section.
        """
        self._budget().check("section frame")
        if self._frame is not None:
            self._frame.deleteMe()
            self._frame = None
        if self._triad is not None:
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
        if self.palette is not None and self.palette.isValid:
            self.palette.deleteMe()
        self.palette = None
        self._handler = None
        for occurrence in self._methods.values():
            if occurrence.isValid:
                occurrence.deleteMe()
        self._methods.clear()

    def dispatch(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Apply a validated selection and send matching frozen geometry to the palette.
        """
        if action == "select":
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
                raise ValueError("Diagnostic visibility needs three explicit boolean layers.")
            self._visibility.update(data)
            self._apply_visibility()
        elif action != "ready":
            raise ValueError("Unknown diagnostic action.")
        state = self.session.state()
        state["visibility"] = self._visibility.copy()
        state["visible_sections"] = visible_section_indices(
            len(self._sections), self.session.section
        )
        self.palette.sendInfoToHTML("state", json.dumps(state, allow_nan=False))
        return state
