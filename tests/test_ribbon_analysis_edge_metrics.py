"""
Verify optional boundary diagnostics preserve missing data and edge identity.
"""

from dataclasses import dataclass

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.edge_metrics import boundary_macaroni
from devtools.ribbon_analysis.regions import regions


@dataclass(frozen=True)
class Field:
    """
    Supply independent scalar controls for regular and folded boundary regions.
    """

    gradient: float
    lines: int = 3
    diameter_mm: float = 1.0
    half_width_mm: float = 1.6

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Return a finite constant-curvature control at each normalized station.
        """
        assert 0 <= u <= 1
        return 0.3, 0.0, self.gradient


@dataclass(frozen=True)
class Path:
    """
    Give samples distinct positions without invoking a routing solver or Fusion.
    """

    field: Field

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return diagnostic points and a finite actual curve derivative.
        """
        assert abs(offset_mm) <= self.field.half_width_mm
        return Vector3(10 * u, offset_mm, 0), Vector3(10, 0, 0)


def test_companion_boundary_can_fail_when_outside_proxy_is_gentle() -> None:
    """
    Preserve which boundary carries the stronger proposed curvature finding.
    """
    a, b = boundary_macaroni(Path(Field(0.4)), intervals=16)
    assert (a.trace, b.trace) == (-1, -2)
    assert not regions(a)
    assert regions(b)[0].severity == "red"
    assert regions(b)[0].first_u == 0 and regions(b)[0].last_u == 1


def test_folded_boundary_curvature_is_missing_not_zero_or_regular() -> None:
    """
    Require separateJinspection when the regular curvature formula is invalid.
    """
    _, b = boundary_macaroni(Path(Field(1.0)), intervals=16)
    assert all(sample.value is None for sample in b.samples)
    assert regions(b) == ()
    assert all(b.severity(i) == "unmeasured" for i in range(17))


def test_invalid_sampling_budget_rejects_before_measurement() -> None:
    """
    Keep optional analysis workloads bounded independently of solver budgets.
    """
    with pytest.raises(ValueError, match="bounded boundary"):
        boundary_macaroni(Path(Field(0)), intervals=2048)


def test_overflowing_jacobian_cannot_look_like_zero_curvature() -> None:
    """
    Reject overflow instead of dividing by infinity and displaying a clean boundary.
    """
    with pytest.raises(ValueError, match="Jacobian overflowed"):
        boundary_macaroni(Path(Field(1.7e308)), intervals=16)
