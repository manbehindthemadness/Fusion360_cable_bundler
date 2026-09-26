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


def test_matching_face_resolutions_share_a_contact_but_disagreement_is_rejected(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Collapse the two Z-separated pad faces only when their 2D identity agrees.
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
    assert len(footprints) == 1
    assert (
        footprints[0].x,
        footprints[0].y,
        footprints[0].width,
        footprints[0].height,
        footprints[0].hole_diameter_mm,
    ) == pytest.approx((0, 0, 1.53, 1.53, 0.95))
    faces[1] = _face(x=0.5)
    assert module._contact_footprints(design, interface) == []


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
        lambda *_: [ContactFootprint(str(contact_id), 1, 2, 1.53, 1.53, 1, 0.95)],
    )
    monkeypatch.setitem(vars(module), "name_interface_contacts", persist)
    notice = module.import_interface_contact_names(object(), harness_id, interface_id, "live")
    persist.assert_called_once_with(
        harness_id, interface_id, {contact_id: "J3.03 (P1.09)"}, gateway
    )
    assert notice == "Named 1 of 2 Interface contacts; 1 unchanged."
