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
    Use the saved on-face sample when no usable centroid exists.
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


def test_face_widget_uses_annular_contact_center(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Keep the hover marker on the same center anchor as the routed cable end.
    """
    from cable_bundler.domain import AttachmentTargetKind, CableEndAttachment

    graphics = importlib.import_module("cable_bundler.fusion.hover_graphics")
    center = SimpleNamespace(x=1.0, y=2.0, z=3.0)
    centroid = SimpleNamespace(x=1.2, y=2.0, z=3.0)
    on_face = SimpleNamespace(x=1.2, y=2.0, z=3.0)
    edge = SimpleNamespace(
        geometry=SimpleNamespace(objectType="adsk::core::Circle3D", center=center),
        assemblyContext=None,
    )
    coedges = SimpleNamespace(count=1, item=Mock(return_value=SimpleNamespace(edge=edge)))
    loops = SimpleNamespace(
        count=1, item=Mock(return_value=SimpleNamespace(isOuter=False, coEdges=coedges))
    )
    entity = SimpleNamespace(
        centroid=centroid,
        loops=loops,
        evaluator=SimpleNamespace(getPointAtParameter=Mock(return_value=(True, on_face))),
    )
    monkeypatch.setitem(
        vars(graphics),
        "adsk",
        SimpleNamespace(core=SimpleNamespace(Point2D=SimpleNamespace(create=lambda *uv: uv))),
    )
    target = CableEndAttachment(AttachmentTargetKind.FACE, "face", "Contact", parameters=(0.2, 0.8))

    assert graphics.target_point(entity, target) is center
