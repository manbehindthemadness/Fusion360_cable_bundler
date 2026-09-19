# =============================================================================
# DEVELOPMENT-ONLY EXTERNAL UI CAPTURE — OPT-IN CALL SITE
#
# OS-level capture is reachable only through the explicit --desktop-ui command-line
# flag. The default end-to-end QA procedure does not invoke it. The capture adapter
# enforces Fusion identity and exact-window ownership for the fixed palette and main
# application frame, never accepts an arbitrary target or rectangle, and purges all
# pixel and handshake files before this orchestrator reports.
# =============================================================================

"""
Orchestrate local checks and cleanup-safe Fusion scenarios into one QA report.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import platform
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Optional
from urllib.parse import urlparse

from experiments.desktop_ui_capture import (
    DesktopCaptureSafetyError,
    DesktopCaptureUnavailable,
    PaletteBounds,
    capture_harness_builder_window,
    desktop_capture_observation,
)
from experiments.png_oracle import compare_pngs
from experiments.qa_coverage import load_coverage_ledger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "verification"
DEFAULT_MCP_URL = "http://127.0.0.1:27182/mcp"
MAXIMUM_STABLE_DESKTOP_CHANGE = 0.02
MCP_PROTOCOL_VERSION = "2025-03-26"
FUSION_RESULT_PREFIX = "WIRE_BUNDLER_QA_RESULT="
VISUAL_RESULT_PREFIX = "WIRE_BUNDLER_VISUAL_RESULT="
GENERATED_VISUAL_RESULT_PREFIX = "WIRE_BUNDLER_GENERATED_VISUAL_RESULT="
PALETTE_BOUNDS_RESULT_PREFIX = "WIRE_BUNDLER_PALETTE_BOUNDS_RESULT="
DIAGRAM_OBSERVATION_RESULT_PREFIX = "WIRE_BUNDLER_DIAGRAM_OBSERVATION_RESULT="
NATIVE_DIALOG_RESULT_PREFIX = "WIRE_BUNDLER_NATIVE_DIALOG_RESULT="
NATIVE_DIALOG_HANDSHAKE_ROOT = PROJECT_ROOT / "artifacts" / "native_dialog_handshake"
MINIMUM_NATIVE_DIALOG_CHANGE = 0.00001
VISUAL_WIDTH = 640
VISUAL_HEIGHT = 480
LOCAL_CHECK_NAMES = ("pytest", "palette", "ruff-lint", "ruff-format", "diff-check")
FUSION_SCENARIO_NAMES = ("fusion_capabilities",)


@dataclass(frozen=True)
class CheckResult:
    """
    Describe one local or live QA operation.
    """

    name: str
    status: str
    elapsed_ms: float
    detail: str = ""


@dataclass(frozen=True)
class HttpResponse:
    """
    Retain the relevant result of one MCP HTTP request.
    """

    status: int
    headers: dict[str, str]
    body: str


Transport = Callable[[str, str, dict[str, str], Optional[bytes], float], HttpResponse]


class McpClient:
    """
    Minimal Streamable HTTP MCP client for the local Fusion development server.
    """

    def __init__(
        self,
        endpoint: str,
        timeout_seconds: float,
        transport: Optional[Transport] = None,
    ) -> None:
        """
        Configure the endpoint and injectable HTTP transport.
        """
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _http_request
        self.session_id = ""
        self._next_id = 1

    def initialize(self) -> dict[str, object]:
        """
        Negotiate an MCP session and send the initialized notification.
        """
        response = self._request(
            "POST",
            {
                "jsonrpc": "2.0",
                "id": self._allocate_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "wire-bundler-qa", "version": "0.1.0"},
                },
                "session": False,
            },
        )
        self.session_id = response.headers.get("mcp-session-id", "")
        if not self.session_id:
            raise RuntimeError("Fusion MCP initialize response omitted MCP-Session-Id.")
        payload = _decode_json_response(response)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"Fusion MCP initialize failed: {payload!r}")
        self._request(
            "POST",
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
                "session": True,
            },
            allow_empty=True,
        )
        return result

    def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        """
        Invoke one MCP tool in the initialized session.
        """
        if not self.session_id:
            raise RuntimeError("Fusion MCP client is not initialized.")
        response = self._request(
            "POST",
            {
                "jsonrpc": "2.0",
                "id": self._allocate_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
                "session": True,
            },
        )
        payload = _decode_json_response(response)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"Fusion MCP tool call failed: {payload!r}")
        return result

    def close(self) -> None:
        """
        Delete the current MCP session when one was established.
        """
        if not self.session_id:
            return
        try:
            self._request("DELETE", None, allow_empty=True)
        finally:
            self.session_id = ""

    def _request(
        self,
        method: str,
        payload: Optional[dict[str, object]],
        allow_empty: bool = False,
    ) -> HttpResponse:
        """
        Send one JSON request with the active MCP session header.
        """
        request_payload = dict(payload) if payload is not None else None
        use_session = bool(request_payload and request_payload.pop("session", False))
        headers = {"Accept": "application/json, text/event-stream"}
        body = None
        if request_payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(request_payload).encode("utf-8")
        if use_session or method == "DELETE":
            headers["MCP-Session-Id"] = self.session_id
        response = self.transport(
            self.endpoint,
            method,
            headers,
            body,
            self.timeout_seconds,
        )
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(
                f"Fusion MCP returned HTTP {response.status}: {response.body.strip()}"
            )
        if not allow_empty and not response.body.strip():
            raise RuntimeError("Fusion MCP returned an empty response.")
        return response

    def _allocate_id(self) -> int:
        """
        Return the next JSON-RPC request identity.
        """
        request_id = self._next_id
        self._next_id += 1
        return request_id


def run_qa(
    run_local: bool = True,
    run_fusion: bool = True,
    mcp_url: str = DEFAULT_MCP_URL,
    command_timeout_seconds: float = 180.0,
    fusion_timeout_seconds: float = 600.0,
    capture_desktop_ui: bool = False,
    local_checks: Optional[Sequence[str]] = None,
    fusion_scenarios: Optional[Sequence[str]] = None,
) -> tuple[int, Path]:
    """
    Run the selected QA layers and write one aggregate report.
    """
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    local_results = (
        _run_local_checks(command_timeout_seconds, local_checks)
        if run_local
        else [CheckResult("local", "skipped", 0.0, "Disabled by command option.")]
    )
    fusion_result: dict[str, object]
    if run_fusion:
        fusion_result = _run_fusion_suite(mcp_url, fusion_timeout_seconds, fusion_scenarios)
        if capture_desktop_ui:
            desktop_result = _run_desktop_ui_oracle(mcp_url, fusion_timeout_seconds)
            fusion_result["desktopUiOracle"] = desktop_result
            if desktop_result.get("status") == "failed":
                fusion_result["status"] = "failed"
            elif desktop_result.get("status") == "passed":
                fusion_result["nativeDialogUiOracle"] = {
                    "status": "skipped",
                    "detail": "Legacy persistent-wire dialog fixture removed.",
                }
    else:
        fusion_result = {"status": "skipped", "detail": "Disabled by command option."}

    ledger = load_coverage_ledger()
    local_passed = all(result.status in {"passed", "skipped"} for result in local_results)
    fusion_passed = fusion_result.get("status") in {"passed", "skipped"}
    status = "passed" if local_passed and fusion_passed else "failed"
    finished_at = datetime.now(timezone.utc)
    payload = {
        "schemaVersion": 1,
        "status": status,
        "startedAt": started_at.isoformat(),
        "finishedAt": finished_at.isoformat(),
        "host": {"platform": platform.system(), "machine": platform.machine()},
        "selection": {
            "local": run_local,
            "fusion": run_fusion,
            "desktopUi": capture_desktop_ui,
            "localChecks": list(local_checks) if local_checks is not None else None,
            "fusionScenarios": list(fusion_scenarios) if fusion_scenarios is not None else None,
        },
        "local": [asdict(result) for result in local_results],
        "fusion": fusion_result,
        "coverage": {
            "milestone": ledger.milestone,
            "requiredPlatforms": list(ledger.required_platforms),
            "counts": ledger.counts_by_status(),
            "manualOrDeferred": [
                {
                    "id": target.target_id,
                    "status": target.status,
                    "reason": target.manual_reason,
                    "reviewTrigger": target.review_trigger,
                }
                for target in ledger.targets
                if target.status == "manual"
            ],
        },
    }
    timestamp = started_at.strftime("%Y%m%dT%H%M%S.%fZ")
    report_path = ARTIFACT_ROOT / f"qa_suite_{timestamp}.json"
    report_path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return (0 if status == "passed" else 1), report_path


def main(arguments: Optional[Sequence[str]] = None) -> int:
    """
    Parse command-line options, run QA, and print the final report location.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--local-only", action="store_true", help="Skip live Fusion checks.")
    mode.add_argument("--fusion-only", action="store_true", help="Skip local checks.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--command-timeout", type=float, default=180.0)
    parser.add_argument("--fusion-timeout", type=float, default=600.0)
    parser.add_argument(
        "--local-check",
        action="append",
        choices=LOCAL_CHECK_NAMES,
        dest="local_checks",
        help="Run only this local check; repeat to select more than one.",
    )
    parser.add_argument(
        "--fusion-scenario",
        action="append",
        choices=FUSION_SCENARIO_NAMES,
        dest="fusion_scenarios",
        help=(
            "Run only this structural Fusion scenario and skip viewport visual oracles; "
            "repeat to select more than one."
        ),
    )
    parser.add_argument(
        "--desktop-ui",
        action="store_true",
        help=(
            "Opt into Fusion-only desktop window capture; requires development-mode "
            "Screen Recording permission."
        ),
    )
    options = parser.parse_args(arguments)
    if options.local_only and options.desktop_ui:
        parser.error("--desktop-ui requires the live Fusion layer.")
    if options.fusion_only and options.local_checks:
        parser.error("--local-check cannot be used with --fusion-only.")
    if options.local_only and options.fusion_scenarios:
        parser.error("--fusion-scenario cannot be used with --local-only.")
    exit_code, report_path = run_qa(
        run_local=not options.fusion_only,
        run_fusion=not options.local_only,
        mcp_url=options.mcp_url,
        command_timeout_seconds=options.command_timeout,
        fusion_timeout_seconds=options.fusion_timeout,
        capture_desktop_ui=options.desktop_ui,
        local_checks=options.local_checks,
        fusion_scenarios=options.fusion_scenarios,
    )
    print(f"Wire Bundler QA: {'PASS' if exit_code == 0 else 'FAIL'}")
    print(f"Report: {report_path}")
    return exit_code


def _run_local_checks(
    timeout_seconds: float,
    selected_checks: Optional[Sequence[str]] = None,
) -> list[CheckResult]:
    """
    Execute every host-independent repository check.
    """
    commands = (
        ("pytest", (sys.executable, "-m", "pytest", "-q")),
        ("palette", ("node", "tests/test_palette.cjs")),
        (
            "ruff-lint",
            (
                sys.executable,
                "-m",
                "ruff",
                "check",
                "Fusion360_wire_bundler.py",
                "wire_bundler",
                "tests",
                "experiments",
            ),
        ),
        (
            "ruff-format",
            (
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "Fusion360_wire_bundler.py",
                "wire_bundler",
                "tests",
                "experiments",
            ),
        ),
        ("diff-check", ("git", "diff", "--check")),
    )
    commands_by_name = dict(commands)
    selected_names = tuple(selected_checks) if selected_checks is not None else LOCAL_CHECK_NAMES
    unknown_names = tuple(name for name in selected_names if name not in commands_by_name)
    if unknown_names:
        raise ValueError(f"Unknown local QA checks: {', '.join(unknown_names)}")
    return [_run_command(name, commands_by_name[name], timeout_seconds) for name in selected_names]


def _run_command(name: str, command: Sequence[str], timeout_seconds: float) -> CheckResult:
    """
    Run one local command and retain a bounded output tail.
    """
    started = perf_counter()
    try:
        completed = subprocess.run(
            tuple(command),
            cwd=PROJECT_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
        )
        status = "passed" if completed.returncode == 0 else "failed"
        detail = completed.stdout[-8000:].strip()
    except FileNotFoundError as error:
        status = "failed"
        detail = str(error)
    except subprocess.TimeoutExpired as error:
        status = "failed"
        output = error.stdout or ""
        detail = f"Timed out after {timeout_seconds:.1f} seconds.\n{output}"[-8000:].strip()
    elapsed_ms = (perf_counter() - started) * 1000
    print(f"[{status.upper():7}] {name} ({elapsed_ms:.0f} ms)")
    return CheckResult(name, status, elapsed_ms, detail)


def _run_fusion_suite(
    endpoint: str,
    timeout_seconds: float,
    selected_scenarios: Optional[Sequence[str]] = None,
) -> dict[str, object]:
    """
    Execute the in-host suite through one temporary MCP session.
    """
    started = perf_counter()
    client = McpClient(endpoint, timeout_seconds)
    suite_result: dict[str, object] = {"status": "failed"}
    try:
        server = client.initialize()
        tool_result = client.call_tool(
            "fusion_mcp_execute",
            {
                "featureType": "script",
                "object": {"script": _fusion_suite_script(selected_scenarios)},
            },
        )
        suite_result = _parse_fusion_tool_result(tool_result)
        suite_result["server"] = server
        skipped = {
            "status": "skipped",
            "detail": "Legacy persistent-wire visual fixtures removed.",
        }
        suite_result["visualOracle"] = skipped
        suite_result["generatedVisualOracle"] = skipped
    except (ConnectionError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        suite_result = {"status": "failed", "error": str(error)}
    finally:
        try:
            client.close()
        except (ConnectionError, OSError, RuntimeError):
            pass
    elapsed_ms = (perf_counter() - started) * 1000
    suite_result["elapsed_ms"] = elapsed_ms
    raw_status = suite_result.get("status", "failed")
    display_status = raw_status.upper() if isinstance(raw_status, str) else "FAILED"
    print(f"[{display_status:7}] fusion ({elapsed_ms:.0f} ms)")
    return suite_result


def _run_desktop_ui_oracle(endpoint: str, timeout_seconds: float) -> dict[str, object]:
    """
    Compare two verified captures of the stable Fusion palette when explicitly requested.
    """
    try:
        diagram_observation = _read_relationship_diagram_observation(
            endpoint,
            timeout_seconds,
        )
        first_bounds = _read_palette_bounds(endpoint, timeout_seconds)
        first_capture = capture_harness_builder_window(first_bounds)
        second_bounds = _read_palette_bounds(endpoint, timeout_seconds)
        second_capture = capture_harness_builder_window(second_bounds)
        observations = [
            desktop_capture_observation(first_capture),
            desktop_capture_observation(second_capture),
        ]
    except DesktopCaptureSafetyError as error:
        return {"status": "failed", "error": str(error), "capturesPurged": True}
    except (
        ConnectionError,
        DesktopCaptureUnavailable,
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return {"status": "deferred", "reason": str(error), "capturesPurged": True}
    try:
        difference = asdict(compare_pngs(first_capture.png, second_capture.png))
    except ValueError as error:
        return {"status": "failed", "error": str(error), "capturesPurged": True}
    changed_fraction = float(difference["changed_pixel_fraction"])
    palette_bounds_stable = first_bounds == second_bounds
    comparison = {
        **difference,
        "maximum_changed_pixel_fraction": MAXIMUM_STABLE_DESKTOP_CHANGE,
        "palette_bounds_stable": palette_bounds_stable,
    }
    result = {
        "status": "passed",
        "diagramObservation": diagram_observation,
        "observations": observations,
        "comparison": comparison,
        "capturesPurged": True,
    }
    if diagram_observation.get("status") == "failed":
        result["status"] = "failed"
        result["error"] = "Relationship diagram contains disconnected or obstructed rendered edges."
    elif not palette_bounds_stable:
        result["status"] = "failed"
        result["error"] = "Stable desktop palette moved or resized between captures."
    elif changed_fraction > MAXIMUM_STABLE_DESKTOP_CHANGE:
        result["status"] = "failed"
        result["error"] = (
            f"Stable desktop palette changed {changed_fraction:.2%}; maximum is "
            f"{MAXIMUM_STABLE_DESKTOP_CHANGE:.2%}."
        )
    return result


# noinspection DuplicatedCode
def _read_relationship_diagram_observation(
    endpoint: str,
    timeout_seconds: float,
) -> dict[str, object]:
    """
    Prepare the relationship diagram and read its rendered edge-continuity result.

    The palette computes the observation from its final DOM geometry, then reports
    connector continuity and node-obstruction metrics through private QA state.
    """
    client = McpClient(endpoint, timeout_seconds)
    payload: dict[str, object] = {}
    try:
        client.initialize()
        tool_result = client.call_tool(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": _diagram_observation_script()}},
        )
        payload = _parse_execute_result(tool_result, DIAGRAM_OBSERVATION_RESULT_PREFIX)
    finally:
        try:
            client.close()
        except (ConnectionError, OSError, RuntimeError):
            pass
    status = payload.get("status")
    connector_count = payload.get("connectorCount")
    maximum_gap = payload.get("maximumEndpointGap")
    minimum_trace_gap = payload.get("minimumUnrelatedTraceGap")
    minimum_parallel_gap = payload.get("minimumParallelTraceGap")
    overlapping_trace_pair_count = payload.get("overlappingTracePairCount")
    obstructed_trace_count = payload.get("obstructedTraceCount")
    port_count = payload.get("portCount")
    topology_edge_count = payload.get("topologyEdgeCount")
    expected_topology_edge_count = payload.get("expectedTopologyEdgeCount")
    invalid_trace_group_count = payload.get("invalidTraceGroupCount")
    layout_revision = payload.get("layoutRevision")
    layout_error = payload.get("layoutError")
    redraw_completed = payload.get("redrawCompleted")
    layout_changed = payload.get("layoutChanged")
    layout_candidate_count = payload.get("layoutCandidateCount")
    layout_candidate_index = payload.get("layoutCandidateIndex")
    visual_overlap_count = payload.get("visualOverlapCount")
    visible_overflow_count = payload.get("visibleOverflowCount")
    contract_version = payload.get("contractVersion")
    layout = payload.get("layout")
    if status not in {"passed", "failed", "skipped"}:
        raise RuntimeError("Palette returned an invalid diagram-observation status.")
    if isinstance(connector_count, bool) or not isinstance(connector_count, int):
        raise RuntimeError("Palette returned an invalid diagram connector count.")
    if isinstance(maximum_gap, bool) or not isinstance(maximum_gap, (int, float)):
        raise RuntimeError("Palette returned an invalid diagram endpoint gap.")
    if (
        isinstance(minimum_trace_gap, bool)
        or not isinstance(minimum_trace_gap, (int, float))
        or not math.isfinite(float(minimum_trace_gap))
        or float(minimum_trace_gap) < 0
    ):
        raise RuntimeError("Palette returned an invalid diagram trace clearance.")
    if (
        isinstance(minimum_parallel_gap, bool)
        or not isinstance(minimum_parallel_gap, (int, float))
        or not math.isfinite(float(minimum_parallel_gap))
        or float(minimum_parallel_gap) < 0
    ):
        raise RuntimeError("Palette returned an invalid parallel trace gap.")
    if (
        isinstance(overlapping_trace_pair_count, bool)
        or not isinstance(overlapping_trace_pair_count, int)
        or overlapping_trace_pair_count < 0
    ):
        raise RuntimeError("Palette returned an invalid overlapping trace-pair count.")
    if (
        isinstance(obstructed_trace_count, bool)
        or not isinstance(obstructed_trace_count, int)
        or obstructed_trace_count < 0
    ):
        raise RuntimeError("Palette returned an invalid diagram obstruction count.")
    if isinstance(port_count, bool) or not isinstance(port_count, int) or port_count < 0:
        raise RuntimeError("Palette returned an invalid diagram port count.")
    if (
        isinstance(topology_edge_count, bool)
        or not isinstance(topology_edge_count, int)
        or topology_edge_count < 0
    ):
        raise RuntimeError("Palette returned an invalid topology edge count.")
    if (
        isinstance(expected_topology_edge_count, bool)
        or not isinstance(expected_topology_edge_count, int)
        or expected_topology_edge_count < 0
    ):
        raise RuntimeError("Palette returned an invalid expected topology edge count.")
    if (
        isinstance(invalid_trace_group_count, bool)
        or not isinstance(invalid_trace_group_count, int)
        or invalid_trace_group_count < 0
    ):
        raise RuntimeError("Palette returned an invalid diagram trace-group count.")
    if (
        isinstance(layout_revision, bool)
        or not isinstance(layout_revision, int)
        or layout_revision < 0
    ):
        raise RuntimeError("Palette returned an invalid diagram layout revision.")
    if not isinstance(layout_error, bool):
        raise RuntimeError("Palette returned an invalid diagram layout error flag.")
    if not isinstance(redraw_completed, bool):
        raise RuntimeError("Palette returned an invalid diagram redraw completion flag.")
    if not isinstance(layout_changed, bool):
        raise RuntimeError("Palette returned an invalid diagram layout-change flag.")
    for value, label in (
        (layout_candidate_count, "layout candidate count"),
        (layout_candidate_index, "layout candidate index"),
        (visual_overlap_count, "visual overlap count"),
        (visible_overflow_count, "visible overflow count"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RuntimeError(f"Palette returned an invalid diagram {label}.")
    if contract_version != "10":
        raise RuntimeError("Palette returned an unsupported diagram contract version.")
    if layout != "layered-cardinal-topology":
        raise RuntimeError("Palette returned an unsupported diagram layout.")
    return {
        "status": status,
        "connectorCount": connector_count,
        "maximumEndpointGap": float(maximum_gap),
        "minimumUnrelatedTraceGap": float(minimum_trace_gap),
        "minimumParallelTraceGap": float(minimum_parallel_gap),
        "overlappingTracePairCount": overlapping_trace_pair_count,
        "obstructedTraceCount": obstructed_trace_count,
        "portCount": port_count,
        "topologyEdgeCount": topology_edge_count,
        "expectedTopologyEdgeCount": expected_topology_edge_count,
        "invalidTraceGroupCount": invalid_trace_group_count,
        "layoutRevision": layout_revision,
        "layoutError": layout_error,
        "redrawCompleted": redraw_completed,
        "layoutChanged": layout_changed,
        "layoutCandidateCount": layout_candidate_count,
        "layoutCandidateIndex": layout_candidate_index,
        "visualOverlapCount": visual_overlap_count,
        "visibleOverflowCount": visible_overflow_count,
        "contractVersion": contract_version,
        "layout": layout,
    }


def _diagram_observation_script() -> str:
    """
    Build the fixed in-host handshake for relationship-diagram visual QA.
    """
    return f'''import json
import sys
from time import monotonic

import adsk
import adsk.core


def run(_context: str):
    modules = [
        module for name, module in sys.modules.items()
        if name.endswith("wire_bundler.addin")
    ]
    if len(modules) != 1:
        raise RuntimeError("Harness Builder add-in module is unavailable or ambiguous.")
    module = modules[0]
    module._last_diagram_qa_observation = None
    palette = adsk.core.Application.get().userInterface.palettes.itemById(
        "kev0_wire_bundler_harness_builder_palette"
    )
    if palette is None or not palette.isVisible:
        raise RuntimeError("Harness Builder palette must be visible for diagram QA.")
    palette.sendInfoToHTML(
        "qa_probe",
        json.dumps({{"operation": "observe_relationship_diagram"}}),
    )
    deadline = monotonic() + 5.0
    while module._last_diagram_qa_observation is None and monotonic() < deadline:
        adsk.doEvents()
    observation = module._last_diagram_qa_observation or {{
        "status": "skipped",
        "connectorCount": 0,
        "maximumEndpointGap": 0.0,
        "minimumUnrelatedTraceGap": 32.0,
        "minimumParallelTraceGap": 10.0,
        "overlappingTracePairCount": 0,
        "obstructedTraceCount": 0,
        "portCount": 0,
        "topologyEdgeCount": 0,
        "expectedTopologyEdgeCount": 0,
        "invalidTraceGroupCount": 0,
        "layoutRevision": 0,
        "layoutError": False,
        "redrawCompleted": True,
        "layoutChanged": True,
        "layoutCandidateCount": 0,
        "layoutCandidateIndex": 0,
        "visualOverlapCount": 0,
        "visibleOverflowCount": 0,
        "contractVersion": "10",
        "layout": "layered-cardinal-topology",
    }}
    print("{DIAGRAM_OBSERVATION_RESULT_PREFIX}" + json.dumps(observation, sort_keys=True))
'''


def _read_palette_bounds(endpoint: str, timeout_seconds: float) -> PaletteBounds:
    """
    Read the fixed Harness Builder palette geometry through Fusion's API.
    """
    client = McpClient(endpoint, timeout_seconds)
    payload: dict[str, object] = {}
    try:
        client.initialize()
        tool_result = client.call_tool(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": _palette_bounds_script()}},
        )
        payload = _parse_execute_result(tool_result, PALETTE_BOUNDS_RESULT_PREFIX)
    finally:
        try:
            client.close()
        except (ConnectionError, OSError, RuntimeError):
            pass
    if (
        payload.get("id") != "kev0_wire_bundler_harness_builder_palette"
        or payload.get("name") != "Harness Builder"
    ):
        raise DesktopCaptureSafetyError("Fusion returned an unexpected palette identity.")
    if payload.get("valid") is not True or payload.get("visible") is not True:
        raise DesktopCaptureUnavailable("Harness Builder is not a valid visible Fusion palette.")
    left = _finite_number(payload.get("left"), "left")
    top = _finite_number(payload.get("top"), "top")
    width = _finite_number(payload.get("width"), "width")
    height = _finite_number(payload.get("height"), "height")
    if width <= 0 or height <= 0:
        raise DesktopCaptureUnavailable("Harness Builder reported invalid palette dimensions.")
    return PaletteBounds(left, top, width, height)


def _palette_bounds_script() -> str:
    """
    Build a fixed in-host query for the Harness Builder palette only.
    """
    return f'''import json

import adsk.core


def run(_context: str):
    application = adsk.core.Application.get()
    palette = application.userInterface.palettes.itemById(
        "kev0_wire_bundler_harness_builder_palette"
    )
    if palette is None:
        raise RuntimeError("Harness Builder palette is not registered.")
    result = {{
        "id": palette.id,
        "name": palette.name,
        "valid": palette.isValid,
        "visible": palette.isVisible,
        "left": palette.left,
        "top": palette.top,
        "width": palette.width,
        "height": palette.height,
    }}
    print("{PALETTE_BOUNDS_RESULT_PREFIX}" + json.dumps(result, sort_keys=True))
'''


def _finite_number(value: object, label: str) -> float:
    """
    Validate one numeric Palette API coordinate or dimension.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DesktopCaptureUnavailable(f"Harness Builder {label} is not numeric.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise DesktopCaptureUnavailable(f"Harness Builder {label} is not finite.")
    return parsed


def _fusion_suite_script(selected_scenarios: Optional[Sequence[str]] = None) -> str:
    """
    Build the small in-host bootstrap submitted to ``fusion_mcp_execute``.
    """
    root = json.dumps(str(PROJECT_ROOT))
    scenario_selection = (
        json.dumps(list(selected_scenarios)) if selected_scenarios is not None else "None"
    )
    return f'''import importlib
import json
import sys

import adsk.core


def run(_context: str):
    root = {root}
    if root not in sys.path:
        sys.path.insert(0, root)
    import experiments.scenario_report as scenario_report_module
    import experiments.experiment_fusion_capabilities as capabilities_module

    importlib.reload(scenario_report_module)
    importlib.reload(capabilities_module)
    import experiments.fusion_qa_suite as suite_module

    suite_module = importlib.reload(suite_module)
    result = suite_module.run_automated_fusion_suite(
        adsk.core.Application.get(),
        {scenario_selection},
    )
    print("{FUSION_RESULT_PREFIX}" + json.dumps(result, sort_keys=True))
'''


def _parse_fusion_tool_result(tool_result: dict[str, object]) -> dict[str, object]:
    """
    Extract the suite sentinel from Fusion MCP's nested execute result.
    """
    return _parse_execute_result(tool_result, FUSION_RESULT_PREFIX)


def _parse_execute_result(
    tool_result: dict[str, object],
    result_prefix: str,
) -> dict[str, object]:
    """
    Extract one prefixed JSON object from Fusion MCP's nested execute result.
    """
    content = tool_result.get("content")
    if not isinstance(content, list):
        raise RuntimeError("Fusion MCP tool result omitted content.")
    text_blocks = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    if not text_blocks:
        raise RuntimeError("Fusion MCP execute returned no text result.")
    execution_payload = json.loads("\n".join(text_blocks))
    if not isinstance(execution_payload, dict):
        raise RuntimeError("Fusion MCP execute result was not an object.")
    if not execution_payload.get("success"):
        raise RuntimeError(str(execution_payload.get("error", "Fusion script failed.")))
    message = execution_payload.get("message")
    if not isinstance(message, str):
        raise RuntimeError("Fusion MCP execute result omitted script output.")
    for line in reversed(message.splitlines()):
        if line.startswith(result_prefix):
            result = json.loads(line[len(result_prefix) :])
            if not isinstance(result, dict):
                raise RuntimeError("Fusion suite result was not an object.")
            return result
    raise RuntimeError("Fusion script output omitted the QA result sentinel.")


def _decode_json_response(response: HttpResponse) -> dict[str, object]:
    """
    Decode one MCP JSON response and reject protocol errors.
    """
    payload = json.loads(response.body)
    if not isinstance(payload, dict):
        raise RuntimeError("Fusion MCP response was not an object.")
    if "error" in payload:
        raise RuntimeError(f"Fusion MCP protocol error: {payload['error']!r}")
    return payload


def _http_request(
    endpoint: str,
    method: str,
    headers: dict[str, str],
    body: Optional[bytes],
    timeout_seconds: float,
) -> HttpResponse:
    """
    Send one HTTP request using only the Python standard library.
    """
    parsed = urlparse(endpoint)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or host is None:
        raise ValueError(f"Invalid MCP endpoint: {endpoint!r}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    connection_type = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_type(host, port, timeout=timeout_seconds)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = response.read().decode("utf-8", errors="replace")
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        result = HttpResponse(response.status, response_headers, response_body)
    finally:
        connection.close()
    return result
