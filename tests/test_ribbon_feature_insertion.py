"""
Verify deterministic guide insertion, coupled interior allocation and fixed-radius material closure.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion.allocation import fit
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.linear_fit import least_squares
from experiments.experiment_ribbon_feature_insertion.repair import nearest, reframed
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from experiments.experiment_ribbon_reduced_joints.kinematics import moved


def _targets(scale: float = 1.0) -> Targets:
    """
    Supply a deterministic spatial frame challenge independently of saved gym outcomes.
    """
    return Targets(
        "analytical feature insertion",
        Vector3(0, 0, 0),
        Vector3(8 * scale, 3 * scale, 2 * scale),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
        1,
        0.2 * scale,
    )


def test_frame_targets_and_extra_station_are_scale_covariant() -> None:
    """
    Preserve both ordered endpoint frames and derive exactly one extra ordered site across scales.
    """
    small, large = Frames.create(_targets()), Frames.create(_targets(20))
    a, b = small.inserted_parameters(), large.inserted_parameters()
    assert a is not None and b == pytest.approx(a) and 0 < a[0] < a[1] < 1 and 0.5 in a
    for parameter in (0.0, *a, 1.0):
        first, second = small.at(parameter), large.at(parameter)
        assert magnitude(difference(first.tangent, second.tangent)) < 1e-10
        assert magnitude(difference(first.width, second.width)) < 1e-10
        assert (
            magnitude(
                difference(
                    second.origin,
                    Vector3(first.origin.x * 20, first.origin.y * 20, first.origin.z * 20),
                )
            )
            < 1e-10
        )
    assert magnitude(difference(small.at(0).width, small.targets.start_width)) < 1e-10
    assert magnitude(difference(small.at(1).width, small.targets.end_width)) < 1e-10


def test_zero_turn_guide_does_not_invent_a_feature() -> None:
    """
    Leave a straight reference without an invented insertion landmark or angle.
    """
    target = replace(
        _targets(), end=Vector3(8, 0, 0), end_tangent=Vector3(1, 0, 0), end_width=Vector3(0, 1, 0)
    )
    assert Frames.create(target).inserted_parameters() is None


def test_spatial_fit_can_find_an_interior_allocation() -> None:
    """
    Satisfy endpoint closure while placing a shared site inside the feasible segment, not at an LP vertex.
    """
    result = least_squares([[1.0, 1.0]], [2.0], [[1.0, 0.0]], [0.5], 2)
    assert result == pytest.approx([0.5, 1.5])
    assert least_squares([[1.0], [1.0]], [1.0, 2.0], [[1.0]], [0.0], 1) is None


def test_fixed_radius_chain_closes_caps_and_preserves_metric() -> None:
    """
    Keep guide-derived steering orientations exact while the whole-chain straight allocation closes position.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    rows: list[dict[str, Any]] = []
    derived = chains(boundary, frames, (0.5,), lambda: None, rows.append)
    choices = [fit(boundary, c, 1e-5, lambda: None, rows.append) for c in derived]
    valid = [a for a in choices if a is not None]
    assert valid and len(derived) <= 8
    for allocation in valid:
        assert cap_error(allocation.route) < 1e-7 and material_error(allocation.route) < 1e-10
        assert all(p.radius_mm == boundary.radius_mm for p in allocation.chain.topology.folds)
        assert allocation.chain.feature_count == 2 and allocation.masks <= 128


def test_one_added_feature_supplies_two_ordered_shared_sites() -> None:
    """
    Exercise the inserted three-stage construction without changing any bend radius.
    """
    frames = Frames.create(_targets())
    parameters = frames.inserted_parameters()
    assert parameters is not None
    boundary = Boundary(frames.targets, 0.101)
    choices = chains(boundary, frames, parameters, lambda: None, lambda event: None)
    fitted = [fit(boundary, c, 1e-5, lambda: None, lambda event: None) for c in choices]
    valid = [a for a in fitted if a is not None]
    assert valid
    for allocation in valid:
        assert allocation.chain.feature_count == 3 and len(allocation.chain.group_ends) == 2
        assert len(allocation.chain.topology.folds) <= 6
        assert cap_error(allocation.route) < 1e-7
        assert all(p.radius_mm == boundary.radius_mm for p in allocation.chain.topology.folds)


@pytest.mark.parametrize("status", ("penetration", "unresolved", "separated"))
def test_contact_is_bounded_and_unresolved_is_not_accepted(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    Keep real closed-chain construction while isolating conservative contact acceptance.
    """
    frames = Frames.create(_targets())
    calls: list[int] = []

    def contact(*args: Any, maximum_pairs: int, checkpoint: Callable[[], None]) -> ContactResult:
        """
        Verify the finite contact-work boundary without native geometry.
        """
        del args
        checkpoint()
        calls.append(maximum_pairs)
        return ContactResult(status, maximum_pairs)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_feature_insertion.solve.inspect_contact", contact
    )
    result = construct(
        Boundary(frames.targets, 0.101), frames, (0.5,), 1e-5, lambda: None, lambda event: None
    )
    assert calls and result.contacts == len(calls) <= 2 and all(n == 1024 for n in calls)
    assert (result.route is not None) == (status == "separated")


def test_hard_resource_stop_propagates() -> None:
    """
    Never turn a source/time stop into a retained successful construction.
    """
    frames = Frames.create(_targets())

    def stop() -> None:
        """
        Simulate a frozen phase stopping before orientation/allocation work.
        """
        raise TimeoutError("feature unit stop")

    with pytest.raises(TimeoutError, match="feature unit stop"):
        construct(Boundary(frames.targets, 0.101), frames, (0.5,), 1e-5, stop, lambda event: None)


def test_nearest_endpoint_reports_a_true_missing_direction() -> None:
    """
    Project exactly onto a single forward ray without pretending its transverse residual is closed.
    """
    target = replace(
        _targets(), end=Vector3(2, 3, 0), end_tangent=Vector3(1, 0, 0), end_width=Vector3(0, 1, 0)
    )
    result = nearest(
        Model(Boundary(target, 0.101), Topology("analytical ray", (), None)), lambda: None
    )
    assert result.values == pytest.approx((10.0,))
    assert result.residual == pytest.approx((0.0, -15.0, 0.0)) and result.error == pytest.approx(
        15.0
    )


def test_shared_heading_correction_preserves_terminal_orientation_and_radius() -> None:
    """
    Permit a guide joint to move angularly while exact algebraic endpoint rotation remains closed.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    chain = chains(boundary, frames, (0.5,), lambda: None, lambda event: None)[0]
    reference = moved(chain.targets[0], (1.0, 0.0, 0.0), 0.03)
    changed = reframed(boundary, chain, (reference,))
    assert changed is not None and changed.feature_count == chain.feature_count
    model = Model(boundary, changed.topology)
    endpoint = model.endpoint((0.0,) * model.size)
    assert magnitude(difference(endpoint.tangent, boundary.targets.end_tangent)) < 1e-7
    assert magnitude(difference(endpoint.width, boundary.targets.end_width)) < 1e-7
    assert all(f.radius_mm == boundary.radius_mm for f in changed.topology.folds)
