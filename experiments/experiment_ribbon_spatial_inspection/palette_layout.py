"""
Initialize the native browser surface after visibility and acknowledge read-only viewport paint.
"""

from __future__ import annotations

import json
import math
from typing import Any, cast

# noinspection PyUnresolvedReferences
import adsk.core


def show(palette: Any, width: int, height: int) -> None:
    """
    Apply final bounds after the native embedded browser exists, without collapsing the palette.
    """
    palette.isVisible = True
    palette.width = width
    palette.height = height


def refresh(palette: Any) -> None:
    """
    Refresh an existing floating browser surface while retaining its final size and position.

    Cached presentation methods may have already assigned the requested bounds
    while hidden. A one-pixel native size change ensures that the embedded view
    receives a resize after visibility; no collapse, geometry or worker action occurs.
    """
    width, height = palette.width, palette.height
    palette.isVisible = True
    palette.width = width + 1
    palette.height = height + 1
    palette.width = width
    palette.height = height


def _dimension(value: Any) -> float:
    """
    Keep external browser dimensions finite, nonnegative and bounded before retaining diagnostics.
    """
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 32768:
        raise ValueError("Viewport dimensions must be finite values from zero to32768")
    return float(value)


def _layout(value: Any) -> dict[str, Any]:
    """
    Validate only presentation metadata, with no authority over material or probe state.
    """
    if not isinstance(value, dict):
        raise ValueError("Viewport report must be an object")
    fingerprint = value.get("fingerprint")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(char not in "0123456789abcdef" for char in fingerprint)
    ):
        raise ValueError("Viewport report requires its frozen baseline fingerprint")
    painted = value.get("painted_views")
    if not isinstance(painted, int) or isinstance(painted, bool) or not 0 <= painted <= 4:
        raise ValueError("Viewport report requires zero to four painted views")
    canvases = value.get("canvases")
    if not isinstance(canvases, list) or len(canvases) != 4:
        raise ValueError("Viewport report requires four canvas dimensions")
    records: list[dict[str, Any]] = []
    names: set[str] = set()
    for canvas in canvases:
        if not isinstance(canvas, dict) or canvas.get("view") not in (
            "top",
            "front",
            "side",
            "iso",
        ):
            raise ValueError("Viewport report contains an unknown canvas")
        name = canvas["view"]
        if name in names:
            raise ValueError("Viewport report repeats a canvas")
        names.add(name)
        records.append(
            {
                "view": name,
                **{
                    key: _dimension(canvas.get(key))
                    for key in ("width", "height", "pixel_width", "pixel_height")
                },
            }
        )
    return {
        "fingerprint": fingerprint,
        "viewport_width": _dimension(value.get("viewport_width")),
        "viewport_height": _dimension(value.get("viewport_height")),
        "painted_views": painted,
        "canvases": records,
    }


class LayoutIncoming(adsk.core.HTMLEventHandler):
    """
    Observe the browser's first paint while delegating all existing inspection actions unchanged.
    """

    def __init__(self, delegate: Any, palette: Any = None) -> None:
        """
        Retain the original acknowledged bridge and separate presentation-only diagnostics.
        """
        super().__init__()
        self.delegate = delegate
        self.palette = palette
        self.last_layout: dict[str, Any] | None = None
        self.layout_reports = 0
        self.last_layout_error: str | None = None
        self.initial_layout_seen = False
        self.surface_refreshes = 0

    def notify(self, args: Any) -> None:
        """
        Correct one initial child-size mismatch while preserving all original inspection guards.
        """
        native = adsk.core.HTMLEventArgs.cast(args)
        if native is None or native.action != "ribbon_spatial_layout":
            self.delegate.notify(args)
            return
        try:
            report = _layout(json.loads(native.data))
        except (TypeError, ValueError) as error:
            self.last_layout_error = str(error)
            native.returnData = json.dumps({"error": str(error)})
            return
        self.last_layout = report
        self.layout_reports += 1
        self.last_layout_error = None
        if not self.initial_layout_seen:
            self.initial_layout_seen = True
            try:
                palette = cast(Any, self.palette)
                if (
                    palette is not None
                    and palette.isVisible
                    and (
                        report["viewport_width"] < palette.width / 2
                        or report["viewport_height"] < palette.height / 2
                    )
                ):
                    refresh(palette)
                    self.surface_refreshes += 1
            except RuntimeError as error:
                self.last_layout_error = str(error)
                native.returnData = json.dumps({"error": str(error)})
                return
        native.returnData = json.dumps({"ok": True})
