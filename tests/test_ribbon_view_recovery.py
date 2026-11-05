"""
Verify deleted display recovery preserves saved inputs, sessions, output ownership and execution logs.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import generate
from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.fixture
def recovery_host(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, Any, Any]:
    """
    Supply an owned idle document and observable native component creation without Fusion.
    """
    del addin_module
    module = importlib.import_module("experiments.experiment_ribbon_locked_solver.views")
    created: list[Any] = []

    def add(matrix: Any) -> Any:
        """
        Create a distinguishable occurrence with its own observable child collection.
        """
        item = SimpleNamespace(
            isValid=True,
            component=SimpleNamespace(
                isValid=True, occurrences=SimpleNamespace(addNewComponent=Mock(side_effect=add))
            ),
            transform2=matrix,
            isLightBulbOn=True,
        )
        created.append(item)
        return item

    root = SimpleNamespace(occurrences=SimpleNamespace(addNewComponent=Mock(side_effect=add)))
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(creationId="owned"),
        userInterface=SimpleNamespace(activeCommand="SelectCommand"),
        activeProduct=root,
    )
    monkeypatch.setitem(vars(module.adsk.core), "Application", SimpleNamespace(get=lambda: app))
    monkeypatch.setitem(vars(module.adsk.core), "Matrix3D", SimpleNamespace(create=SimpleNamespace))
    monkeypatch.setitem(
        vars(module.adsk.core), "Vector3D", SimpleNamespace(create=lambda *args: args)
    )
    monkeypatch.setitem(
        vars(module.adsk.fusion),
        "Design",
        SimpleNamespace(cast=lambda product: SimpleNamespace(rootComponent=product)),
    )
    monkeypatch.setitem(
        vars(module),
        "NativeBudget",
        Mock(return_value=SimpleNamespace(check=Mock(), memory=lambda: 0)),
    )
    monkeypatch.setitem(vars(module), "verify", Mock(return_value={"test": "pinned"}))
    return module, app, SimpleNamespace(root=root, created=created)


@pytest.mark.parametrize("missing", ("gym", "diagnostics", "both"))
def test_recovery_recreates_only_missing_owned_views_without_solving(
    recovery_host: tuple[Any, Any, Any], tmp_path: Path, missing: str
) -> None:
    """
    Reuse a live parent and surviving sibling; repeated requests cannot duplicate display containers.
    """
    module, _, host = recovery_host
    parent = host.root.occurrences.addNewComponent(object())
    gym_occurrence = SimpleNamespace(isValid=missing not in ("gym", "both"))
    diagnostic_occurrence = SimpleNamespace(isValid=missing not in ("diagnostics", "both"))
    scene = generate()
    runner = Mock()
    workspace = SimpleNamespace(
        container=parent,
        gym_occurrence=gym_occurrence,
        diagnostic_occurrence=diagnostic_occurrence,
        directory=tmp_path,
        native=SimpleNamespace(document_id="owned", display_x_cm=610, displayed=None),
        gym=SimpleNamespace(scene=scene, rebind_component=Mock()),
        diagnostics=SimpleNamespace(rebind_root=Mock(), runner=runner, palette=object()),
    )
    expected = 2 if missing == "both" else 1
    module.restore(workspace)
    module.restore(workspace)
    assert len(host.created) == 1 + expected
    assert workspace.container is parent and workspace.native.displayed is None
    assert workspace.gym.scene is scene
    if missing == "gym":
        assert workspace.diagnostic_occurrence is diagnostic_occurrence
        workspace.diagnostics.rebind_root.assert_not_called()
    if missing == "diagnostics":
        assert workspace.gym_occurrence is gym_occurrence
        workspace.gym.rebind_component.assert_not_called()
    assert len(list(tmp_path.glob("display-recovery-*.json"))) == 1
    runner.assert_not_called()
    assert not runner.method_calls


def test_deleted_parent_is_replaced_at_the_original_display_offset(
    recovery_host: tuple[Any, Any, Any], tmp_path: Path
) -> None:
    """
    Recover from deleting the complete browser container without resurrecting deleted output.
    """
    module, _, host = recovery_host
    workspace = SimpleNamespace(
        container=SimpleNamespace(isValid=False),
        gym_occurrence=SimpleNamespace(isValid=False),
        diagnostic_occurrence=SimpleNamespace(isValid=False),
        directory=tmp_path,
        native=SimpleNamespace(document_id="owned", display_x_cm=610, displayed=None),
        gym=SimpleNamespace(rebind_component=Mock()),
        diagnostics=SimpleNamespace(rebind_root=Mock()),
    )
    module.restore(workspace)
    assert len(host.created) == 3
    assert workspace.container.transform2.translation == (610, 0, 0)
    assert workspace.gym_occurrence.isValid and workspace.diagnostic_occurrence.isValid
    assert workspace.native.displayed is None


def test_recovery_refuses_unrelated_active_design_before_creating_anything(
    recovery_host: tuple[Any, Any, Any], tmp_path: Path
) -> None:
    """
    Preserve user document boundaries when a retained palette outlives its original active design.
    """
    module, app, host = recovery_host
    app.activeDocument.creationId = "unrelated"
    workspace = SimpleNamespace(
        gym_occurrence=SimpleNamespace(isValid=False),
        diagnostic_occurrence=SimpleNamespace(isValid=False),
        directory=tmp_path,
        native=SimpleNamespace(document_id="owned"),
    )
    with pytest.raises(RuntimeError, match="owned idle"):
        module.restore(workspace)
    assert not host.created and not list(tmp_path.iterdir())


def test_gym_rebind_keeps_inputs_palette_revision_and_archive(
    addin_module: _PaletteLifecycleModule, tmp_path: Path
) -> None:
    """
    Drop invalid handles and redraw the same layout without generating a new one.
    """
    del addin_module
    module = importlib.import_module("devtools.ribbon_analysis.gym.view")
    view: Any = object.__new__(module.GymView)
    view.component = SimpleNamespace(isValid=False)
    view.scene, view.revision, view.directory, view.palette = generate(), 7, tmp_path, object()
    before = (view.scene, view.revision, view.directory, view.palette)
    view.group = view._profiles = view._pending_profiles = object()
    view._draw = Mock()
    replacement = SimpleNamespace(isValid=True)
    view.rebind_component(replacement)
    assert view.component is replacement
    assert (view.scene, view.revision, view.directory, view.palette) == before
    assert view.group is view._profiles is view._pending_profiles is None
    view._draw.assert_called_once_with(view.scene)


@pytest.mark.parametrize("recoverable", [True, False])
def test_new_run_archives_only_a_reviewed_checkpoint_interruption(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch, recoverable: bool
) -> None:
    """
    Preserve failed geometry and keep the blocking guard after actual native authoring failures.
    """
    del addin_module
    module = importlib.import_module("devtools.ribbon_analysis.gym.view")
    view: Any = object.__new__(module.GymView)
    pending = SimpleNamespace(
        isValid=True, isLightBulbOn=True, component=SimpleNamespace(name="Pending")
    )
    view._pending_profiles = pending
    view._draw = Mock()
    validate = Mock(return_value=recoverable)
    monkeypatch.setitem(vars(module), "checkpoint_interrupted", validate)
    view.archive_interrupted_profiles()
    validate.assert_called_once_with(pending.component)
    if recoverable:
        assert (view._pending_profiles, pending.isLightBulbOn, pending.component.name) == (
            None,
            False,
            "Sweep profiles - interrupted preparation (retained)",
        )
    else:
        assert view._pending_profiles is pending and pending.isLightBulbOn
    view._draw.assert_not_called()


def test_diagnostic_rebind_keeps_replay_sessions_selection_and_terminal_job(
    addin_module: _PaletteLifecycleModule, tmp_path: Path
) -> None:
    """
    Remove only cached native objects while preserving current and other-layout replay state.
    """
    del addin_module
    module = importlib.import_module("devtools.ribbon_analysis.inspection.fusion_view")
    view: Any = object.__new__(module.DiagnosticViewer)
    view.root = SimpleNamespace(isValid=False)
    view.session = SimpleNamespace(methods=[{"id": "input"}], solver="input", section=4)
    original = view.session
    view._methods = {"input": object()}
    other = {"old-result": object()}
    view._sessions = {
        tmp_path / "first": (original, view._methods),
        tmp_path / "second": (object(), other),
    }
    view.runner = SimpleNamespace(state=Mock(return_value={"status": "completed", "job": "last"}))
    view._register_method = Mock(
        side_effect=lambda method: view._methods.update({method["id"]: object()})
    )
    view._draw = Mock()
    view.rebind_root(SimpleNamespace(isValid=True))
    assert view.session is original and view.session.section == 4
    assert len(view._sessions) == 2 and not other and list(view._methods) == ["input"]
    assert view.runner.state() == {"status": "completed", "job": "last"}
    assert view._scene is view._solver_sketch is view._gym_group is None
    view._draw.assert_called_once_with()
