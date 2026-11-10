"""
Verify exact retained material traversal and nonrenewable comparison accounting.
"""

from __future__ import annotations

from dataclasses import replace
from math import pi
from typing import cast

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.contact_traversal import ContactTraversal
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route


class _HashGuardPiece(PlacedPiece):
    """
    Keep normal immutable geometry while rejecting unrelated payload hashing during proof.
    """

    def __hash__(self) -> int:
        """
        Fail if a context-local material identity is replaced by recursive geometry hashing.
        """
        raise AssertionError("Material proof must not hash complete piece payloads")


def _parallel(gap: float) -> FoldRoute:
    """
    Author three analytical strips with a distant last strip to force an initial yield.
    """
    source = _route((Straight(10),))
    first = source.pieces[0]
    pieces = (
        first,
        PlacedPiece(replace(first.pose, origin=Vector3(0, 0, gap)), Straight(10), "parallel"),
        PlacedPiece(
            Pose(Vector3(100, 0, 0), first.pose.tangent, first.pose.width), Straight(10), "distant"
        ),
    )
    return replace(source, pieces=pieces)


@pytest.mark.parametrize("kind", ("overlap", "clear", "fold"))
def test_projection_context_uses_local_piece_identity_without_changing_complete_proof(
    kind: str,
) -> None:
    """
    Preserve full bounds, strict witnesses and pair counts independently of geometry payload hashing.

    These are analytical material-pair controls, not complete configuration coverage.
    """
    source = (
        _route((Straight(2), fold(2, 1.2, 1.3, 0, 2), Straight(2)))
        if kind == "fold"
        else _parallel(0.2 if kind == "overlap" else 1.2)
    )
    expected = contact.inspect_contact(
        source, maximum_pairs=512, cap_policy=CapPolicy.ANALYTIC_SUPPORT
    )
    guarded = replace(
        source,
        pieces=tuple(
            _HashGuardPiece(piece.pose, piece.geometry, piece.label) for piece in source.pieces
        ),
    )
    measured = contact.inspect_contact(
        guarded, maximum_pairs=512, cap_policy=CapPolicy.ANALYTIC_SUPPORT
    )
    assert measured == expected


@pytest.mark.parametrize("gap", (0.2, 1.0, 1.2))
@pytest.mark.parametrize("chunk", (1, 7, 31))
@pytest.mark.parametrize("reuse", tuple(contact.ProjectionReuse))
def test_chunked_contact_preserves_complete_cell_order_and_final_result(
    gap: float, chunk: int, reuse: contact.ProjectionReuse, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Match every clipped material cell, strict witness and count against uninterrupted execution.
    """
    source = _parallel(gap)
    trace: list[Cell] = []
    original = contact.clip_profile

    def track(cell: Cell, lines: int, diameter: float) -> Cell | None:
        """
        Observe the actual material-cell sequence without replacing its computation.
        """
        trace.append(cell)
        return original(cell, lines, diameter)

    monkeypatch.setitem(vars(contact), "clip_profile", track)
    expected = contact.inspect_contact(source, maximum_pairs=128, projection_reuse=reuse)
    expected_trace = trace.copy()
    trace.clear()
    traversal = ContactTraversal(source, maximum_pairs=128, projection_reuse=reuse)
    measurements: list[contact.ContactResult] = []
    for limit in range(chunk, 128 + chunk, chunk):
        current = traversal.advance(min(limit, 128))
        measurements.append(current)
        assert current.pairs_checked <= min(limit, 128)
        if current.limit != "pairs":
            break
    measured = measurements[-1]
    assert measured == expected
    assert trace == expected_trace
    assert traversal.advance(128) is measured
    assert trace == expected_trace
    if gap == 0.2:
        assert measured.status == "penetration" and measured.witness is not None
        for index in measured.witness.pieces:
            assert (
                occupied_coordinates(
                    source.pieces[index],
                    measured.witness.point,
                    source.targets.lines,
                    source.targets.diameter_mm,
                )
                is not None
            )
    elif gap == 1.2:
        assert measured.status == "separated"


def test_original_ceiling_and_monotone_limits_cannot_be_renewed() -> None:
    """
    Reject malformed, decreasing and enlarged limits while retaining a genuine pending pair.
    """
    traversal = ContactTraversal(_parallel(0.75), maximum_pairs=4)
    first = traversal.advance(1)
    assert first.status == "unresolved" and first.limit == "pairs" and first.pairs_checked == 1
    assert traversal.advance(1) is first
    for invalid in (0, True, 5, 1.5):
        with pytest.raises(ValueError):
            traversal.advance(cast(int, invalid))
    result = traversal.advance(4)
    assert result.pairs_checked <= 4
    with pytest.raises(ValueError):
        traversal.advance(1)


def test_cancellation_between_chunks_permanently_invalidates_traversal() -> None:
    """
    Propagate the original cancellation before resumed geometry and disallow another attempt.
    """
    cancelled = False

    def checkpoint() -> None:
        """
        Cancel only after the first actual suspension.
        """
        if cancelled:
            raise InterruptedError("original source cancellation")

    traversal = ContactTraversal(_parallel(0.75), maximum_pairs=128, checkpoint=checkpoint)
    assert traversal.advance(1).limit == "pairs"
    cancelled = True
    with pytest.raises(InterruptedError, match="source cancellation"):
        traversal.advance(128)
    with pytest.raises(RuntimeError, match="cannot resume"):
        traversal.advance(128)


@pytest.mark.parametrize("policy", tuple(CapPolicy))
def test_depth_exhaustion_is_final_and_geometry_cannot_be_rebound(policy: CapPolicy) -> None:
    """
    Extra pair availability cannot override the fixed depth gate or transfer proof to another route.
    """
    source = _parallel(1.0)
    traversal = ContactTraversal(source, maximum_pairs=128, maximum_depth=1, cap_policy=policy)
    first = traversal.advance(64)
    assert first.limit == "depth"
    assert traversal.advance(128) is first
    changed = _parallel(1.2)
    assert ContactTraversal(changed, maximum_pairs=128).advance(128).status == "separated"
    assert traversal.advance(128) is first


@pytest.mark.parametrize("bank", (-0.3, 0.0, 0.3))
@pytest.mark.parametrize("policy", tuple(CapPolicy))
def test_curved_subdivision_retains_the_original_pending_pair(
    bank: float, policy: CapPolicy
) -> None:
    """
    Match curved return subdivision, including shared-cap treatment, under uneven chunking.
    """
    source = _route((fold(2, 1.2, pi, bank, 0), fold(2, 1.2, pi, -bank, 0)))
    expected = contact.inspect_contact(source, maximum_pairs=256, cap_policy=policy)
    traversal = ContactTraversal(source, maximum_pairs=256, cap_policy=policy)
    results = [traversal.advance(limit) for limit in (1, 5, 29, 128, 256)]
    assert results[-1] == expected
    assert all(a.pairs_checked <= b.pairs_checked for a, b in zip(results, results[1:]))
    assert results[0].pairs_checked <= 1
