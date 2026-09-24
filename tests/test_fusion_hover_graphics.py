"""
Regressions for transient node-local viewport markers.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.fusion_ui_support import _PaletteLifecycleModule


def test_crosses_are_view_scaled_nonselectable_and_deduplicated(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Draw three centered axes once per contact point and replace prior hover graphics.
    """
    graphics = importlib.import_module("cable_bundler.fusion.hover_graphics")
    old = SimpleNamespace(id=graphics._GROUP_ID, deleteMe=Mock())
    lines = Mock(spec_set=["color", "weight", "isSelectable", "depthPriority", "viewScale"])
    group = SimpleNamespace(addLines=Mock(return_value=lines))
    groups = SimpleNamespace(count=1, item=lambda _index: old, add=Mock(return_value=group))
    design = SimpleNamespace(rootComponent=SimpleNamespace(customGraphicsGroups=groups))
    scale = object()
    show_through = object()
    monkeypatch.setitem(
        vars(graphics),
        "adsk",
        SimpleNamespace(
            core=SimpleNamespace(Color=SimpleNamespace(create=lambda *rgba: rgba)),
            fusion=SimpleNamespace(
                CustomGraphicsCoordinates=SimpleNamespace(create=lambda values: values),
                CustomGraphicsViewScale=SimpleNamespace(create=Mock(return_value=scale)),
                CustomGraphicsShowThroughColorEffect=SimpleNamespace(
                    create=Mock(return_value=show_through)
                ),
            ),
        ),
    )
    point = SimpleNamespace(x=2.0, y=3.0, z=4.0)

    graphics.show_hover_widgets(design, (point, point))

    old.deleteMe.assert_called_once()
    group.addLines.assert_called_once_with(
        [
            -18.0,
            3.0,
            4.0,
            22.0,
            3.0,
            4.0,
            2.0,
            -17.0,
            4.0,
            2.0,
            23.0,
            4.0,
            2.0,
            3.0,
            -16.0,
            2.0,
            3.0,
            24.0,
        ],
        [],
        False,
    )
    assert lines.viewScale is scale
    assert lines.color is show_through
    assert not lines.isSelectable
    assert lines.weight == 4.0
    assert lines.depthPriority == 100
    graphics.adsk.fusion.CustomGraphicsViewScale.create.assert_called_once_with(1.0, point)
    graphics.adsk.fusion.CustomGraphicsShowThroughColorEffect.create.assert_called_once_with(
        (232, 78, 180, 255), 0.98
    )


def test_face_widget_uses_saved_contact_parameters(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Place the widget at the node's saved contact, not the face or body center.
    """
    from cable_bundler.domain import AttachmentTargetKind, CableEndAttachment

    graphics = importlib.import_module("cable_bundler.fusion.hover_graphics")
    point = object()
    entity = SimpleNamespace(
        evaluator=SimpleNamespace(getPointAtParameter=Mock(return_value=(True, point)))
    )
    monkeypatch.setitem(
        vars(graphics),
        "adsk",
        SimpleNamespace(core=SimpleNamespace(Point2D=SimpleNamespace(create=lambda *uv: uv))),
    )
    target = CableEndAttachment(AttachmentTargetKind.FACE, "face", "Contact", parameters=(0.2, 0.8))

    assert graphics.target_point(entity, target) is point
    entity.evaluator.getPointAtParameter.assert_called_once_with((0.2, 0.8))
