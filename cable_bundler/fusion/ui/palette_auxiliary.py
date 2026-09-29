"""
Handle palette board previews and development-only edit timing.
"""

from __future__ import annotations

import json
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

from ..interface_contact_naming import preview_board_file_contact_names
from .constants import PALETTE_ID
from .payloads import _read_palette_payload, _read_payload_uuid
from .runtime import runtime as _runtime
from .support import _log_to_fusion


def _send_board_file_preview(application: adsk.core.Application, data: str) -> None:
    """
    Return a local board's read-only name preview to the active palette form.
    """
    payload = _read_palette_payload(data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
    project = payload.get("project", False)
    if not isinstance(project, bool):
        raise ValueError("Project must be a boolean.")
    response: dict[str, object] = {
        "harnessId": str(harness_id),
        "interfaceId": str(interface_id),
    }
    try:
        preview = preview_board_file_contact_names(application, harness_id, interface_id, project)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        response["error"] = str(error)
    else:
        if preview is None:
            response["cancelled"] = True
        else:
            response.update(preview)
    palette = application.userInterface.palettes.itemById(PALETTE_ID)
    if palette is None:
        raise RuntimeError("Fusion could not return the board preview to the palette.")
    palette.sendInfoToHTML("board_file_preview", json.dumps(response))


def _log_slow_palette_edit(action: str, started: float, applied_at: float) -> None:
    """
    Record slow edit persistence separately from subsequent preview and palette work.
    """
    finished = perf_counter()
    if not _runtime.developer_mode_enabled or finished - started < 0.25:
        return
    _log_to_fusion(
        f"Harness Builder slow edit {action}: "
        f"applyMs={(applied_at - started) * 1000:.0f} "
        f"postMs={(finished - applied_at) * 1000:.0f}"
    )
