"""
Board pad parsing and conservative contact matching regressions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cable_bundler.application.board_contact_import import (
    BoardPad,
    ContactFootprint,
    match_board_contacts,
    read_eagle_board,
)


def test_read_eagle_board_applies_element_rotation_and_signals(tmp_path: Path) -> None:
    """
    Convert package-local pads to placed board coordinates and preserve nets.
    """
    board = tmp_path / "example.brd"
    board.write_text(
        '<eagle><drawing><board><libraries><library name="L"><packages>'
        '<package name="P"><smd name="1" x="1" y="0" dx="0.8" dy="0.4" layer="1"/>'
        "</package></packages></library></libraries><elements>"
        '<element name="J1" library="L" package="P" x="10" y="20" rot="R90"/>'
        '</elements><signals><signal name="GND"><contactref element="J1" pad="1"/>'
        "</signal></signals></board></drawing></eagle>",
        encoding="utf-8",
    )
    pads = read_eagle_board(board)
    assert len(pads) == 1
    assert pads[0].label == "J1.1"
    assert (pads[0].x, pads[0].y, pads[0].width, pads[0].height) == pytest.approx(
        (10, 21, 0.4, 0.8)
    )
    assert (pads[0].layer, pads[0].signal) == (1, "GND")


def test_match_board_contacts_rejects_ambiguous_and_wrong_layer() -> None:
    """
    A pad must be the unique position, layer, and size match in both directions.
    """
    contacts = [
        ContactFootprint("a", 10, 20, 0.8, 0.4, 1),
        ContactFootprint("b", 12, 20, 0.8, 0.4, 16),
    ]
    pads = [BoardPad("J1.1", 10, 20, 0.8, 0.4, 1)]
    assert match_board_contacts(contacts, pads) == {"a": pads[0]}
    assert match_board_contacts(contacts, pads * 2) == {}
    duplicate = ContactFootprint("c", 10, 20, 0.8, 0.4, 1)
    assert match_board_contacts([*contacts, duplicate], pads) == {}


def test_through_hole_matching_uses_hole_not_annulus_and_rejects_ambiguity() -> None:
    """
    Match plated holes on either copper side without naming solid SMD faces.
    """
    pad = BoardPad("J3.03", 1.781, 42.421, 1.37, 1.37, 0, "P1.09", 1.02)
    for layer in (1, 16):
        contact = ContactFootprint("a", 1.781, 42.421, 1.53, 1.53, layer, 0.95)
        assert match_board_contacts([contact], [pad]) == {"a": pad}
        assert match_board_contacts([contact], [pad, pad]) == {}
    solid = ContactFootprint("solid", 1.781, 42.421, 1.37, 1.37, 1)
    wrong_hole = ContactFootprint("wrong", 1.781, 42.421, 1.53, 1.53, 1, 0.5)
    assert match_board_contacts([solid, wrong_hole], [pad]) == {}


def test_read_eagle_board_handles_mirrored_placement_and_missing_file(tmp_path: Path) -> None:
    """
    Flip bottom-side pad placement while refusing an unreadable file.
    """
    board = tmp_path / "bottom.brd"
    board.write_text(
        '<eagle><drawing><board><libraries><library name="L"><packages>'
        '<package name="P"><smd name="1" x="1" y="0" dx="1" dy="0.5" layer="1"/>'
        "</package></packages></library></libraries><elements>"
        '<element name="J1" library="L" package="P" x="10" y="20" rot="MR0"/>'
        "</elements></board></drawing></eagle>",
        encoding="utf-8",
    )
    pad = read_eagle_board(board)[0]
    assert (pad.x, pad.y, pad.layer) == (9, 20, 16)
    with pytest.raises(ValueError, match="cannot be read"):
        read_eagle_board(tmp_path / "missing.brd")
