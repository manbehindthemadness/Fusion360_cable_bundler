"""
Check whole-volume cap-collar evidence without accepting unresolved seam contact.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from artifacts.verification.resume3216.field import Midsurface
from experiments.experiment_ribbon_complete.c2_material import prepare
from experiments.experiment_ribbon_complete.contact_cell import BendPreparation
from experiments.experiment_ribbon_complete.contact_junction import certify_bend_cap
from experiments.experiment_ribbon_complete.flat_chart import (
    FlatRegion,
    MaterialCut,
    lead,
    straight,
)
from tests.test_ribbon_complete_flat_chart import piece
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


@pytest.mark.parametrize("region", (FlatRegion.BEFORE, FlatRegion.AFTER))
@pytest.mark.parametrize("shear", (False, True))
def test_complete_adjacent_interiors_are_separated_outside_bounded_cap_collar(
    region: FlatRegion, shear: bool
) -> None:
    """
    Whole original coefficients and positive projection rates bound both material distances.
    """
    volume = candidate(shear)
    chart = lead(volume, region, Fraction(2))
    result = certify_bend_cap(chart, checkpoint)
    assert result.chart is chart and result.volume is volume
    assert result.status == "certified_material_cap_collar"
    assert result.cap_position_upper_mm <= Fraction(1, 100)
    assert result.flat_projection_rate > 0
    assert result.bend_phase_projection_rate is not None and result.bend_phase_projection_rate > 0
    assert result.flat_collar_mm is not None and result.bend_collar_mm is not None
    assert Fraction(0) <= max(result.flat_collar_mm, result.bend_collar_mm) <= Fraction(1, 100)
    # This names a bounded unresolved cap collar, not a whole-contact acceptance.
    assert "separated" not in result.status and "contact" not in result.status
    theta = volume.source.surface.basis.breaks[-1]
    cap_phase = Fraction(0) if region is FlatRegion.BEFORE else theta
    direction = 1 if region is FlatRegion.BEFORE else -1
    for u in (Fraction(0), theta / 3, theta):
        for q in (-volume.source.half_mm, volume.source.half_mm / 7, volume.source.half_mm):
            v = (q / volume.source.half_mm + 1) / 2
            for b in (-volume.half_thickness_mm, volume.half_thickness_mm):
                actual = tuple(
                    volume.source.surface.jet(u, v).point[k] + b * volume.normals[k].jet(u)[0]
                    for k in range(3)
                )
                cap = tuple(
                    volume.source.surface.jet(cap_phase, v).point[k]
                    + b * volume.normals[k].jet(cap_phase)[0]
                    for k in range(3)
                )
                projection = direction * sum(
                    n * (a - c) for n, a, c in zip(result.axis, actual, cap)
                )
                assert projection >= result.bend_phase_projection_rate * abs(u - cap_phase)


def test_displaced_cap_and_reversed_material_labels_cannot_inherit_junction_evidence() -> None:
    """
    A geometric gap alone cannot excuse lost correspondence on the original q/b labels.
    """
    chart = lead(candidate(), FlatRegion.BEFORE, Fraction(2))
    moved = replace(
        chart, origin=tuple(o + Fraction(1, 10) * a for o, a in zip(chart.origin, chart.columns[0]))
    )
    assert certify_bend_cap(moved, checkpoint).status == "unresolved_cap_correspondence"
    reversed_width = replace(
        chart, columns=(chart.columns[0], tuple(-x for x in chart.columns[1]), chart.columns[2])
    )
    assert certify_bend_cap(reversed_width, checkpoint).status == "unresolved_cap_correspondence"


def test_matching_cap_does_not_hide_a_collapsed_or_reversing_bend_interior() -> None:
    """
    Full-span projected progress is required independently of cap position agreement.
    """
    volume = candidate()
    surface = Midsurface(
        volume.source.surface.basis,
        (volume.source.surface.rows[0],) * volume.source.surface.basis.count,
    )
    changed = replace(
        volume,
        source=prepare(surface, volume.source.half_mm, "collapsed analytical control", checkpoint),
    )
    chart = lead(changed, FlatRegion.BEFORE, Fraction(2))
    result = certify_bend_cap(chart, checkpoint)
    assert result.cap_position_upper_mm <= Fraction(1, 100)
    assert result.status == "unresolved_bend_projection_progress"
    assert result.flat_collar_mm is None and result.bend_collar_mm is None


def test_wrong_owner_flat_kind_and_caller_stop_reject_without_a_collar_certificate() -> None:
    """
    Discrete source ownership and caller cancellation cannot be waived by a small cap gap.
    """
    volume = candidate()
    chart = lead(volume, FlatRegion.BEFORE, Fraction(2))
    with pytest.raises(ValueError, match="SAME original"):
        certify_bend_cap(chart, checkpoint, preparation=BendPreparation(replace(volume)))
    with pytest.raises(ValueError, match="before/after"):
        certify_bend_cap(straight(piece()), checkpoint)
    with pytest.raises(ValueError, match="shared material cut"):
        certify_bend_cap(replace(chart, high=MaterialCut(Fraction(1))), checkpoint)

    def stop() -> None:
        """
        Model exhaustion of the shared caller allocation before any evidence is returned.
        """
        raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        certify_bend_cap(chart, stop)
