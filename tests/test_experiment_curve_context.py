"""
Check reference-only occurrence resolution without importing Fusion.
"""

from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_cap_transition.curve_context import (
    connected_curve_order,
    occurrence_curve,
)


def test_proxy_preserves_reference_and_calls_once() -> None:
    """
    Return the exact API proxy without reconstructing or transforming a curve.
    """
    curve, occurrence, proxy = Mock(), Mock(), Mock()
    curve.assemblyContext = None
    curve.createForAssemblyContext.return_value = proxy
    assert occurrence_curve(curve, occurrence) is proxy
    curve.createForAssemblyContext.assert_called_once_with(occurrence)
    assert len(curve.method_calls) == 1


def test_missing_proxy_stops_without_retry() -> None:
    """
    Reject a failed resolution rather than falling back to a native reference.
    """
    curve, occurrence = Mock(), Mock()
    curve.assemblyContext = None
    curve.createForAssemblyContext.return_value = None
    with pytest.raises(RuntimeError, match="proxy unavailable"):
        occurrence_curve(curve, occurrence)
    curve.createForAssemblyContext.assert_called_once_with(occurrence)


def test_existing_context_rejected_before_api_call() -> None:
    """
    Do not silently remap a curve that belongs to a different assembly context.
    """
    curve = Mock()
    with pytest.raises(ValueError, match="native section curve"):
        occurrence_curve(curve, Mock())
    curve.createForAssemblyContext.assert_not_called()


def curve_between(start: float, stop: float) -> Mock:
    """
    Provide distinct references whose endpoint keys encode one test chain.
    """
    curve = Mock()
    for point, value in ((curve.startSketchPoint, start), (curve.endSketchPoint, stop)):
        point.worldGeometry.x = value
        point.worldGeometry.y = 0.0
        point.worldGeometry.z = 0.0
    return curve


def test_unordered_curves_form_complete_closed_chain() -> None:
    """
    Reorder references only, including opposed natural curve directions.
    """
    a, b, c, d = curve_between(0, 1), curve_between(2, 1), curve_between(2, 3), curve_between(3, 0)
    assert connected_curve_order((a, c, d, b)) == (a, b, c, d)
    assert all(not curve.method_calls for curve in (a, b, c, d))


@pytest.mark.parametrize("kind", ["empty", "gap", "branch", "loops"])
def test_malformed_contours_are_not_partial_successes(kind: str) -> None:
    """
    Reject incomplete, ambiguous or multiple chains instead of accepting a subset.
    """
    curves = {
        "empty": [],
        "gap": [curve_between(0, 1), curve_between(2, 3)],
        "branch": [curve_between(0, 1), curve_between(1, 2), curve_between(1, 3)],
        "loops": [
            curve_between(0, 1),
            curve_between(1, 0),
            curve_between(2, 3),
            curve_between(3, 2),
        ],
    }
    with pytest.raises(ValueError):
        connected_curve_order(curves[kind])
