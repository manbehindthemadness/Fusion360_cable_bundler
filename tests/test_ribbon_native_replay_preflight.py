"""
Reject incomplete native review inputs before connecting to Fusion or constructing geometry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.experiment_ribbon_fold_relaxation import native_runner
from experiments.qa_orchestrator import McpClient


@pytest.mark.parametrize(
    ("status", "message"),
    [("stopped", "Numerical batch is not complete"), ("completed", "metadata incomplete")],
)
def test_invalid_numerical_evidence_never_reaches_fusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str, message: str
) -> None:
    """
    Catch the missing baseline-fold metadata that previously rolled back a successful build.
    """
    directory = tmp_path / "artifacts/verification/input"
    directory.mkdir(parents=True)
    (directory / "result.json").write_text(
        json.dumps({"status": status, "cases": [{"id": "control", "status": "eased"}]})
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_fold_relaxation.native_runner.ROOT", tmp_path
    )

    def forbid_client(endpoint: str, timeout: float) -> McpClient:
        """
        Fail the test if a rejected input reaches the external-resource boundary.
        """
        del endpoint, timeout
        raise AssertionError("Invalid metadata must be rejected before MCP initialization")

    monkeypatch.setattr(
        "experiments.experiment_ribbon_fold_relaxation.native_runner.McpClient", forbid_client
    )
    spec = native_runner.ReplaySpec(
        numerical_path="artifacts/verification/input/result.json",
        route_suffix="eased",
        changed_status="eased",
        component_prefix="unit-only",
        body_name="unit-only",
        display_x_cm=0,
        review_title="unit-only",
        pass_label="unit-only",
        method_note="unit-only",
        question="Reject incomplete review evidence before external work",
        source_directory=tmp_path,
    )
    with pytest.raises(RuntimeError, match=message):
        native_runner.replay(spec, tmp_path / "artifacts/verification/output")
