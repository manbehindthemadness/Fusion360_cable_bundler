"""
Test component archive persistence while original baked PNG paths are unavailable.
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


def native(run_directory: str) -> None:
    """
    Export/reimport only owned components, restoring external image directories.

    This is a same-session archive test, not a cold Fusion restart. It opens no
    documents and changes no original body, physical rule, target or native shape.
    """
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    from devtools.ribbon_analysis.budget import NativeBudget
    from devtools.ribbon_analysis.inspection.archive import write_document
    from experiments.experiment_optional_appearance.host import DOCUMENT_ID, capture

    run = Path(run_directory)
    plan = json.loads((run / "plan.json").read_text())
    budget = NativeBudget(maximum_seconds=120, maximum_rss_kib=4194304)
    output: dict[str, Any] = {"status": "preparing", "cases": []}
    try:
        for name, digest in plan["sources"].items():
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
        baked = json.loads((Path(plan["bake_path"]) / "result.json").read_text())
        for case in baked["cases"]:
            budget.check("archive one complete calibration or gym case")
            occurrence = next(o for o in root.occurrences if o.component.name == case["component"])
            body = occurrence.component.bRepBodies.item(0)
            record: dict[str, Any] = {"id": case["id"], "verified_faces": 0}
            output["cases"].append(record)
            if body.revisionId != case["revision"] or abs(body.volume - case["volume_cm3"]) > 1e-12:
                raise RuntimeError("Source copy changed before archive")
            points = {}
            for item in case["faces"]:
                face = body.faces.item(item["index"])
                face.attributes.add("OptionalAppearanceTrial", "source_face", str(item["index"]))
                p = face.pointOnFace
                points[item["index"]] = (p.x, p.y, p.z)
            archive = run / (case["id"] + ".f3d")
            options = design.exportManager.createFusionArchiveExportOptions(
                str(archive), occurrence.component
            )
            if not design.exportManager.execute(options):
                raise RuntimeError("Component archive export failed")
            record["archive_bytes"] = archive.stat().st_size
            folder = Path(case["faces"][0]["path"]).parent
            offline = folder.with_name(folder.name + "-temporarily-offline")
            if offline.exists():
                raise RuntimeError("Offline retention path already exists")
            folder.rename(offline)
            try:
                if any(Path(item["path"]).exists() for item in case["faces"]):
                    raise RuntimeError("Original PNG paths still available")
                target = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
                target.component.name = run.name + " - Reimport - " + case["id"]
                target.isLightBulbOn = False
                imported = app.importManager.importToTarget2(
                    app.importManager.createFusionArchiveImportOptions(str(archive)),
                    target.component,
                )
                if imported is None:
                    raise RuntimeError("Component archive import failed")
                bodies = list(target.component.bRepBodies)
                for child in target.component.allOccurrences:
                    bodies.extend(child.component.bRepBodies)
                if len(bodies) != 1:
                    raise RuntimeError("Expected exactly one imported body")
                restored = bodies[0]
                if (
                    restored.faces.count != body.faces.count
                    or abs(restored.volume - case["volume_cm3"]) > 1e-10
                ):
                    raise RuntimeError("Imported body count/volume mismatch")
                started = time.perf_counter()
                first_poll = True
                while True:
                    unavailable = 0
                    for face in restored.faces:
                        if (
                            face.attributes.itemByName("OptionalAppearanceTrial", "source_face")
                            is None
                        ):
                            continue
                        appearance = face.appearance
                        path = None if appearance is None else Path(appearance.colorTexture)
                        if path is None or not path.is_absolute() or not path.is_file():
                            unavailable += 1
                    if first_poll:
                        record["initial_unavailable_images"] = unavailable
                        first_poll = False
                    if not unavailable:
                        break
                    if time.perf_counter() - started > 10:
                        raise RuntimeError(
                            "Embedded images did not become readable within10seconds"
                        )
                    budget.check("bounded wait for imported image resources")
                    adsk.doEvents()
                    time.sleep(0.05)
                record["resource_wait_seconds"] = time.perf_counter() - started
                seen = set()
                for face in restored.faces:
                    identity = face.attributes.itemByName("OptionalAppearanceTrial", "source_face")
                    if identity is None:
                        continue
                    index = int(identity.value)
                    if index in seen:
                        raise RuntimeError("Duplicate restored face identity")
                    seen.add(index)
                    appearance = face.appearance
                    if appearance is None:
                        raise RuntimeError("Missing imported face appearance")
                    path = Path(appearance.colorTexture)
                    if not path.is_absolute() or not path.is_file():
                        raise RuntimeError("Imported image is not independently readable")
                    if (
                        hashlib.sha256(path.read_bytes()).hexdigest()
                        != case["faces"][index]["sha256"]
                    ):
                        raise RuntimeError("Imported embedded image differs")
                    point = adsk.core.Point3D.create(*points[index])
                    ok, uv = face.evaluator.getParameterAtPoint(point)
                    valid, actual = face.evaluator.getPointAtParameter(uv) if ok else (False, None)
                    if not valid or actual.distanceTo(point) * 10 > 1e-6:
                        raise RuntimeError("Persistent face correspondence failed")
                    record["verified_faces"] += 1
                if len(seen) != len(case["faces"]):
                    raise RuntimeError("Missing restored face identities")
                record["external_sources_unavailable"] = True
                record["images_embedded_and_corresponding"] = True
                record["imported_component"] = target.component.name
            finally:
                restore_offline_directory(folder, offline)
        first = next(
            o for o in root.occurrences if o.component.name == baked["cases"][0]["component"]
        )
        first.isLightBulbOn = True
        capture(app, first, run / "visible-calibration.png")
        output["status"] = "four_archives_reimported_without_external_baked_files"
    except Exception:
        # Retain all archives and partial imported copies on native or resource stops.
        output["status"] = "stopped"
        output["error"] = traceback.format_exc()
    finally:
        output["elapsed_seconds"] = budget.clock() - budget.started
        output["rss_samples"] = budget.samples
        write_document(run / "result.json", output)
        print(json.dumps({k: v for k, v in output.items() if k != "rss_samples"}))


def main() -> None:
    """
    Freeze an archive-only reliability phase before local MCP execution.
    """
    from experiments.qa_orchestrator import McpClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bake", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.output.resolve()
    run.relative_to(ROOT / "artifacts" / "verification")
    run.mkdir(parents=True, exist_ok=True)
    paths = [
        *Path(__file__).parent.glob("*.py"),
        args.bake / "result.json",
        *args.bake.glob("*/*.png"),
    ]
    plan = {
        "renewal": "250stopped after21calibration images because imported resources were not all independently readable immediately.251read-only diagnosis confirms all imported paths become valid deserializer-cache files later. Preserve250and251. This phase adds bounded10second event-pumped resource readiness before hash checks; no image fallback,copying or geometry/tolerance change. Other three original250cases were unattempted.",
        "bake_path": str(args.bake.resolve()),
        "scope": "Four existing configurations;export each owned component,reimport into owned current design while its external baked-image directory is temporarily renamed. Always restore that directory.4archive copies,0newgeometry builds/solves/targets. Native face identity attributes,volume/face count,image bytes and face geometry correspondences checked. One owned design,no cloudsave or document close.120s/4GiB/3.8GiB launch,no retries. Same-session archive evidence only;do not claim cold restart.",
        "sources": {
            str(p.resolve().relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
    }
    with (run / "plan.json").open("x") as stream:
        json.dump(plan, stream, indent=2)
    client = McpClient("http://127.0.0.1:27182/mcp", 150)
    client.initialize()
    script = (
        "def run(context):\n import runpy\n ns=runpy.run_path("
        + repr(str(Path(__file__)))
        + ")\n ns['native']("
        + repr(str(run))
        + ")\n"
    )
    response = client.call_tool(
        "fusion_mcp_execute",
        {"featureType": "script", "object": {"script": script, "readOnly": False}},
    )
    with (run / "response.json").open("x") as stream:
        json.dump(response, stream)
    print(json.dumps(response)[:5000])


if __name__ == "__main__":
    main()
