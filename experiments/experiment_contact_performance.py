"""
Read-only contact performance probe for the active PCB assembly with saved contacts.

Requires Fusion and the local MCP server. Run with readOnly=true, no active native
command. Uses isolated source modules without reloading the running add-in. Samples
at most eight faces; reports timings and Python allocation retention, not a claim
about Fusion's native heap. No selection, geometry, names, or attributes are changed.
"""

from __future__ import annotations

import gc
import json
import os
import runpy
import subprocess
import tracemalloc
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads
from cable_bundler.fusion.interface_contact_cache import clear_contact_resolutions
from cable_bundler.fusion.interface_targets import resolve_interface_target


def _resident_bytes() -> int | None:
    """
    Read this Fusion process's resident footprint on the local macOS host, if available.
    """
    try:
        result = subprocess.run(
            ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return int(result.stdout.strip()) * 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def run(_context: object) -> None:
    """
    Guarantee the read-only probe releases all temporary cached Fusion references.
    """
    try:
        _measure()
    finally:
        clear_contact_resolutions()


def _measure() -> None:
    """
    Compare sampled and analytic pad measurements on the same live faces.
    """
    naming = runpy.run_module("cable_bundler.fusion.interface_contact_naming")
    rows = runpy.run_module("cable_bundler.fusion.interface_contact_rows", alter_sys=True)
    projection = runpy.run_module("cable_bundler.fusion.interface_contact_projection")
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Activate the PCB assembly first.")
    for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition"):
        for interface in loads(attribute.value).interfaces:
            if not interface.contacts:
                continue
            board = resolve_interface_target(design, interface.targets[0])
            origin, axes = naming["_frame"](board)
            faces = []
            for contact in sorted(
                interface.contacts, key=lambda item: not item.name.startswith("J")
            )[:32]:
                candidates = design.findEntityByToken(contact.entity_token) or ()
                for candidate in candidates:
                    measured = naming["_face_footprint"](
                        candidate, str(contact.contact_id), board.fullPathName, origin, axes
                    )
                    if measured is not None and measured.hole_diameter_mm > 0:
                        faces.append((candidate, str(contact.contact_id)))
                        break
                if len(faces) == 8:
                    break
            if not faces:
                print(
                    json.dumps(
                        {
                            "skipped_interface": interface.name,
                            "board_path": board.fullPathName,
                            "reason": "No comparable through-hole faces among 32 contacts",
                        }
                    )
                )
                continue
            report = {"sample_count": len(faces), "saved_contacts": len(interface.contacts)}
            results = {}
            token_start = perf_counter()
            for contact in interface.contacts[:8]:
                design.findEntityByToken(contact.entity_token)
            report["resolve_8_tokens_seconds"] = perf_counter() - token_start
            projection_start = perf_counter()
            for contact in interface.contacts[:8]:
                projection["project_interface_contact"](design, contact)
            report["project_8_contacts_seconds"] = perf_counter() - projection_start
            projection_start = perf_counter()
            for contact in interface.contacts[:8]:
                projection["project_interface_contact"](design, contact)
            report["cached_project_8_contacts_seconds"] = perf_counter() - projection_start
            for label, helper in (
                ("sampled", "_face_footprint"),
                ("analytic", "_through_hole_footprint"),
            ):
                start = perf_counter()
                results[label] = [
                    naming[helper](face, identity, board.fullPathName, origin, axes)
                    for face, identity in faces
                ]
                report[label + "_seconds"] = perf_counter() - start
            comparable = [
                (a, b)
                for a, b in zip(results["sampled"], results["analytic"])
                if a is not None and b is not None and a.hole_diameter_mm > 0
            ]
            report["matching_holes"] = len(comparable)
            assert all(
                abs(a.x - b.x) < 0.02
                and abs(a.y - b.y) < 0.02
                and abs(a.hole_diameter_mm - b.hole_diameter_mm) < 0.02
                for a, b in comparable
            )
            if len(faces) > 1:
                first, last = faces[0][0], faces[-1][0]
                start, end = rows["describe_row_target"](first), rows["describe_row_target"](last)
                scope = rows["_scope"](first)
                for label, bounds in (("all", None), ("bounded", (start.center_mm, end.center_mm))):
                    began = perf_counter()
                    report[label + "_candidates"] = sum(
                        1 for _ in rows["_candidates"](scope, start.kind, bounds)
                    )
                    report[label + "_enumeration_seconds"] = perf_counter() - began
            owned_trace = not tracemalloc.is_tracing()
            if owned_trace:
                tracemalloc.start()
            try:
                retained = []
                resident = []
                for _ in range(5):
                    for contact in interface.contacts[:8]:
                        projection["project_interface_contact"](design, contact)
                    for face, identity in faces:
                        naming["_through_hole_footprint"](
                            face, identity, board.fullPathName, origin, axes
                        )
                    gc.collect()
                    retained.append(tracemalloc.get_traced_memory()[0])
                    resident.append(_resident_bytes())
                report["python_retained_bytes_by_pass"] = retained
                report["fusion_resident_bytes_by_pass"] = resident
            finally:
                if owned_trace:
                    tracemalloc.stop()
            print(json.dumps(report))
            return
    raise RuntimeError("Save Interface contacts in the active assembly first.")
