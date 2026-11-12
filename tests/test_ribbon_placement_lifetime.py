"""
Release completed numerical models promptly while preserving exact bounded placement behavior.
"""

from __future__ import annotations

import gc
import weakref

import pytest

from experiments.experiment_ribbon_fold_relaxation.placement_cache import placement_cache
from experiments.experiment_ribbon_fold_relaxation.prefixes import PrefixModel
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from tests.test_ribbon_aesthetic import _route


def test_model_and_prefix_owner_release_without_cyclic_collection() -> None:
    """
    Keeping pure query handles and placed geometry cannot retain either model after its owner is dropped.
    """
    original = _route((Straight(2), fold(2, 1.2, 1, 0.2, 0), Straight(3)))
    enabled = gc.isenabled()
    gc.disable()
    try:
        model = SignedJoints(original)
        values = model.initial
        pieces = model.pieces(values)
        model_reference, full_reference = weakref.ref(model), weakref.ref(model.full)
        query, prefix_query = model._placements, model.full._prefixes
        full_values = model.expanded(values)
        del model
        assert model_reference() is None and full_reference() is None
        assert query(values) is pieces
        assert prefix_query(full_values) == pieces
        with pytest.raises(ReferenceError, match="outlived"):
            query((values[0] + 1e-5,) + values[1:])
    finally:
        if enabled:
            gc.enable()


def test_cached_prefix_preserves_subclass_dispatch_and_identical_hit() -> None:
    """
    Bind the actual override, retaining recursive prefix behavior and ordinary cache hits.
    """
    calls: list[tuple[float, ...]] = []

    class ObservedPrefix(PrefixModel):
        """
        Observe a specialized placement entry point without changing its geometry.
        """

        def _prefix(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
            """
            Delegate to the original immutable prefix implementation after recording dispatch.
            """
            calls.append(values)
            return super()._prefix(values)

    model = ObservedPrefix(_route((Straight(2), fold(2, 1.2, 1, 0.2, 0), Straight(3))))
    first = model.pieces(model.initial)
    count = len(calls)
    assert count > 0 and model.pieces(model.initial) is first
    assert len(calls) == count


def test_failed_placement_queries_propagate_and_are_not_retained() -> None:
    """
    A hard caller failure cannot become a cached numerical result or suppress a later actual evaluation.
    """

    class Owner:
        """
        Supply a weak-referenceable query lifetime independent of any geometry fixture.
        """

        attempts = 0

        def place(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
            """
            Fail twice before returning a successful empty placement.
            """
            del values
            self.attempts += 1
            if self.attempts < 3:
                raise RuntimeError("source failure")
            return ()

    owner = Owner()
    query = placement_cache(owner, Owner.place)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="source failure"):
            query((1.0,))
    assert query((1.0,)) == query((1.0,)) == ()
    assert owner.attempts == 3
