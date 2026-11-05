"""
Verify explicit preview allowances and timing evidence without changing solver inputs or real resources.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.gym import generate
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification
from tests.fusion_ui_support import _PaletteLifecycleModule
from tests.test_ribbon_range_sequence import specification


def test_preview_allowance_is_explicit_replayable_and_does_not_change_layouts() -> None:
    """
    Read old plans at ten seconds and preserve their exact inputs when another allowance is selected.
    """
    payload = specification()
    payload.pop("preview_seconds", None)
    old = Specification.parse(payload)
    assert old.preview_seconds == 10
    payload["preview_seconds"] = 30
    selected = Specification.parse(payload)
    assert selected.payload()["preview_seconds"] == 30
    assert [old.scene(i) for i in range(5)] == [selected.scene(i) for i in range(5)]


@pytest.mark.parametrize("invalid", [9, 121, True, "30", 30.5, None])
def test_invalid_preview_limits_reject_before_scheduling(invalid: Any) -> None:
    """
    Refuse an unbounded, fractional or malformed host allowance without silent coercion.
    """
    payload = specification()
    payload["preview_seconds"] = invalid
    with pytest.raises(ValueError, match="Preview setup limit"):
        Specification.parse(payload)


@pytest.mark.parametrize("seconds", [10, 30])
def test_configured_limit_and_interrupted_stage_report(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    seconds: int,
) -> None:
    """
    Model the observed11.959second stall without waiting, enlarging real budgets or constructing geometry.
    """
    del addin_module
    module = importlib.import_module("devtools.ribbon_analysis.gym.view")
    clock = [0.0]

    def budget(**kwargs: Any) -> NativeBudget:
        """
        Supply the real scheduling policy with an entirely controlled clock and RSS sample.
        """
        return NativeBudget(clock=lambda: clock[0], memory=lambda: 1, **kwargs)

    def replace(scene: Any, allowance: NativeBudget) -> None:
        """
        Advance one measured stage to the reported interruption boundary.
        """
        del scene

        def work() -> None:
            """
            Represent a completed cap operation followed by its next scheduling checkpoint.
            """
            clock[0] = 11.959

        allowance.measure("end_profiles", work)()
        allowance.check("gym end profiles")

    monkeypatch.setitem(vars(module), "NativeBudget", budget)
    view: Any = object.__new__(module.GymView)
    view.directory, view._pending_profiles = tmp_path, None
    view._replace = replace
    if seconds == 10:
        with pytest.raises(RuntimeError, match="Scheduling limit"):
            view._draw(generate(), maximum_seconds=seconds)
        report = json.loads(Path(view.last_preparation["log"]).read_text())
        assert report["stop_reason"] and report["maximum_seconds"] == 10
    else:
        view._draw(generate(), maximum_seconds=seconds)
        report = view.last_preparation
        assert report["stop_reason"] is None and not list(tmp_path.iterdir())
    assert report["elapsed_seconds"] == report["timings"]["end_profiles"] == 11.959


def test_inspection_guard_preserves_the_original_interruption_measurement(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep the first useful timing record when later inspection encounters the retained-prefix guard.
    """
    del addin_module
    module = importlib.import_module("devtools.ribbon_analysis.gym.view")
    view: Any = object.__new__(module.GymView)
    original = {"stop_reason": "setup allowance"}
    view._pending_profiles, view.last_preparation, view._replace = object(), original, Mock()
    with pytest.raises(RuntimeError, match="Incomplete gym end profiles"):
        view._draw(generate())
    assert view.last_preparation is original
    view._replace.assert_not_called()


def test_host_preparation_uses_the_frozen_test_allowance(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Pass the selected preview limit to the ordinary gym update without touching solver settings.
    """
    del addin_module
    module = importlib.import_module("experiments.experiment_ribbon_locked_solver.tester.runtime")
    payload = specification()
    payload["preview_seconds"] = 30
    host: Any = object.__new__(module.Runtime)
    preview = SimpleNamespace(set_scene=Mock(), palette=SimpleNamespace(isVisible=True))
    host.workspace = SimpleNamespace(
        ensure_views=Mock(),
        gym=preview,
        gym_occurrence=SimpleNamespace(isLightBulbOn=False),
        diagnostic_occurrence=SimpleNamespace(isLightBulbOn=True),
    )
    host.engine = SimpleNamespace(specification=Specification.parse(payload))
    scene = generate()
    host._prepare(scene)
    preview.set_scene.assert_called_once_with(scene, maximum_seconds=30)
