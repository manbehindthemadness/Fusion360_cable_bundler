"""
Reuse exact flat preparation while retaining every original support query and strict witness decision.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Callable, cast
from unittest.mock import Mock, patch

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route import contact_flat_probe as probing
from experiments.experiment_ribbon_fold_route.contact import ProbeResult
from experiments.experiment_ribbon_fold_route.contact_convex import Triple
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import (
    FlatShapes,
    Shape,
    profile_arcs,
    shapes,
)
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_probe_axis import _skew


def _support_observer(
    trace: list[tuple[Shape, Triple, Triple]],
) -> Callable[[Shape, Triple], Triple]:
    """
    Bind one support trace without a mutable default or a changing loop closure.
    """
    original = cast(Callable[[Shape, Triple], Triple], Shape.support)

    def observe(shape: Shape, direction: Triple) -> Triple:
        """
        Record the unchanged actual extremum in its original query order.
        """
        result = original(shape, direction)
        trace.append((shape, direction, result))
        return result

    return observe


@pytest.mark.parametrize("index", (0, 2, 6, 7, 8))
@pytest.mark.parametrize("lines", (1, 9))
def test_distinct_pair_calls_reuse_preparation_but_keep_exact_support_trace_and_counters(
    index: int,
    lines: int,
) -> None:
    """
    Observe real extrema and probe results on authored skew members; mock no geometric decision.
    """
    source = _skew(index)
    extra = replace(source.pieces[0], pose=replace(source.pieces[0].pose, origin=Vector3(0, 5, 10)))
    route = replace(
        source, pieces=(*source.pieces, extra), targets=replace(source.targets, lines=lines)
    )
    traces: list[list[tuple[Shape, Triple, Triple]]] = []
    counters: list[dict[str, Any]] = []
    outputs: list[list[ProbeResult]] = []
    preparations: list[int] = []
    for reuse in (False, True):
        trace: list[tuple[Shape, Triple, Triple]] = []
        observe = _support_observer(trace)
        prepare = Mock(wraps=shapes)
        with patch.dict(vars(probing), shapes=prepare):
            probe = FlatProbe()
            if not reuse:
                probe.__dict__["_shapes"] = prepare
            with patch.object(Shape, "support", observe):
                outputs.append([probe(route, a, b, 128, None) for a, b in ((0, 1), (0, 2), (1, 2))])
        traces.append(trace)
        counters.append(asdict(probe))
        preparations.append(prepare.call_count)
    assert outputs[0] == outputs[1] and traces[0] == traces[1] and counters[0] == counters[1]
    assert preparations == [6, 3]
    assert probe.shape_preparations() == {
        "hits": 3,
        "preparations": 3,
        "retained": 3,
        "capacity": 64,
    }
    assert set(counters[1]) == {"comparisons", "supports", "inverse_tests", "skipped_phase_pairs"}


@pytest.mark.parametrize("bank", (-0.4, 0.0, 0.4))
def test_banked_before_after_shapes_and_changed_pose_or_profile_are_prepared_exactly(
    bank: float,
) -> None:
    """
    Full immutable keys distinguish every material, placement and ordered-profile dependency.
    """
    source = _route((Straight(3), fold(2, 1.2, 1.1, bank, 1), Straight(5)))
    piece = source.pieces[1]
    arcs = profile_arcs(1, 1.0)
    prepare = Mock(wraps=shapes)
    context = FlatShapes(prepare)
    result = context(piece, arcs)
    assert result == shapes(piece, arcs) and context(replace(piece), arcs) is result
    variants = (
        (replace(piece, pose=replace(piece.pose, origin=Vector3(1, 2, 3))), arcs),
        (replace(piece, geometry=fold(2, 1.2, -1.1, bank, 1)), arcs),
        (piece, profile_arcs(9, 1.0)),
        (piece, profile_arcs(1, 0.75)),
    )
    for member, profile in variants:
        assert context(member, profile) == shapes(member, profile)
    assert prepare.call_count == 5


def test_eviction_separate_contexts_and_preparation_failure_never_transfer_acceptance() -> None:
    """
    Bound strong retention and retry only pure preparation after a propagated preparation exception.
    """
    member = _route((Straight(5),)).pieces[0]
    arcs = profile_arcs(1, 1)
    prepare = Mock(wraps=shapes)
    context, other = FlatShapes(prepare), FlatShapes(prepare)
    first = context(member, arcs)
    assert other(member, arcs) == first and prepare.call_count == 2
    for index in range(1, 65):
        context(replace(member, pose=replace(member.pose, origin=Vector3(index, 0, 0))), arcs)
    assert context.statistics()["retained"] == 64
    assert context(member, arcs) == first and prepare.call_count == 67
    failed = Mock(side_effect=(ArithmeticError("preparation failure"), first))
    fresh = FlatShapes(failed)
    with pytest.raises(ArithmeticError, match="preparation failure"):
        fresh(member, arcs)
    assert fresh.statistics()["retained"] == 0
    assert fresh(member, arcs) == first and failed.call_count == 2


def test_cached_preparation_preserves_guard_support_limit_and_phase_omission_contract() -> None:
    """
    Reuse cannot bypass cancellation or turn prior preparation into a probe/clearance certificate.
    """
    route = _skew(6)
    probe = FlatProbe()
    first = probe(route, 0, 1, 128, None)
    assert first.witness is None
    with pytest.raises(InterruptedError, match="original guard"):
        probe(route, 0, 1, 128, Mock(side_effect=InterruptedError("original guard")))
    probe.supports = 2048
    limited = probe(route, 0, 1, 128, None)
    assert limited.limit == "supports" and limited.witness is None
    assert probe.supports == 2048 and probe.shape_preparations()["hits"] == 2


def test_every_witness_still_requires_actual_inversion_after_preparation_reuse() -> None:
    """
    A repeated occupied pair must repeat support and strict inverse work within the original ceiling.
    """
    source: FoldRoute = _skew(0)
    probe = FlatProbe()
    first = probe(source, 0, 1, 128, None)
    before = asdict(probe)
    second = probe(source, 0, 1, 128, None)
    assert first.witness is not None and second == first
    assert probe.supports > before["supports"] and probe.inverse_tests > before["inverse_tests"]
    assert probe.shape_preparations()["hits"] == 2
