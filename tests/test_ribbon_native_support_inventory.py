"""
Check exact native support identity without accepting parameter reordering or malformed captures.
"""

from __future__ import annotations

from typing import Any

import pytest

from artifacts.verification.resume3363.native import surface_key
from cable_bundler.routing.geometry import Vector3


def capture() -> tuple[Any, ...]:
    """
    Supply a complete synthetic positive-weight planar tensor observation.
    """
    return (
        True,
        1,
        1,
        2,
        2,
        (Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(1, 1, 0)),
        (0, 0, 1, 1),
        (0, 0, 1, 1),
        (1, 2, 3, 4),
        0,
        0,
    )


def test_inventory_ignores_only_common_weight_scale() -> None:
    """
    Weight normalization preserves the curve while point, knot and weight changes remain distinct.
    """
    data = capture()
    scaled = (*data[:8], tuple(2 * value for value in data[8]), *data[9:])
    assert surface_key(data) == surface_key(scaled)
    reordered = (*data[:5], tuple(reversed(data[5])), *data[6:])
    assert surface_key(data) != surface_key(reordered)
    changed = (*data[:8], (1, 2, 3, 5), *data[9:])
    assert surface_key(data) != surface_key(changed)


@pytest.mark.parametrize("weights", [(1, 2, 3), (1, 2, 3, 0), (1, 2, 3, -1)])
def test_incomplete_or_nonpositive_native_observations_reject(weights: tuple[int, ...]) -> None:
    """
    Missing controls or invalid rational denominators cannot acquire a support identity.
    """
    data = capture()
    with pytest.raises(RuntimeError, match="Complete positive-weight"):
        surface_key((*data[:8], weights, *data[9:]))
