"""
Finite row selection, directed orientation, and parent-frame invariance.
"""

import math
from dataclasses import replace

import pytest

from cable_bundler.application.interface_contact_rows import RowTarget, select_contact_row
from cable_bundler.domain import AttachmentTargetKind


def _target(token: str, x: float, y: float = 0, z: float = 0) -> RowTarget:
    """
    Make a planar contact center with a forward-facing normal.
    """
    return RowTarget(token, AttachmentTargetKind.FACE, "Plane", (x, y, z), (0, 0, 1))


def test_row_includes_endpoints_and_rejects_other_rows_sides_types_and_outside() -> None:
    """
    Collect only compatible centers on the finite segment, in either pick order.
    """
    first, last = _target("first", 0), _target("last", 10)
    middle = _target("middle", 5, 0.02)
    candidates = [
        last,
        middle,
        first,
        middle,
        _target("neighbor", 5, 1),
        _target("below", 5, 0, -0.05),
        _target("before", -1),
        _target("after", 11),
        replace(_target("back", 5), normal=(0, 0, -1)),
        replace(_target("edge", 5), kind=AttachmentTargetKind.CIRCULAR_EDGE),
        replace(_target("cylinder", 5), geometry_type="Cylinder"),
    ]
    assert [item.token for item in select_contact_row(first, last, candidates)] == [
        "first",
        "middle",
        "last",
    ]
    assert [item.token for item in select_contact_row(last, first, candidates)] == [
        "last",
        "middle",
        "first",
    ]


@pytest.mark.parametrize("angle", [0.4, 1.2, math.pi / 2, math.pi])
def test_row_membership_survives_parent_rotation_and_translation(angle: float) -> None:
    """
    A tilted board retains its row membership without a global-Z assumption.
    """

    def rotate(vector: tuple[float, float, float]) -> tuple[float, float, float]:
        """
        Rotate through two planes so no input axis is treated as special.
        """
        x, y, z = vector
        c, s = math.cos(angle), math.sin(angle)
        return c * x - s * z, s * x + c * z, y

    def move(target: RowTarget) -> RowTarget:
        """
        Express a contact in the transformed assembly frame.
        """
        x, y, z = rotate(target.center_mm)
        assert target.normal is not None
        return replace(target, center_mm=(x + 40, y - 20, z + 7), normal=rotate(target.normal))

    first, last = move(_target("first", 0)), move(_target("last", 10))
    candidates = [move(_target("middle", 5)), move(_target("off", 5, 0.5))]
    assert [item.token for item in select_contact_row(first, last, candidates)] == [
        "first",
        "middle",
        "last",
    ]


@pytest.mark.parametrize(
    "last",
    [
        _target("first", 10),
        _target("last", 0),
        replace(_target("last", 10), normal=(0, 0, -1)),
        replace(_target("last", 10), kind=AttachmentTargetKind.PROFILE),
    ],
)
def test_invalid_endpoints_fail_before_collecting_candidates(last: RowTarget) -> None:
    """
    Reject identical centers, repeated picks, and incompatible endpoint geometry.
    """
    with pytest.raises(ValueError):
        select_contact_row(_target("first", 0), last, ())
