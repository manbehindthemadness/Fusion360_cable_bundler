"""
Bake a later-selected image appearance over four frozen native chart exports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude, unit
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc, material_profile

from .bitmap import ColorMap, read_png
from .boundary import boundary_nodes, crease_coordinates
from .material import material_coordinates
from .raster import SIZE, png, raster, sample
from .runner import CASES, ROOT


def source_map(
    descriptor: dict[str, Any], alternate: bool, asset_root: Path | None = None
) -> tuple[ColorMap, Path]:
    """
    Reject untested texture types/transforms before reading a supported PNG map.
    """
    if descriptor["type"] != 1:
        raise ValueError("Native procedural/unknown color textures are unsupported")
    props = descriptor["properties"]
    if any(
        props[k] != 0
        for k in ("texture_RealWorldOffsetX", "texture_RealWorldOffsetY", "texture_WAngle")
    ):
        raise ValueError("Nonzero source offsets/rotation require separate validation")
    if not props["texture_URepeat"] or not props["texture_VRepeat"]:
        raise ValueError("The current source sampler requires both repeat modes")
    path = Path(descriptor["alternate_image"] if alternate else descriptor["path"])
    if not path.is_absolute():
        if asset_root is None:
            raise ValueError("Library-relative images require an explicit asset root")
        base = asset_root.resolve()
        path = (base / path).resolve()
        path.relative_to(base)
    return ColorMap(
        read_png(path),
        (props["texture_RealWorldScaleX"] * 10, props["texture_RealWorldScaleY"] * 10),
    ), path


def restore(row: dict[str, Any]) -> tuple[PlacedPiece, ...]:
    """
    Restore only the frozen physical pieces, without invoking a solver.
    """
    return tuple(
        PlacedPiece(
            Pose(**{k: Vector3(**v) for k, v in item["pose"].items()}),
            CylindricalFold(**item["geometry"])
            if item["kind"] == "fold"
            else Straight(**item["geometry"]),
            item["label"],
        )
        for item in row["pieces"]
    )


def face_coordinates(
    face: dict[str, Any], piece: PlacedPiece, start: float, half: float, arc: MaterialArc
) -> tuple[list[tuple[float, float]], float]:
    """
    Reconstruct actual float display nodes before using their material coordinates.
    """
    values = []
    worst = 0.0
    boundary = boundary_nodes(face) if face["region"] == "bend" else set()
    for index, p in enumerate(face["points_cm"]):
        point = Vector3(*(v * 10 for v in p))
        s, q, height = material_coordinates(piece, face["region"], point)
        known_section = crease_coordinates(piece, arc, p) if index in boundary else None
        if known_section is not None:
            s, q, height = known_section
        if not -1e-5 <= s <= piece.geometry.material_length_mm + 1e-5 or abs(q) > half + 1e-5:
            raise RuntimeError("Display point outside bounded endpoint roundoff")
        u = min(1.0, max(0.0, s / piece.geometry.material_length_mm))
        planned, velocity, across, _ = piece.surface(u, min(half, max(-half, q)))
        error = magnitude(
            difference(point, planned.translated(unit(cross(velocity, across)), height))
        )
        worst = max(worst, error)
        if error > 1e-3:
            raise RuntimeError("Material reconstruction failed")
        values.append((start + s, q))
    return values, worst


def audit_seams(
    charts: dict[str, Any],
    maps: list[list[tuple[float, float]]],
    images: list[tuple[bytes, list[float]]],
) -> dict[str, Any]:
    """
    Measure saved-image interpolation over every actual native side adjacency.
    """
    edges: dict[int, set[int]] = defaultdict(set)
    nodes: dict[tuple[int, ...], list[tuple[int, int]]] = defaultdict(list)
    for face in charts["faces"]:
        for edge in face["edges"]:
            edges[edge].add(face["index"])
        for j, point in enumerate(face["points_cm"]):
            nodes[tuple(round(v * 10 / 1e-6) for v in point)].append((face["index"], j))
    rows = {
        tuple(sorted(pair)): {
            "faces": sorted(pair),
            "nodes": 0,
            "maximum_rgb_error": 0.0,
            "maximum_material_error_mm": 0.0,
            "rgb_error_sum": 0.0,
        }
        for pair in edges.values()
        if len(pair) == 2
    }
    for values in nodes.values():
        for k, (i, a) in enumerate(values):
            for j, b in values[k + 1 :]:
                key = tuple(sorted((i, j)))
                if (
                    key not in rows
                    or math.dist(
                        charts["faces"][i]["points_cm"][a], charts["faces"][j]["points_cm"][b]
                    )
                    * 10
                    > 1e-6
                ):
                    continue
                row = rows[key]
                first = sample(*images[i], charts["faces"][i]["uv"][a])
                second = sample(*images[j], charts["faces"][j]["uv"][b])
                error = max(abs(x - y) for x, y in zip(first, second))
                material_error = max(abs(x - y) for x, y in zip(maps[i][a], maps[j][b]))
                row["nodes"] += 1
                row["maximum_rgb_error"] = max(row["maximum_rgb_error"], error)
                row["rgb_error_sum"] += error
                row["maximum_material_error_mm"] = max(
                    row["maximum_material_error_mm"], material_error
                )
    if any(row["nodes"] == 0 or row["maximum_material_error_mm"] > 1e-4 for row in rows.values()):
        raise RuntimeError("Missing seam evidence or material-coordinate mismatch")
    count = sum(row["nodes"] for row in rows.values())
    return {
        "adjacencies": len(rows),
        "sampled_adjacencies": sum(row["nodes"] > 0 for row in rows.values()),
        "matched_nodes": count,
        "maximum_rgb_error": max(row["maximum_rgb_error"] for row in rows.values()),
        "mean_rgb_error": sum(row["rgb_error_sum"] for row in rows.values()) / count,
        "maximum_material_error_mm": max(row["maximum_material_error_mm"] for row in rows.values()),
        "seams": list(rows.values()),
    }


def bake_case(
    run: Path,
    export: Path,
    spec: dict[str, str],
    color_map: ColorMap,
    source_digest: str,
    budget: NativeBudget,
) -> dict[str, Any]:
    """
    Produce one face image per native side face with a content-bound cache key.
    """
    started = time.perf_counter()
    charts_path = export / (spec["id"] + "-charts.json")
    charts = json.loads(charts_path.read_text())
    row = json.loads((ROOT / spec["input"]).read_text())
    pieces = restore(row)
    profile = material_profile(row["lines"], row["diameter_mm"])
    starts = [sum(p.geometry.material_length_mm for p in pieces[:i]) for i in range(len(pieces))]
    half = row["profile_width_mm"] / 2
    target = run / spec["id"]
    target.mkdir()
    maps = []
    images = []
    records = []
    maximum_error = 0.0
    cache_key = hashlib.sha256(
        json.dumps(
            {
                "source": source_digest,
                "scale": color_map.scale_mm,
                "charts": hashlib.sha256(charts_path.read_bytes()).hexdigest(),
                "input": hashlib.sha256((ROOT / spec["input"]).read_bytes()).hexdigest(),
                "resolution": SIZE,
                "algorithm": hashlib.sha256(
                    b"".join(
                        Path(__file__).with_name(name).read_bytes()
                        for name in ("material.py", "raster.py", "bitmap.py", "boundary.py")
                    )
                ).hexdigest(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    for face in charts["faces"]:
        if face["index"] % 16 == 0:
            budget.check("bounded group of sixteen baked faces")
        if time.perf_counter() - started > 120:
            raise RuntimeError("Per-configuration bake budget")
        coordinates, error = face_coordinates(
            face,
            pieces[face["piece_index"]],
            starts[face["piece_index"]],
            half,
            profile[face["profile_index"]],
        )
        maximum_error = max(maximum_error, error)
        rgb, bounds, coverage = raster(face, coordinates, color_map.sample)
        path = target / f"face-{face['index']:03}.png"
        with path.open("xb") as stream:
            stream.write(png(rgb, SIZE))
        # Audit the saved RGB bytes through the independent PNG decoder.
        decoded = read_png(path)
        if decoded.pixels != rgb:
            raise RuntimeError("Saved PNG differs from raster bytes")
        images.append((decoded.pixels, bounds))
        maps.append(coordinates)
        records.append(
            {
                "index": face["index"],
                "bounds": bounds,
                "covered_pixels": coverage,
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    raster_seconds = time.perf_counter() - started
    audit = audit_seams(charts, maps, images)
    return {
        "id": spec["id"],
        "component": charts["component"],
        "revision": charts["revision"],
        "volume_cm3": charts["volume_cm3"],
        "cache_key": cache_key,
        "faces": records,
        "raster_and_mapping_seconds": raster_seconds,
        "total_seconds": time.perf_counter() - started,
        "maximum_reconstruction_error_mm": maximum_error,
        "audit": audit,
    }


def main() -> None:
    """
    Freeze a finite four-case image-source trial and retain any interrupted cases.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", dest="export_path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alternate", action="store_true")
    parser.add_argument("--asset-root", type=Path)
    args = parser.parse_args()
    run, export = args.output.resolve(), args.export_path.resolve()
    run.relative_to(ROOT / "artifacts" / "verification")
    run.mkdir(parents=True, exist_ok=True)
    source = json.loads((export / "result.json").read_text())
    color_map, image_path = source_map(source["source"], args.alternate, args.asset_root)
    source_digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    paths = [
        *Path(__file__).parent.glob("*.py"),
        *export.glob("*-charts.json"),
        export / "result.json",
        *(ROOT / spec["input"] for spec in CASES),
    ]
    plan = {
        "question": "Validate deferred image-color baking across four existing complete gym configurations.",
        "scope": "Zero newgeometry/solves;native source bitmap taken from a Fusion appearance after copies existed. Base-color only,128square,zero source offset/rotation,repeat on. Endcap mismatch accepted. Original raster algorithm retained;no specimen tuning. Check source-data rejection,all copied charts,image hashes,physical mapping and every native side adjacency. RGB errors are measured diagnostics,not a pixel-perfect claim.",
        "limits": {"case_seconds": 120, "aggregate_seconds": 480, "rss_kib": 4194304, "retries": 0},
        "alternate": args.alternate,
        "source_image": str(image_path),
        "source_sha256": source_digest,
        "sources": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
    }
    with (run / "plan.json").open("x") as stream:
        json.dump(plan, stream, indent=2)
    budget = NativeBudget(maximum_seconds=480, maximum_rss_kib=4194304)
    output: dict[str, Any] = {
        "status": "preparing",
        "cases": [],
        "source_image_sha256": source_digest,
        "source_scale_mm": color_map.scale_mm,
        "source_is_later_selected": True,
        "new_geometry_attempts": 0,
        "new_solves": 0,
    }
    try:
        budget.check("local launch")
        for spec in CASES:
            output["cases"].append(bake_case(run, export, spec, color_map, source_digest, budget))
        output["status"] = "four_supported_color_maps_baked"
    except Exception:
        # Preserve failed and unfinished outputs without retries or input changes.
        output["status"] = "stopped"
        output["error"] = traceback.format_exc()
    finally:
        output["elapsed_seconds"] = budget.clock() - budget.started
        output["rss_samples"] = budget.samples
        with (run / "result.json").open("x") as stream:
            json.dump(output, stream)
        print(json.dumps({k: v for k, v in output.items() if k not in {"cases", "rss_samples"}}))
        for case in output["cases"]:
            print(
                json.dumps(
                    {
                        "id": case["id"],
                        "faces": len(case["faces"]),
                        "seconds": case["total_seconds"],
                        **{k: v for k, v in case["audit"].items() if k != "seams"},
                    }
                )
            )


if __name__ == "__main__":
    main()
