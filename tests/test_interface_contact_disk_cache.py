"""
Version-scoped file-cache regressions for projected Interface contacts.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import AttachmentTargetKind, InterfaceContact


@pytest.mark.parametrize(
    ("platform", "os_name", "expected_suffix"),
    [
        ("darwin", "posix", "Library/Caches"),
        ("linux", "posix", ".cache"),
        ("win32", "nt", "AppData/Local"),
    ],
)
def test_default_disk_cache_lives_under_user_home(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    os_name: str,
    expected_suffix: str,
) -> None:
    """
    Never depend on the add-in directory for cache write permissions.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setitem(vars(cache), "os", SimpleNamespace(name=os_name, environ=os.environ))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert (
        cache._cache_root()
        == tmp_path / expected_suffix / "Fusion360_cable_bundler" / "contact_outlines_v1"
    )


def test_relative_cache_environment_paths_fall_back_to_home(
    addin_module: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Ignore malformed relative cache locations to avoid writing into the add-in.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", "relative-cache")

    assert (
        cache._cache_root()
        == tmp_path / ".cache" / "Fusion360_cable_bundler" / "contact_outlines_v1"
    )


def test_absolute_user_cache_environment_path_is_honored(
    addin_module: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Use the user's configured local cache directory when it is absolute.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "user-cache"))

    assert (
        cache._cache_root() == tmp_path / "user-cache/Fusion360_cable_bundler/contact_outlines_v1"
    )


def test_linux_disk_cache_is_inactive_placeholder(
    addin_module: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Keep Linux cache location prospective until Fusion ships a native client.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    application = _application()
    ids = (UUID(int=1), UUID(int=2))
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")
    projector = Mock(side_effect=_projection)

    cache.project_cached_contact_batch(application, object(), *ids, [contact], projector)
    cache.project_cached_contact_batch(application, object(), *ids, [contact], projector)

    assert not cache.disk_cache_available(application, *ids)
    assert not cache.clear_interface_contact_snapshot(application, *ids)
    assert projector.call_count == 2
    assert not (tmp_path / "cache").exists()


def _application(*, modified: bool = False, version: int = 3) -> SimpleNamespace:
    """
    Provide one saved Fusion-like document without loading the host API.
    """
    document = SimpleNamespace(
        isModified=modified,
        dataFile=SimpleNamespace(id="urn:example:board", versionNumber=version),
    )
    return SimpleNamespace(activeDocument=document)


def _projection(_design: object, contact: InterfaceContact) -> dict[str, object]:
    """
    Return a small world-space face projection with current naming metadata.
    """
    return {
        "contactId": str(contact.contact_id),
        "kind": contact.kind.value,
        "name": contact.name or "Pad",
        "sourceName": "Pad",
        "assignedName": contact.name,
        "linked": True,
        "normal": [0.0, 0.0, 1.0],
        "parentAxes": None,
        "loops": [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]]],
    }


def test_saved_projection_reuses_disk_but_merges_current_name(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reopen a saved Interface without reprojecting or preserving an old name.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    application = _application()
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")
    projector = Mock(side_effect=_projection)
    ids = (UUID(int=1), UUID(int=2))
    first_stats: dict[str, int] = {}
    second_stats: dict[str, int] = {}

    first = cache.project_cached_contact_batch(
        application, object(), *ids, [contact], projector, diagnostics=first_stats
    )
    renamed = InterfaceContact(contact.contact_id, contact.kind, contact.entity_token, "J1.1")
    second = cache.project_cached_contact_batch(
        application, object(), *ids, [renamed], projector, diagnostics=second_stats
    )
    cleared = cache.project_cached_contact_batch(application, object(), *ids, [contact], projector)

    assert first[0]["name"] == "Pad"
    assert first_stats == {"hits": 0, "misses": 1}
    assert second_stats == {"hits": 1, "misses": 0}
    assert second[0]["name"] == second[0]["assignedName"] == "J1.1"
    assert cleared[0]["name"] == "Pad"
    assert projector.call_count == 1
    snapshots = list((tmp_path / "cache").glob("contact-*.json"))
    assert len(snapshots) == 1
    stored = json.loads(snapshots[0].read_text(encoding="utf-8"))
    stored_projection = stored["entries"][str(contact.contact_id)]["projection"]
    assert stored_projection["name"] == "Pad"
    assert "assignedName" not in stored_projection


def test_complete_warm_snapshot_is_single_read_without_geometry_calls(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Serve a whole diagram at once, but reject incomplete or unvalidated data.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    application = _application()
    ids = (UUID(int=1), UUID(int=2))
    contacts = [
        InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-3"),
        InterfaceContact(UUID(int=4), AttachmentTargetKind.FACE, "face-4"),
    ]
    assert cache.read_complete_cached_contacts(application, *ids, contacts, 0) is None
    cache.project_cached_contact_batch(application, object(), *ids, contacts, _projection)
    renamed = InterfaceContact(
        contacts[0].contact_id, contacts[0].kind, contacts[0].entity_token, "J1.1"
    )
    result = cache.read_complete_cached_contacts(application, *ids, [renamed, contacts[1]], 0)
    assert result is not None
    assert [item["contactId"] for item in result] == [
        str(renamed.contact_id),
        str(contacts[1].contact_id),
    ]
    assert result[0]["name"] == result[0]["assignedName"] == "J1.1"
    assert cache.read_complete_cached_contacts(application, *ids, contacts, 1) is None
    assert cache.read_complete_cached_contacts(application, *ids, contacts[:1], 0) is not None
    changed = InterfaceContact(UUID(int=5), AttachmentTargetKind.FACE, "face-5")
    assert cache.read_complete_cached_contacts(application, *ids, [contacts[0], changed], 0) is None


def test_cache_diagnostics_explain_eligibility_and_snapshot_write(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Keep modified saved documents eligible for per-contact validation.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    ids = (UUID(int=1), UUID(int=2))
    application = _application()
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")

    assert cache.describe_interface_contact_cache(application, *ids) == {
        "reason": "eligible",
        "snapshot": "missing",
    }
    cache.project_cached_contact_batch(application, object(), *ids, [contact], _projection)
    status = cache.describe_interface_contact_cache(application, *ids)
    assert status["reason"] == "eligible"
    assert status["snapshot"] == "present"
    assert status["entries"] == 1
    assert status["lastWrite"] == "written"
    dirty_status = cache.describe_interface_contact_cache(_application(modified=True), *ids)
    assert dirty_status["reason"] == "eligible"
    assert dirty_status["snapshot"] == "present"


def test_modified_or_unsaved_document_never_uses_disk(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Avoid persistence when a dirty source cannot be validated or has no file ID.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")
    projector = Mock(side_effect=_projection)
    for application in (_application(modified=True), SimpleNamespace(activeDocument=None)):
        cache.project_cached_contact_batch(
            application, object(), UUID(int=1), UUID(int=2), [contact], projector
        )
        cache.project_cached_contact_batch(
            application, object(), UUID(int=1), UUID(int=2), [contact], projector
        )
    assert projector.call_count == 4
    assert not (tmp_path / "cache").exists()


def test_static_snapshot_revalidates_incrementally_after_observed_model_edits(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reuse static hits, then check each contact once after a model-edit event.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    design = SimpleNamespace(source_signature="body-revision-1")
    checked: list[str] = []

    def source_signature(current_design: Any, _contact: InterfaceContact) -> str:
        """
        Model a cheap live revision and placement fingerprint.
        """
        checked.append(current_design.source_signature)
        return current_design.source_signature

    monkeypatch.setitem(vars(cache), "contact_source_signature", source_signature)
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")
    projector = Mock(side_effect=_projection)
    ids = (UUID(int=1), UUID(int=2))
    cache.project_cached_contact_batch(_application(), design, *ids, [contact], projector)
    assert checked == ["body-revision-1"]

    dirty = _application(modified=True)
    diagnostics: dict[str, int] = {}
    cache.project_cached_contact_batch(
        dirty, design, *ids, [contact], projector, diagnostics=diagnostics
    )
    assert diagnostics == {"hits": 1, "misses": 0}
    assert projector.call_count == 1
    assert checked == ["body-revision-1"]

    design.source_signature = "body-revision-2"
    cache.project_cached_contact_batch(
        dirty, design, *ids, [contact], projector, diagnostics=diagnostics, geometry_revision=1
    )
    assert diagnostics == {"hits": 0, "misses": 1}
    assert projector.call_count == 2
    assert checked == ["body-revision-1", "body-revision-2"]

    cache.project_cached_contact_batch(
        dirty, design, *ids, [contact], projector, diagnostics=diagnostics, geometry_revision=1
    )
    assert diagnostics == {"hits": 1, "misses": 0}
    assert checked == ["body-revision-1", "body-revision-2"]

    design.source_signature = "body-revision-1"
    cache.project_cached_contact_batch(
        _application(),
        design,
        *ids,
        [contact],
        projector,
        diagnostics=diagnostics,
        geometry_revision=2,
    )
    assert diagnostics == {"hits": 0, "misses": 1}
    assert projector.call_count == 3


def test_observed_edit_reprojects_only_changed_contact(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Stage changed geometry without reprojecting unchanged neighboring contacts.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    signatures = {"first": "revision-1", "second": "revision-1"}
    checked: list[str] = []

    def source_signature(_design: object, contact: InterfaceContact) -> str:
        """
        Resolve the current source revision for one target.
        """
        checked.append(contact.entity_token)
        return signatures[contact.entity_token]

    monkeypatch.setitem(vars(cache), "contact_source_signature", source_signature)
    contacts = (
        InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "first"),
        InterfaceContact(UUID(int=4), AttachmentTargetKind.FACE, "second"),
    )
    projector = Mock(side_effect=_projection)
    ids = (UUID(int=1), UUID(int=2))
    cache.project_cached_contact_batch(_application(), object(), *ids, contacts, projector)
    assert projector.call_count == 2
    checked.clear()

    signatures["second"] = "revision-2"
    diagnostics: dict[str, int] = {}
    cache.project_cached_contact_batch(
        _application(modified=True),
        object(),
        *ids,
        contacts,
        projector,
        diagnostics=diagnostics,
        geometry_revision=1,
    )

    assert diagnostics == {"hits": 1, "misses": 1}
    assert checked == ["first", "second"]
    assert [call.args[1].entity_token for call in projector.call_args_list] == [
        "first",
        "second",
        "second",
    ]


def test_initially_named_contact_retains_unnamed_source_label(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Clearing an imported name reveals the original target label without reprojection.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token", "J1.1")
    projector = Mock(side_effect=_projection)
    ids = (UUID(int=1), UUID(int=2))

    cache.project_cached_contact_batch(_application(), object(), *ids, [contact], projector)
    unnamed = InterfaceContact(contact.contact_id, contact.kind, contact.entity_token)
    result = cache.project_cached_contact_batch(
        _application(), object(), *ids, [unnamed], projector
    )

    assert result[0]["name"] == "Pad"
    assert result[0]["assignedName"] == ""
    assert projector.call_count == 1


def test_version_token_and_rebuild_invalidate_only_the_current_snapshot(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Keep old versions isolated and make the explicit rebuild a genuine miss.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")
    projector = Mock(side_effect=_projection)
    ids = (UUID(int=1), UUID(int=2))
    application = _application()
    cache.project_cached_contact_batch(application, object(), *ids, [contact], projector)
    changed_token = InterfaceContact(contact.contact_id, contact.kind, "new-token")
    cache.project_cached_contact_batch(application, object(), *ids, [changed_token], projector)
    cache.project_cached_contact_batch(
        _application(version=4), object(), *ids, [contact], projector
    )
    assert projector.call_count == 3

    assert cache.clear_interface_contact_snapshot(application, *ids)
    cache.project_cached_contact_batch(application, object(), *ids, [changed_token], projector)
    cache.project_cached_contact_batch(
        _application(version=4), object(), *ids, [contact], projector
    )
    assert projector.call_count == 4


def test_corrupt_snapshot_is_ignored_and_replaced(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Treat malformed local cache data as a miss, not as diagram geometry.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    application = _application()
    ids = (UUID(int=1), UUID(int=2))
    path = cache._snapshot_path(application, *ids)
    assert path is not None
    path.parent.mkdir(parents=True)
    path.write_text('{"format":1,"entries":', encoding="utf-8")
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")
    projector = Mock(side_effect=_projection)

    result = cache.project_cached_contact_batch(application, object(), *ids, [contact], projector)

    assert result[0]["loops"] == _projection(object(), contact)["loops"]
    assert projector.call_count == 1
    assert json.loads(path.read_text(encoding="utf-8"))["format"] == 1


def test_clear_propagates_io_error_instead_of_serving_stale_cache(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Rebuild must report a failed deletion rather than loading the old snapshot.
    """
    cache: Any = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")
    path = cache._snapshot_path(_application(), UUID(int=1), UUID(int=2))
    assert path is not None

    def fail_unlink(_path: Path, *, missing_ok: bool = False) -> None:
        """
        Simulate an unwritable local cache file.
        """
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(OSError, match="permission denied"):
        cache.clear_interface_contact_snapshot(_application(), UUID(int=1), UUID(int=2))


def test_unwritable_cache_does_not_interrupt_projection(
    addin_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Security-policy or permission errors must not block the contact diagram.
    """
    cache = importlib.import_module("cable_bundler.fusion.interface_contact_disk_cache")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(vars(cache), "_cache_root", lambda: tmp_path / "cache")

    def deny_directory(*_args: object, **_kwargs: object) -> None:
        """
        Model a local cache directory that cannot be created.
        """
        raise PermissionError("cache location denied")

    monkeypatch.setattr(Path, "mkdir", deny_directory)
    contact = InterfaceContact(UUID(int=3), AttachmentTargetKind.FACE, "face-token")
    result = cache.project_cached_contact_batch(
        _application(), object(), UUID(int=1), UUID(int=2), [contact], _projection
    )

    assert result[0]["name"] == "Pad"
    status = cache.describe_interface_contact_cache(_application(), UUID(int=1), UUID(int=2))
    assert status["reason"] == "eligible"
    assert status["snapshot"] == "missing"
    assert status["lastWrite"] == "failed (PermissionError)"
