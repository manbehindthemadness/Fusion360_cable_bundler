"""
Geometry and sizing invariants for connection-face circle packing.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.domain.connection_packing import (
    PackedConnection,
    pack_connections,
    required_parent_diameter,
)


def _assert_valid_pack(circles: tuple[PackedConnection, ...], parent_mm: float) -> None:
    """
    Require every disk to lie inside its parent without touching siblings.
    """
    for index, circle in enumerate(circles):
        assert math.hypot(circle.x_mm, circle.y_mm) + circle.diameter_mm / 2 <= (
            parent_mm / 2 + 1e-7
        )
        for sibling in circles[index + 1 :]:
            assert (
                math.hypot(circle.x_mm - sibling.x_mm, circle.y_mm - sibling.y_mm)
                >= (circle.diameter_mm + sibling.diameter_mm) / 2 - 1e-7
            )


@pytest.mark.parametrize("count", (2, 3, 4, 8, 24, 100))
def test_auto_siblings_pack_inside_parent_with_slack(count: int) -> None:
    """
    Pack small and large equal-size batches without wedge-shaped diameter division.
    """
    circles = pack_connections(10.0, (None,) * count)

    assert circles is not None
    assert len(circles) == count
    if count >= 3:
        assert circles[0].diameter_mm > 10.0 / count
    assert len({circle.diameter_mm for circle in circles}) == 1
    assert pack_connections(10.0, (None,) * count) == circles
    _assert_valid_pack(circles, 10.0)


def test_mixed_explicit_and_auto_disks_share_parent_area() -> None:
    """
    Preserve fixed sizes while automatically filling the remaining face area.
    """
    circles = pack_connections(10.0, (3.0, None, 2.0, None))

    assert circles is not None
    assert circles[0].diameter_mm == 3.0
    assert circles[2].diameter_mm == 2.0
    assert circles[1].diameter_mm == circles[3].diameter_mm
    _assert_valid_pack(circles, 10.0)


def test_large_mixed_batch_packs_around_fixed_contact() -> None:
    """
    Keep a large automatic batch responsive around one fixed-size branch.
    """
    circles = pack_connections(10.0, (1.0,) + (None,) * 99)

    assert circles is not None
    assert circles[0].diameter_mm == 1.0
    assert len(circles) == 100
    _assert_valid_pack(circles, 10.0)


def test_fixed_disks_need_geometric_fit_not_diameter_sum() -> None:
    """
    Accept a circle pack whose diameter sum exceeds its parent diameter.
    """
    circles = pack_connections(10.0, (4.0, 4.0, 4.0))

    assert circles is not None
    assert sum(circle.diameter_mm for circle in circles) > 10.0
    _assert_valid_pack(circles, 10.0)
    assert pack_connections(7.0, (4.0, 4.0)) is None
    assert required_parent_diameter((4.0, 4.0)) == pytest.approx(8.0)
