"""
Stress PH-projection hairpins and ribbon twist in an unsaved Fusion design.

Run through Fusion ``Python.Run`` with no active command. This leaves the
scratch design open and writes an ignored JSON report. No product data is
modified.
"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter_ns

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_ph_fusion_sweep import _sweep_case
from experiments.experiment_ph_quintic import ph_hermite_candidates
from experiments.experiment_ph_spaghetti import hermite_case, stress_cases
from experiments.experiment_ph_spaghetti import run as run_math


def run(_context: object) -> None:
    """
    Probe 69 sweep configurations in a fresh design, retaining all geometry.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before the spaghetti probe.")
    math_report = run_math()
    math_by_name = {entry["name"]: entry for entry in math_report["cases"]}
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create a spaghetti scratch design.")
    report: dict[str, object] = {"document": scratch.name, "cases": []}
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("The spaghetti scratch is not a Fusion design.")
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        root = design.rootComponent
        for index, stress in enumerate(stress_cases()):
            entry: dict[str, object] = {
                "name": stress.name,
                "profile": stress.profile,
                "separation_mm": stress.separation_mm,
                "twist_degrees": stress.twist_degrees,
                "lateral_displacement_mm": stress.lateral_displacement_mm,
                "curve_type": math_by_name[stress.name]["curve_type"],
                "planar_minimum_sampled_radius_mm": math_by_name[stress.name][
                    "planar_minimum_sampled_radius_mm"
                ],
            }
            report["cases"].append(entry)
            started = perf_counter_ns()
            try:
                curve = ph_hermite_candidates(hermite_case(stress))[0]
                entry.update(
                    _sweep_case(
                        root,
                        stress.name,
                        curve.controls,
                        index * 10.0,
                        wire_radius_mm=1.5,
                        ribbon_width_mm=(10.0 if stress.profile == "ribbon_10x0p5mm" else None),
                        twist_degrees=stress.twist_degrees,
                        lateral_displacement_mm=stress.lateral_displacement_mm,
                    )
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                entry["result"] = "failed"
                entry["error"] = str(error)
            entry["sweep_wall_ms"] = (perf_counter_ns() - started) / 1e6
        application.activeViewport.fit()
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        report["fatal_error"] = str(error)
    finally:
        report["active_document"] = application.activeDocument.name
        output = (
            Path(cable_bundler.__file__).resolve().parents[1]
            / "artifacts/verification/ph_spaghetti_fusion.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
        )
        print(
            "PH_SPAGHETTI_SWEEP="
            + json.dumps(
                {
                    "document": scratch.name,
                    "case_count": len(report["cases"]),
                    "solid_count": sum(entry["result"] == "solid" for entry in report["cases"]),
                    "fatal_error": report.get("fatal_error"),
                    "report": str(output),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    run(None)
