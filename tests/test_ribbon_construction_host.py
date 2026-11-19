"""
Verify the registered script retains its event lifetime and preserves frozen-source ownership.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Any, Any]:
    """
    Replace only Fusion's native event/lifetime boundary and external resource sampling.
    """
    native = ModuleType("adsk")
    native.autoTerminate, native.terminate = Mock(), Mock()
    native.core, native.fusion = ModuleType("adsk.core"), ModuleType("adsk.fusion")
    for module in (native, native.core, native.fusion):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    native.core.HTMLEventHandler = object
    native.core.UserInterfaceGeneralEventHandler = object
    path = (
        Path(__file__).parents[1]
        / "experiments/experiment_ribbon_construction_host/experiment_ribbon_construction_host.py"
    )
    spec = importlib.util.spec_from_file_location("_construction_script_host_test", path)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setitem(vars(module), "ROOT", tmp_path)
    monkeypatch.setitem(
        vars(module), "budget", Mock(return_value=SimpleNamespace(check=Mock(), samples=[]))
    )
    return module, native


def test_script_lifetime_extends_until_palette_close(
    host: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Returning from run leaves a live callback owner; closing releases only that palette.
    """
    module, native = host
    palette = SimpleNamespace(
        id="owned",
        isValid=True,
        deleteMe=Mock(return_value=True),
        closed=SimpleNamespace(add=Mock()),
    )
    viewer = SimpleNamespace(palette=palette, native_handler=object())
    monkeypatch.setitem(vars(module), "request", Mock(return_value=(viewer, tmp_path)))
    show = Mock()
    monkeypatch.setitem(vars(module), "Viewer", SimpleNamespace(show=show))
    module.run(None)
    native.autoTerminate.assert_called_once_with(False)
    native.terminate.assert_not_called()
    assert module.VIEWER is viewer
    show.assert_called_once_with(viewer)
    palette.closed.add.assert_called_once_with(module.CLOSED)
    module.CLOSED.notify(None)
    assert module.VIEWER is None and module.CLOSED is None
    assert viewer.native_handler is None
    native.terminate.assert_called_once_with()


def test_failed_start_does_not_leave_a_persistent_script(
    host: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    An SDK startup failure releases this host and restores normal script termination.
    """
    module, native = host
    palette = SimpleNamespace(isValid=True, deleteMe=Mock(return_value=True))
    viewer = SimpleNamespace(palette=palette, native_handler=object())
    monkeypatch.setitem(vars(module), "request", Mock(return_value=(viewer, tmp_path)))
    monkeypatch.setitem(
        vars(module), "Viewer", SimpleNamespace(show=Mock(side_effect=RuntimeError("SDK failure")))
    )
    with pytest.raises(RuntimeError, match="SDK failure"):
        module.run(None)
    assert [call.args for call in native.autoTerminate.call_args_list] == [(False,), (True,)]
    assert module.VIEWER is None


def test_request_requires_frozen_sources_and_explicit_owner(
    host: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Only a retained known viewer with matching local sources may acquire a persistent host.
    """
    module, _ = host
    directory = tmp_path / "artifacts/verification"
    directory.mkdir(parents=True)
    source = tmp_path / "source.py"
    source.write_text("frozen", encoding="utf-8")
    viewer = module.Viewer.__new__(module.Viewer)
    viewer.guard = Mock()
    owner = ModuleType("ribbon_construction_history_unit_test")
    owner.VIEWER = viewer
    monkeypatch.setitem(sys.modules, owner.__name__, owner)
    request = {
        "owner_module": owner.__name__,
        "directory": "artifacts/verification",
        "sources": {"source.py": hashlib.sha256(source.read_bytes()).hexdigest()},
    }
    (directory / "construction-host-request.json").write_text(json.dumps(request), encoding="utf-8")
    assert module.request() == (viewer, directory)
    viewer.guard.assert_called_once_with()
    source.write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source drift"):
        module.request()
    viewer.guard.assert_called_once_with()
