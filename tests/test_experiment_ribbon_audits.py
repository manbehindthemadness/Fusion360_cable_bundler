"""
Check planned-section location independently of Fusion's loft output.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame
from experiments.experiment_secure_discrete_ribbon.shape import RibbonShape
from tests.fusion_ui_support import _PaletteLifecycleModule


def _folded_shape() -> RibbonShape:
    """
    Move the median lane off the route axis without changing ordered frames.
    """
    frames = tuple(
        RibbonFrame(Vector3(x, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
        for x in (0, 10, 20)
    )
    lanes = tuple(
        tuple(Vector3(frame.origin.x, y, height) for frame, height in zip(frames, (0, 2, 0)))
        for y in (-1, 0, 1)
    )
    return RibbonShape(frames, lanes, (20.4, 20.4, 20.4), 0.0, True, 1.0)


@pytest.mark.parametrize(
    "x, height", ((0.0, 0.0), (5.0, 1.0), (10.0, 2.0), (15.0, 1.0), (20.0, 0.0))
)
def test_section_locator_follows_solved_lane_not_unfolded_route(
    addin_module: _PaletteLifecycleModule,
    x: float,
    height: float,
) -> None:
    """
    Planned folds must not be misclassified as a missing local section.
    """
    del addin_module
    from experiments.experiment_secure_discrete_ribbon.audits import _planned_lane_reference

    assert _planned_lane_reference(_folded_shape(), Vector3(x, 0, 0)) == Vector3(x, 0, height)


def test_section_failure_does_not_skip_connection_audit(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Preserve connection coverage even when the preceding contour check fails.
    """
    del addin_module
    from experiments.experiment_secure_discrete_ribbon.audits import AuditFailure, collect_audits

    calls: list[str] = []

    def sections() -> dict[str, object]:
        """
        Represent an independent output-audit rejection.
        """
        calls.append("sections")
        raise AuditFailure("missing contour")

    def connection() -> dict[str, object]:
        """
        Retain evidence from the subsequent connection check.
        """
        calls.append("connection")
        return {"connection_rim_landmarks": 8}

    results, failures = collect_audits({"sections": sections, "connection": connection})
    assert calls == ["sections", "connection"]
    assert results == {"connection": {"connection_rim_landmarks": 8}}
    assert failures == [{"audit": "sections", "error": "missing contour"}]
