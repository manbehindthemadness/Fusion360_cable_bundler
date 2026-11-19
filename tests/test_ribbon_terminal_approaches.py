"""
Verify outward terminal construction frames and occupied-material corridor guidance.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from devtools.ribbon_analysis.prepath import controls
from experiments.experiment_ribbon_constrained_construction.terminal_approaches import (
    bridge,
    chains,
    corridors,
)
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_reduced_joints.kinematics import rotate
from experiments.experiment_ribbon_spatial_inspection.geometry import physical
from tests.test_ribbon_aesthetic import _route


def checkpoint() -> None:
    """
    Supply an analytical-only checkpoint with no host or geometry side effects.
    """


def boundary(scale: float = 1.0) -> Boundary:
    """
    Author spatial terminal frames from a known asymmetric analytical fold chain.
    """
    source = _route(
        (
            Straight(3 * scale),
            fold(scale, 1.2 * scale, 0.8, 0.2, 0),
            Straight(8 * scale),
            fold(scale, 1.2 * scale, -1.1, -0.3, 0),
            Straight(4 * scale),
        )
    )
    return Boundary(replace(source.targets, lines=3, diameter_mm=scale), scale)


@pytest.mark.parametrize("scale", (0.1, 1.0, 10.0))
def test_outward_references_preserve_ordered_terminal_rotation(scale: float) -> None:
    """
    Derived factors match both terminal orientations without exchanging conductor sides.
    """
    source = boundary(scale)
    frame = bridge(source)
    _, a, b, _ = controls(source.targets)
    assert dot(frame.tangent, unit(difference(b, a))) > 1 - 1e-12
    assert abs(dot(frame.tangent, frame.width)) < 1e-12
    derived = chains(source, checkpoint)
    assert 1 <= len(derived) <= 8
    for chain in derived:
        model = Model(source, chain.topology)
        end = model.endpoint((0.0,) * model.size)
        assert magnitude(difference(end.tangent, source.targets.end_tangent)) < 1e-10
        assert magnitude(difference(end.width, source.targets.end_width)) < 1e-10
        assert model.pieces((0.0,) * model.size)[0].pose.origin == source.targets.start
        assert len(chain.topology.folds) <= 6 and chain.feature_count == 2


def test_frame_and_corridors_are_covariant_under_common_rigid_motion() -> None:
    """
    World position and rotation cannot select a different terminal bend construction.
    """
    source = boundary()
    axis = unit(Vector3(1, -2, 3))
    shift = Vector3(11, 5, -7)
    target = source.targets

    def direction(vector: Vector3) -> Vector3:
        """
        Apply one common proper rotation to an ordered frame vector.
        """
        return rotate(vector, axis, 0.7)

    moved = Boundary(
        replace(
            target,
            start=shift.translated(direction(target.start), 1),
            end=shift.translated(direction(target.end), 1),
            start_tangent=direction(target.start_tangent),
            end_tangent=direction(target.end_tangent),
            start_width=direction(target.start_width),
            end_width=direction(target.end_width),
        ),
        source.radius_mm,
    )
    original, changed = chains(source, checkpoint), chains(moved, checkpoint)
    assert len(original) == len(changed)
    for first, second in zip(original, changed):
        for a, b in zip(first.topology.folds, second.topology.folds):
            assert (a.angle_radians, a.bank_radians) == pytest.approx(
                (b.angle_radians, b.bank_radians), abs=1e-10
            )
        rows_a = corridors(Model(source, first.topology), first, checkpoint)
        rows_b = corridors(Model(moved, second.topology), second, checkpoint)
        for a, b in zip(rows_a, rows_b):
            assert a.coefficients == pytest.approx(b.coefficients, abs=1e-8)
            assert a.right == pytest.approx(b.right, abs=1e-8)


def test_corridors_bound_full_material_on_correct_side_of_both_terminals() -> None:
    """
    Independent thick-material samples cannot lie behind the affine lower bound.

    B uses its outward normal opposite material arrival, while all folds retain
    A-to-B order. Arithmetic tolerances here test transported support consistency,
    not a relaxation of physical dimensional acceptance.
    """
    source = boundary()
    for chain in chains(source, checkpoint):
        model = Model(source, chain.topology)
        values = tuple(float(i + 1) if i % 2 == 0 else 0.0 for i in range(model.size))
        rows = corridors(model, chain, checkpoint)
        pieces = [p for p in model.pieces(values) if isinstance(p.geometry, CylindricalFold)]
        for index, (row, piece) in enumerate(zip(rows, pieces)):
            entry = index < chain.group_ends[0]
            origin = source.targets.start if entry else source.targets.end
            tangent = source.targets.start_tangent if entry else source.targets.end_tangent
            outward = tangent if entry else tangent.translated(tangent, -2)
            bound = sum(a * b for a, b in zip(row.coefficients, values[::2])) - row.right
            samples = [
                dot(difference(physical(piece, i / 20, q, b), origin), outward)
                for i in range(21)
                for q in (-source.half_width_mm, 0, source.half_width_mm)
                for b in (-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2)
            ]
            assert min(samples) >= bound - 1e-7


def test_ambiguous_widths_and_checkpoint_failures_do_not_invent_a_route() -> None:
    """
    Unsupported frame ambiguity and resource stops propagate without fallback headings.
    """
    target = _route((Straight(10),)).targets
    opposed = Boundary(
        replace(target, end_width=target.end_width.translated(target.end_width, -2)), 1
    )
    with pytest.raises(ValueError, match="Opposed transported widths"):
        bridge(opposed)

    def stopped() -> None:
        """
        Reject the first factor branch under an external resource stop.
        """
        raise TimeoutError("external stop")

    with pytest.raises(TimeoutError, match="external stop"):
        chains(boundary(), stopped)
