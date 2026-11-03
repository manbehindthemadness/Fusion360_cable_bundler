"""
Verify gym replacement recovers orphaned graphics without deleting unrelated drawings.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from tests.fusion_ui_support import _PaletteLifecycleModule


class Groups:
    """
    Model mutable native group indices and invalidation after deletion.
    """

    def __init__(self) -> None:
        """
        Start with an owned empty graphics collection.
        """
        self.records: list[Any] = []

    @property
    def count(self) -> int:
        """
        Reflect collection mutations immediately, as Fusion does.
        """
        return len(self.records)

    def item(self, index: int) -> Any:
        """
        Return a native-style group at the current collection index.
        """
        return self.records[index]

    def add(self) -> Any:
        """
        Add a unique group whose deletion removes its collection entry.
        """
        group = Mock()
        group.name = ""
        group.isValid = True

        def delete() -> bool:
            """
            Retain identity rather than treating equal group names as equal objects.
            """
            self.records.remove(group)
            group.isValid = False
            return True

        group.deleteMe.side_effect = delete
        self.records.append(group)
        return group


@pytest.fixture
def graphics(addin_module: _PaletteLifecycleModule) -> Any:
    """
    Load the Fusion graphics boundary against the existing SDK test doubles.
    """
    del addin_module
    return importlib.import_module("devtools.ribbon_analysis.gym.graphics")


def test_repeated_draw_retires_all_owned_groups_even_when_handles_are_lost(graphics: Any) -> None:
    """
    Recover two orphaned scenes, retain unrelated graphics, and remain idempotent.
    """
    groups = Groups()
    unrelated = groups.add()
    unrelated.name = "User's other diagnostic"
    stale = [groups.add(), groups.add()]
    for group in stale:
        group.name = graphics.GROUP_NAME
    component = SimpleNamespace(customGraphicsGroups=groups)
    current = graphics.draw(component, {"surfaces": [], "strokes": []}, lambda: None)
    assert groups.records == [unrelated, current]
    assert all(not group.isValid for group in stale)
    final = graphics.draw(component, {"surfaces": [], "strokes": []}, lambda: None)
    assert groups.records == [unrelated, final] and not current.isValid
    unrelated.deleteMe.assert_not_called()


def test_incomplete_drawing_preserves_old_scene(graphics: Any) -> None:
    """
    Keep the last usable gym if the replacement stops before drawing completes.
    """
    groups = Groups()
    previous = groups.add()
    previous.name = graphics.GROUP_NAME

    def stop() -> None:
        """
        Model a resource stop before the new drawing has completed.
        """
        raise RuntimeError("display budget")

    with pytest.raises(RuntimeError, match="display budget"):
        graphics.draw(
            SimpleNamespace(customGraphicsGroups=groups), {"surfaces": [], "strokes": []}, stop
        )
    assert groups.records == [previous] and previous.isValid
    previous.deleteMe.assert_not_called()


def test_failed_stale_group_deletion_is_reported(graphics: Any) -> None:
    """
    Reject an unsuccessful replacement and retain the old group for diagnosis.
    """
    groups = Groups()
    previous = groups.add()
    previous.name = graphics.GROUP_NAME
    previous.deleteMe.side_effect = None
    previous.deleteMe.return_value = False
    with pytest.raises(RuntimeError, match="prior owned gym"):
        graphics.draw(
            SimpleNamespace(customGraphicsGroups=groups),
            {"surfaces": [], "strokes": []},
            lambda: None,
        )
    assert groups.records == [previous] and previous.isValid
