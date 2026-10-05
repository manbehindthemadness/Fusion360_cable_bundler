"""
Run the production public Split-ribbon builder on the existing cap-turn matrix.

The harness is loaded as a separate module instance and supplied copied
production functions. Neither the secured harness nor production bindings are
modified. Known unsafe controls stay unconstructed under the shared test policy;
they are not claimed as production rejections. The full branch planner is outside
this comparison: connection cubics are identical authored fixture inputs.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from types import ModuleType
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import CableGroupDefinition, CableMaterialSettings
from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
from cable_bundler.routing import RibbonShape, RoutePreview
from experiments.experiment_secure_discrete_ribbon.audits import AuditFailure, audit_lobe_landmarks
from experiments.experiment_secure_discrete_ribbon.cases import (
    Expectation,
    audit_end_boundary,
    stress_cases,
)
from experiments.experiment_secure_discrete_ribbon.reporting import (
    compare_outcomes,
    matrix_fingerprint,
    summarize,
)
from experiments.experiment_secure_discrete_ribbon.transitions import transition_coverage

from .sources import PROJECT_ROOT, SOURCE_REVISION, load_sources, verify_sources

SCRATCH_NAME = "Production Split ribbon comparison"
if TYPE_CHECKING:
    GuidePlanes = tuple[Optional[RibbonGuidePlane], Optional[RibbonGuidePlane]]
    LoftResult = tuple[
        adsk.fusion.LoftFeature,
        tuple[adsk.fusion.Sketch, ...],
        tuple[adsk.fusion.ConstructionPlane, ...],
    ]
    LoftFunction = Callable[
        [
            adsk.fusion.Component,
            adsk.fusion.Path,
            RibbonShape,
            CableGroupDefinition,
            adsk.core.Matrix3D,
            GuidePlanes,
        ],
        LoftResult,
    ]


@dataclass
class _LoftObserver:
    """
    Retain returned audit references while forwarding the original result unchanged.
    """

    original: LoftFunction
    sections: tuple[adsk.fusion.Sketch, ...] = ()

    def __call__(
        self,
        component: adsk.fusion.Component,
        path: adsk.fusion.Path,
        shape: RibbonShape,
        group: CableGroupDefinition,
        transform: adsk.core.Matrix3D,
        guide_planes: GuidePlanes,
    ) -> LoftResult:
        """
        Observe only a successful return; propagate failures and inputs unchanged.
        """
        result = self.original(component, path, shape, group, transform, guide_planes)
        self.sections = result[1]
        return result


@dataclass(frozen=True)
class _BodyCollection:
    """
    Present the public builder's single output to the unchanged test harness.
    """

    body: adsk.fusion.BRepBody

    def item(self, index: int) -> adsk.fusion.BRepBody:
        """
        Return the sole output, rejecting an invalid requested index.
        """
        if index != 0:
            raise IndexError(index)
        return self.body


@dataclass(frozen=True)
class _BuildOutput:
    """
    Adapt output access only, without inventing a Fusion feature or geometry.
    """

    bodies: _BodyCollection


def _defer_path(
    _component: adsk.fusion.Component, _route: RoutePreview, _transform: adsk.core.Matrix3D
) -> tuple[None, None, None]:
    """
    Let the public production builder own path creation instead of duplicating it.
    """
    return None, None, None


def _build_main(
    component: adsk.fusion.Component,
    _path: None,
    shape: RibbonShape,
    group: CableGroupDefinition,
    transform: adsk.core.Matrix3D,
    guide_planes: tuple[RibbonGuidePlane | None, RibbonGuidePlane | None],
    *,
    builder: ModuleType,
    route: RoutePreview,
    notices: list[str],
    observations: dict[str, object],
    design: adsk.fusion.Design,
) -> tuple[_BuildOutput, tuple[adsk.fusion.Sketch, ...], tuple[adsk.fusion.ConstructionPlane, ...]]:
    """
    Invoke the unedited public builder, including its metadata and fallback policy.
    """
    fixture_name = component.name
    original = builder._build_folded_loft
    observer = _LoftObserver(original)
    builder._build_folded_loft = observer
    try:
        body = builder.build_discrete_ribbon_solid(
            component,
            group,
            0,
            route,
            shape,
            guide_planes,
            transform,
            uuid4(),
            CableMaterialSettings(),
            design,
            "production_split_experiment",
            notices=notices,
        )
    finally:
        builder._build_folded_loft = original
    component.name = fixture_name
    observations["loft_section_count"] = len(observer.sections)
    observations["loft_section_names"] = [section.name for section in observer.sections]
    return _BuildOutput(_BodyCollection(body)), observer.sections, ()


def _landmarks(
    body: adsk.fusion.BRepBody, sections: tuple[adsk.fusion.Sketch, ...], lines: int
) -> dict[str, int]:
    """
    Do not silently pass a fallback with no fitted interior loft sections.
    """
    if len(sections) < 3:
        raise AuditFailure("Production output has no fitted interior loft sections to audit.")
    return audit_lobe_landmarks(body, sections, lines)


def _harness(modules: dict[str, ModuleType]) -> ModuleType:
    """
    Create a private harness instance with explicit production-copy dependencies.
    """
    path = PROJECT_ROOT / "experiments/experiment_secure_discrete_ribbon/live.py"
    name = "experiments.experiment_secure_discrete_ribbon._production_comparison"
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not load the isolated comparison harness.")
    harness = importlib.util.module_from_spec(specification)
    sys.modules[name] = harness
    specification.loader.exec_module(harness)
    bindings = {
        "ribbon_frames": ("frames", "ribbon_frames"),
        "bank_ribbon_frames": ("bank", "bank_ribbon_frames"),
        "solve_ribbon_shape": ("shape", "solve_ribbon_shape"),
        "_guide_fit": ("guides", "_guide_fit"),
        "RibbonExitEnd": ("exits", "RibbonExitEnd"),
        "_cap_face": ("exits", "_cap_face"),
        "_section_sketch": ("exits", "_section_sketch"),
        "build_ribbon_exit_loft": ("exits", "build_ribbon_exit_loft"),
    }
    for attribute, (module, symbol) in bindings.items():
        setattr(harness, attribute, getattr(modules[module], symbol))
    harness._build_path = _defer_path
    harness.audit_lobe_landmarks = _landmarks
    return harness


def _run_matrix(case_names: tuple[str, ...] | None, report_name: str) -> None:
    """
    Leave the production-copy matrix open and preserve the secured run's report.
    """
    app = adsk.core.Application.get()
    if str(app.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this comparison.")
    hashes = verify_sources()
    modules = load_sources()
    harness = _harness(modules)
    complete_matrix = stress_cases()
    fingerprint = matrix_fingerprint(complete_matrix)
    matrix = tuple(
        case for case in complete_matrix if case_names is None or case.name in case_names
    )
    if not matrix or (case_names is not None and len(matrix) != len(case_names)):
        raise ValueError("The production comparison selection is invalid.")
    baseline_path = (
        PROJECT_ROOT / "artifacts/verification/secure_discrete_ribbon_bounded/report.json"
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if (
        not isinstance(baseline, dict)
        or baseline.get("completed") is not True
        or baseline.get("matrix_fingerprint") != fingerprint
        or baseline.get("matrix_version") != 4
        or baseline.get("audit_version") != 4
    ):
        raise RuntimeError("A completed identical-input secured baseline is required.")
    for previous in tuple(app.documents):
        if previous.name in (SCRATCH_NAME, "Secure ribbon experiment — Discrete Split"):
            if not previous.close(False):
                raise RuntimeError("Could not close the previous experiment scratch.")
    document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    document.name = SCRATCH_NAME
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("Fusion did not activate the production comparison scratch.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    directory = PROJECT_ROOT / "artifacts/verification" / report_name
    directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    report = {
        "source_revision": SOURCE_REVISION,
        "source_sha256": hashes,
        "production_modified": False,
        "public_production_builder": True,
        "matrix_fingerprint": fingerprint,
        "matrix_version": 4,
        "audit_version": 4,
        "adapter_version": 2,
        "selected_cases": [case.name for case in matrix],
        "safety_controls": "Known negative controls excluded, not production rejections.",
        "completed": False,
        "planned_cases": len(matrix),
        "cases": rows,
    }
    for case in matrix:
        boundary = audit_end_boundary(case)
        if case.expectation is not Expectation.BUILD:
            coverage = transition_coverage(case.lines)
            for transition in coverage:
                transition["reason"] = (
                    "Known negative control; unchanged shared experiment safety policy."
                )
            row = {
                "name": case.name,
                "status": "not_run_safety_control",
                "transitions": coverage,
                "end_boundary": boundary,
            }
        else:
            notices: list[str] = []
            observations: dict[str, object] = {}
            harness._build_folded_loft = partial(
                _build_main,
                builder=modules["builder"],
                route=case.route,
                notices=notices,
                observations=observations,
                design=design,
            )
            row = harness._case(design, case)
            row["production_notices"] = notices
            row["production_observation"] = observations
            row["production_fallback"] = any(
                "using the original sweep" in notice for notice in notices
            )
            if row["production_fallback"] and row["status"] == "built_and_audited":
                row["status"] = "built_with_production_fallback"
        rows.append(row)
        (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        adsk.doEvents()
    built_names = {case.name for case in matrix if case.expectation is Expectation.BUILD}
    baseline_rows = baseline.get("cases")
    if not isinstance(baseline_rows, list) or not all(
        isinstance(row, dict) for row in baseline_rows
    ):
        raise RuntimeError("The secured baseline has malformed case results.")
    report["changed_cases_from_secured"] = compare_outcomes(
        [row for row in baseline_rows if row.get("name") in built_names],
        [row for row in rows if row["name"] in built_names],
    )
    report["summary"] = summarize(rows)
    report["completed"] = True
    report["other_documents"] = [
        {"name": other.name, "modified": other.isModified}
        for other in app.documents
        if other != document
    ]
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    document.activate()
    app.activeViewport.fit()


def run_smoke(_context: object) -> None:
    """
    Verify one public-builder case and audit-reference capture before the matrix.
    """
    _run_matrix(("straight_3x1",), "production_split_ribbon_bounded_smoke")


def run(_context: object) -> None:
    """
    Leave the complete production-copy comparison open with independent reports.
    """
    _run_matrix(None, "production_split_ribbon_bounded")
