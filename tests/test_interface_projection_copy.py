"""
Regressions for copying Interface fields by actual projected geometry.
"""

from __future__ import annotations

from uuid import UUID

from cable_bundler.application.interface_projection_copy import (
    OrientedContact,
    match_projected_interface_contacts,
    projected_interface_candidates,
)


def _contact(
    identity: int,
    x: float,
    y: float,
    z: float,
    normal: tuple[float, float, float] = (0, 0, 1),
) -> OrientedContact:
    """
    Build an assembly-space contact with a known source-facing normal.
    """
    return OrientedContact(UUID(int=identity), (x, y, z), normal)


def test_live_connector_matches_j4_not_distant_j3_pattern() -> None:
    """
    Match actual J4.17–19 positions despite a small XY offset and large Z gap.
    """
    destinations = tuple(
        _contact(index + 11, 12.1089525, 65.7959642 - index * 2.54, -9.4) for index in range(3)
    )
    j4 = tuple(
        _contact(index + 21, 11.8748964, 65.6750261 - index * 2.54, -20.3) for index in range(3)
    )
    j3 = tuple(
        _contact(index + 31, -13.5231036, 106.3150261 - index * 2.54, -20.3) for index in range(3)
    )
    assert match_projected_interface_contacts(destinations, j3 + j4) == {
        UUID(int=11 + index): UUID(int=21 + index) for index in range(3)
    }


def test_source_plane_ignores_only_normal_displacement() -> None:
    """
    Project into a tilted source plane, not the destination's local origin.
    """
    source = (_contact(1, 10, 20, 0, (0, 1, 0)),)
    assert match_projected_interface_contacts((_contact(11, 10.2, 200, 0.1),), source) == {
        UUID(int=11): UUID(int=1)
    }
    assert match_projected_interface_contacts((_contact(12, 12, 200, 0),), source) == {}


def test_dense_pad_ambiguity_is_returned_for_review() -> None:
    """
    Nearby dense pads remain distinct candidates instead of an arbitrary copy.
    """
    sources = (_contact(1, 0, 0, 0), _contact(2, 0.5, 0, 0))
    midpoint = (_contact(11, 0.25, 0, 10),)
    assert projected_interface_candidates(midpoint, sources) == {
        UUID(int=11): (UUID(int=1), UUID(int=2))
    }
    assert match_projected_interface_contacts(midpoint, sources) == {}
    assert match_projected_interface_contacts((_contact(12, 0, 0, 10),), sources) == {
        UUID(int=12): UUID(int=1)
    }
