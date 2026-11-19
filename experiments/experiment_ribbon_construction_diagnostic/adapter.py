"""
Record material primitives, explicit placement ancestry and existing solver journal events.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.construction.journal import Journal
from devtools.ribbon_analysis.prepath import drawing
from experiments.experiment_ribbon_contraction.runner import restore
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight


def xyz(vector: Vector3) -> list[float]:
    """
    Convert a millimeter position or direction without rounding or changing its frame.
    """
    return [vector.x, vector.y, vector.z]


def item(
    identifier: str,
    paths: list[list[list[float]]],
    *,
    space: str = "world",
    frame: dict[str, Any] | None = None,
    material: tuple[float, float] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Describe one frozen display object using the shared solver-independent contract.
    """
    return {
        "feature": identifier,
        "space": space,
        "paths": paths,
        "frame": frame,
        "material_mm": material,
        "details": details or {},
    }


def inputs(journal: Journal, route: FoldRoute) -> list[dict[str, Any]]:
    """
    Retain fixed cap frames and an explicitly reconstructed unconstrained endpoint pre-plot.
    """
    target = route.targets
    context = []
    for identifier, origin, tangent, width in (
        ("End A", target.start, target.start_tangent, target.start_width),
        ("End B", target.end, target.end_tangent, target.end_width),
    ):
        journal.define(identifier, identifier, "target", (), "frozen input: ordered target pose")
        context.append(
            item(
                identifier,
                [
                    [
                        xyz(origin.translated(width, -route.half_width_mm)),
                        xyz(origin.translated(width, route.half_width_mm)),
                    ]
                ],
                frame={"origin": xyz(origin), "forward": xyz(tangent), "across": xyz(width)},
                details={"fixed": True, "lines": target.lines, "diameter_mm": target.diameter_mm},
            )
        )
    journal.emit(
        "input",
        "Fixed ordered connector targets A / B",
        "reference",
        "observed",
        context,
        {"source": "frozen input, not a new solve"},
    )
    journal.define(
        "preplot",
        "Endpoint tangent pre-plot",
        "guide",
        ("End A", "End B"),
        "devtools/ribbon_analysis/prepath.py:controls",
    )
    guide = drawing(target)
    preplot = item(
        "preplot",
        [[[p[axis] for axis in ("x", "y", "z")] for p in guide["points"]]],
        details={"controls": guide["controls"], "physical_route": False},
    )
    journal.emit(
        "preplot",
        "Endpoint pre-plot reference; original execution not recorded",
        "reference",
        "reconstructed",
        context + [preplot],
        {
            "warning": "Derived from frozen targets using the shared chord/3 convention. Not proof the original run used this guide."
        },
    )
    return context


def route_scene(journal: Journal, route: FoldRoute, chain_id: str) -> list[dict[str, Any]]:
    """
    Sample unchanged material pieces with ordered-fold/straight-slot identity and rigid entry frames.

    The caller must provide a new chain_id when topology/feature provenance changes.
    Ordinal identity is valid only within an explicitly unchanged ordered chain.
    These sampled sheets are not solid, contact or material-coordinate audits.
    """
    if len(route.pieces) > 32:
        raise ValueError("Construction display supports at most32material pieces per snapshot")
    result = []
    fold_index = 0
    previous = "End A"
    placement_predecessor = "End A"
    for ordinal, piece in enumerate(route.pieces):
        straight = isinstance(piece.geometry, Straight)
        if not straight:
            fold_index += 1
        identifier = f"{chain_id}/S{fold_index}" if straight else f"{chain_id}/F{fold_index}"
        kind = "straight" if straight else "fold"
        journal.define(
            identifier,
            f"{chain_id} · {'S' if straight else 'F'}{fold_index}",
            kind,
            (previous,),
            "experiments/experiment_ribbon_fold_route/geometry.py:PlacedPiece; isometric_fold.py:CylindricalFold"
            if not straight
            else "experiments/experiment_ribbon_fold_route/geometry.py:Straight",
        )
        paths = [
            [xyz(piece.surface(u / 32, q)[0]) for u in range(33)]
            for q in (-route.half_width_mm, 0.0, route.half_width_mm)
        ]
        start = route.starts_mm[ordinal]
        result.append(
            item(
                identifier,
                paths,
                frame={
                    "origin": xyz(piece.pose.origin),
                    "forward": xyz(piece.pose.tangent),
                    "across": xyz(piece.pose.width),
                },
                material=(start, start + piece.geometry.material_length_mm),
                details={
                    "geometry": asdict(piece.geometry),
                    "piece_label": piece.label,
                    "ordered_piece": ordinal,
                    "half_width_mm": route.half_width_mm,
                    "thickness_mm": route.targets.diameter_mm,
                    "entry_frame": asdict(piece.pose),
                    "exit_frame": asdict(piece.end_pose()),
                    "placement_predecessor": placement_predecessor,
                    "correspondence": "ordered fold/straight slot within caller-declared unchanged chain",
                },
            )
        )
        if not straight:
            previous = identifier
        placement_predecessor = identifier
    return result


def assembly(
    journal: Journal, route: FoldRoute, chain_id: str, context: list[dict[str, Any]]
) -> None:
    """
    Replay exact local primitive and placement data as reconstructed assembly, never solver chronology.
    """
    scene = route_scene(journal, route, chain_id)
    prefix = []
    for piece, placed in zip(route.pieces, scene):
        identity = placed["feature"]
        length = piece.geometry.material_length_mm
        local_frame = {"origin": [0, 0, 0], "forward": [1, 0, 0], "across": [0, 1, 0]}
        blank = item(
            identity,
            [[[0, q, 0], [length, q, 0]] for q in (-route.half_width_mm, 0.0, route.half_width_mm)],
            space="local",
            frame=local_frame,
            material=placed["material_mm"],
            details={
                "role": "unrolled reference blank, not an executed solver operation",
                "geometry": placed["details"]["geometry"],
            },
        )
        journal.emit(
            "primitive",
            f"{identity}: flat material reference blank",
            "reference",
            "reconstructed",
            [blank],
            {"focus": identity, "partial_construction": True},
        )
        if not isinstance(piece.geometry, Straight):
            local = item(
                identity,
                [
                    [xyz(piece.geometry.surface(u / 32, q)[0]) for u in range(33)]
                    for q in (-route.half_width_mm, 0.0, route.half_width_mm)
                ],
                space="local",
                frame=local_frame,
                material=placed["material_mm"],
                details=placed["details"],
            )
            journal.emit(
                "bend",
                f"{identity}: local finite-radius bend primitive",
                "reference",
                "reconstructed",
                [local],
                {"focus": identity, "partial_construction": True},
            )
        prefix.append(placed)
        journal.emit(
            "placement",
            f"{identity}: entry frame places primitive in world route",
            "reference",
            "reconstructed",
            context + list(prefix),
            {
                "focus": identity,
                "partial_construction": True,
                "note": "Assembly from saved poses, not original solve timing; prefix is not a complete ribbon output.",
            },
        )
    journal.emit(
        "output",
        "Complete retained material snapshot; qualification unchanged",
        "unresolved",
        "observed",
        context + scene,
        {
            "length_mm": route.material_length_mm,
            "native": "not captured",
            "physical_checks": "not run by viewer",
            "geometry_source": "frozen retained route",
        },
    )


class EventBridge:
    """
    Tee existing selected-solver or experiment callbacks into bounded visual history.

    No route is synthesized for a status-only event. Unrecorded geometry stays
    absent. Navigation never re-executes the callback or invokes a solver.
    Use stable_chain only when the caller guarantees unchanged feature topology;
    otherwise each snapshot receives independent identities, with no guessed match.
    """

    def __init__(
        self,
        journal: Journal,
        context: list[dict[str, Any]],
        *,
        downstream: Callable[[dict[str, Any]], None] | None = None,
        stable_chain: str | None = None,
    ) -> None:
        """
        Bind an explicit output journal and optional original callback without patching solver globals.
        """
        self.journal, self.context = journal, context
        self.downstream, self.stable_chain = downstream, stable_chain
        self.ordinal = 0
        self.scene: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        """
        Preserve the original event first, then capture its available geometry and equation details.
        """
        if self.downstream is not None:
            self.downstream(event)
        self.ordinal += 1
        raw = event.get("route")
        details = {key: value for key, value in event.items() if key != "route"}
        status_text = event.get("status") or event.get("stage") or "event"
        if not isinstance(status_text, str):
            raise ValueError("A solver event status/stage must be text")
        phase = (
            "correction"
            if "correction" in status_text or "restoration" in status_text
            else "proposal"
        )
        if event.get("stage") in ("contact", "hardware"):
            phase = "audit"
        if isinstance(raw, dict):
            route = restore(raw)
            key = self.stable_chain or f"snapshot-{self.ordinal}"
            self.scene = route_scene(self.journal, route, key)
            details["geometry_available"] = True
        else:
            details["geometry_available"] = False
            details["geometry_notice"] = (
                "No geometry in this event; previous snapshot shown only as context."
            )
        status = (
            "accepted"
            if status_text == "accepted"
            else "rejected"
            if any(word in status_text for word in ("failed", "rejected", "declined"))
            else "attempted"
        )
        self.journal.emit(
            phase,
            f"Event {self.ordinal}: {status_text}",
            status,
            "observed",
            self.context + self.scene,
            details,
        )
