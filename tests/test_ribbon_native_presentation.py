"""
Verify provenance-gated stopped-result presentation without creating native or replay geometry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_locked_solver.native_presentation import (
    finish,
    matches,
    replay,
    show,
)


@dataclass
class _Native:
    """
    Retain only mock native ownership and visibility at the Fusion boundary.
    """

    displayed: Any
    rejected_job: Path | None = None

    def has_geometry(self) -> bool:
        """
        Require an existing valid occurrence with at least one native body.
        """
        return self.displayed.isValid and self.displayed.component.bRepBodies.count > 0

    def hide(self) -> None:
        """
        Hide the retained occurrence without modifying its identity or geometry.
        """
        self.displayed.isLightBulbOn = False


@pytest.fixture
def retained(tmp_path: Path) -> tuple[_Native, Path, dict[str, Any]]:
    """
    Provide one audited record and an exact mock body revision with no native builder.
    """
    native = _Native(
        SimpleNamespace(
            isValid=True,
            isLightBulbOn=False,
            component=SimpleNamespace(
                bRepBodies=SimpleNamespace(
                    count=1, item=Mock(return_value=SimpleNamespace(revisionId="body-revision"))
                )
            ),
        )
    )
    record = {
        "status": "built_and_named_fidelity_checks_pass",
        "native_attempted": 1,
        "built": 1,
        "fidelity_audited": 1,
        "revision": "body-revision",
    }
    return native, tmp_path / "manifest.json", record


@pytest.mark.parametrize(
    "status", ("built_and_named_fidelity_checks_pass", "built_with_precision_warning")
)
def test_matching_accepted_body_is_shown_and_explicit_replay_restores_diagnostics(
    retained: tuple[_Native, Path, dict[str, Any]], status: str
) -> None:
    """
    Prefer the exact recorded body while retaining the existing explicit section-inspection path.
    """
    native, manifest, record = retained
    record["status"] = status
    manifest.with_name("native-result.json").write_text(json.dumps(record))
    diagnostics = SimpleNamespace(isLightBulbOn=True)
    assert show(native, diagnostics, manifest)
    finish(native, diagnostics, manifest)
    assert native.displayed.isLightBulbOn and not diagnostics.isLightBulbOn
    replay(native, diagnostics)
    assert diagnostics.isLightBulbOn and not native.displayed.isLightBulbOn


@pytest.mark.parametrize(
    "patch",
    (
        {"revision": "other"},
        {"revision": None},
        {"status": "failed"},
        {"built": 0},
        {"fidelity_audited": None},
        {"native_attempted": True},
    ),
)
def test_mismatched_or_incomplete_result_preserves_normal_scaffold_fallback(
    retained: tuple[_Native, Path, dict[str, Any]], patch: dict[str, Any]
) -> None:
    """
    A stale body or unaudited result cannot be presented as this selected accepted output.
    """
    native, manifest, record = retained
    record.update(patch)
    manifest.with_name("native-result.json").write_text(json.dumps(record))
    diagnostics = SimpleNamespace(isLightBulbOn=True)
    assert not show(native, diagnostics, manifest)
    assert diagnostics.isLightBulbOn and not native.displayed.isLightBulbOn


@pytest.mark.parametrize("text", (None, "{", "null", "[]"))
def test_unavailable_native_record_does_not_suppress_diagnostic_inspection(
    retained: tuple[_Native, Path, dict[str, Any]], text: str | None
) -> None:
    """
    Missing and malformed external result records decline this optional presentation optimization.
    """
    native, manifest, _record = retained
    if text is not None:
        manifest.with_name("native-result.json").write_text(text)
    assert not matches(native, manifest)


def test_rejected_identity_and_missing_or_changed_geometry_remain_distinct(
    retained: tuple[_Native, Path, dict[str, Any]],
) -> None:
    """
    Preserve rejected display ownership without requiring or fabricating an accepted audit receipt.
    """
    native, manifest, record = retained
    native.rejected_job = manifest.parent.resolve()
    assert matches(native, manifest)
    native.displayed.isValid = False
    assert not matches(native, manifest)
    native.displayed.isValid = True
    native.rejected_job = None
    manifest.with_name("native-result.json").write_text(json.dumps(record))
    native.displayed.component.bRepBodies.count = 2
    assert not matches(native, manifest)
