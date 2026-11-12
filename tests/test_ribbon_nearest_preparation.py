"""
Preserve endpoint-cone decisions while omitting unused radius-growth preparations.
"""

from __future__ import annotations

import math
from typing import Callable, cast

import pytest

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_feature_insertion.repair import nearest
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from tests.test_ribbon_feature_insertion import _targets


class _FullColumns(Model):
    """
    Supply the original full-equation preparation to the otherwise unchanged cone algorithm.
    """

    def straight_equations(
        self,
    ) -> tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float]]:
        """
        Retain exactly the original even-index columns after preparing every old basis.
        """
        columns, right = self.equations()
        return columns[::2], right


@pytest.mark.parametrize("scale", (1e-3, 1e3))
@pytest.mark.parametrize("bank", (-0.4, 0.0, 0.4))
@pytest.mark.parametrize("fold_count", (2, 8))
@pytest.mark.parametrize("policy", ("free", "native", "budget", "native_budget"))
def test_nearest_matches_original_closure_without_radius_basis_work(
    scale: float,
    bank: float,
    fold_count: int,
    policy: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep exact coordinates, actual residuals, tie-breaking and checkpoints across domains.

    Independently authored signed folds include more than six events. Both
    variants use real physical placement and all original support/face solves.
    Only the old variant prepares coordinates that grow an immutable radius.
    """
    boundary = Boundary(_targets(scale), 0.101 * scale)
    topology = Topology(
        "authored nearest preparation",
        tuple(
            CylindricalFold(
                boundary.radius_mm,
                0.8 if index % 2 == 0 else -1.1,
                bank,
                2 * boundary.half_width_mm,
                0.5 * scale,
                0.6 * scale,
            )
            for index in range(fold_count)
        ),
        None,
    )
    placed: list[tuple[float, ...]] = []
    original = cast(Callable[[Model, tuple[float, ...]], tuple[PlacedPiece, ...]], Model._place)

    def place(owner: Model, coordinates: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Observe real pure placements without altering any equation or chosen support.
        """
        placed.append(coordinates)
        return original(owner, coordinates)

    monkeypatch.setattr(Model, "_place", place)
    checkpoints: list[int] = []

    def checkpoint() -> None:
        """
        Observe every original support and native-face debit.
        """
        checkpoints.append(1)

    options = {
        "maximum_straight_mm": 4 * scale if "budget" in policy else None,
        "minimum_straight_mm": 1e-5 * scale if "native" in policy else 0.0,
    }
    legacy = nearest(_FullColumns(boundary, topology), checkpoint, **options)
    old_checkpoints = len(checkpoints)
    assert sum(any(v > 0 for v in coordinates[1::2]) for coordinates in placed) == fold_count
    placed.clear()
    checkpoints.clear()
    current = nearest(Model(boundary, topology), checkpoint, **options)
    assert current == legacy and math.isfinite(current.error)
    assert len(checkpoints) == old_checkpoints
    assert all(all(v == 0 for v in coordinates[1::2]) for coordinates in placed)
