"""
Time read-only containment queries on a saved generated ribbon in Fusion.

Requires the active ``Wire creation tester v105`` design, no active command,
and the optional local Fusion MCP script executor. Submit this file as a
``readOnly=true`` script. It neither regenerates nor saves geometry. The
probe is deliberately limited to 24 queries on one generated ribbon body.
"""

import json
from statistics import median
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion


def _ribbon_body(design: adsk.fusion.Design) -> adsk.fusion.BRepBody:
    """
    Find the largest valid solid in the current Cable Group 5 occurrence.
    """
    candidates: list[adsk.fusion.BRepBody] = []
    for occurrence in design.rootComponent.allOccurrences:
        if "Cable Group 5" not in occurrence.name and "Cable Group 5" not in (
            occurrence.component.name
        ):
            continue
        for body in occurrence.component.bRepBodies:
            if body.isValid and body.isSolid:
                candidates.append(body)
    if not candidates:
        raise RuntimeError("The active design has no generated Cable Group 5 solid.")

    def box_size(body: adsk.fusion.BRepBody) -> float:
        """
        Rank without accessing volume, which failed on the former probe.
        """
        box = body.boundingBox
        return (
            (box.maxPoint.x - box.minPoint.x)
            * (box.maxPoint.y - box.minPoint.y)
            * (box.maxPoint.z - box.minPoint.z)
        )

    return max(candidates, key=box_size)


def run(_context: object) -> None:
    """
    Print bounded native timing results without changing the Fusion design.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.name != "Wire creation tester v105":
        raise RuntimeError("Open the expected Wire creation tester v105 design first.")
    modified_before = document.isModified
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before measuring containment.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    body = _ribbon_body(design)
    box = body.boundingBox
    minimum, maximum = box.minPoint, box.maxPoint
    points = tuple(
        adsk.core.Point3D.create(
            minimum.x + (maximum.x - minimum.x) * ((index % 4) + 1) / 5.0,
            minimum.y + (maximum.y - minimum.y) * (((index // 4) % 3) + 1) / 4.0,
            minimum.z + (maximum.z - minimum.z) * (((index // 12) % 2) + 1) / 3.0,
        )
        for index in range(24)
    )
    times_ms: list[float] = []
    classifications: dict[str, int] = {}
    for point in points:
        started = perf_counter()
        containment = body.pointContainment(point)
        times_ms.append((perf_counter() - started) * 1000.0)
        name = str(containment)
        classifications[name] = classifications.get(name, 0) + 1
    ordered = sorted(times_ms)
    print(
        "RIBBON_OVERLAP_PROBE="
        + json.dumps(
            {
                "document": document.name,
                "body": body.name,
                "query_count": len(points),
                "total_ms": round(sum(times_ms), 2),
                "median_ms": round(median(times_ms), 2),
                "p95_ms": round(ordered[int((len(ordered) - 1) * 0.95)], 2),
                "classifications": classifications,
                "design_modified_before": modified_before,
                "design_modified_after": document.isModified,
            },
            sort_keys=True,
        )
    )
