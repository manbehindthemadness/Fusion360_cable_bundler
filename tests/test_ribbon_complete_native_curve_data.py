"""
Exercise native collection capture and reject malformed SDK extraction without repairing its coefficients.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterator

import pytest

from experiments.experiment_ribbon_complete.native_curve_data import capture_nurbs_data


class NativePointVector:
    """
    Model an iterable SDK collection that is neither a Python list nor a tuple.
    """

    def __iter__(self) -> Iterator[SimpleNamespace]:
        """
        Expose original native point coordinates in source order.
        """
        yield SimpleNamespace(x=0, y=1, z=2)
        yield SimpleNamespace(x=3, y=4, z=5)
        yield SimpleNamespace(x=6, y=7, z=8)


def native_curve(
    *, success: bool = True, weights: tuple[float, ...] = (1, -0.5, 1)
) -> SimpleNamespace:
    """
    Supply documented SDK fields using an API-shaped boundary double.
    """

    def get_data() -> tuple[Any, ...]:
        """
        Return native points without converting them to a Python container first.
        """
        return success, NativePointVector(), 2, (0, 0, 0, 1, 1, 1), True, weights, False

    return SimpleNamespace(getData=get_data)


def test_native_vector_retains_controls_and_unqualified_negative_weights() -> None:
    """
    Capture SDK vector collections and preserve coefficients that later proof gates may reject.
    """
    result = capture_nurbs_data(native_curve())
    assert result["controls_cm"] == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    assert result["weights"] == [1, -0.5, 1]
    assert result["degree"] == 2 and result["knots"] == [0, 0, 0, 1, 1, 1]
    assert result["rational"] is True and result["periodic"] is False


@pytest.mark.parametrize("weights", [(1, 1), (1, float("nan"), 1)])
def test_invalid_native_coefficients_are_not_normalized(weights: tuple[float, ...]) -> None:
    """
    Missing or nonfinite native weights cannot become a successful coefficient capture.
    """
    with pytest.raises(ValueError, match="Complete finite"):
        capture_nurbs_data(native_curve(weights=weights))


def test_failed_native_extraction_is_not_accepted() -> None:
    """
    Preserve an API extraction failure rather than serializing plausible remaining fields.
    """
    with pytest.raises(ValueError, match="extraction failed"):
        capture_nurbs_data(native_curve(success=False))


def test_original_uv_vector_preserves_units_without_requiring_world_z() -> None:
    """
    Original coedge coordinates remain native UV values and retain negative weights as unqualified evidence.
    """
    from experiments.experiment_ribbon_complete.native_spline_data import capture_trim_data

    def get_data() -> tuple[Any, ...]:
        """
        Supply SDK-shaped two-dimensional points without a world-space z attribute.
        """
        return (
            True,
            iter((SimpleNamespace(x=2, y=3), SimpleNamespace(x=5, y=7))),
            1,
            (4, 4, 9, 9),
            True,
            (1, -1),
            False,
        )

    curve = SimpleNamespace(objectType="adsk::core::NurbsCurve2D", getData=get_data)
    result = capture_trim_data(curve)
    assert result == {
        "controls_native_uv": [[2, 3], [5, 7]],
        "degree": 1,
        "knots": [4, 4, 9, 9],
        "rational": True,
        "weights": [1, -1],
        "periodic": False,
    }
    assert "controls_cm" not in result


def test_model_space_curve_cannot_be_substituted_for_original_uv_trim() -> None:
    """
    A fitted 3D curve cannot acquire original coedge provenance merely by having valid coefficients.
    """
    from experiments.experiment_ribbon_complete.native_spline_data import capture_trim_data

    curve = native_curve()
    curve.objectType = "adsk::core::NurbsCurve3D"
    with pytest.raises(ValueError, match="original native NurbsCurve2D"):
        capture_trim_data(curve)
