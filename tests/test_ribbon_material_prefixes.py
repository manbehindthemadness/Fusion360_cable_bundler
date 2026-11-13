"""
Preserve rounded material joins while avoiding duplicate full-accuracy prefix calculations.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight


@pytest.mark.parametrize(
    "lengths",
    ((3.0,), (1e16, 1.0, 1.0, 1.0, 4.0), (1.0, 1e-16, 1e-16, 2.0), (0.1, 0.2, 0.3, 0.4)),
)
def test_material_prefixes_preserve_full_accuracy_and_share_work(
    lengths: tuple[float, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Tiny spans retain their accumulated join bits instead of disappearing in an incremental sum.

    Instrument only complete-accuracy sums; avoiding duplicate evaluations is
    computational evidence, not geometric coverage or a solve-time guarantee.
    """
    total = math.fsum(lengths)
    expected_starts = tuple(math.fsum(lengths[:i]) for i in range(len(lengths)))
    expected_boundaries = (
        (0.0,) + tuple(math.fsum(lengths[:i]) / total for i in range(1, len(lengths))) + (1.0,)
    )
    pose = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pieces = tuple(PlacedPiece(pose, Straight(length), str(i)) for i, length in enumerate(lengths))
    targets = Targets(
        name="analytical material prefixes",
        start=pose.origin,
        end=Vector3(total, 0, 0),
        start_tangent=pose.tangent,
        end_tangent=pose.tangent,
        start_width=pose.width,
        end_width=pose.width,
        lines=1,
        diameter_mm=0.75,
    )
    sum_values = Mock(wraps=math.fsum)
    monkeypatch.setattr(math, "fsum", sum_values)
    route = FoldRoute(targets, pieces, 1)
    assert sum_values.call_count == len(lengths) + 1
    assert route.material_length_mm.hex() == total.hex()
    assert tuple(v.hex() for v in route.starts_mm) == tuple(v.hex() for v in expected_starts)
    assert tuple(v.hex() for v in route.boundaries) == tuple(v.hex() for v in expected_boundaries)
    assert route.pieces is pieces
