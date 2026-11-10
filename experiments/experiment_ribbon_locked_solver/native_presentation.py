"""
Present an already owned native result by provenance without constructing replay geometry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class NativeDisplay(Protocol):
    """
    Expose only the retained output and visibility operations of the existing native owner.
    """

    displayed: Any
    rejected_job: Path | None

    def has_geometry(self) -> bool:
        """
        Check that the retained output still owns native bodies.
        """
        ...

    def hide(self) -> None:
        """
        Hide this owner's output without rebuilding or deleting it.
        """
        ...


def matches(native: NativeDisplay, manifest: Path) -> bool:
    """
    Match rejected ownership or an audited accepted result's exact native body revision.

    Missing, malformed or incomplete accepted records decline native preference;
    the normal diagnostic scaffold remains available. This does not re-audit a
    body or award acceptance. The caller has already matched layout targets and
    gym provenance before selecting this presentation. External body edits,
    missing geometry and results from another job cannot reuse a stale body.
    """
    if not native.has_geometry():
        return False
    directory = manifest.parent.resolve()
    if native.rejected_job == directory:
        return True
    try:
        result = json.loads((directory / "native-result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(result, dict) or result.get("status") not in (
        "built_and_named_fidelity_checks_pass",
        "built_with_precision_warning",
    ):
        return False
    if any(
        type(result.get(key)) is not int or result[key] != 1
        for key in ("native_attempted", "built", "fidelity_audited")
    ):
        return False
    revision = result.get("revision")
    bodies = native.displayed.component.bRepBodies
    return (
        isinstance(revision, str)
        and bool(revision)
        and bodies.count == 1
        and bodies.item(0).revisionId == revision
    )


def show(native: NativeDisplay, diagnostics: Any, manifest: Path) -> bool:
    """
    Show the matching existing body and suppress automatic scaffold construction.
    """
    available = matches(native, manifest)
    if available:
        native.displayed.isLightBulbOn = True
        diagnostics.isLightBulbOn = False
    return available


def replay(native: NativeDisplay, diagnostics: Any) -> None:
    """
    Restore explicit diagnostic browsing after either accepted or rejected native presentation.
    """
    native.hide()
    diagnostics.isLightBulbOn = True


def finish(native: NativeDisplay, diagnostics: Any, manifest: Path | None) -> None:
    """
    Keep automatic stopped-case visibility consistent with its selected native presentation.
    """
    diagnostics.isLightBulbOn = not (manifest is not None and matches(native, manifest))
