"""
Verify that required material metrics and source trajectories share one immutable atlas.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.branch_lengths import measure
from experiments.experiment_ribbon_complete.collared_transport import evaluate, world
from experiments.experiment_ribbon_complete.curve_lengths import LengthWork
from experiments.experiment_ribbon_complete.material_atlas import audit as atlas_audit
from experiments.experiment_ribbon_complete.material_contract import bind
from experiments.experiment_ribbon_complete.material_traces import audit as midline_audit
from tests.test_ribbon_complete_branch_plan import data, planned, with_frames
from tests.test_ribbon_complete_lengths import checkpoint


@pytest.mark.parametrize("split", (False, True))
def test_source_labels_reproduce_entire_measured_trajectories(split: bool) -> None:
    """
    Exact polynomial curves retain canonical labels and agree with world evaluation across source spans.
    """
    plan = planned(data(split=split))
    atlas = atlas_audit(plan, checkpoint)
    measured = measure(
        plan, LengthWork(len(plan.patches), checkpoint), "same-plan material contract"
    )
    metrics = measured.midline
    result = bind(atlas, metrics, checkpoint)
    assert result.atlas is atlas and result.midline is metrics
    assert result.status == "certified_corresponding_midlines"
    for span, controls in zip(plan.patches, result.span_controls):
        for point, curve in zip(result.labels, controls):
            for t in (Fraction(0), Fraction(1, 2), Fraction(1)):
                homogeneous = tuple(evaluate(tuple(p[k] for p in curve), t) for k in range(4))
                actual = tuple(homogeneous[k] / homogeneous[3] for k in range(3))
                frame = span[0].frame
                assert actual == world(
                    plan, point, frame.low + t * (frame.high - frame.low), checkpoint
                )
    assert "material_metrics" in plan.outstanding and "native_junctions" in plan.outstanding


@pytest.mark.parametrize("fault", ("plan", "traces", "spans", "patch", "coordinate", "accounting"))
def test_stale_or_incomplete_metric_evidence_cannot_transfer_to_an_atlas(fault: str) -> None:
    """
    Shared UUIDs and a certified outer status cannot replace original metric ownership and coverage.
    """
    plan = planned(data())
    atlas = atlas_audit(plan, checkpoint)
    metrics = midline_audit(plan, checkpoint)
    first, second = metrics.spans[0]
    if fault == "plan":
        metrics = replace(metrics, plan=replace(plan))
    elif fault == "traces":
        metrics = replace(metrics, left=metrics.right, right=metrics.left)
    elif fault == "spans":
        metrics = replace(metrics, spans=())
    elif fault == "patch":
        metrics = replace(metrics, spans=((replace(first, patch=replace(first.patch)), second),))
    elif fault == "coordinate":
        metrics = replace(
            metrics, spans=((replace(first, edge_coordinate=Fraction(1, 3)), second),)
        )
    else:
        metrics = replace(metrics, pairwise_upper_mm=Fraction(0))
    with pytest.raises(ValueError):
        bind(atlas, metrics, checkpoint)


def test_coordinate_validity_does_not_waive_unresolved_local_material_lengths() -> None:
    """
    A source-valid longitudinal width displacement remains unresolved when its required metric bound is too large.
    """
    values = data()
    frame = values[-1][0]
    y = Vector3(0, 1, 0)
    changed = replace(frame, width=(y, y, y, Vector3(0.2, 1, 0), y, y))
    plan = planned(with_frames(values, (changed,)))
    atlas = atlas_audit(plan, checkpoint)
    metrics = midline_audit(plan, checkpoint)
    assert atlas.status == "certified_piecewise_coordinates"
    assert metrics.status == "unresolved"
    result = bind(atlas, metrics, checkpoint)
    assert result.status == "unresolved" and result.midline is metrics


def test_borrowed_coordinate_receipt_requires_all_inner_proofs() -> None:
    """
    A copied successful outer atlas status cannot hide a missing transport bound.
    """
    plan = planned(data())
    atlas = atlas_audit(plan, checkpoint)
    metrics = midline_audit(plan, checkpoint)
    first = replace(atlas.transports[0], minimum_monotonicity=None)
    with pytest.raises(ValueError, match="complete material atlas"):
        bind(replace(atlas, transports=(first,) + atlas.transports[1:]), metrics, checkpoint)
