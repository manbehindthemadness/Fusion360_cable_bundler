"""
Regression coverage for local planar rectangle membership and validation.
"""

import math
from dataclasses import replace

import pytest

from cable_bundler.application.interface_contact_planes import (
    contact_rectangle,
    select_contact_plane,
)
from cable_bundler.application.interface_contact_rows import RowTarget
from cable_bundler.domain import AttachmentTargetKind


@pytest.mark.parametrize("angle", [0, 0.7, 1.57, 2.8])
def test_plane_membership_is_local_and_excludes_other_depths(angle: float) -> None:
    """
    Include interior and boundary centers, even when the entire board is tilted.
    """
    c, s = math.cos(angle), math.sin(angle)
    axes = [(c, 0, s), (0, 1, 0), (-s, 0, c)]

    def target(token: str, x: float, y: float, z: float = 0) -> RowTarget:
        """
        Place a pad into a rotated and translated board frame.
        """
        return RowTarget(
            token,
            AttachmentTargetKind.FACE,
            "Plane",
            (10 + x * c - z * s, 20 + y, 30 + x * s + z * c),
            axes[2],
        )

    first, last = target("first", 0, 0), target("last", 4, 3)
    middle, edge = target("middle", 2, 1), target("edge", 4, 1)
    candidates = [
        middle,
        edge,
        target("outside", 5, 1),
        target("rear", 2, 1, 0.01),
        replace(middle, token="back", normal=tuple(-v for v in axes[2])),
        replace(middle, token="other", geometry_type="Cylinder"),
        middle,
    ]
    rectangle = contact_rectangle(first, last, axes)
    assert [item.token for item in select_contact_plane(rectangle, candidates)] == [
        "first",
        "middle",
        "edge",
        "last",
    ]
    reverse = contact_rectangle(last, first, axes)
    assert [item.token for item in select_contact_plane(reverse, candidates)] == [
        "last",
        "edge",
        "middle",
        "first",
    ]
    low, high = rectangle.bounds()
    assert all(low[i] <= middle.center_mm[i] <= high[i] for i in range(3))


@pytest.mark.parametrize(
    "end, message", [((0, 3, 0), "diagonal"), ((4, 0, 0), "diagonal"), ((4, 3, 0.01), "same plane")]
)
def test_plane_rejects_degenerate_or_noncoplanar_corners(
    end: tuple[float, float, float], message: str
) -> None:
    """
    Do not silently guess a rectangle for an invalid two-pick definition.
    """
    first = RowTarget("first", AttachmentTargetKind.FACE, "Plane", (0, 0, 0), (0, 0, 1))
    with pytest.raises(ValueError, match=message):
        contact_rectangle(
            first, replace(first, token="last", center_mm=end), [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
        )
