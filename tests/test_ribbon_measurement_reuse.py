"""
Verify model-owned placement bounds and unchanged full-contact reports under preparation reuse.
"""

from __future__ import annotations

from typing import Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, prepare_projection
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route

Prepare = Callable[[PlacedPiece, Vector3], Callable[[Cell], Span]]


def test_joint_placements_are_exact_bounded_and_owned_by_each_model() -> None:
    """
    Reuse identical immutable coordinates without globally retaining models or unbounded histories.
    """
    source = _route((fold(1, 1.2, 1, 0.2, 0), Straight(3)))
    model, other = MovableBends(source), MovableBends(source)
    original = model.pieces(model.initial)
    assert model.pieces(model.initial) is original
    assert original == model._place(model.initial) == other.pieces(other.initial)
    assert other.pieces(other.initial) is not original
    for index in range(63):
        values = (model.initial[0] + (index + 1) / 100,) + model.initial[1:]
        assert model.pieces(values) == model._place(values)
    assert model.pieces(model.initial) is original
    for index in range(63, 127):
        values = (model.initial[0] + (index + 1) / 100,) + model.initial[1:]
        assert model.pieces(values) == model._place(values)
    assert model.pieces(model.initial) == original
    assert model.pieces(model.initial) is not original
    with pytest.raises(ValueError, match="bounds"):
        model.pieces((-1.0,) + model.initial[1:])


@pytest.mark.parametrize("policy", tuple(CapPolicy))
@pytest.mark.parametrize("maximum_pairs", (64, 1024))
def test_contact_reuse_keeps_every_report_field_and_pair_count(
    monkeypatch: pytest.MonkeyPatch,
    policy: CapPolicy,
    maximum_pairs: int,
) -> None:
    """
    Repeated prepared transforms save work while witnesses, exhaustion and separation remain exact.
    """
    source = _route(
        (
            fold(1, 1.2, 2.5, 0.3, 0),
            Straight(3),
            fold(1, 1.2, -2, -0.2, 0),
            Straight(2),
            fold(1, 1.2, 1.5, 0.1, 0),
        )
    )
    prepare = Mock(wraps=prepare_projection)
    monkeypatch.setitem(vars(contact), "prepare_projection", prepare)
    reused = contact.inspect_contact(source, maximum_pairs=maximum_pairs, cap_policy=policy)
    prepared_calls = prepare.call_count
    prepare.reset_mock()

    def no_reuse(*, maxsize: int) -> Callable[[Prepare], Prepare]:
        """
        Run the same full material algorithm with fresh preparation on every projection.
        """
        assert maxsize == 64

        def unchanged(function: Prepare) -> Prepare:
            """
            Leave the exact projection preparation callable uncached.
            """
            return function

        return unchanged

    monkeypatch.setitem(vars(contact), "lru_cache", no_reuse)
    uncached = contact.inspect_contact(source, maximum_pairs=maximum_pairs, cap_policy=policy)
    assert reused == uncached
    assert prepared_calls < prepare.call_count
