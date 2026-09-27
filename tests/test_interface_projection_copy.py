"""
Regressions for copying Interface fields by orientation-local positions.
"""

from __future__ import annotations

from uuid import UUID

from cable_bundler.application.interface_projection_copy import (
    OrientedContact,
    match_projected_interface_contacts,
)


def _contact(
    identity: int,
    x: float,
    y: float,
    z: float,
    axes: tuple[tuple[float, float, float], ...] | None = None,
) -> OrientedContact:
    """
    Build a horizontal contact in a chosen occurrence frame.
    """
    return OrientedContact(UUID(int=identity), (x, y, z), (0, 0, 1), axes)


def test_shifted_and_elevated_connector_matches_board_local_pattern() -> None:
    """
    Ignore assembly translation and Z while retaining the pin order in XY.
    """
    sources = tuple(_contact(index + 1, index * 2.5, 3, 0) for index in range(3))
    destinations = tuple(_contact(index + 11, 100 + index * 2.5, 40, 18) for index in range(3))
    assert match_projected_interface_contacts(destinations, sources) == {
        UUID(int=11 + index): UUID(int=1 + index) for index in range(3)
    }


def test_rotated_occurrence_axes_preserve_local_order() -> None:
    """
    A rotated connector compares its own local row to the board's local row.
    """
    rotated_axes = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))
    sources = (_contact(1, 0, 0, 0), _contact(2, 2.5, 0, 0))
    destinations = (
        _contact(11, 100, 40, 5, rotated_axes),
        _contact(12, 100, 42.5, 5, rotated_axes),
    )
    assert match_projected_interface_contacts(destinations, sources) == {
        UUID(int=11): UUID(int=1),
        UUID(int=12): UUID(int=2),
    }


def test_ambiguous_or_misaligned_patterns_do_not_guess() -> None:
    """
    Duplicate source positions and shifted pitches cannot silently copy data.
    """
    destinations = (_contact(11, 100, 40, 5), _contact(12, 102.5, 40, 5))
    sources = (_contact(1, 0, 0, 0), _contact(2, 0, 0, 0))
    assert match_projected_interface_contacts(destinations, sources) == {}
    wrong_pitch = (_contact(1, 0, 0, 0), _contact(2, 3, 0, 0))
    assert match_projected_interface_contacts(destinations, wrong_pitch) == {
        UUID(int=11): UUID(int=1)
    }
