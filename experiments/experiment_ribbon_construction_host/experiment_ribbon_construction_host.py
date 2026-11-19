"""
Host an explicitly prepared frozen viewer in a persistent registered Fusion script.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devtools.ribbon_analysis.construction.host import Viewer  # noqa: E402
from devtools.ribbon_analysis.construction.resources import budget  # noqa: E402

VIEWER: Viewer | None = None
CLOSED: Any = None


def request() -> tuple[Viewer, Path]:
    """
    Verify a repository-local launch receipt and resolve only its explicit retained viewer.

    Preparing the owner and frozen journal remains the caller's responsibility.
    This script never discovers geometry, imports an arbitrary requested module,
    runs a solver or selects a layout implicitly.
    """
    path = ROOT / "artifacts/verification/construction-host-request.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"owner_module", "directory", "sources"}:
        raise ValueError("Malformed construction-host request")
    if not isinstance(value["owner_module"], str) or not value["owner_module"].startswith(
        "ribbon_construction_history_"
    ):
        raise ValueError("Explicit construction viewer module required")
    if not isinstance(value["directory"], str) or not isinstance(value["sources"], dict):
        raise ValueError("Construction host requires a receipt directory and source pins")
    directory = (ROOT / value["directory"]).resolve()
    directory.relative_to(ROOT / "artifacts/verification")
    if not directory.is_dir() or not value["sources"]:
        raise ValueError("Prepared receipt directory and source pins required")
    for name, expected in value["sources"].items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ValueError("Source pins must contain paths and SHA256 strings")
        source = (ROOT / name).resolve()
        relative = source.relative_to(ROOT)
        if relative.parts[0] in ("reference", "F360WireGenerator", "standards"):
            raise ValueError("Construction host cannot inspect protected source trees")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Construction-host source drift: " + name)
    owner = sys.modules.get(value["owner_module"])
    viewer = getattr(owner, "VIEWER", None)
    if not isinstance(viewer, Viewer):
        raise ValueError("Prepared construction viewer is unavailable")
    viewer.guard()
    return viewer, directory


class Closed(adsk.core.UserInterfaceGeneralEventHandler):
    """
    End this registered script when its explicitly owned palette closes.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: Any) -> None:
        """
        Release the palette's callbacks and terminate only this script host.
        """
        del args
        stop(None)
        adsk.terminate()


def run(context: object) -> None:
    """
    Reopen one frozen palette and keep Python event handling alive after returning.
    """
    del context
    global VIEWER, CLOSED
    if VIEWER is not None:
        raise RuntimeError("Construction host is already running")
    viewer, directory = request()
    guard = budget(10)
    with (directory / "persistent-host-started.json").open("x", encoding="utf-8") as stream:
        json.dump({"scope": "one registered persistent frozen-viewer launch"}, stream)
    adsk.autoTerminate(False)
    VIEWER = viewer
    try:
        if viewer.palette is not None and viewer.palette.isValid:
            if not viewer.palette.deleteMe():
                raise RuntimeError("Could not retire the exact previous diagnostic palette")
        Viewer.show(viewer)
        CLOSED = Closed()
        if not viewer.palette.closed.add(CLOSED):
            raise RuntimeError("Could not register construction-host cleanup")
        guard.check("persistent construction palette opened")
        with (directory / "persistent-host-opened.json").open("x", encoding="utf-8") as stream:
            json.dump({"palette": viewer.palette.id, "samples": guard.samples}, stream, indent=2)
    except (OSError, RuntimeError, ValueError, TypeError):
        stop(None)
        adsk.autoTerminate(True)
        raise


def stop(context: object) -> None:
    """
    Retire only this host's palette; leave frozen records and owned graphics intact.
    """
    del context
    global VIEWER, CLOSED
    viewer = VIEWER
    if viewer is not None and viewer.palette is not None and viewer.palette.isValid:
        if not viewer.palette.deleteMe():
            raise RuntimeError("Could not release the owned construction palette")
    if viewer is not None:
        viewer.native_handler = None
    VIEWER, CLOSED = None, None
