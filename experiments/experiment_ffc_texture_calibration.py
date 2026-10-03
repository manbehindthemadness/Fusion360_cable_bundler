"""
Adjust the procedural FFC stripe mapping in the open unsaved scratch.

This experiment only edits the scratch appearance. The source design, sweep
geometry, and copied Interface contacts are not changed. Run through the
local Fusion MCP script runner with no command active.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

APPEARANCE_NAME = "FFC procedural 19-trace stripe test"
SCALE_PROPERTY = "texture_RealWorldScaleX"
OFFSET_PROPERTY = "texture_RealWorldOffsetX"


def calibrate(_context: object, scale_cm: float, offset_cm: float) -> None:
    """
    Set cross-ribbon texture pitch and phase in Fusion's real-world units.

    Both values are centimeter-valued material properties. Existing values
    are retained in an ignored report so each experimental step is traceable.
    """
    if not 0.1 <= scale_cm <= 10.0 or not -10.0 <= offset_cm <= 10.0:
        raise ValueError("Texture scale or offset is outside the experiment bounds.")
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before calibrating.")
    scratch = application.activeDocument
    if scratch is None or scratch.name != "Untitled" or scratch.isSaved:
        raise RuntimeError("Activate the unsaved textured FFC sweep scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    appearance = None if design is None else design.appearances.itemByName(APPEARANCE_NAME)
    if appearance is None:
        raise RuntimeError("The procedural stripe appearance is missing.")
    slot = appearance.appearanceProperties.itemById("opaque_albedo")
    texture = None if slot is None else slot.connectedTexture
    if texture is None:
        raise RuntimeError("The stripe appearance has no connected texture.")
    scale = texture.properties.itemById(SCALE_PROPERTY)
    offset = texture.properties.itemById(OFFSET_PROPERTY)
    if scale is None or offset is None:
        raise RuntimeError("The stripe texture lacks real-world mapping controls.")
    previous = {"scale_cm": scale.value, "offset_cm": offset.value}
    scale.value = scale_cm
    offset.value = offset_cm
    if abs(scale.value - scale_cm) > 1e-9 or abs(offset.value - offset_cm) > 1e-9:
        raise RuntimeError("Fusion did not retain the requested texture mapping.")
    application.activeViewport.refresh()
    output = (
        Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_texture_calibration.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(output.read_text(encoding="utf-8")) if output.exists() else []
    history.append(
        {
            "document": scratch.name,
            "previous": previous,
            "calibrated": {"scale_cm": scale.value, "offset_cm": offset.value},
            "scratch_open": scratch.isValid,
        }
    )
    output.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    print("FFC_TEXTURE_CALIBRATION=" + json.dumps(history[-1], sort_keys=True))


if __name__ == "__main__":
    calibrate(None, 4.035, -0.10)
