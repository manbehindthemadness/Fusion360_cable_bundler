"""
Check audited approximate material inversion, provenance and caller-owned stopping.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.collared_transport import boundary, label, world
from experiments.experiment_ribbon_complete.curve_lengths import distance
from experiments.experiment_ribbon_complete.material_atlas import audit
from experiments.experiment_ribbon_complete.material_inverse import recover
from tests.test_ribbon_complete_branch_lengths import complete_plans
from tests.test_ribbon_complete_branch_plan import data, planned, with_frames
from tests.test_ribbon_complete_lengths import checkpoint


@pytest.mark.parametrize("radial", (Fraction(0), Fraction(1, 8), Fraction(2, 3), Fraction(1)))
@pytest.mark.parametrize("edge", (0, -1))
def test_roundtrip_world_points_retain_source_identity_and_quantitative_error(
    radial: Fraction,
    edge: int,
) -> None:
    """
    Include the regular center, identity collar, outer fan and original boundary.
    """
    _complete, plans = complete_plans()
    atlas = audit(plans[0], checkpoint)
    point = label(plans[0], edge % len(plans[0].patches[0]), Fraction(1, 3), radial)
    target = world(plans[0], point, Fraction(2, 5), checkpoint)
    calls: list[int] = []

    def take_step() -> None:
        """
        Charge the one test query to an explicit24-step allocation.
        """
        assert len(calls) < 24
        calls.append(1)

    result = recover(atlas, target, take_step, checkpoint)
    assert result.status == "within_dimensional_tolerance"
    assert result.atlas is atlas and result.source_label is not None and result.phase is not None
    assert result.source_label.source == point.source
    assert result.residual_upper_mm is not None and result.residual_upper_mm <= Fraction(1, 100)
    assert result.root_error_upper_if_in_image_mm is not None
    root = boundary(
        plans[0].patches[0][point.edge_index].section, Fraction(0), point.edge_coordinate
    )
    other = result.source_label
    recovered = boundary(
        plans[0].patches[0][other.edge_index].section, Fraction(0), other.edge_coordinate
    )
    discrepancy = distance(
        tuple(radial * x for x in root), tuple(other.radial_fraction * x for x in recovered)
    )[1]
    assert discrepancy <= result.root_error_upper_if_in_image_mm <= Fraction(1, 100)


def test_unresolved_or_stale_atlas_cannot_transfer_material_coordinates() -> None:
    """
    Equal-looking reconstructed plans and unresolved charts remain insufficient provenance.
    """
    _complete, plans = complete_plans()
    atlas = audit(plans[0], checkpoint)
    for changed in (replace(atlas, status="unresolved"), replace(atlas, plan=replace(plans[0]))):
        with pytest.raises(ValueError, match="same source plan"):
            recover(changed, (Fraction(0),) * 3, checkpoint, checkpoint)


def test_inverse_keeps_global_phase_on_split_nonplanar_shear_fields() -> None:
    """
    A changing raw width field and two source spans cannot be replaced by a fixed station normal.
    """
    values = data(split=True)
    frames = tuple(
        replace(
            span,
            width=(
                Vector3(0, 1, float(span.low**2) / 10),
                Vector3(0, 1, float(span.low * span.high) / 10),
                Vector3(0, 1, float(span.high**2) / 10),
            ),
        )
        for span in values[-1]
    )
    plan = planned(with_frames(values, frames))
    atlas = audit(plan, checkpoint)
    point = label(plan, 0, Fraction(2, 3), Fraction(3, 4))
    target = world(plan, point, Fraction(3, 4), checkpoint)
    result = recover(atlas, target, checkpoint, checkpoint)
    assert result.status == "within_dimensional_tolerance"
    assert result.phase is not None and abs(result.phase - Fraction(3, 4)) <= Fraction(1, 100)
    assert result.residual_upper_mm is not None and result.residual_upper_mm <= Fraction(1, 100)


def test_outside_query_and_latched_work_stop_never_become_inverse_passes() -> None:
    """
    No extrapolation, hidden work renewal or target movement rescues an out-of-volume query.
    """
    _complete, plans = complete_plans()
    atlas = audit(plans[0], checkpoint)
    target = (Fraction(1000),) * 3
    result = recover(atlas, target, checkpoint, checkpoint)
    assert result.status == "unresolved" and result.source_label is None

    def stopped() -> None:
        """
        Model an already exhausted shared solver or audit allocation.
        """
        raise RuntimeError("shared inverse work exhausted")

    with pytest.raises(RuntimeError, match="shared inverse work exhausted"):
        recover(atlas, target, stopped, checkpoint)
