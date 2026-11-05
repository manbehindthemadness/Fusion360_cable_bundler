"""
Verify sweep-input retention preserves target poses, joined profiles and visibility.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.domain import CableGroupType
from cable_bundler.routing.geometry import Vector3, cross
from devtools.ribbon_analysis import end_profiles
from devtools.ribbon_analysis.contracts import Targets


class _Attributes:
    """
    Store native provenance stamps independently of user-visible sketch names.
    """

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], Any] = {}

    def add(self, group: str, name: str, value: str) -> None:
        """
        Preserve the latest value using the Fusion attribute-key contract.
        """
        self.values[group, name] = SimpleNamespace(value=value)

    # noinspection PyPep8Naming
    def itemByName(self, group: str, name: str) -> Any:
        """
        Return a retained stamp or the native missing-value sentinel.
        """
        return self.values.get((group, name))


def _targets(lines: int = 3) -> Targets:
    """
    Supply two distinct perpendicular target frames without authoring a route.
    """
    return Targets(
        "profile retention",
        Vector3(0, 0, 0),
        Vector3(8, 3, 2),
        Vector3(1, 0, 0),
        Vector3(0, 0, 1),
        Vector3(0, 1, 0),
        Vector3(0, -1, 0),
        lines,
        1.5,
    )


@pytest.fixture
def native_boundary(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Mock]:
    """
    Replace only native contour authoring, preserving actual retention decisions.
    """
    component = SimpleNamespace(attributes=_Attributes(), sketches=[])

    def author(owner: Any, targets: Targets, role: str) -> Any:
        """
        Retain one native sketch with one joined region at the requested cap.
        """
        assert owner is component and targets == _targets(targets.lines)
        assert role in ("start", "end")
        sketch = SimpleNamespace(attributes=_Attributes(), profiles=SimpleNamespace(count=1))
        component.sketches.append(sketch)
        return sketch

    boundary = Mock(side_effect=author)
    monkeypatch.setattr(end_profiles, "_author", boundary)
    return component, boundary


@pytest.mark.parametrize("lines", [1, 3])
def test_profiles_reuse_exact_caps_without_changing_manual_visibility(
    native_boundary: tuple[Any, Mock], lines: int
) -> None:
    """
    Keep one region per cap rather than per conductor and reuse an inspectable pair.
    """
    component, author = native_boundary
    checkpoint = Mock()
    pair = end_profiles.retain_end_profiles(component, _targets(lines), checkpoint)
    assert list(pair) == ["start", "end"] and len(component.sketches) == 2
    assert [sketch.name for sketch in pair.values()] == [
        "Sweep profile - Start cap",
        "Sweep profile - End cap",
    ]
    assert all(not sketch.isLightBulbOn for sketch in pair.values())
    pair["end"].isLightBulbOn = True
    reused = end_profiles.retain_end_profiles(component, _targets(lines))
    assert reused == pair and reused["end"].isLightBulbOn
    assert author.call_count == checkpoint.call_count == 2


def test_changed_or_partial_profiles_cannot_be_replaced_silently(
    native_boundary: tuple[Any, Mock],
) -> None:
    """
    Refuse changed boundary conditions and failed native work without another attempt.
    """
    component, author = native_boundary
    author.side_effect = RuntimeError("native setup stopped")
    with pytest.raises(RuntimeError, match="native setup stopped"):
        end_profiles.retain_end_profiles(component, _targets())
    with pytest.raises(RuntimeError, match="Incomplete end profiles"):
        end_profiles.retain_end_profiles(component, _targets())
    with pytest.raises(RuntimeError, match="separate layout"):
        end_profiles.retain_end_profiles(component, replace(_targets(), end=Vector3(9, 0, 0)))
    assert author.call_count == 1
    assert not end_profiles.checkpoint_interrupted(component)


@pytest.mark.parametrize("completed", [0, 1])
def test_checkpoint_interruptions_preserve_only_the_completed_native_prefix(
    native_boundary: tuple[Any, Mock], completed: int
) -> None:
    """
    Distinguish a scheduling stop before authoring from a failed native operation, without retrying.
    """
    component, author = native_boundary
    calls = 0

    def checkpoint() -> None:
        """
        Interrupt immediately before the selected unattempted native cap operation.
        """
        nonlocal calls
        if calls == completed:
            raise RuntimeError("scheduling limit")
        calls += 1

    with pytest.raises(RuntimeError, match="scheduling limit"):
        end_profiles.retain_end_profiles(component, _targets(), checkpoint)
    assert author.call_count == completed and end_profiles.checkpoint_interrupted(component)
    with pytest.raises(RuntimeError, match="Incomplete end profiles"):
        end_profiles.retain_end_profiles(component, _targets())
    assert author.call_count == completed
    if completed:
        component.sketches[0].profiles.count = 0
        assert not end_profiles.checkpoint_interrupted(component)


def test_complete_profiles_cannot_be_reclassified_as_interrupted(
    native_boundary: tuple[Any, Mock],
) -> None:
    """
    Preserve complete native pairs and reject stale or externally modified interruption markers.
    """
    component, _ = native_boundary
    assert not end_profiles.checkpoint_interrupted(component)
    end_profiles.retain_end_profiles(component, _targets())
    source = component.attributes.itemByName("RibbonAnalysisEndProfiles", "source")
    component.attributes.add(
        "RibbonAnalysisEndProfiles", "checkpoint_interrupted", source.value + ":end"
    )
    assert not end_profiles.checkpoint_interrupted(component)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "open"])
def test_damaged_retained_pair_requires_review(
    native_boundary: tuple[Any, Mock], damage: str
) -> None:
    """
    Do not create substitute sketches when an existing retained pair is damaged.
    """
    component, author = native_boundary
    end_profiles.retain_end_profiles(component, _targets())
    if damage == "missing":
        component.sketches.pop()
    elif damage == "duplicate":
        component.sketches.append(component.sketches[0])
    else:
        component.sketches[0].profiles.count = 0
    with pytest.raises(RuntimeError, match="missing, duplicated or invalid"):
        end_profiles.retain_end_profiles(component, _targets())
    assert author.call_count == 2


def test_native_authoring_uses_the_original_joined_profile_and_target_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Delegate to the existing builder with target dimensions, orientation and no path.
    """
    core = ModuleType("adsk.core")
    core.Matrix3D = SimpleNamespace(create=lambda: "identity transform")
    host = ModuleType("adsk")
    host.core = core
    monkeypatch.setitem(sys.modules, "adsk", host)
    monkeypatch.setitem(sys.modules, "adsk.core", core)
    sketch, plane = SimpleNamespace(), SimpleNamespace(isLightBulbOn=True)
    builder = ModuleType("ribbon_builder")
    builder._add_section = Mock(return_value=(sketch, plane))
    fusion_package = ModuleType("cable_bundler.fusion")
    fusion_package.__path__ = []
    package = ModuleType("cable_bundler.fusion.cable_solid_parts")
    package.ribbon_builder = builder
    monkeypatch.setitem(sys.modules, "cable_bundler.fusion", fusion_package)
    monkeypatch.setitem(sys.modules, "cable_bundler.fusion.cable_solid_parts", package)
    guide_module = ModuleType("cable_bundler.fusion.ribbon_geometry")
    guide_module.RibbonGuidePlane = lambda origin, normal: SimpleNamespace(
        origin=origin, normal=normal
    )
    monkeypatch.setitem(sys.modules, "cable_bundler.fusion.ribbon_geometry", guide_module)
    component, targets = object(), _targets()
    # noinspection PyProtectedMember
    assert end_profiles._author(component, targets, "end") is sketch
    # noinspection PyProtectedMember
    args, kwargs = builder._add_section.call_args
    owner, path, frame, group, transform = args
    assert owner is component and path is None and transform == "identity transform"
    assert frame.origin == targets.end and frame.tangent == targets.end_tangent
    assert frame.width == targets.end_width
    assert frame.thickness == cross(targets.end_tangent, targets.end_width)
    assert group.ribbon_lines == 3 and group.diameter_mm == 1.5
    assert group.group_type is CableGroupType.RIBBON
    assert kwargs["guide_plane"].origin == targets.end
    assert kwargs["guide_plane"].normal == targets.end_tangent
    assert not plane.isLightBulbOn
