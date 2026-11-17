"""
Challenge direct material comparisons with symmetry, asymmetry and original moving frames.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from math import sqrt

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.branch_construction import construct
from experiments.experiment_ribbon_complete.ending_material import bound as center_bound
from experiments.experiment_ribbon_complete.ending_material import branch_bound
from experiments.experiment_ribbon_complete.ending_pair import absolute_integral, bound
from experiments.experiment_ribbon_complete.material_traces import traces
from experiments.experiment_ribbon_complete.profile_transition import TransitionTiming, build
from experiments.experiment_ribbon_complete.root_profiles import partition
from experiments.experiment_ribbon_complete.spatial_frame import ChartOrientation, FrameSpan
from experiments.experiment_ribbon_complete.spatial_transition import SpatialPatch, compose
from tests.test_ribbon_complete_branch_construction import data
from tests.test_ribbon_complete_execution import checkpoint


def patches(lines: int = 1, lateral: float = 0, motion: float = 0) -> tuple[SpatialPatch, ...]:
    """
    Compose real profile transitions on analytical, unnormalized physical frame fields.
    """
    frame = FrameSpan(
        Fraction(0),
        Fraction(1),
        (Vector3(0, 0, 0), Vector3(lateral, 0, 10)),
        (Vector3(1, 0, 0), Vector3(1, motion, 0)),
        (Vector3(0, 1, 0),),
        ChartOrientation.POSITIVE,
    )
    sections = build(
        partition(lines, 0.75)[0], -(lines - 1) * 0.375, 0.375, timing=TransitionTiming.LOW_ENERGY
    )
    return tuple(compose(section, frame, checkpoint) for section in sections)


def test_mirrored_paths_cancel_pointwise_speed_difference_only() -> None:
    """
    Equal side speeds still retain their positive discrepancy from the center path.
    """
    span = patches()
    left, right = traces(tuple(p.section for p in span))
    a, b = span[left.edge_index], span[right.edge_index]
    assert bound(a, left.coordinate, b, right.coordinate, checkpoint) == 0
    first = center_bound(a, left.coordinate, checkpoint)
    second = center_bound(b, right.coordinate, checkpoint)
    assert first is not None and second is not None and first > 0 and second > 0
    complete, roots = data(1)
    branch = next(iter(construct(complete, roots, checkpoint)))
    result = branch_bound(replace(branch, patches=(span,)), checkpoint)
    assert result == max(first, second)


@pytest.mark.parametrize("lines,lateral,motion", [(1, 2, 0), (2, 0, 0), (2, 1, 0.01)])
def test_direct_bound_encloses_actual_pairwise_increments(
    lines: int,
    lateral: float,
    motion: float,
) -> None:
    """
    Asymmetry, a nonorthogonal center and width motion cannot disappear through symmetry logic.
    """
    span = patches(lines, lateral, motion)
    left, right = traces(tuple(p.section for p in span))
    a, b = span[left.edge_index], span[right.edge_index]
    upper = bound(a, left.coordinate, b, right.coordinate, checkpoint)
    assert upper is not None and upper > 0
    # Independent actual quotient jets witness a nonzero discrepancy on the original tensors.
    increments = []
    for i in range(41):
        va = a.jet(i / 40, float(left.coordinate)).along
        vb = b.jet(i / 40, float(right.coordinate)).along
        increments.append(
            abs(sqrt(va.x**2 + va.y**2 + va.z**2) - sqrt(vb.x**2 + vb.y**2 + vb.z**2))
        )
    observed = (sum(increments) - (increments[0] + increments[-1]) / 2) / 40
    assert 0 < observed <= float(upper)
    if lateral == 2:
        first = center_bound(a, left.coordinate, checkpoint)
        second = center_bound(b, right.coordinate, checkpoint)
        assert first is not None and second is not None
        assert observed > float(max(first, second))


def test_absolute_polynomial_integral_retains_opposite_local_distortions() -> None:
    """
    An exactly zero signed integral must still have a positive absolute enclosure.
    """
    assert absolute_integral((Fraction(-1), Fraction(1))) == 1


def test_changed_geometry_or_trace_provenance_cannot_receive_original_certificate() -> None:
    """
    Reject changed world or section controls and refuse unrelated frame charts.
    """
    span = patches()
    left, right = traces(tuple(p.section for p in span))
    a, b = span[left.edge_index], span[right.edge_index]
    rows = list(a.section_rows)
    rows[0] = tuple((p[0] + 1, p[1], p[2]) for p in rows[0])
    changed = replace(a, section_rows=tuple(rows))
    with pytest.raises(ValueError, match="changed geometry"):
        bound(changed, left.coordinate, b, right.coordinate, checkpoint)
    moving = replace(b.frame, center=(Vector3(0, 0, 0), Vector3(0, 0, 11)))
    assert (
        bound(
            a, left.coordinate, compose(b.section, moving, checkpoint), right.coordinate, checkpoint
        )
        is None
    )
    assert bound(a, Fraction(1, 3), b, right.coordinate, checkpoint) is None
    stationary = replace(a.frame, center=(Vector3(0, 0, 0),))
    assert (
        bound(
            compose(a.section, stationary, checkpoint),
            left.coordinate,
            compose(b.section, stationary, checkpoint),
            right.coordinate,
            checkpoint,
        )
        is None
    )
