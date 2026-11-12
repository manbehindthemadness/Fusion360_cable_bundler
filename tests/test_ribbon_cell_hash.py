"""
Preserve immutable cell key identity while preparing its original tuple hash only once.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, fields, replace
from types import FunctionType
from typing import cast
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span


def _cell() -> Cell:
    """
    Supply one authored material box independent of any retained route.
    """
    return Cell(2, Span(0.1, 0.2), Span(-3.0, 3.0), Span(-0.5, 0.5), 4)


@pytest.mark.parametrize(
    "change",
    ({}, {"piece": 3}, {"depth": 5}, {"u": Span(-0.0, 1.0)}, {"height": Span(-5e-324, 5e-324)}),
)
def test_cell_hash_preserves_original_dataclass_key_semantics(change: dict[str, object]) -> None:
    """
    Match the previous tuple hash exactly, including signed zero, subnormals and equal independent objects.
    """
    cell = replace(_cell(), **change)
    expected = hash((cell.piece, cell.u, cell.q, cell.height, cell.depth))
    clone = replace(cell)
    assert hash(cell) == hash(cell) == hash(clone) == expected
    assert cell == clone and {cell: "material"}[clone] == "material"
    assert len({cell, clone}) == 1


def test_repeated_hashing_never_repeats_interval_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Amortize nested interval hashing while retaining a distinct preparation for a replacement cell.
    """
    original = cast(FunctionType, Span.__hash__)
    calls = Mock()

    def measured(interval: Span) -> int:
        """
        Count actual nested hash evaluations without replacing the immutable value's hash.
        """
        calls()
        return original(interval)

    monkeypatch.setattr(Span, original.__name__, measured)
    cell = _cell()
    first = hash(cell)
    assert calls.call_count == 3
    assert [hash(cell) for _ in range(20)] == [first] * 20
    assert calls.call_count == 3
    clone = replace(cell)
    assert hash(clone) == first and calls.call_count == 6


def test_prepared_hash_does_not_change_fields_freezing_or_split_identity() -> None:
    """
    Keep five-field receipts and independent child keys after the internal hash has been prepared.
    """
    cell = _cell()
    before = asdict(cell)
    assert hash(cell) == hash((cell.piece, cell.u, cell.q, cell.height, cell.depth))
    assert asdict(cell) == before
    assert tuple(field.name for field in fields(cell)) == ("piece", "u", "q", "height", "depth")
    with pytest.raises(FrozenInstanceError):
        setattr(cell, "u", Span(0, 1))  # noqa: B010 - exercise the frozen public setter
    first, second = cell.split(10)
    assert "_cached_hash" not in first.__dict__ and "_cached_hash" not in second.__dict__
    assert first != second and first.depth == second.depth == cell.depth + 1
    assert {cell: "parent", first: "first", second: "second"}[replace(first)] == "first"
