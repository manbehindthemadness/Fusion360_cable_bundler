"""
Check exact material labels, identity collar and transverse transport folding counterexamples.
"""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.collared_transport import (
    boundary,
    collar,
    label,
    transverse,
    world,
)
from experiments.experiment_ribbon_complete.profile_transition import (
    TransitionEdge,
    homogeneous_row,
)
from experiments.experiment_ribbon_complete.root_profiles import RootEdge
from experiments.experiment_ribbon_complete.transport_certificate import certify
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_branch_plan import data, planned
from tests.test_ribbon_complete_lengths import checkpoint


def uniform_section(scale: float) -> TransitionEdge:
    """
    Specify an exact uniform radial scale of one circular arc with unchanged weights.
    """
    arc = MaterialArc(((1, 0), (1, -1), (0, -1)), (1, math.sqrt(0.5), 1), "analytical quarter")
    target = MaterialArc(
        tuple((scale * q, scale * b) for q, b in arc.controls), arc.weights, arc.label
    )
    root, end = homogeneous_row(arc, 0), homogeneous_row(target, 0)
    return TransitionEdge(RootEdge(arc, None), 0, scale, target, (root,) * 3 + (end,) * 3)


@pytest.mark.parametrize("scale", (1, 0.875))
def test_identity_and_moderate_uniform_contraction_have_positive_transverse_jacobians(
    scale: float,
) -> None:
    """
    For radial P=lambda*R, outer radius derivative is1+4(lambda-1) at the terminal boundary.
    """
    result = certify(uniform_section(scale), checkpoint)
    assert result.status == "certified"
    assert result.cartesian_jacobian_lower is not None and Fraction(
        0
    ) < result.cartesian_jacobian_lower <= Fraction(1)


def test_strong_contraction_cannot_hide_a_transverse_material_fold() -> None:
    """
    At scale1/2, s=3/4 maps farther out than s=1, despite the prescribed outer circle being valid.
    """
    result = certify(uniform_section(0.5), checkpoint)
    assert result.status == "unresolved"
    assert Fraction(3, 4) - collar(Fraction(3, 4)) / 2 > Fraction(1, 2)


def test_root_and_central_collar_keep_original_cartesian_material_points_exactly() -> None:
    """
    The complete inner quarter remains identity for all longitudinal phases, not only at one center sample.
    """
    plan = planned(data())
    for s in (Fraction(0), Fraction(1, 8), Fraction(1, 4), Fraction(1, 2), Fraction(1)):
        point = label(plan, 0, Fraction(1, 3), s)
        root = boundary(
            plan.patches[0][point.edge_index].section, Fraction(0), point.edge_coordinate
        )
        expected = (s * root[0], s * root[1])
        assert transverse(plan, point, Fraction(0)) == expected
        if s <= Fraction(1, 4):
            assert all(
                transverse(plan, point, u) == expected
                for u in (Fraction(1, 4), Fraction(1, 2), Fraction(1))
            )


def test_inherited_boundary_and_spatial_fields_are_not_changed_by_transport() -> None:
    """
    At s=1 the same exact section boundary and composed world surface are authoritative.
    """
    plan = planned(data(split=True))
    point = label(plan, 0, Fraction(1, 3), Fraction(1))
    for u in (Fraction(0), Fraction(1, 2), Fraction(1)):
        assert transverse(plan, point, u) == boundary(plan.patches[0][0].section, u, Fraction(1, 3))
        actual = world(plan, point, u, checkpoint)
        patch = next(
            span[0] for span in plan.patches if span[0].frame.low <= u <= span[0].frame.high
        )
        observed = patch.jet(float(u), 1 / 3).point
        assert (
            sum((float(a) - b) ** 2 for a, b in zip(actual, (observed.x, observed.y, observed.z)))
            < 1e-20
        )


def test_center_and_shared_fan_boundaries_have_canonical_source_owners() -> None:
    """
    Explicit adjacency identifies seams without a nearest-point search or new material labels.
    """
    plan = planned(data())
    assert label(plan, 0, Fraction(1), Fraction(1, 2)) == label(
        plan, 1, Fraction(0), Fraction(1, 2)
    )
    assert label(plan, 0, Fraction(1, 3), Fraction(0)) == label(
        plan, 2, Fraction(2, 3), Fraction(0)
    )


def test_material_label_cannot_transfer_to_another_conductor_or_changed_root() -> None:
    """
    Identical-looking surfaces cannot override persistent material source identity.
    """
    plan = planned(data())
    point = label(plan, 0, Fraction(1, 2), Fraction(1, 2))
    key = replace(plan.source.conductor, pin_number=99)
    changed = replace(plan, source=replace(plan.source, conductor=key))
    with pytest.raises(ValueError, match="root identity or geometry"):
        world(changed, point, Fraction(1, 2), checkpoint)
    reordered = replace(
        point.source, root_rows=point.source.root_rows[1:] + point.source.root_rows[:1]
    )
    with pytest.raises(ValueError, match="root identity or geometry"):
        world(plan, replace(point, source=reordered), Fraction(1, 2), checkpoint)


def test_material_world_coordinates_cannot_ignore_changed_authoring_controls() -> None:
    """
    Preserved fields are not authority for an independently changed frozen spatial boundary net.
    """
    plan = planned(data())
    point = label(plan, 0, Fraction(1, 2), Fraction(1, 2))
    patch = plan.patches[0][0]
    row = patch.rows[2]
    altered = (row[0][0] + 1,) + row[0][1:]
    changed = replace(patch, rows=patch.rows[:2] + ((altered,) + row[1:],) + patch.rows[3:])
    modified = replace(plan, patches=((changed,) + plan.patches[0][1:],))
    with pytest.raises(ValueError, match="changed world control geometry"):
        world(modified, point, Fraction(1, 2), checkpoint)
