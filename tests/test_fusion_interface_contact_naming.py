"""
Regressions for through-hole identity and conservative face resolution.
"""

import importlib
import math
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.application.board_contact_import import BoardPad, ContactFootprint
from cable_bundler.domain import AttachmentTargetKind, InterfaceContact, InterfaceTargetKind


def _face(x: float = 0.0, z: float = 0.0) -> SimpleNamespace:
    """
    Model an annular copper face with its inner loop first, as observed in Fusion.
    """
    hole = [
        [x + 0.475 * math.cos(i * math.pi / 8), 0.475 * math.sin(i * math.pi / 8), z]
        for i in range(17)
    ]
    outer = [
        [x - 0.765, -0.765, z],
        [x + 0.765, -0.765, z],
        [x + 0.765, 0.765, z],
        [x - 0.765, 0.765, z],
    ]
    native = [SimpleNamespace(isOuter=False), SimpleNamespace(isOuter=True)]
    return SimpleNamespace(
        assemblyContext=SimpleNamespace(fullPathName="PCB:1+1-copper:1"),
        sampled=[hole, outer],
        loops=SimpleNamespace(count=2, item=lambda index: native[index]),
    )


def test_matching_face_resolutions_share_a_contact_but_disagreement_has_no_pad(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep every valid face resolution for a common 2D pad identity check.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    monkeypatch.setitem(
        vars(module), "resolve_interface_target", lambda *_: SimpleNamespace(fullPathName="PCB:1")
    )
    monkeypatch.setitem(
        vars(module), "_frame", lambda _: ([0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    )
    monkeypatch.setitem(vars(module), "_face_loops", lambda face: face.sampled)
    faces = [_face(), _face(z=0.0954)]
    design = SimpleNamespace(findEntityByToken=lambda _: faces)
    contact = InterfaceContact(UUID(int=1), AttachmentTargetKind.FACE, "pad")
    interface = SimpleNamespace(
        targets=(SimpleNamespace(kind=InterfaceTargetKind.OCCURRENCE),), contacts=(contact,)
    )
    footprints = module._contact_footprints(design, interface)
    assert len(footprints) == 2
    assert (
        footprints[0].x,
        footprints[0].y,
        footprints[0].width,
        footprints[0].height,
        footprints[0].hole_diameter_mm,
    ) == pytest.approx((0, 0, 1.53, 1.53, 0.95))
    faces[1] = _face(x=0.5)
    divergent = module._contact_footprints(design, interface)
    pad = BoardPad("J1.1", 0, 0, 1.37, 1.37, 0)
    assert module.match_board_contacts(divergent, [pad]) == {}


def test_pos_import_persists_connector_pin_and_signal(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Save useful I/O labels through the existing transactional naming service.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    contact_id, interface_id, harness_id = UUID(int=1), UUID(int=2), UUID(int=3)
    interface = SimpleNamespace(interface_id=interface_id, contacts=(object(), object()))
    gateway = SimpleNamespace(read_harness_definition=lambda _: "saved")
    persist = Mock()
    monkeypatch.setitem(vars(module), "_require_active_design", lambda _: object())
    monkeypatch.setitem(vars(module), "_create_harness_gateway", lambda _: gateway)
    monkeypatch.setitem(vars(module), "loads", lambda _: SimpleNamespace(interfaces=(interface,)))
    monkeypatch.setitem(
        vars(module),
        "_live_board_pads",
        lambda _: [BoardPad("J3.03", 1, 2, 1.37, 1.37, 0, "P1.09", 1.02)],
    )
    monkeypatch.setitem(
        vars(module),
        "_contact_footprints",
        lambda *_, **_kwargs: [ContactFootprint(str(contact_id), 1, 2, 1.53, 1.53, 1, 0.95)],
    )
    monkeypatch.setitem(vars(module), "name_interface_contacts", persist)
    notice = module.import_interface_contact_names(object(), harness_id, interface_id, "live")
    persist.assert_called_once_with(
        harness_id, interface_id, {contact_id: "J3.03 (P1.09)"}, gateway
    )
    assert notice == "Named 1 of 2 Interface contacts; 1 unchanged."


def test_pos_import_preview_reports_conflicts_and_unmatched_without_edit(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Offer ambiguous PCB names and a blank fallback without persisting preview.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    harness_id, interface_id = UUID(int=10), UUID(int=11)
    contacts = tuple(
        SimpleNamespace(contact_id=UUID(int=index), name="old" if index == 3 else "")
        for index in range(1, 4)
    )
    interface = SimpleNamespace(interface_id=interface_id, contacts=contacts)
    gateway = SimpleNamespace(read_harness_definition=lambda _: "saved")
    persist = Mock()
    monkeypatch.setitem(vars(module), "_require_active_design", lambda _: object())
    monkeypatch.setitem(vars(module), "_create_harness_gateway", lambda _: gateway)
    monkeypatch.setitem(vars(module), "loads", lambda _: SimpleNamespace(interfaces=(interface,)))
    monkeypatch.setitem(vars(module), "name_interface_contacts", persist)
    monkeypatch.setitem(
        vars(module),
        "_contact_footprints",
        lambda *_: [
            ContactFootprint(str(UUID(int=1)), 0, 0, 0.2, 0.2, 1),
            ContactFootprint(str(UUID(int=2)), 1, 0, 0.2, 0.2, 1),
        ],
    )
    pads = [
        BoardPad("J1.1", 0, 0, 0.5, 0.5, 1, "GND"),
        BoardPad("J1.2", 1, 0, 0.5, 0.5, 1),
        BoardPad("J2.2", 1, 0, 0.5, 0.5, 1),
    ]
    preview = module.preview_interface_contact_names(object(), harness_id, interface_id, pads)
    assert preview == {
        "autoNames": [{"contactId": str(UUID(int=1)), "name": "J1.1 (GND)"}],
        "unresolved": [
            {
                "contactId": str(UUID(int=2)),
                "label": "Contact 2",
                "currentName": "",
                "suggestions": ["J1.2", "J2.2"],
            },
            {
                "contactId": str(UUID(int=3)),
                "label": "Contact 3",
                "currentName": "old",
                "suggestions": [],
            },
        ],
    }
    persist.assert_not_called()


def test_live_hole_measurement_does_not_sample_outlines(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Read the analytic circular hole without retaining or tessellating copper geometry.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    face = _face()
    face.geometry = SimpleNamespace(
        objectType="adsk::core::Plane", normal=SimpleNamespace(x=0, y=0, z=1)
    )
    edge = SimpleNamespace(
        assemblyContext=face.assemblyContext,
        geometry=SimpleNamespace(
            objectType="adsk::core::Circle3D", center=SimpleNamespace(x=1, y=2, z=0), radius=0.05
        ),
    )
    inner = SimpleNamespace(
        isOuter=False, coEdges=SimpleNamespace(count=1, item=lambda _: SimpleNamespace(edge=edge))
    )
    face.loops = SimpleNamespace(count=1, item=lambda _: inner)
    sampled = Mock(side_effect=AssertionError("No outline sampling expected"))
    monkeypatch.setitem(vars(module), "_face_loops", sampled)
    result = module._through_hole_footprint(
        face, "pad", "PCB:1", [0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    )
    assert result == ContactFootprint("pad", 10, 20, 1, 1, 1, 1)
    sampled.assert_not_called()


def test_circular_copper_edge_projects_to_board_local_pad_center(
    addin_module: object,
) -> None:
    """
    Allow a selected solderable edge to drive the same position lookup as a face.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    edge = SimpleNamespace(
        assemblyContext=SimpleNamespace(fullPathName="PCB:1+16-copper:2"),
        geometry=SimpleNamespace(
            objectType="adsk::core::Circle3D",
            center=SimpleNamespace(x=0.1, y=0.2, z=0),
            radius=0.05,
        ),
    )
    result = module._circular_edge_footprint(
        edge, "pad", "PCB:1", [0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    )
    assert result == ContactFootprint("pad", 1, 2, 1, 1, 16)


def test_split_outer_pad_arcs_keep_one_contact_center(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fragmented copper faces share the pad center through their outer arcs.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    monkeypatch.setitem(
        vars(module), "resolve_interface_target", lambda *_: SimpleNamespace(fullPathName="PCB:1")
    )
    monkeypatch.setitem(
        vars(module), "_frame", lambda _: ([0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    )
    sampled = Mock(side_effect=AssertionError("Outer arcs should avoid fragment sampling"))
    monkeypatch.setitem(vars(module), "_face_loops", sampled)

    def fragment(center_x: float) -> SimpleNamespace:
        """
        Model a copper fragment retaining only part of the outer circle.
        """
        context = SimpleNamespace(fullPathName="PCB:1+1-copper:1")
        edge = SimpleNamespace(
            assemblyContext=context,
            geometry=SimpleNamespace(
                objectType="adsk::core::Arc3D",
                center=SimpleNamespace(x=center_x, y=2.0, z=0.0),
                radius=0.075,
            ),
        )
        outer = SimpleNamespace(
            isOuter=True,
            coEdges=SimpleNamespace(count=1, item=lambda _: SimpleNamespace(edge=edge)),
        )
        return SimpleNamespace(
            assemblyContext=context,
            geometry=SimpleNamespace(
                objectType="adsk::core::Plane", normal=SimpleNamespace(x=0, y=0, z=1)
            ),
            loops=SimpleNamespace(count=1, item=lambda _: outer),
        )

    faces = [fragment(1.0), fragment(1.0)]
    design = SimpleNamespace(findEntityByToken=lambda _: faces)
    contact = InterfaceContact(UUID(int=4), AttachmentTargetKind.FACE, "split-pad")
    interface = SimpleNamespace(
        targets=(SimpleNamespace(kind=InterfaceTargetKind.OCCURRENCE),), contacts=(contact,)
    )
    assert module._contact_footprints(design, interface) == [
        ContactFootprint(str(contact.contact_id), 10, 20, 1.5, 1.5, 1),
        ContactFootprint(str(contact.contact_id), 10, 20, 1.5, 1.5, 1),
    ]
    sampled.assert_not_called()
    faces[1] = fragment(1.05)
    divergent = module._contact_footprints(design, interface)
    pad = BoardPad("J4.16", 10, 20, 1.5, 1.5, 0)
    assert module.match_board_contacts(divergent, [pad]) == {}


def test_split_rectangular_faces_match_the_same_board_pad(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Carry noncircular face fragments through to one common PCB-pad decision.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    monkeypatch.setitem(
        vars(module), "resolve_interface_target", lambda *_: SimpleNamespace(fullPathName="PCB:1")
    )
    monkeypatch.setitem(
        vars(module), "_frame", lambda _: ([0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    )
    monkeypatch.setitem(vars(module), "_face_loops", lambda face: face.sampled)

    def fragment(x: float) -> SimpleNamespace:
        """
        Model one selected piece of an otherwise rectangular SMD pad.
        """
        return SimpleNamespace(
            assemblyContext=SimpleNamespace(fullPathName="PCB:1+1-copper:1"),
            sampled=[
                [[x - 0.1, 1.85, 0], [x + 0.1, 1.85, 0], [x + 0.1, 2.15, 0], [x - 0.1, 2.15, 0]]
            ],
            loops=SimpleNamespace(count=1, item=lambda _: SimpleNamespace(isOuter=True)),
        )

    design = SimpleNamespace(findEntityByToken=lambda _: [fragment(0.7), fragment(1.3)])
    contact = InterfaceContact(UUID(int=5), AttachmentTargetKind.FACE, "rectangular-pad")
    interface = SimpleNamespace(
        targets=(SimpleNamespace(kind=InterfaceTargetKind.OCCURRENCE),), contacts=(contact,)
    )
    footprints = module._contact_footprints(design, interface)
    pad = BoardPad("U1.1", 1, 2, 0.8, 1.2, 1)
    assert len(footprints) == 2
    assert module.match_board_contacts(footprints, [pad]) == {str(contact.contact_id): pad}
