"""
Exercise original material-coordinate extraction and measured trunk/ending accounting.
"""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_complete.execution import prepare
from experiments.experiment_ribbon_complete.planned_material import audit as audit_complete
from experiments.experiment_ribbon_complete.profile_transition import TransitionTiming
from experiments.experiment_ribbon_complete.trunk_material import TrunkMetricWork, audit, piece_path
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches
from tests.test_ribbon_complete_execution import checkpoint, targets, trunk


def piece() -> PlacedPiece:
    """
    Author an oblique crease with staggered material entry, no endpoint solve or native geometry.
    """
    return PlacedPiece(
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)),
        CylindricalFold(1, 1, 0.3, 2.4, 1, 1),
        "analytical crease",
    )


def test_oblique_hermite_paths_cover_common_distance_with_staggered_phase_entry() -> None:
    """
    Actual authoring controls have small measured error, not an assumed exact zero.
    """
    source = piece()
    results = tuple(
        piece_path(source, q, TrunkMetricWork(256, checkpoint)) for q in (Fraction(-1), Fraction(1))
    )
    assert all(Fraction(0) < row.upper_mm < Fraction(1, 1000) for row in results)
    assert results[0].spans[0].source.high_mm != results[1].spans[0].source.high_mm
    assert all(
        row.spans[0].source.low_mm == 0
        and row.spans[-1].source.high_mm == Fraction(source.geometry.material_length_mm)
        for row in results
    )


def test_nonunit_authoring_frame_is_measured_without_normalizing_away_its_error() -> None:
    """
    A long, stretched source line cannot inherit an ideal unit-speed certificate.
    """
    source = replace(
        piece(),
        pose=Pose(Vector3(0, 0, 0), Vector3(2, 0, 0), Vector3(0, 1, 0)),
        geometry=Straight(10),
    )
    result = piece_path(source, Fraction(0), TrunkMetricWork(4, checkpoint))
    assert result.upper_mm == Fraction(10)


@pytest.mark.parametrize("angle", (0.102, -0.102, 1.0))
@pytest.mark.parametrize("coordinate", (-1, 0, 1))
def test_uniform_material_chart_keeps_original_controls_and_exact_declared_phase_extent(
    angle: float, coordinate: int
) -> None:
    """
    Both fold signs and staggered labels keep their complete original curves despite knot roundoff.
    """
    original = piece()
    assert isinstance(original.geometry, CylindricalFold)
    fold = replace(original.geometry, angle_radians=angle)
    source = replace(original, geometry=fold)
    q = Fraction(coordinate)
    probe = MaterialArc(((float(q), 0.0),) * 3, (1.0,) * 3, "independent-test-probe")
    patch = next(p for p in material_patches((source,), (probe,)) if p.region == "bend")
    result = piece_path(source, q, TrunkMetricWork(256, checkpoint))
    cosine = Fraction(math.cos(fold.bank_radians))
    sine = Fraction(math.sin(fold.bank_radians))
    entry = Fraction(fold.before_mm) - q * sine / cosine
    extent = Fraction(fold.radius_mm) * Fraction(abs(angle)) / cosine
    count = math.ceil(abs(angle) / 0.025)
    bends = result.spans[1:-1]
    assert len(bends) == count
    for index, row in enumerate(bends):
        assert row.source.low_mm == entry + extent * index / count
        assert row.source.high_mm == entry + extent * (index + 1) / count
        assert row.source.controls == tuple(
            tuple(Fraction(getattr(point[0], axis)) for axis in "xyz")
            for point in patch.rows[3 * index : 3 * index + 4]
        )
    assert all(a.source.high_mm == b.source.low_mm for a, b in zip(result.spans, result.spans[1:]))
    assert result.spans[0].source.low_mm == Fraction(0)
    assert result.spans[-1].source.high_mm == Fraction(source.geometry.material_length_mm)
    assert 0 < result.upper_mm < Fraction(1, 1000)


def test_complete_plan_keeps_geometry_provenance_and_missing_material_correspondence() -> None:
    """
    A small combined metric bound still cannot clear the other complete physical gates.
    """
    plan = prepare(
        targets(), trunk, checkpoint, lambda row: None, timing=TransitionTiming.LOW_ENERGY
    )
    result = audit_complete(plan, TrunkMetricWork(1024, checkpoint))
    assert result.trunk.plan is plan
    assert all(path.route is plan.trunk.route for path in result.trunk.paths)
    assert all(row.plan is plan.captured and row.upper_mm == 0 for row in result.trunk.conductors)
    assert len(result.findings) == 4 and all(
        row.status == "within_declared_bound" for row in result.findings
    )
    assert "junction_material_correspondence" in result.outstanding
    assert "native_material_correspondence" in result.outstanding


def test_foreign_targets_and_shared_measurement_exhaustion_stop_without_retry() -> None:
    """
    Missing source ownership and a spent allocation never become numerical physical results.
    """
    plan = prepare(targets(), trunk, checkpoint, lambda row: None)
    assert plan.trunk.route is not None
    wrong = replace(
        plan.trunk.route, targets=replace(plan.trunk.route.targets, end=Vector3(99, 0, 0))
    )
    with pytest.raises(ValueError, match="original trunk"):
        audit(
            replace(plan, trunk=replace(plan.trunk, route=wrong)), TrunkMetricWork(1024, checkpoint)
        )
    work = TrunkMetricWork(1, checkpoint)
    with pytest.raises(RuntimeError, match="span allocation exhausted"):
        piece_path(piece(), Fraction(0), work)
    assert work.spans == 1
