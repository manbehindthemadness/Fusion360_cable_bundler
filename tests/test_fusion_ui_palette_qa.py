"""
Focused Fusion UI regressions for palette.
"""

from __future__ import annotations

from tests.fusion_ui_support import (
    SimpleNamespace,
    _PaletteLifecycleModule,
    json,
    pytest,
    sys,
)


# noinspection DuplicatedCode
def test_palette_records_bounded_relationship_diagram_observation(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Retain only report-safe continuity metrics from the visual QA probe.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    args = SimpleNamespace(
        action="qa_diagram_observation",
        data=json.dumps(
            {
                "status": "passed",
                "connectorCount": 4,
                "maximumEndpointGap": 0.0,
                "minimumUnrelatedTraceGap": 32.0,
                "minimumParallelTraceGap": 10.0,
                "overlappingTracePairCount": 0,
                "obstructedTraceCount": 0,
                "portCount": 4,
                "topologyEdgeCount": 2,
                "expectedTopologyEdgeCount": 2,
                "invalidTraceGroupCount": 0,
                "layoutRevision": 2,
                "layoutError": False,
                "redrawCompleted": True,
                "layoutChanged": True,
                "layoutCandidateCount": 3,
                "layoutCandidateIndex": 1,
                "visualOverlapCount": 0,
                "visibleOverflowCount": 0,
                "contractVersion": "10",
                "layout": "layered-cardinal-topology",
            }
        ),
        returnData="",
    )

    addin_module._PaletteIncomingHandler().notify(args)

    assert addin_module._runtime.last_diagram_qa_observation == {
        "status": "passed",
        "connectorCount": 4,
        "maximumEndpointGap": 0.0,
        "minimumUnrelatedTraceGap": 32.0,
        "minimumParallelTraceGap": 10.0,
        "overlappingTracePairCount": 0,
        "obstructedTraceCount": 0,
        "portCount": 4,
        "topologyEdgeCount": 2,
        "expectedTopologyEdgeCount": 2,
        "invalidTraceGroupCount": 0,
        "layoutRevision": 2,
        "layoutError": False,
        "redrawCompleted": True,
        "layoutChanged": True,
        "layoutCandidateCount": 3,
        "layoutCandidateIndex": 1,
        "visualOverlapCount": 0,
        "visibleOverflowCount": 0,
        "contractVersion": "10",
        "layout": "layered-cardinal-topology",
    }
    assert json.loads(args.returnData) == {"ok": True}


# noinspection DuplicatedCode
def test_palette_accepts_loaded_legacy_diagram_observation_during_reload(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Let an already-open version-eight palette report once while Fusion reloads Python.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    args = SimpleNamespace(
        action="qa_diagram_observation",
        data=json.dumps(
            {
                "status": "failed",
                "connectorCount": 4,
                "maximumEndpointGap": 0.0,
                "minimumUnrelatedTraceGap": 32.0,
                "minimumParallelTraceGap": 10.0,
                "overlappingTracePairCount": 0,
                "obstructedTraceCount": 0,
                "portCount": 4,
                "invalidTraceGroupCount": 0,
                "contractVersion": "8",
                "layout": "route-aware-cardinal-topology",
            }
        ),
        returnData="",
    )

    addin_module._PaletteIncomingHandler().notify(args)

    observation = addin_module._runtime.last_diagram_qa_observation
    assert observation is not None
    assert observation["contractVersion"] == "8"
    assert observation["topologyEdgeCount"] == 0
    assert observation["layoutRevision"] == 0
    assert observation["redrawCompleted"] is False
    assert json.loads(args.returnData) == {"ok": True}


# noinspection DuplicatedCode,PyDictCreation
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("portCount", -1),
        ("topologyEdgeCount", -1),
        ("expectedTopologyEdgeCount", True),
        ("invalidTraceGroupCount", True),
        ("minimumUnrelatedTraceGap", -0.1),
        ("minimumParallelTraceGap", -0.1),
        ("overlappingTracePairCount", True),
        ("layoutRevision", -1),
        ("layoutError", "false"),
        ("redrawCompleted", 1),
        ("layoutChanged", 1),
        ("layoutCandidateCount", -1),
        ("layoutCandidateIndex", True),
        ("visualOverlapCount", -1),
        ("visibleOverflowCount", True),
        ("contractVersion", "7"),
    ],
)
def test_palette_rejects_invalid_relationship_diagram_rendering_metrics(
    addin_module: _PaletteLifecycleModule,
    field: str,
    value: object,
) -> None:
    """
    Reject malformed adaptive-trace observations before retaining QA state.
    """
    application = SimpleNamespace(userInterface=None)
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda candidate: candidate)
    payload = {
        "status": "passed",
        "connectorCount": 4,
        "maximumEndpointGap": 0.0,
        "minimumUnrelatedTraceGap": 32.0,
        "minimumParallelTraceGap": 10.0,
        "overlappingTracePairCount": 0,
        "obstructedTraceCount": 0,
        "portCount": 4,
        "topologyEdgeCount": 2,
        "expectedTopologyEdgeCount": 2,
        "invalidTraceGroupCount": 0,
        "layoutRevision": 2,
        "layoutError": False,
        "redrawCompleted": True,
        "layoutChanged": True,
        "layoutCandidateCount": 3,
        "layoutCandidateIndex": 1,
        "visualOverlapCount": 0,
        "visibleOverflowCount": 0,
        "contractVersion": "10",
        "layout": "layered-cardinal-topology",
    }
    payload[field] = value
    args = SimpleNamespace(
        action="qa_diagram_observation",
        data=json.dumps(payload),
        returnData="",
    )
    addin_module._runtime.last_diagram_qa_observation = None

    addin_module._PaletteIncomingHandler().notify(args)

    assert addin_module._runtime.last_diagram_qa_observation is None
    assert json.loads(args.returnData)["ok"] is False
