"""
Return one experimental native transient to physical scale without retries or relaxed audit gates.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.material_scale import NativeScale
from tests.fusion_ui_support import _PaletteLifecycleModule
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def native(addin_module: _PaletteLifecycleModule) -> ModuleType:
    """
    Import the original native boundary with SDK stubs, never a live Fusion session.
    """
    del addin_module
    return importlib.import_module("experiments.experiment_ribbon_locked_solver.native")


def _api(native: ModuleType, monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock, Mock]:
    """
    Observe the original SDK matrix and transient-transform boundary only.
    """
    sdk: Any = native.adsk
    matrix = Mock()
    matrix.setCell.return_value = True
    matrices = Mock()
    matrices.create.return_value = matrix
    manager = Mock()
    manager.transform.return_value = True
    managers = Mock()
    managers.get.return_value = manager
    monkeypatch.setitem(vars(sdk.core), "Matrix3D", matrices)
    monkeypatch.setitem(vars(sdk.fusion), "TemporaryBRepManager", managers)
    return matrices, matrix, manager


def test_default_native_owner_selects_one_conditioned_representation(native: ModuleType) -> None:
    """
    Ordinary new owners select the tested fixed policy; explicit unit policy remains available.
    """
    assert native.NativeOwner("owned").construction_scale is NativeScale.CONDITIONED
    assert (
        native.NativeOwner("owned", construction_scale=NativeScale.UNIT).construction_scale
        is NativeScale.UNIT
    )


@pytest.mark.parametrize("policy", tuple(NativeScale))
def test_range_setup_preserves_the_selected_construction_policy(
    native: ModuleType, monkeypatch: pytest.MonkeyPatch, policy: NativeScale
) -> None:
    """
    A fresh owned body handle cannot silently change an explicit native representation between cohorts.
    """
    module: Any = importlib.import_module(
        "experiments.experiment_ribbon_locked_solver.tester.runtime"
    )
    previous = native.NativeOwner("owned", construction_scale=policy)
    monkeypatch.setitem(vars(previous), "hide", Mock())
    workspace = SimpleNamespace(
        native=previous,
        gym=SimpleNamespace(archive_interrupted_profiles=Mock()),
        diagnostics=SimpleNamespace(report_progress=Mock(), enable_geometry_clear=Mock()),
    )
    runtime = module.Runtime.__new__(module.Runtime)
    runtime.workspace, runtime.document_id = workspace, "owned"
    runtime.runner = SimpleNamespace(build=None)
    runtime._setup()
    assert workspace.native is runtime.native and workspace.native is not previous
    assert workspace.native.construction_scale is policy
    assert runtime.runner.build.__self__ is workspace.native
    previous.hide.assert_called_once()


@pytest.mark.parametrize("policy", tuple(NativeScale))
def test_one_inverse_transform_precedes_persistence_and_keeps_the_original_clock(
    native: ModuleType, monkeypatch: pytest.MonkeyPatch, policy: NativeScale
) -> None:
    """
    The same transient is transformed exactly once; unit construction makes no native transform call.
    """
    matrices, matrix, manager = _api(native, monkeypatch)
    body, checkpoint = Mock(), Mock()
    native._physical_scale(body, policy, checkpoint)
    if policy is NativeScale.UNIT:
        matrices.create.assert_not_called()
        manager.transform.assert_not_called()
    else:
        assert checkpoint.call_count == 2
        assert matrix.setCell.call_args_list == [
            ((0, 0, 1 / 1024),),
            ((1, 1, 1 / 1024),),
            ((2, 2, 1 / 1024),),
        ]
        manager.transform.assert_called_once_with(body, matrix)


@pytest.mark.parametrize("failure", ("missing", "matrix", "transform", "resource"))
def test_failed_inverse_cannot_start_another_body_or_native_scale(
    native: ModuleType, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """
    Missing geometry, SDK declines and original resource stops propagate without an alternative attempt.
    """
    matrices, matrix, manager = _api(native, monkeypatch)
    body = None if failure == "missing" else Mock()
    checkpoint = Mock()
    if failure == "matrix":
        matrix.setCell.return_value = False
    if failure == "transform":
        manager.transform.return_value = False
    if failure == "resource":
        checkpoint.side_effect = TimeoutError("original resource ceiling")
    with pytest.raises((RuntimeError, TimeoutError)):
        native._physical_scale(body, NativeScale.CONDITIONED, checkpoint)
    assert matrices.create.call_count <= 1 and manager.transform.call_count <= 1
    if failure in ("missing", "matrix", "resource"):
        manager.transform.assert_not_called()


def test_original_build_charges_inverse_time_and_audits_physical_targets_once(
    native: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Run real orchestration with mock SDK boundaries and stop at the original physical audit entry.

    Seven seconds of body creation plus three seconds of inverse transformation
    belong to the same kernel/generation clock. No full native fidelity is claimed.
    """
    matrices, _matrix, manager = _api(native, monkeypatch)
    route = _route((Straight(10),))
    snapshot = native.snapshot(route)
    (tmp_path / "route.json").write_text(json.dumps(snapshot))
    (tmp_path / "plan.json").write_text(
        json.dumps(
            {
                "version": "guide-material-v2",
                "settings": {"smoothing_percent": 0, "material_uv": False},
                "document_id": "owned",
                "sources": {},
                "targets": snapshot["case"],
            }
        )
    )
    clock = [0.0]
    budget = SimpleNamespace(
        memory=lambda: 0, check=Mock(), samples=[], clock=lambda: clock[0], started=0.0
    )
    monkeypatch.setitem(vars(native), "NativeBudget", Mock(return_value=budget))
    monkeypatch.setitem(vars(native), "verify", lambda: {})
    monkeypatch.setitem(vars(native.time), "perf_counter", lambda: clock[0])
    profile = native.material_profile(route.targets.lines, route.targets.diameter_mm)
    patches = native.material_patches(route.pieces, profile)
    body = SimpleNamespace(
        isSolid=True,
        volume=1.0,
        faces=SimpleNamespace(count=len(patches) + 2),
        revisionId="original-body",
        isLightBulbOn=False,
    )
    occurrence = SimpleNamespace(
        component=SimpleNamespace(
            name="owned", bRepBodies=SimpleNamespace(add=Mock(return_value=body))
        )
    )
    root = SimpleNamespace(
        occurrences=SimpleNamespace(addNewComponent=Mock(return_value=occurrence))
    )
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(creationId="owned"),
        userInterface=SimpleNamespace(activeCommand="SelectCommand"),
        activeProduct=object(),
    )
    monkeypatch.setitem(vars(native.adsk.core), "Application", SimpleNamespace(get=lambda: app))
    monkeypatch.setitem(
        vars(native.adsk.fusion),
        "Design",
        SimpleNamespace(cast=lambda product: SimpleNamespace(rootComponent=root)),
    )

    def create() -> Any:
        """
        Charge one original body creation and return its existing transient.
        """
        clock[0] += 7
        return body

    def transform(original: Any, matrix: Any) -> bool:
        """
        Charge inverse scale work without creating or substituting another body.
        """
        del matrix
        assert original is body
        clock[0] += 3
        return True

    manager.transform.side_effect = transform
    builder = Mock(
        return_value=SimpleNamespace(
            definition=SimpleNamespace(createBody=Mock(side_effect=create)), face_records=()
        )
    )
    monkeypatch.setitem(vars(native), "define_material_body", builder)
    audit = Mock(side_effect=RuntimeError("stop at original physical audit"))
    monkeypatch.setitem(vars(native), "audit_with", audit)
    owner = native.NativeOwner("owned")
    monkeypatch.setitem(vars(owner), "_progress", Mock())
    result = owner.build(tmp_path)
    assert builder.call_count == 1 and builder.return_value.definition.createBody.call_count == 1
    assert builder.call_args.args[0][0].geometry.material_length_mm == 10240
    assert manager.transform.call_count == 1 and matrices.create.call_count == 2
    assert result["create_body_seconds"] == 7 and result["inverse_scale_seconds"] == 3
    assert result["kernel_seconds"] == result["generation_seconds"] == 10
    assert result["native_attempted"] == result["built"] == 1 and result["fidelity_audited"] == 0
    assert audit.call_count == 1 and audit.call_args.args[1]["case"] == snapshot["case"]
    assert "stop at original physical audit" in result["error"]
