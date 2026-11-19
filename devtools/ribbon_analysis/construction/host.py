"""
Follow frozen construction steps in an explicitly owned idle Fusion component and palette.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3

from ..graphics import draw_lines, draw_text
from ..palette_layout import LayoutIncoming
from .journal import load
from .resources import budget


def bind(palette: Any, delegate: Any) -> adsk.core.HTMLEventHandler:
    """
    Register a fresh native callback and return it for retention by the palette owner.

    Keep native registration separate from the reusable layout/navigation policy.
    In the live session, a fresh callback forwarded events successfully while
    direct registration of the cached policy handler received no events.
    """

    class NativeIncoming(adsk.core.HTMLEventHandler):
        """
        Forward the native event unchanged to the retained presentation policy.
        """

        def __init__(self) -> None:
            """
            Retain the policy for the full lifetime of the native callback.
            """
            super().__init__()
            self.delegate = delegate

        def notify(self, args: Any) -> None:
            """
            Preserve the original event and its acknowledgement channel.
            """
            self.delegate.notify(args)

    handler = NativeIncoming()
    if not palette.incomingFromHTML.add(handler):
        raise RuntimeError("Fusion could not register construction navigation")
    return handler


class Incoming(adsk.core.HTMLEventHandler):
    """
    Retain and acknowledge only frozen-view navigation; expose all host errors visibly.
    """

    def __init__(self, viewer: Viewer) -> None:
        """
        Bind the explicitly retained viewer and native callback lifetime.
        """
        super().__init__()
        self.viewer = viewer

    def notify(self, args: Any) -> None:
        """
        Return selected frozen geometry or a latched host failure, with no solve or retry action.
        """
        event = adsk.core.HTMLEventArgs.cast(args)
        if event is None or event.action == "response":
            return
        try:
            if event.action == "construction_ready":
                if json.loads(event.data) != {}:
                    raise ValueError("Malformed construction readiness request")
                self.viewer.guard()
                event.returnData = json.dumps({"ok": True, "index": self.viewer.index})
                return
            if event.action != "construction_select":
                raise ValueError("Unknown construction viewer action")
            request = json.loads(event.data)
            if not isinstance(request, dict) or set(request) not in (
                {"index", "feature"},
                {"index", "feature", "auto_zoom"},
            ):
                raise ValueError("Malformed construction selection")
            if "auto_zoom" in request:
                if type(request["auto_zoom"]) is not bool:
                    raise ValueError("Auto-zoom must be a boolean")
                self.viewer.auto_zoom = request["auto_zoom"]
            self.viewer.draw(request["index"], request["feature"])
            event.returnData = json.dumps({"ok": True, "index": self.viewer.index})
        except (ValueError, TypeError, RuntimeError, OSError, ArithmeticError) as error:
            self.viewer.last_error = str(error)
            event.returnData = json.dumps({"error": str(error)})


class Viewer:
    """
    Replace only this viewer's active graphics group, retaining at most one pending failure group.

    The caller provides an empty, explicitly tagged component in the active idle
    document. This class never discovers or deletes other owners or BRep geometry.
    Frozen local samples are displayed locally; world snapshots retain saved poses.
    A host error latches navigation until the operator reviews the retained state.
    """

    def __init__(self, component: Any, document_id: str, journal: Path, page: Path) -> None:
        """
        Validate bounded evidence and empty component ownership before any display mutation.
        """
        self.component, self.document_id = component, document_id
        self.packet = load(journal)
        self.run_id = self.packet["header"]["run_id"]
        attribute = component.attributes.itemByName("ribbonConstruction", "run")
        if attribute is None or attribute.value != self.run_id:
            raise ValueError("Explicit construction-viewer ownership is required")
        if (
            component.bRepBodies.count
            or component.sketches.count
            or component.occurrences.count
            or component.customGraphicsGroups.count
        ):
            raise ValueError("Start construction viewing in an empty explicitly owned component")
        self.page = page.resolve()
        self.pins = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (journal.resolve(), self.page, *Path(__file__).parent.glob("*.py"))
        }
        self.group: Any = None
        self.pending: Any = None
        self.palette: Any = None
        self.handler: Any = None
        self.native_handler: Any = None
        self.index = -1
        self.auto_zoom = True
        self.selected = ""
        self.last_error: str | None = None
        self.last_samples: list[dict[str, object]] = []

    def guard(self) -> None:
        """
        Require original sources, owner, same active idle document and no latched display failure.
        """
        app = adsk.core.Application.get()
        if self.last_error is not None:
            raise RuntimeError("Construction display stopped: " + self.last_error)
        attribute = self.component.attributes.itemByName("ribbonConstruction", "run")
        if (
            app.activeDocument is None
            or app.activeDocument.creationId != self.document_id
            or app.userInterface.activeCommand != "SelectCommand"
            or attribute is None
            or attribute.value != self.run_id
        ):
            raise RuntimeError("Construction viewer ownership or idle document changed")
        if any(
            hashlib.sha256(path.read_bytes()).hexdigest() != expected
            for path, expected in self.pins.items()
        ):
            raise RuntimeError("Construction-viewer source/evidence drift")

    def draw(self, index: int, selected: str = "") -> None:
        """
        Replay one frozen scene in at most ten seconds, retaining only active graphics on success.
        """
        self.guard()
        if (
            type(index) is not int
            or not 0 <= index < len(self.packet["steps"])
            or not isinstance(selected, str)
            or (selected and selected not in self.packet["features"])
        ):
            raise ValueError("Selection is outside the frozen construction trace")
        guard = budget(10)
        stage = self.packet["steps"][index]
        new_group = self.component.customGraphicsGroups.add()
        self.pending = new_group
        for item in stage["scene"]:
            guard.check("construction feature display")
            identifier = item["feature"]
            color = (
                (240, 155, 250)
                if identifier == selected
                else (255, 120, 130)
                if stage["status"] == "rejected"
                else (110, 180, 240)
            )
            for ordinal, path in enumerate(item["paths"]):
                draw_lines(
                    new_group,
                    tuple(Vector3(*p) for p in path),
                    color,
                    f"{identifier}: sampled path {ordinal}",
                )
            frame = item["frame"]
            if frame is not None:
                origin = Vector3(*frame["origin"])
                scale = max(1.0, float(item["details"].get("half_width_mm", 1.0)))
                draw_lines(
                    new_group,
                    (origin, origin.translated(Vector3(*frame["forward"]), scale)),
                    (255, 130, 130),
                    identifier + " +material direction",
                )
                draw_lines(
                    new_group,
                    (origin, origin.translated(Vector3(*frame["across"]), scale)),
                    (130, 235, 170),
                    identifier + " +width direction",
                )
            if item["paths"] and (
                identifier == selected or self.packet["features"][identifier]["kind"] == "target"
            ):
                point = Vector3(*item["paths"][0][0])
                draw_text(
                    new_group,
                    self.packet["features"][identifier]["label"],
                    point,
                    (235, 235, 245),
                    1.0,
                )
                new_group.item(
                    new_group.count - 1
                ).billBoarding = adsk.fusion.CustomGraphicsBillBoard.create(
                    adsk.core.Point3D.create(0, 0, 0)
                )
        guard.check("construction display commit")
        if self.group is not None and not self.group.deleteMe():
            raise RuntimeError("Could not retire prior construction display group")
        self.group, self.pending = new_group, None
        changed = self.index != index
        self.index, self.selected = index, selected
        self.last_samples = list(guard.samples)
        app = adsk.core.Application.get()
        if changed and self.auto_zoom:
            app.activeViewport.fit()
        app.activeViewport.refresh()

    def show(self) -> None:
        """
        Open the self-contained page using the working routing-diagnostics startup sequence.
        """
        self.draw(max(0, self.index), self.selected)
        ui = adsk.core.Application.get().userInterface
        self.palette = ui.palettes.add(
            "ribbon_construction_" + str(id(self)),
            "Ribbon construction history",
            str(self.page.resolve()),
            False,
            True,
            True,
            620,
            800,
            True,
        )
        if self.palette is None:
            raise RuntimeError("Fusion could not create construction palette")
        self.handler = LayoutIncoming(Incoming(self), self.palette, action="construction_layout")
        self.native_handler = bind(self.palette, self.handler)
        self.palette.dockingOption = (
            adsk.core.PaletteDockingOptions.PaletteDockOptionsToVerticalOnly
        )
        self.palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        self.palette.isVisible = True
