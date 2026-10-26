"""
Check observational event labels and consistent material coordinates across runtimes.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.coupled_motion import ZERO, CoupledMotion
from experiments.experiment_ribbon_cap_transition.event_cases import cases, construct
from experiments.experiment_ribbon_cap_transition.event_labels import EventKind, _regions, inspect
from experiments.experiment_ribbon_cap_transition.material_strip import MaterialSpan, MaterialStrip

X, Y = Vector3(1, 0, 0), Vector3(0, 1, 0)


def test_terminal_coordinates_share_one_accumulation_with_nonbinary_lengths() -> None:
    """
    Prefixes and total length remain identical even when sum algorithms differ.
    """
    lengths = (
        12.121658243309694,
        69.39076570809787,
        29.228228634771025,
        82.4331957015132,
        29.228228634771018,
        69.39076570809786,
        12.121658243309689,
    )
    spans, start = [], ZERO
    for length in lengths:
        motion = CoupledMotion(start, X, Y, Y, 0, length)
        spans.append(MaterialSpan(motion, 0, 0))
        start = motion.jet(1)[0]
    strip = MaterialStrip(tuple(spans), 14.4)
    assert strip.length_mm == math.fsum(lengths)
    for offset in (-14.4, 0.0, 14.4):
        assert strip.boundaries(offset)[-1] == strip.length_mm
        assert strip.jet(strip.boundaries(offset)[-1], offset)[1] == X
    with pytest.raises(ValueError, match="distance"):
        strip.jet(math.nextafter(strip.length_mm, math.inf))


def test_observing_straight_path_does_not_modify_geometry() -> None:
    """
    Zero bend and twist yields one neutral straight region on both signals.
    """
    motion = CoupledMotion(ZERO, X, Y, Y, 0, 80)
    strip = MaterialStrip((MaterialSpan(motion, 0, 0),), 14.4)
    before = strip.jet(37, 5)
    readout = inspect(strip)
    assert len(readout.edge_regions) == len(readout.bend_regions) == 1
    assert readout.edge_regions[0].kind is EventKind.STRAIGHT
    assert readout.bend_regions[0].kind is EventKind.STRAIGHT
    assert strip.jet(37, 5) == before
    assert readout.sample_count == 257


def test_s_control_exposes_difference_between_edge_symmetry_and_two_signed_turns() -> None:
    """
    A continuous S can reverse bending without one width edge taking greater curvature.
    """
    case = cases()[-1]
    plan = construct(case)
    before = plan.strip.jet(plan.strip.length_mm / 2)
    readout = inspect(plan.strip)
    turns = [
        region.kind
        for region in readout.bend_regions
        if region.kind in (EventKind.POSITIVE, EventKind.NEGATIVE)
    ]
    assert turns == [EventKind.POSITIVE, EventKind.NEGATIVE]
    assert all(region.kind not in (EventKind.A, EventKind.B) for region in readout.edge_regions)
    assert readout.maximum_relative_edge_difference < 1e-12
    assert plan.connected and plan.endpoint_gap_mm < 1e-8
    assert plan.strip.jet(plan.strip.length_mm / 2) == before
    assert plan.motions[0].maximum_curvature() > 0
    assert plan.motions[0].jet(1)[2] == ZERO
    assert plan.motions[1].jet(0)[2] == ZERO


def test_s_control_rejects_changed_endpoint_inputs() -> None:
    """
    The exact control branch cannot silently accept post-result target relocation.
    """
    with pytest.raises(ValueError, match="frozen"):
        construct(replace(cases()[-1], end=Vector3(81, 0, 20)))


def test_short_label_flicker_does_not_create_an_event() -> None:
    """
    Three supporting samples confirm a handoff while one isolated opposite label does not.
    """
    labels = [
        EventKind.A,
        EventKind.A,
        EventKind.B,
        EventKind.A,
        EventKind.B,
        EventKind.B,
        EventKind.B,
        EventKind.B,
    ]
    regions = _regions(labels, 70)
    assert [region.kind for region in regions] == [EventKind.A, EventKind.B]
    assert regions[0].end_mm == regions[1].start_mm == 40


@pytest.mark.parametrize("lengths", ((1e16, 1.0), (1e308, 1e308)))
def test_unrepresentable_material_intervals_are_rejected(lengths: tuple[float, ...]) -> None:
    """
    Finite individual lengths cannot silently create collapsed or overflowing coordinates.
    """
    spans, start = [], ZERO
    for length in lengths:
        motion = CoupledMotion(start, X, Y, Y, 0, length)
        spans.append(MaterialSpan(motion, 0, 0))
        start = motion.jet(1)[0]
    with pytest.raises(ValueError, match="coordinates|representable"):
        MaterialStrip(tuple(spans), 14.4)
