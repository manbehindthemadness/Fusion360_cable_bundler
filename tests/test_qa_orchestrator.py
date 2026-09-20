"""
Tests for the cross-platform local and Fusion QA orchestrator.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from experiments import qa_orchestrator
from experiments.png_oracle import ImageDifference
from experiments.qa_orchestrator import CheckResult, HttpResponse, McpClient


def test_mcp_client_negotiates_uses_and_closes_session() -> None:
    """
    Preserve the Streamable HTTP handshake and session-header lifecycle.
    """
    requests: list[tuple[str, dict[str, str], object]] = []

    def transport(
        _endpoint: str,
        method: str,
        headers: dict[str, str],
        body: bytes | None,
        _timeout_seconds: float,
    ) -> HttpResponse:
        decoded: dict[str, object] | None = None
        if body:
            raw_decoded = json.loads(body)
            if isinstance(raw_decoded, dict):
                decoded = raw_decoded
        requests.append((method, headers, decoded))
        if decoded and decoded.get("method") == "initialize":
            return HttpResponse(
                200,
                {"mcp-session-id": "qa-session"},
                json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {}}}),
            )
        if decoded and decoded.get("method") == "tools/call":
            return HttpResponse(
                200,
                {},
                json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"content": []}}),
            )
        return HttpResponse(202, {}, "")

    client = McpClient("http://127.0.0.1:27182/mcp", 5.0, transport)

    client.initialize()
    result = client.call_tool("fusion_mcp_execute", {"featureType": "script"})
    client.close()

    assert result == {"content": []}
    assert [request[0] for request in requests] == ["POST", "POST", "POST", "DELETE"]
    assert "MCP-Session-Id" not in requests[0][1]
    assert all(request[1].get("MCP-Session-Id") == "qa-session" for request in requests[1:])
    assert client.session_id == ""


def test_extracts_fusion_suite_result_from_execute_envelope() -> None:
    """
    Decode Fusion MCP's nested execute payload and the suite sentinel.
    """
    expected = {"status": "passed", "scenarios": [{"scenario": "history"}]}
    execution = {
        "success": True,
        "message": f"host output\n{qa_orchestrator.FUSION_RESULT_PREFIX}{json.dumps(expected)}\n",
    }
    tool_result = {"content": [{"type": "text", "text": json.dumps(execution)}]}

    assert qa_orchestrator._parse_fusion_tool_result(tool_result) == expected


def test_aggregate_report_returns_failure_for_failed_selected_layer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Return a failing exit code while retaining local and Fusion evidence.
    """
    monkeypatch.setattr(qa_orchestrator, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_local_checks",
        lambda _timeout, _selected=None: [CheckResult("pytest", "failed", 1.0, "failure")],
    )
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_fusion_suite",
        lambda _endpoint, _timeout, _selected=None: {
            "status": "passed",
            "scenarios": [],
        },
    )

    exit_code, report_path = qa_orchestrator.run_qa()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["local"][0]["detail"] == "failure"
    assert payload["fusion"]["status"] == "passed"
    assert payload["coverage"]["requiredPlatforms"] == ["macos", "windows"]


def test_local_only_report_marks_fusion_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Support useful local runs when Fusion or its MCP server is unavailable.
    """
    monkeypatch.setattr(qa_orchestrator, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_local_checks",
        lambda _timeout, _selected=None: [CheckResult("pytest", "passed", 1.0)],
    )

    exit_code, report_path = qa_orchestrator.run_qa(run_fusion=False)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["fusion"]["status"] == "skipped"


def test_local_check_selection_runs_only_requested_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Run a task-specific local subset in the requested order.
    """
    observed: list[tuple[str, tuple[str, ...], float]] = []

    def record_command(
        name: str,
        command: tuple[str, ...],
        timeout_seconds: float,
    ) -> CheckResult:
        observed.append((name, command, timeout_seconds))
        return CheckResult(name, "passed", 1.0)

    monkeypatch.setattr(qa_orchestrator, "_run_command", record_command)

    results = qa_orchestrator._run_local_checks(
        12.0,
        ("palette", "diff-check"),
    )

    assert [result.name for result in results] == ["palette", "diff-check"]
    assert [item[0] for item in observed] == ["palette", "diff-check"]
    assert observed[0][1] == ("node", "tests/test_palette.cjs")
    assert all(item[2] == 12.0 for item in observed)


def test_qa_report_records_and_forwards_focused_selections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve focused selections in execution and durable report evidence.
    """
    observed: dict[str, object] = {}

    def local_checks(
        _timeout: float,
        selected: tuple[str, ...] | None = None,
    ) -> list[CheckResult]:
        observed["local"] = selected
        return [CheckResult("palette", "passed", 1.0)]

    def fusion_suite(
        _endpoint: str,
        _timeout: float,
        selected: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        observed["fusion"] = selected
        return {"status": "passed", "scenarios": []}

    monkeypatch.setattr(qa_orchestrator, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(qa_orchestrator, "_run_local_checks", local_checks)
    monkeypatch.setattr(qa_orchestrator, "_run_fusion_suite", fusion_suite)

    exit_code, report_path = qa_orchestrator.run_qa(
        local_checks=("palette",),
        fusion_scenarios=("fusion_capabilities",),
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert observed == {
        "local": ("palette",),
        "fusion": ("fusion_capabilities",),
    }
    assert payload["selection"]["localChecks"] == ["palette"]
    assert payload["selection"]["fusionScenarios"] == ["fusion_capabilities"]


def test_desktop_ui_capture_is_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Never invoke permission-requiring desktop capture in the default suite.
    """
    monkeypatch.setattr(qa_orchestrator, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_local_checks",
        lambda _timeout, _selected=None: [CheckResult("pytest", "passed", 1.0)],
    )
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_fusion_suite",
        lambda _endpoint, _timeout, _selected=None: {
            "status": "passed",
            "scenarios": [],
        },
    )
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_desktop_ui_oracle",
        lambda _endpoint, _timeout: pytest.fail("desktop capture must remain opt-in"),
    )

    exit_code, report_path = qa_orchestrator.run_qa()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["selection"]["desktopUi"] is False


def test_desktop_ui_unavailable_does_not_fail_fusion_suite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve live QA when an opted-in host still lacks desktop permission.
    """
    monkeypatch.setattr(qa_orchestrator, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_fusion_suite",
        lambda _endpoint, _timeout, _selected=None: {
            "status": "passed",
            "scenarios": [],
        },
    )
    monkeypatch.setattr(
        qa_orchestrator,
        "_run_desktop_ui_oracle",
        lambda _endpoint, _timeout: {"status": "deferred", "reason": "permission"},
    )

    exit_code, report_path = qa_orchestrator.run_qa(
        run_local=False,
        capture_desktop_ui=True,
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["fusion"]["desktopUiOracle"]["status"] == "deferred"


def test_desktop_ui_oracle_compares_two_ephemeral_stable_captures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Turn opted-in exact-window capture into a rendered stability assertion.
    """
    bounds = qa_orchestrator.PaletteBounds(10, 20, 840, 760)
    captures = [SimpleNamespace(png=b"first"), SimpleNamespace(png=b"second")]
    monkeypatch.setattr(
        qa_orchestrator,
        "_read_relationship_diagram_observation",
        lambda *_args: {"status": "passed", "connectorCount": 2, "maximumEndpointGap": 0.0},
    )
    monkeypatch.setattr(qa_orchestrator, "_read_palette_bounds", lambda *_args: bounds)
    monkeypatch.setattr(
        "experiments.qa_orchestrator.capture_harness_builder_window",
        lambda _bounds: captures.pop(0),
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.desktop_capture_observation",
        lambda capture: {"bytesObserved": len(capture.png), "purged": True},
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.compare_pngs",
        lambda first, second: ImageDifference(0.001, 0.2, 4),
    )

    result = qa_orchestrator._run_desktop_ui_oracle("local", 1.0)

    assert result["status"] == "passed"
    observations = cast(list[dict[str, object]], result["observations"])
    comparison = cast(dict[str, object], result["comparison"])
    assert len(observations) == 2
    assert comparison["palette_bounds_stable"] is True
    assert comparison["changed_pixel_fraction"] == 0.001
    assert result["capturesPurged"] is True


# noinspection DuplicatedCode
def test_desktop_ui_oracle_fails_when_stable_palette_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reject visible instability above the bounded desktop comparison tolerance.
    """
    bounds = qa_orchestrator.PaletteBounds(10, 20, 840, 760)
    captures = [SimpleNamespace(png=b"first"), SimpleNamespace(png=b"second")]
    monkeypatch.setattr(
        qa_orchestrator,
        "_read_relationship_diagram_observation",
        lambda *_args: {"status": "passed", "connectorCount": 2, "maximumEndpointGap": 0.0},
    )
    monkeypatch.setattr(qa_orchestrator, "_read_palette_bounds", lambda *_args: bounds)
    monkeypatch.setattr(
        "experiments.qa_orchestrator.capture_harness_builder_window",
        lambda _bounds: captures.pop(0),
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.desktop_capture_observation",
        lambda _capture: {"purged": True},
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.compare_pngs",
        lambda first, second: ImageDifference(0.03, 1.0, 20),
    )

    result = qa_orchestrator._run_desktop_ui_oracle("local", 1.0)

    assert result["status"] == "failed"
    assert "changed 3.00%" in result["error"]
    assert result["capturesPurged"] is True


# noinspection DuplicatedCode
def test_desktop_ui_oracle_fails_when_palette_moves_between_captures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Detect the fullscreen Space regression even when window contents remain stable.
    """
    bounds = [
        qa_orchestrator.PaletteBounds(-840, 20, 840, 760),
        qa_orchestrator.PaletteBounds(0, 30, 840, 760),
    ]
    captures = [SimpleNamespace(png=b"first"), SimpleNamespace(png=b"second")]
    monkeypatch.setattr(
        qa_orchestrator,
        "_read_relationship_diagram_observation",
        lambda *_args: {"status": "passed", "connectorCount": 2, "maximumEndpointGap": 0.0},
    )
    monkeypatch.setattr(
        qa_orchestrator,
        "_read_palette_bounds",
        lambda *_args: bounds.pop(0),
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.capture_harness_builder_window",
        lambda _bounds: captures.pop(0),
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.desktop_capture_observation",
        lambda _capture: {"purged": True},
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.compare_pngs",
        lambda first, second: ImageDifference(0.0, 0.0, 0),
    )

    result = qa_orchestrator._run_desktop_ui_oracle("local", 1.0)

    assert result["status"] == "failed"
    comparison = cast(dict[str, object], result["comparison"])
    assert comparison["palette_bounds_stable"] is False
    assert "moved or resized" in result["error"]
    assert result["capturesPurged"] is True


# noinspection DuplicatedCode
def test_desktop_ui_oracle_fails_disconnected_relationship_diagram(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reject a stable screenshot when the DOM geometry reports a connector gap.
    """
    bounds = qa_orchestrator.PaletteBounds(10, 20, 840, 760)
    captures = [SimpleNamespace(png=b"first"), SimpleNamespace(png=b"second")]
    monkeypatch.setattr(
        qa_orchestrator,
        "_read_relationship_diagram_observation",
        lambda *_args: {"status": "failed", "connectorCount": 2, "maximumEndpointGap": 8.0},
    )
    monkeypatch.setattr(qa_orchestrator, "_read_palette_bounds", lambda *_args: bounds)
    monkeypatch.setattr(
        "experiments.qa_orchestrator.capture_harness_builder_window",
        lambda _bounds: captures.pop(0),
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.desktop_capture_observation",
        lambda _capture: {"purged": True},
    )
    monkeypatch.setattr(
        "experiments.qa_orchestrator.compare_pngs",
        lambda first, second: ImageDifference(0.0, 0.0, 0),
    )

    result = qa_orchestrator._run_desktop_ui_oracle("local", 1.0)

    assert result["status"] == "failed"
    assert "disconnected or obstructed rendered edges" in result["error"]
    assert result["diagramObservation"] == {
        "status": "failed",
        "connectorCount": 2,
        "maximumEndpointGap": 8.0,
    }


def test_diagram_observation_script_targets_only_harness_builder_palette() -> None:
    """
    Keep diagram visual QA fixed to the consent-gated Harness Builder target.
    """
    script = qa_orchestrator._diagram_observation_script()

    assert "observe_relationship_diagram" in script
    assert "kev0_cable_bundler_harness_builder_palette" in script
    assert "_last_diagram_qa_observation" in script
    assert '"portCount": 0' in script
    assert '"topologyEdgeCount": 0' in script
    assert '"expectedTopologyEdgeCount": 0' in script
    assert '"invalidTraceGroupCount": 0' in script
    assert '"layoutRevision": 0' in script
    assert '"layoutError": False' in script
    assert '"redrawCompleted": True' in script
    assert '"layoutChanged": True' in script
    assert '"layoutCandidateCount": 0' in script
    assert '"visualOverlapCount": 0' in script
    assert '"visibleOverflowCount": 0' in script
    assert '"minimumUnrelatedTraceGap": 32.0' in script
    assert '"minimumParallelTraceGap": 10.0' in script
    assert '"overlappingTracePairCount": 0' in script
    assert '"contractVersion": "10"' in script
    assert "fusion_mcp_execute" not in script


def test_fusion_bootstrap_refreshes_dependencies_before_importing_suite() -> None:
    """
    Refresh the retained capability scenario before importing the suite.
    """
    script = qa_orchestrator._fusion_suite_script()

    capability_reload = script.index("importlib.reload(capabilities_module)")
    suite_import = script.index("import experiments.fusion_qa_suite")

    assert capability_reload < suite_import


def test_fusion_bootstrap_forwards_focused_scenario_selection() -> None:
    """
    Submit the requested scenario subset to the in-host suite.
    """
    script = qa_orchestrator._fusion_suite_script(("fusion_capabilities",))

    assert '["fusion_capabilities"]' in script
    assert "run_automated_fusion_suite(" in script


def test_fusion_bootstrap_uses_python_none_for_complete_suite() -> None:
    """
    Keep the default scenario selection valid inside the generated Python script.
    """
    script = qa_orchestrator._fusion_suite_script()

    assert "\n        None,\n" in script
    assert "\n        null,\n" not in script
