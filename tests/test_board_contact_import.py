"""
Board pad parsing and conservative contact matching regressions.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from cable_bundler.application.board_contact_import import (
    BoardPad,
    ContactFootprint,
    analyze_board_contacts,
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


@pytest.mark.parametrize("archive", [False, True])
def test_read_fusion_board_accepts_xml_and_archive(tmp_path: Path, archive: bool) -> None:
    """
    Import a local Fusion board through the same pad placement path as .brd.
    """
    board = tmp_path / "example.fbrd"
    xml = (
        '<eagle><drawing><board><libraries><library name="L"><packages>'
        '<package name="P"><smd name="1" x="1" y="0" dx="0.8" dy="0.4" layer="1"/>'
        "</package></packages></library></libraries><elements>"
        '<element name="J1" library="L" package="P" x="10" y="20"/>'
        '</elements><signals><signal name="GND"><contactref element="J1" pad="1"/>'
        "</signal></signals></board></drawing></eagle>"
    )
    if archive:
        with ZipFile(board, "w") as contents:
            contents.writestr("board/layout.brd", xml)
    else:
        board.write_text(xml, encoding="utf-8")
    pads = read_eagle_board(board)
    assert len(pads) == 1
    assert (pads[0].label, pads[0].x, pads[0].y, pads[0].signal) == ("J1.1", 11, 20, "GND")


def test_read_fusion_board_rejects_ambiguous_archive(tmp_path: Path) -> None:
    """
    Never guess which board supplies contact names in a malformed archive.
    """
    board = tmp_path / "ambiguous.fbrd"
    xml = "<eagle><drawing><board/></drawing></eagle>"
    with ZipFile(board, "w") as contents:
        contents.writestr("first.brd", xml)
        contents.writestr("second.brd", xml)
    with pytest.raises(ValueError, match="one Eagle board"):
        read_eagle_board(board)


def test_match_board_contacts_rejects_ambiguous_and_wrong_layer() -> None:
    """
    A pad must be the unique position and layer match in both directions.
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


def test_through_hole_matching_uses_position_for_face_or_edge() -> None:
    """
    Match either copper side even when 3D and nominal 2D sizes differ.
    """
    pad = BoardPad("J3.03", 1.781, 42.421, 1.37, 1.37, 0, "P1.09", 1.02)
    for layer in (1, 16):
        contact = ContactFootprint("a", 1.781, 42.421, 1.53, 1.53, layer, 0.95)
        assert match_board_contacts([contact], [pad]) == {"a": pad}
        assert match_board_contacts([contact], [pad, pad]) == {}
    solid = ContactFootprint("solid", 1.781, 42.421, 1.37, 1.37, 1)
    edge = ContactFootprint("edge", 1.781, 42.421, 0.5, 0.5, 1)
    assert match_board_contacts([solid], [pad]) == {"solid": pad}
    assert match_board_contacts([edge], [pad]) == {"edge": pad}
    assert match_board_contacts([solid, edge], [pad]) == {}


def test_split_noncircular_face_matches_only_its_containing_pad() -> None:
    """
    Use a selected rectangular pad fragment without requiring a circular edge.
    """
    pad = BoardPad("U1.1", 1, 2, 0.8, 1.2, 1)
    fragment = ContactFootprint("split", 1.3, 2.1, 0.2, 0.3, 1)
    assert match_board_contacts([fragment], [pad]) == {"split": pad}
    other_fragment = ContactFootprint("split", 0.7, 1.9, 0.2, 0.3, 1)
    assert match_board_contacts([fragment, other_fragment], [pad]) == {"split": pad}
    displaced = ContactFootprint("split", 2, 2, 0.2, 0.3, 1)
    assert match_board_contacts([fragment, displaced], [pad]) == {}
    overlapping = BoardPad("U2.1", 1.45, 2.1, 0.6, 0.8, 1)
    assert match_board_contacts([fragment], [pad, overlapping]) == {}
    unrelated = ContactFootprint("trace", 1.3, 2.1, 2.0, 0.3, 1)
    assert match_board_contacts([unrelated], [pad]) == {}


def test_analysis_exposes_ambiguous_and_disagreeing_fragment_pad_values() -> None:
    """
    Review receives every plausible value while automatic matching stays strict.
    """
    left = BoardPad("J1.1", 0, 0, 0.8, 0.8, 1)
    right = BoardPad("J1.2", 1, 0, 0.8, 0.8, 1)
    contacts = [
        ContactFootprint("split", 0, 0, 0.2, 0.2, 1),
        ContactFootprint("split", 1, 0, 0.2, 0.2, 1),
        ContactFootprint("conflict", 0, 0, 0.2, 0.2, 1),
        ContactFootprint("unmatched", 5, 5, 0.2, 0.2, 1),
    ]
    analysis = analyze_board_contacts(contacts, [left, right])
    assert analysis.matches == {"conflict": left}
    assert analysis.suggestions == {
        "split": (left, right),
        "unmatched": (),
    }
    assert analyze_board_contacts(
        [ContactFootprint("ambiguous", 0, 0, 0.2, 0.2, 1)], [left, left]
    ).suggestions == {"ambiguous": (left, left)}
    assert analyze_board_contacts(
        [ContactFootprint("a", 0, 0, 0.2, 0.2, 1), ContactFootprint("b", 0, 0, 0.2, 0.2, 1)], [left]
    ).suggestions == {"a": (left,), "b": (left,)}


def test_read_eagle_board_places_through_hole_contacts(tmp_path: Path) -> None:
    """
    Project through-hole pad positions using the same placement as SMDs.
    """
    board = tmp_path / "mixed.brd"
    board.write_text(
        '<eagle><drawing><board><libraries><library name="L"><packages>'
        '<package name="P"><pad name="P1" x="1" y="0" drill="0.8" diameter="1.2"/>'
        '<pad name="P2" x="2" y="0" drill="0.8" diameter="1.2"/>'
        '<smd name="S1" x="0" y="1" dx="0.6" dy="0.5" layer="1"/>'
        "</package></packages></library></libraries><elements>"
        '<element name="J1" library="L" package="P" x="10" y="20" rot="R90"/>'
        '</elements><signals><signal name="GND"><contactref element="J1" pad="P1"/>'
        "</signal></signals></board></drawing></eagle>",
        encoding="utf-8",
    )
    pads = read_eagle_board(board)
    assert {pad.label for pad in pads} == {"J1.P1", "J1.P2", "J1.S1"}
    through_hole = next(pad for pad in pads if pad.label == "J1.P1")
    assert (through_hole.x, through_hole.y, through_hole.layer) == pytest.approx((10, 21, 0))
    assert through_hole.drill_diameter_mm == pytest.approx(0.8)
    assert through_hole.signal == "GND"
    unconnected = next(pad for pad in pads if pad.label == "J1.P2")
    assert (unconnected.x, unconnected.y, unconnected.signal) == (10, 22, "")


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
