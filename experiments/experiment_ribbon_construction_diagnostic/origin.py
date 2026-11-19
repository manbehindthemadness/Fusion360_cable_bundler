"""
Observe endpoint-only terminal construction before any saved route or placement exists.

Hooks capture executed derivation boundaries, not a reconstructed assembly order.
LP coordinates are sampled through their original immutable model for display;
zero-travel templates are explicitly unclosed, and no observer grants qualification.
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.construction.journal import Journal
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_constrained_construction.envelopes import Exclusion
from experiments.experiment_ribbon_constrained_construction.linear import Problem
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .adapter import item, route_scene, xyz


class OriginTrace:
    """
    Translate live construction hooks into frozen geometry with explicit decision ancestry.

    Original arithmetic and acceptance remain outside this adapter. Observer
    exceptions propagate, preserving the journal prefix instead of hiding gaps.
    """

    def __init__(self, journal: Journal, boundary: Boundary) -> None:
        """
        Bind fixed inputs and a fresh journal without restoring or inventing a route.
        """
        self.journal, self.boundary = journal, boundary
        self.context: list[dict[str, Any]] = []
        self.references: list[dict[str, Any]] = []
        self.models: list[Model] = []
        self.wall_seconds = self.cpu_seconds = 0.0

    def __call__(self, event: dict[str, Any]) -> None:
        """
        Freeze one executed derivation/LP event and account for capture overhead separately.
        """
        wall, cpu = perf_counter(), process_time()
        try:
            self._record(event)
        finally:
            self.wall_seconds += perf_counter() - wall
            self.cpu_seconds += process_time() - cpu

    def _record(self, event: dict[str, Any]) -> None:
        """
        Dispatch trusted internal hooks; refuse unknown stages rather than losing their history.
        """
        stage = event["stage"]
        log, target = self.journal, self.boundary.targets
        if stage == "targets":
            for identifier, origin, tangent, width in (
                ("End A", target.start, target.start_tangent, target.start_width),
                ("End B", target.end, target.end_tangent, target.end_width),
            ):
                log.define(identifier, identifier, "target", (), "endpoint-only input")
                self.context.append(
                    item(
                        identifier,
                        [
                            [
                                xyz(origin.translated(width, -self.boundary.half_width_mm)),
                                xyz(origin.translated(width, self.boundary.half_width_mm)),
                            ]
                        ],
                        frame={
                            "origin": xyz(origin),
                            "forward": xyz(tangent),
                            "across": xyz(width),
                        },
                        details={"fixed": True, "half_width_mm": self.boundary.half_width_mm},
                    )
                )
            log.emit(
                "input",
                "Start from fixed connector poses; no route loaded",
                "reference",
                "observed",
                self.context,
                event,
            )
        elif stage == "handles":
            log.define(
                "handles",
                "Chord/3 approach handles",
                "guide",
                ("End A", "End B"),
                "devtools/ribbon_analysis/prepath.py:controls",
            )
            a, b = Vector3(**event["departure"]), Vector3(**event["arrival"])
            self.references = [
                item(
                    "handles",
                    [[xyz(target.start), xyz(a)], [xyz(a), xyz(b)], [xyz(b), xyz(target.end)]],
                    details={"physical_route": False},
                )
            ]
            log.emit(
                "preplot",
                "Derive approach handles from endpoint distance and tangents",
                "reference",
                "observed",
                self.context + self.references,
                event,
            )
        elif stage == "bridge":
            log.define(
                "bridge",
                "Derived common bridge frame",
                "guide",
                ("handles",),
                "terminal_approaches.py:bridge",
            )
            pose = event["pose"]
            origin, width = Vector3(**pose["origin"]), Vector3(**pose["width"])
            self.references.append(
                item(
                    "bridge",
                    [[xyz(origin), xyz(origin.translated(width, self.boundary.half_width_mm))]],
                    frame={
                        "origin": xyz(origin),
                        "forward": xyz(Vector3(**pose["tangent"])),
                        "across": xyz(width),
                    },
                    details=event,
                )
            )
            log.emit(
                "preplot",
                "Choose bridge heading and transported-width bisector",
                "reference",
                "observed",
                self.context + self.references,
                event,
            )
        elif stage == "rotation_factors":
            for root, group in enumerate(event["choices"]):
                for index, raw in enumerate(group):
                    fold = CylindricalFold(**raw)
                    identifier = f"rotation-{event['terminal']}-{root}-F{index + 1}"
                    log.define(
                        identifier,
                        identifier,
                        "fold",
                        ("bridge", "End " + event["terminal"]),
                        "orientation.py:orient via frames.py:rotation_choices",
                    )
                    local = item(
                        identifier,
                        [
                            [xyz(fold.surface(i / 32, q)[0]) for i in range(33)]
                            for q in (-fold.width_mm / 2, 0.0, fold.width_mm / 2)
                        ],
                        space="local",
                        details={"geometry": raw, "world_placement_not_chosen": True},
                    )
                    log.emit(
                        "bend",
                        f"Derive {identifier}: exact rotation factor; placement unset",
                        "reference",
                        "observed",
                        [local],
                        {**event, "focus": identifier},
                    )
        elif stage == "chain":
            chain = event["chain"]
            identifier = chain["topology"]["identifier"]
            parents = tuple(
                f"rotation-{terminal}-{root}-F{i + 1}"
                for terminal, root, count in (
                    ("A", chain["roots"][0], chain["group_ends"][0]),
                    (
                        "B",
                        chain["roots"][1],
                        len(chain["topology"]["folds"]) - chain["group_ends"][0],
                    ),
                )
                for i in range(count)
            )
            log.define(identifier, identifier, "chain", parents, "terminal_approaches.py:chains")
            log.emit(
                "primitive",
                f"Declare {identifier}: bend order fixed, straight lengths unknown",
                "reference",
                "observed",
                self.context + self.references,
                event,
            )
        elif stage == "allocation":
            root = event["root"]
            scene = self.context
            if event["values"] is not None:
                scene = scene + self.scene(root, event["values"])
            status = (
                "unresolved"
                if event["status"] == "work_limit"
                else (
                    "rejected"
                    if event["values"] is None or event["unsatisfied_exclusions"]
                    else "attempted"
                )
            )
            log.emit(
                "placement",
                f"LP node {event['node']}, root {root}: solve straight lengths",
                status,
                "observed",
                scene,
                {
                    **event,
                    "physical_audit": "not performed",
                    "geometry_available": event["values"] is not None,
                },
            )
        elif stage == "separation_branch":
            log.emit(
                "proposal",
                f"Root {event['root']}: branch on {event['exclusion']['name']}",
                "attempted",
                "observed",
                self.context,
                {
                    **event,
                    "geometry_available": False,
                    "note": "Declared alternative inequalities, not newly executed geometry or angle changes.",
                },
            )
        else:
            raise ValueError("Unknown origin construction stage: " + str(stage))

    def prepared(self, model: Model, problem: Problem, exclusions: tuple[Exclusion, ...]) -> None:
        """
        Retain actual affine equations and an explicitly unclosed zero-travel model template.
        """
        root = len(self.models)
        self.models.append(model)
        self.journal.emit(
            "primitive",
            f"Root {root}: build length equations and whole-material separation rows",
            "reference",
            "observed",
            self.context + self.scene(root, (0.0,) * len(problem.cost)),
            {
                "root": root,
                "problem": asdict(problem),
                "exclusions": [asdict(x) for x in exclusions],
                "warning": "Zero-travel equation template, not a complete or accepted route.",
                "angles_fixed_during_length_allocation": True,
            },
        )

    def scene(self, root: int, values: tuple[float, ...]) -> list[dict[str, Any]]:
        """
        Sample actual nonnegative LP coordinates through the unchanged material placement model.
        """
        model = self.models[root]
        coordinates = tuple(values[i // 2] if i % 2 == 0 else 0.0 for i in range(model.size))
        route = FoldRoute(model.source.targets, model.pieces(coordinates), model.source.radius_mm)
        return route_scene(
            self.journal, route, model.topology.identifier, origin=model.topology.identifier
        )
