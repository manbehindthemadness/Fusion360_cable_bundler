"""
Verify rejected native inspection preserves failures and falls back without retries.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.material_cylinder import FlatSurfaces
from tests.fusion_ui_support import _PaletteLifecycleModule
from tests.test_ribbon_rejected_display import _route


@pytest.fixture
def rejected_host(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Any, Mock, Any]:
    """
    Mock only Fusion/resource boundaries around the real rejected-route build orchestration.
    """
    del addin_module
    module: Any = importlib.import_module(
        "experiments.experiment_ribbon_locked_solver.rejected_native"
    )
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(creationId="owned"),
        userInterface=SimpleNamespace(activeCommand="SelectCommand"),
        activeProduct=object(),
    )
    body = SimpleNamespace(
        isSolid=True, volume=1.0, faces=SimpleNamespace(count=122), isLightBulbOn=False
    )
    occurrence = SimpleNamespace(
        isValid=True,
        isLightBulbOn=False,
        component=SimpleNamespace(
            name="", bRepBodies=SimpleNamespace(add=Mock(return_value=body)), attributes=Mock()
        ),
    )
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(
            occurrences=SimpleNamespace(addNewComponent=Mock(return_value=occurrence))
        )
    )
    monkeypatch.setitem(vars(module.adsk.core), "Application", SimpleNamespace(get=lambda: app))
    monkeypatch.setitem(
        vars(module.adsk.core), "Matrix3D", SimpleNamespace(create=lambda: SimpleNamespace())
    )
    monkeypatch.setitem(
        vars(module.adsk.core), "Vector3D", SimpleNamespace(create=lambda *args: args)
    )
    monkeypatch.setitem(vars(module.adsk.fusion), "Design", SimpleNamespace(cast=lambda _: design))
    budget = Mock(started=perf_counter(), samples=[], memory=Mock(return_value=1024))
    monkeypatch.setitem(vars(module), "NativeBudget", Mock(return_value=budget))
    pins = {"source": "digest"}
    monkeypatch.setitem(vars(module), "verify", lambda: pins)
    monkeypatch.setitem(vars(module), "material_profile", Mock(return_value=()))
    monkeypatch.setitem(vars(module), "material_patches", Mock(return_value=()))
    monkeypatch.setitem(vars(module), "retain_end_profiles", Mock())
    kernel = Mock(return_value=body)
    monkeypatch.setitem(
        vars(module),
        "define_material_body",
        Mock(return_value=SimpleNamespace(definition=SimpleNamespace(createBody=kernel))),
    )
    route = _route()
    (tmp_path / "plan.json").write_text(
        json.dumps({"sources": pins, "targets": asdict(route.targets), "document_id": "owned"})
    )
    (tmp_path / "rejected-geometry.json").write_text(
        json.dumps(
            {
                "branches": [
                    {"roots": [0, 0], "disposition": "penetration", "route": snapshot(route)}
                ]
            }
        )
    )
    return module, kernel, occurrence


@pytest.mark.parametrize(
    "outcome", ("built", "kernel_none", "kernel_error", "sheet", "zero_volume", "persist_none")
)
def test_one_native_attempt_preserves_rejection_or_falls_back(
    rejected_host: tuple[Any, Mock, Any], tmp_path: Path, outcome: str
) -> None:
    """
    Kernel acceptance never changes route acceptance; unusable bodies select the scaffold.
    """
    module, kernel, occurrence = rejected_host
    if outcome == "kernel_none":
        kernel.return_value = None
    elif outcome == "kernel_error":
        kernel.side_effect = RuntimeError("kernel rejected the shell")
    elif outcome == "sheet":
        kernel.return_value.isSolid = False
    elif outcome == "zero_volume":
        kernel.return_value.volume = 0
    elif outcome == "persist_none":
        occurrence.component.bRepBodies.add.return_value = None
    displayed, result = module.build(tmp_path, "owned", 610, FlatSurfaces.CYLINDERS)
    assert result["built"] == int(outcome == "built")
    assert result["accepted"] is False and result["native_fidelity_audits"] == 0
    assert (displayed is occurrence) == (outcome == "built")
    assert result["native_attempts"] == 1
    kernel.assert_called_once_with()
    assert not (tmp_path / "route.json").exists()
    assert (
        json.loads((tmp_path / "rejected-native-result.json").read_text())["built"]
        == result["built"]
    )
    with pytest.raises(RuntimeError, match="no retry"):
        module.build(tmp_path, "owned", 610, FlatSurfaces.CYLINDERS)
    kernel.assert_called_once_with()


@pytest.mark.parametrize("guard", ("cancel", "source", "targets"))
def test_inspection_guards_prevent_kernel_work(
    rejected_host: tuple[Any, Mock, Any], tmp_path: Path, guard: str
) -> None:
    """
    Cancellation, changed sources and unrelated targets cannot trigger an inspection build.
    """
    module, kernel, _ = rejected_host
    if guard == "cancel":
        (tmp_path / "cancel").touch()
    else:
        plan = json.loads((tmp_path / "plan.json").read_text())
        if guard == "source":
            plan["sources"] = {}
        else:
            plan["targets"]["name"] = "another case"
        (tmp_path / "plan.json").write_text(json.dumps(plan))
    occurrence, result = module.build(tmp_path, "owned", 610, FlatSurfaces.CYLINDERS)
    assert occurrence is None and result["built"] == result["native_attempts"] == 0
    kernel.assert_not_called()


def test_native_inspection_uses_the_same_explicit_final_candidate_as_diagnostics(
    rejected_host: tuple[Any, Mock, Any], tmp_path: Path
) -> None:
    """
    A longer final result takes priority without creating an accepted route or extra kernel attempt.
    """
    module, kernel, occurrence = rejected_host
    early = _route()
    final = replace(early, pieces=(replace(early.pieces[0], geometry=Straight(12)),))
    path = tmp_path / "rejected-geometry.json"
    payload = json.loads(path.read_text())
    payload["selected_result"] = {
        "kind": "final_solver_candidate",
        "accepted": False,
        "route": snapshot(final),
        "disposition": "Final candidate failed",
    }
    path.write_text(json.dumps(payload))
    displayed, result = module.build(tmp_path, "owned", 610, FlatSurfaces.CYLINDERS)
    assert displayed is occurrence and result["accepted"] is False
    assert result["inspection_origin"] == "final_solver_candidate" and result["roots"] is None
    assert json.loads((tmp_path / "rejected-native-plan.json").read_text())["route"] == snapshot(
        final
    )
    kernel.assert_called_once_with()
    assert not (tmp_path / "route.json").exists()
