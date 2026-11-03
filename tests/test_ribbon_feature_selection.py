"""
Verify monotonic branch replacement and preservation of the original contact-work boundary.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_feature_insertion.selection import Branch, select
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_spline_guide.guide import Agreement


def _branch(index: int, length: float, rms: float, direction: float, site: float) -> Branch:
    """
    Supply analytical ranking records; geometry feasibility is deliberately owned by the certificate.
    """
    origin, tangent, width = Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)
    target = Targets(
        "selection unit", origin, Vector3(length, 0, 0), tangent, tangent, width, width, 1, 0.2
    )
    route = FoldRoute(
        target, (PlacedPiece(Pose(origin, tangent, width), Straight(length), "unit"),), 0.101
    )
    return Branch((index,), route, Agreement(rms, rms, direction), site)


@pytest.mark.parametrize("safe", (True, False))
def test_only_certified_dominating_replacement_can_displace_baseline(safe: bool) -> None:
    """
    Keep a certified baseline when a better-scoring alternative cannot separate.
    """
    baseline = _branch(0, 40, 5, 0.3, 1)
    improved = _branch(1, 33, 2, 0.1, 2)
    calls: list[tuple[int, ...]] = []

    def certify(branch: Branch) -> bool:
        """
        Make only the proposed improvement's conservative certificate variable.
        """
        calls.append(branch.roots)
        return branch is baseline or safe

    assert select((improved, baseline), certify) is (improved if safe else baseline)
    assert calls == [baseline.roots, improved.roots]


@pytest.mark.parametrize("dimension", ("length", "position", "direction"))
def test_conflicting_preferences_do_not_spend_a_certificate(dimension: str) -> None:
    """
    Reject every length/guide tradeoff before any alternative contact work.
    """
    baseline = _branch(0, 40, 5, 0.3, 1)
    alternatives = {
        "length": _branch(1, 41, 2, 0.1, 2),
        "position": _branch(1, 33, 6, 0.1, 2),
        "direction": _branch(1, 33, 2, 0.4, 2),
    }
    calls: list[Branch] = []

    def certify(branch: Branch) -> bool:
        """
        Record an unconditional baseline certificate without simulating geometry coverage.
        """
        calls.append(branch)
        return True

    assert select((baseline, alternatives[dimension]), certify) is baseline
    assert calls == [baseline]


@pytest.mark.parametrize("maximum_attempts", (2, 8))
def test_failed_first_branch_preserves_original_second_attempt(maximum_attempts: int) -> None:
    """
    Do not displace the original fallback with an attractive untested third branch.
    """
    first = _branch(0, 40, 5, 0.3, 1)
    second = _branch(1, 42, 6, 0.4, 2)
    third = _branch(2, 20, 1, 0.1, 3)
    calls: list[Branch] = []

    def certify(branch: Branch) -> bool:
        """
        Reject the original primary and accept its original fallback.
        """
        calls.append(branch)
        return branch is second

    assert select((third, second, first), certify, maximum_attempts=maximum_attempts) is second
    assert calls == [first, second]


def test_source_or_resource_failure_is_not_masked_by_safe_baseline() -> None:
    """
    Propagate a hard stop even when a valid baseline has already been certified.
    """
    baseline = _branch(0, 40, 5, 0.3, 1)
    improved = _branch(1, 33, 2, 0.1, 2)

    def certify(branch: Branch) -> bool:
        """
        Simulate a source stop during the optional improvement certificate.
        """
        if branch is not baseline:
            raise TimeoutError("source stop")
        return True

    with pytest.raises(TimeoutError, match="source stop"):
        select((baseline, improved), certify)
    assert select((replace(baseline, site_error_mm2=0),), lambda branch: False) is None
