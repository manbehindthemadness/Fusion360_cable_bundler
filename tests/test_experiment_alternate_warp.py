"""
Retain exact terminal sections when decimating diagnostic loft inputs.
"""

import pytest

from experiments.experiment_ribbon_cap_transition.alternate_warp_native import selected_sections


@pytest.mark.parametrize(
    "count,expected", ((2, (1, 2)), (5, (1, 3, 5)), (6, (1, 3, 5, 6)), (32, (*range(1, 32, 2), 32)))
)
def test_alternate_sampling_preserves_terminals(count: int, expected: tuple[int, ...]) -> None:
    """
    No terminal is dropped and selected references stay in original traversal order.
    """
    assert selected_sections(count) == expected


def test_two_terminals_are_required() -> None:
    """
    Reject an invalid profile sequence before a native operation.
    """
    with pytest.raises(ValueError):
        selected_sections(1)
