"""
Keep precision-only diagnostic display separate from hard native fidelity failures.
"""

from __future__ import annotations

from typing import Any

import pytest

from experiments.experiment_ribbon_locked_solver.precision import seam_precision_warning


def _audit() -> dict[str, Any]:
    """
    Supply a complete synthetic audit with one connected native seam precision finding.
    """
    return {
        "body_revision_after": "fixed",
        "native_face_count": 12,
        "native_points_checked": 100,
        "patches_audited": 10,
        "seams_checked": 18,
        "maximum_error_mm": 3e-9,
        "failed_points": [],
        "guide_maximum_position_error_mm": dict.fromkeys(("left", "center", "right"), 1e-9),
        "guide_maximum_tangent_error_degrees": dict.fromkeys(("left", "center", "right"), 1e-8),
        "caps": [
            {
                "side": side,
                "center_error_mm": 1e-10,
                "ordered_width_error_degrees": 1e-9,
                "outward_normal_error_degrees": 1e-9,
            }
            for side in ("start", "end")
        ],
        "seam_failures": [{"faces": [2, 3], "edge_count": 1, "endpoint_error_mm": 4.4e-6}],
    }


def test_warning_preserves_original_strict_findings() -> None:
    """
    Record the live-tolerance warning without erasing or relabelling strict seam failures.
    """
    audit = _audit()
    warning = seam_precision_warning(audit, 1e-5, "fixed")
    assert warning is not None
    assert warning.seam_count == 1 and warning.maximum_error_mm == 4.4e-6
    assert warning.point_tolerance_mm == 1e-5
    assert "strict" in warning.message and "retained" in warning.message
    assert audit == _audit()


@pytest.mark.parametrize("tolerance", [0, True, float("nan"), 1e-6, 4e-6])
def test_seam_warning_requires_the_actual_native_tolerance(tolerance: float) -> None:
    """
    Do not turn a missing, malformed or exceeded point tolerance into display permission.
    """
    assert seam_precision_warning(_audit(), tolerance, "fixed") is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("body_revision_after", "changed"),
        ("failed_points", [{}]),
        ("maximum_error_mm", 1.1e-6),
        ("seams_checked", 0),
        ("native_face_count", None),
        ("guide_maximum_position_error_mm", {"left": 0}),
        ("guide_maximum_tangent_error_degrees", dict.fromkeys(("left", "center", "right"), 0.002)),
        ("caps", [{"side": {}}, {"side": "end"}]),
        ("caps", []),
        ("seam_failures", []),
        ("seam_failures", [{"faces": [2, 3], "edge_count": 0, "endpoint_error_mm": 0}]),
        ("seam_failures", [{"faces": [2, 3], "edge_count": 2, "endpoint_error_mm": 4e-6}]),
        ("seam_failures", [{"faces": [2, 3], "edge_count": True, "endpoint_error_mm": 4e-6}]),
        ("seam_failures", [{"faces": [2, 30], "edge_count": 1, "endpoint_error_mm": 4e-6}]),
        ("seam_failures", [{"faces": [2, 3], "edge_count": 1, "endpoint_error_mm": 1.1e-5}]),
        ("seam_failures", [{"faces": [2, 3], "edge_count": 1, "endpoint_error_mm": 0}]),
        (
            "seam_failures",
            [
                {
                    "kind": "shared_native_face_material_boundary",
                    "faces": [2, 3],
                    "endpoint_error_mm": 4e-6,
                }
            ],
        ),
    ],
)
def test_other_failures_and_incomplete_evidence_remain_hard_stops(field: str, value: Any) -> None:
    """
    Warning classification cannot bypass physical fidelity, topology or incomplete audits.
    """
    audit = _audit()
    audit[field] = value
    assert seam_precision_warning(audit, 1e-5, "fixed") is None


@pytest.mark.parametrize(
    "field", ["center_error_mm", "ordered_width_error_degrees", "outward_normal_error_degrees"]
)
def test_ordered_caps_are_independently_required(field: str) -> None:
    """
    The combined seam/tangent exception occurs before the original final cap gate.
    """
    audit = _audit()
    audit["caps"][1][field] = 0.01
    assert seam_precision_warning(audit, 1e-5, "fixed") is None
