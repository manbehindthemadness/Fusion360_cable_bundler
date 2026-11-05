"""
Use complete cap halfspaces in selected construction without enlarging contact work or historical defaults.
"""

from __future__ import annotations

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_joint_route.boundary import Boundary


def test_complete_cap_support_certifies_the_same_closed_branch_within_original_work() -> None:
    """
    Resolve the current parallel-heading gym without changing its route or accepting uncertainty.
    """
    scene = Scene(
        Config(2993953655, 10, 0.75, 300, 300),
        Goal.from_degrees(7, 7, 75),
        Goal.from_degrees(10, 2, 50),
    )
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    boundary = Boundary(frames.targets, radius)
    historical = construct(boundary, frames, (0.5,), 1e-5, lambda: None, lambda e: None)
    supported = construct(
        boundary,
        frames,
        (0.5,),
        1e-5,
        lambda: None,
        lambda e: None,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
    )
    assert historical.route is None and historical.contact_pairs == 2048
    assert supported.route is not None and supported.contact is not None
    assert supported.contact.status == "separated" and supported.contact_pairs == 890
    assert supported.contacts == 1 and cap_error(supported.route) < 1e-7
    original = next(branch.route for branch, _ in historical.rejected if branch.roots == (1, 0))
    assert supported.route == original
    with pytest.raises(ValueError, match="cap separation policy"):
        construct(
            boundary,
            frames,
            (0.5,),
            1e-5,
            lambda: None,
            lambda e: None,
            cap_policy="analytic_support",  # type: ignore[arg-type]
        )
