"""
Compare actual nearest support results with the placement filter enabled and disabled.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from experiments.experiment_ribbon_feature_insertion import repair
from experiments.experiment_ribbon_feature_insertion.endpoint_ranking import dominated
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
@pytest.mark.parametrize("fraction", (0.4, 1.0))
@pytest.mark.parametrize("native", (False, True))
def test_nearest_values_residual_and_ties_match_original_placement(
    scale: float, fraction: float, native: bool
) -> None:
    """
    Preserve exact measured endpoints for every authored root while omitting only worse placements.
    """
    frames = Frames.create(_targets(scale))
    boundary = Boundary(frames.targets, 0.101 * scale)
    options = chains(boundary, frames, (0.3, 0.7), lambda: None, lambda _: None)
    saved = 0
    for chain in options:
        source = Model(boundary, chain.topology)
        model = Mock(wraps=source)
        model.source, model.topology, model.size = source.source, source.topology, source.size
        arguments = {
            "maximum_straight_mm": frames.guide.distances[-1] * fraction,
            "minimum_straight_mm": 1e-5 * scale if native else 0.0,
        }
        with patch.dict(vars(repair), dominated=lambda *_: False):
            original = repair.nearest(model, lambda: None, **arguments)
        calls = model.endpoint.call_count
        model.endpoint.reset_mock()
        actual = repair.nearest(model, lambda: None, **arguments)
        assert actual == original
        saved += calls - model.endpoint.call_count
    assert saved > 0


def test_ties_rounding_overflow_and_uncertainty_retain_actual_measurement() -> None:
    """
    A strict comparison cannot prune ties, near ties or nonfinite arithmetic envelopes.
    """
    columns = ((1.0, 0.0, 0.0),)
    assert not dominated(columns, (0.0, 0.0, 0.0), (1.0,), 1.0, 1.0)
    assert not dominated(columns, (0.0, 0.0, 0.0), (1.0,), 1 - 1e-8, 1.0)
    assert dominated(columns, (0.0, 0.0, 0.0), (1.0,), 0.5, 1.0)
    assert not dominated(columns, (0.0, 0.0, 0.0), (1e308,), 1.0, 1e308)
