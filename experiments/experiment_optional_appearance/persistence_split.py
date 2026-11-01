"""
Verify embedded images after the import transaction commits, without source PNGs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Any

from experiments.experiment_optional_appearance.files import restore_offline_directory
from experiments.experiment_optional_appearance.runner import ROOT


def native(run_directory: str, case_id: str, operation: str) -> None:
    """
    Execute one isolated export/import/read operation in the owned idle design.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    from devtools.ribbon_analysis.budget import NativeBudget
    from devtools.ribbon_analysis.inspection.archive import write_document
    from experiments.experiment_optional_appearance.host import DOCUMENT_ID

    run = Path(run_directory)
    plan = json.loads((run / "plan.json").read_text())
    budget = NativeBudget(maximum_seconds=60, maximum_rss_kib=4194304)
    result: dict[str, Any] = {"id": case_id, "operation": operation, "status": "preparing"}
    try:
        baked = json.loads((Path(plan["bake_path"]) / "result.json").read_text())
        case = next(c for c in baked["cases"] if c["id"] == case_id)
        offline_names = {str(Path(f["path"]).relative_to(ROOT)) for f in case["faces"]}
        for name, digest in plan["sources"].items():
            if operation in ("import", "verify") and name in offline_names:
                if (ROOT / name).exists():
                    raise RuntimeError("Expected source image is not offline")
                continue
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Source drift")
        budget.check("launch")
        if budget.memory() >= 3984588:
            raise RuntimeError("Launch headroom")
        app = adsk.core.Application.get()
        if (
            app.activeDocument.creationId != DOCUMENT_ID
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Owned idle document guard")
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent
        if operation == "export":
            occurrence = next(o for o in root.occurrences if o.component.name == case["component"])
            body = occurrence.component.bRepBodies.item(0)
            if body.revisionId != case["revision"] or abs(body.volume - case["volume_cm3"]) > 1e-12:
                raise RuntimeError("Source geometry changed")
            points = {}
            for item in case["faces"]:
                face = body.faces.item(item["index"])
                face.attributes.add("OptionalAppearanceTrial", "source_face", str(item["index"]))
                p = face.pointOnFace
                points[item["index"]] = [p.x, p.y, p.z]
            folder = run / case_id
            folder.mkdir()
            archive = folder / "body.f3d"
            if not design.exportManager.execute(
                design.exportManager.createFusionArchiveExportOptions(
                    str(archive), occurrence.component
                )
            ):
                raise RuntimeError("Archive export failed")
            result.update(
                {
                    "points": points,
                    "archive": str(archive),
                    "archive_bytes": archive.stat().st_size,
                    "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                }
            )
        elif operation == "import":
            if any(Path(f["path"]).exists() for f in case["faces"]):
                raise RuntimeError("External source images were not hidden")
            archive = run / case_id / "body.f3d"
            exported = json.loads((run / (case_id + "-export-result.json")).read_text())
            if hashlib.sha256(archive.read_bytes()).hexdigest() != exported["archive_sha256"]:
                raise RuntimeError("Archive changed before import")
            target = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            target.component.name = run.name + " - Post-commit - " + case_id
            target.isLightBulbOn = False
            imported = app.importManager.importToTarget2(
                app.importManager.createFusionArchiveImportOptions(str(archive)), target.component
            )
            if imported is None:
                raise RuntimeError("Archive import failed")
            result["component"] = target.component.name
        elif operation == "verify":
            if any(Path(f["path"]).exists() for f in case["faces"]):
                raise RuntimeError("External source images reappeared before verification")
            exported = json.loads((run / (case_id + "-export-result.json")).read_text())
            imported = json.loads((run / (case_id + "-import-result.json")).read_text())
            target = next(
                o.component for o in root.occurrences if o.component.name == imported["component"]
            )
            bodies = list(target.bRepBodies)
            for child in target.allOccurrences:
                bodies.extend(child.component.bRepBodies)
            if len(bodies) != 1:
                raise RuntimeError("Imported body count mismatch")
            body = bodies[0]
            if (
                body.faces.count != len(case["faces"]) + 2
                or abs(body.volume - case["volume_cm3"]) > 1e-10
            ):
                raise RuntimeError("Imported body topology/volume mismatch")
            seen = set()
            result["verified_faces"] = 0
            for face in body.faces:
                identity = face.attributes.itemByName("OptionalAppearanceTrial", "source_face")
                if identity is None:
                    continue
                index = int(identity.value)
                if index in seen:
                    raise RuntimeError("Duplicated restored face identity")
                seen.add(index)
                appearance = face.appearance
                path = None if appearance is None else Path(appearance.colorTexture)
                if path is None or not path.is_absolute() or not path.is_file():
                    raise RuntimeError(
                        f"Image unavailable after import commit: face{index}: {path}"
                    )
                if hashlib.sha256(path.read_bytes()).hexdigest() != case["faces"][index]["sha256"]:
                    raise RuntimeError("Imported image bytes changed")
                point = adsk.core.Point3D.create(*exported["points"][str(index)])
                ok, uv = face.evaluator.getParameterAtPoint(point)
                valid, actual = face.evaluator.getPointAtParameter(uv) if ok else (False, None)
                if not valid or actual.distanceTo(point) * 10 > 1e-6:
                    raise RuntimeError("Restored face/material association changed")
                result["verified_faces"] += 1
            if len(seen) != len(case["faces"]):
                raise RuntimeError("Lost persistent face identities")
            result["external_sources_unavailable"] = True
        else:
            raise ValueError("Unknown native persistence operation")
        result["status"] = "passed"
    except Exception:
        # Keep partial native state, archives and exact failing operation available.
        result["status"] = "stopped"
        result["error"] = traceback.format_exc()
    finally:
        result["elapsed_seconds"] = budget.clock() - budget.started
        result["rss_samples"] = budget.samples
        write_document(run / (case_id + "-" + operation + "-result.json"), result)
        print(json.dumps({k: v for k, v in result.items() if k not in {"points", "rss_samples"}}))


def main() -> None:
    """
    Keep source/sidecar directories offline across separate committed MCP calls.
    """
    from experiments.qa_orchestrator import McpClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bake", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts" / "verification")
    run.mkdir(parents=True, exist_ok=True)
    baked = json.loads((args.bake / "result.json").read_text())
    paths = [
        *Path(__file__).parent.glob("*.py"),
        args.bake / "result.json",
        *args.bake.glob("*/*.png"),
    ]
    plan = {
        "bake_path": str(args.bake.resolve()),
        "scope": "Four existing configurations,one archive import percase,0newgeometry/solves. Separate export/import/verify MCP calls. SDK finally restores source PNG and export-sidecar directories after each case;they stay unavailable during import,transaction commit and subsequent verification. One owned idle design,no document open/close/cloudsave.60seconds/nativeoperation,300seconds aggregate,4GiB/3.8GiB launch,no retries. Warm-session archive evidence,not cold restart.",
        "renewal": "250immediate resource checks stopped on calibration;252event-pumped10second wait verified calibration then stopped on gym-1.251/253later calls found resources readable. Test whether a committed import boundary is required;preserve failed attempts and do not copy substitute image data.",
        "sources": {
            str(p.resolve().relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
    }
    with (run / "plan.json").open("x") as stream:
        json.dump(plan, stream, indent=2)
    client = McpClient("http://127.0.0.1:27182/mcp", 90)
    client.initialize()
    started = time.perf_counter()
    result: dict[str, Any] = {"status": "preparing", "cases": []}

    def call(case_id: str, operation: str) -> dict[str, Any]:
        """
        Return only after a source-pinned native operation has committed.
        """
        if time.perf_counter() - started > 300:
            raise RuntimeError("Aggregate scheduling budget")
        script = (
            "def run(context):\n import runpy\n ns=runpy.run_path("
            + repr(str(Path(__file__)))
            + ")\n ns['native']("
            + repr(str(run))
            + ","
            + repr(case_id)
            + ","
            + repr(operation)
            + ")\n"
        )
        response = client.call_tool(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": script, "readOnly": False}},
        )
        with (run / (case_id + "-" + operation + "-response.json")).open("x") as stream:
            json.dump(response, stream)
        record = json.loads((run / (case_id + "-" + operation + "-result.json")).read_text())
        if record["status"] != "passed":
            raise RuntimeError(record.get("error", "Native persistence operation stopped"))
        return record

    try:
        for case in baked["cases"]:
            call(case["id"], "export")
            folders = [Path(case["faces"][0]["path"]).parent]
            sidecars = run / case["id"] / "_XRef_"
            if sidecars.exists():
                folders.append(sidecars)
            renamed = []
            try:
                for folder in folders:
                    offline = folder.with_name(folder.name + "-temporarily-offline")
                    if offline.exists():
                        raise RuntimeError("Offline retention path already exists")
                    folder.rename(offline)
                    renamed.append((folder, offline))
                call(case["id"], "import")
                checked = call(case["id"], "verify")
                result["cases"].append({k: v for k, v in checked.items() if k != "rss_samples"})
            finally:
                for folder, offline in reversed(renamed):
                    restore_offline_directory(folder, offline)
        result["status"] = "four_post_commit_archives_verified"
    except Exception:
        # Preserve failed/unfinished cases while restoring all deliberately hidden files.
        result["status"] = "stopped"
        result["error"] = traceback.format_exc()
    finally:
        result["elapsed_seconds"] = time.perf_counter() - started
        with (run / "result.json").open("x") as stream:
            json.dump(result, stream)
        print(json.dumps(result)[:7000])


if __name__ == "__main__":
    main()
