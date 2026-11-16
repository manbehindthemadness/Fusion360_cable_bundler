"""
Verify scheduled full-profile geometry using independent exact evaluations and jets.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.profile_transition import build
from experiments.experiment_ribbon_complete.root_profiles import partition
from experiments.experiment_ribbon_complete.scheduled_transition import compose, construct
from experiments.experiment_ribbon_complete.spatial_frame import restrict, split_at
from experiments.experiment_ribbon_complete.spatial_transition import derive
from experiments.experiment_ribbon_complete.taper_schedule import TaperRequirement, plan
from experiments.experiment_ribbon_complete.tensor_composition import Net, compose_fields
from tests.test_ribbon_complete_lengths import checkpoint
from tests.test_ribbon_complete_spatial import frame


def evaluate(net: Net, u: Fraction, v: Fraction) -> tuple[Fraction, ...]:
    """
    Evaluate an exact homogeneous tensor with successive de Casteljau steps.
    """
    return tuple(
        split_at(tuple(split_at(tuple(p[k] for p in row), v)[0][-1] for row in net), u)[0][-1]
        for k in range(len(net[0][0]))
    )


@pytest.mark.parametrize("moving", (False, True))
def test_full_rational_profile_matches_original_fields_and_global_beta(moving: bool) -> None:
    """
    Non-dyadic intersections retain exact geometry even with curved, changing raw axes.
    """
    fields = frame()
    if moving:
        fields = replace(
            fields,
            center=(Vector3(0, 0, 0), Vector3(4, 2, 1), Vector3(10, 0, 3)),
            width=(Vector3(0, 1, 0), Vector3(0, 1, 0.25)),
        )
    schedule = plan(
        (TaperRequirement(Fraction(3, 4), Fraction(3, 40), Fraction(10)),) * 2,
        Fraction(1, 100),
        checkpoint,
    )
    section = build(partition(2, 0.75)[0], -0.375, 0.375)[0]
    for blend in schedule.intervals:
        patch = compose(section, fields, blend, checkpoint)
        assert patch.section is section and patch.frame is fields and patch.blend is blend
        for t in (Fraction(0), Fraction(2, 7), Fraction(1)):
            global_u = patch.low + t * (patch.high - patch.low)
            local_beta = (global_u - blend.low) / (blend.high - blend.low)
            beta = split_at(blend.controls, local_beta)[0][-1]
            for v in (Fraction(0), Fraction(1, 3), Fraction(1)):
                ends = tuple(
                    tuple(split_at(tuple(point[k] for point in row), v)[0][-1] for k in range(3))
                    for row in (section.rows[0], section.rows[-1])
                )
                q, b, weight = tuple((1 - beta) * a + beta * z for a, z in zip(*ends))
                raw = tuple(
                    tuple(split_at(axis, global_u)[0][-1] for axis in field)
                    for field in fields.fields()
                )
                expected = tuple(
                    raw[0][k] * weight + raw[1][k] * q + raw[2][k] * b for k in range(3)
                ) + (weight,)
                assert evaluate(patch.rows, t, v) == expected


@pytest.mark.parametrize("length", (Fraction(3, 4), Fraction(3)))
def test_intersections_keep_complete_order_shared_boundaries_and_c2_jets(length: Fraction) -> None:
    """
    Frame splits neither restart the blend nor create gaps or derivative jumps.
    """
    sections = build(partition(2, 0.75)[0], -0.375, 0.375)
    schedule = plan(
        (TaperRequirement(length, Fraction(3, 40), Fraction(10)),) * 2,
        Fraction(1, 100),
        checkpoint,
    )
    frames = (frame(Fraction(0), Fraction(1, 4)), frame(Fraction(1, 4), Fraction(1)))
    spans = construct(sections, frames, schedule, checkpoint)
    assert len(spans) == (4 if length == Fraction(3, 4) else 3)
    assert spans[0][0].low == Fraction(0) and spans[-1][0].high == Fraction(1)
    for span in spans:
        for index, patch in enumerate(span):
            following = span[(index + 1) % len(span)]
            assert tuple(row[-1] for row in patch.rows) == tuple(row[0] for row in following.rows)
            assert all(point[-1] > 0 for row in patch.rows for point in row)
    for left, right in zip(spans, spans[1:]):
        for a, b in zip(left, right):
            assert a.high == b.low
            aa, bb = a.rows, b.rows
            for order in range(3):
                for v in (Fraction(0), Fraction(2, 5), Fraction(1)):
                    actual_a = tuple(
                        x / (a.high - a.low) ** order for x in evaluate(aa, Fraction(1), v)
                    )
                    actual_b = tuple(
                        x / (b.high - b.low) ** order for x in evaluate(bb, Fraction(0), v)
                    )
                    assert actual_a == actual_b
                aa, bb = derive(aa, 0), derive(bb, 0)
    assert spans[0][0].section_rows[0] == sections[0].rows[0]
    assert spans[-1][0].section_rows[-1] == sections[0].rows[-1]
    for cap, end in ((spans[0], False), (spans[-1], True)):
        for patch in cap:
            net = patch.section_rows
            for _ in range(2):
                degree = len(net) - 1
                net = tuple(
                    tuple(
                        tuple(degree * (b - a) for a, b in zip(p, q)) for p, q in zip(left, right)
                    )
                    for left, right in zip(net, net[1:])
                )
                assert all(
                    value == Fraction(0) for point in net[-1 if end else 0] for value in point
                )


def test_frame_restriction_is_exact_without_float_vector_round_trip() -> None:
    """
    Original raw frame fields restricted at thirds retain their rational controls.
    """
    section = build(partition(1, 0.75)[0], 0, 0.375)[0]
    schedule = plan(
        (TaperRequirement(Fraction(1), Fraction(0), Fraction(0)),), Fraction(1, 100), checkpoint
    )
    fields = frame(Fraction(0), Fraction(2, 3))
    patch = compose(section, fields, schedule.intervals[-1], checkpoint)
    assert patch.fields[0][0] == restrict(fields.fields()[0][0], Fraction(3, 4), Fraction(1))
    assert any(Fraction(float(value)) != value for value in patch.fields[0][0])


def test_forged_schedule_and_incomplete_frames_are_refused() -> None:
    """
    Changed controls cannot inherit the planner's certificate or hide missing geometry.
    """
    sections = build(partition(1, 0.75)[0], 0, 0.375)
    schedule = plan(
        (TaperRequirement(Fraction(1), Fraction(0), Fraction(0)),), Fraction(1, 100), checkpoint
    )
    changed = replace(schedule.intervals[0], controls=(Fraction(0), Fraction(1)))
    with pytest.raises(ValueError, match="derived controls"):
        construct(
            sections,
            (frame(),),
            replace(schedule, intervals=(changed,) + schedule.intervals[1:]),
            checkpoint,
        )
    with pytest.raises(ValueError, match="complete global"):
        construct(sections, (frame(Fraction(1, 3), Fraction(1)),), schedule, checkpoint)
    with pytest.raises(ValueError, match="nonempty intersection"):
        compose(sections[0], frame(Fraction(0), Fraction(1, 3)), schedule.intervals[-1], checkpoint)


def test_shared_composition_checks_weights_and_propagates_caller_stop() -> None:
    """
    Invalid denominators and resource cancellation never produce substitute geometry.
    """
    section = build(partition(1, 0.75)[0], 0, 0.375)[0]
    bad = ((section.rows[0][0][:-1] + (Fraction(0),),) * 3,)
    with pytest.raises(ValueError, match="positive-weight"):
        compose_fields(bad, frame().fields(), checkpoint)

    def stopped() -> None:
        """
        Represent a caller-owned resource stop.
        """
        raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        compose_fields(section.rows, frame().fields(), stopped)
