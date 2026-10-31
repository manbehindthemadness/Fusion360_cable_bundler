"""
Retain the historical procedure inventory without offering seed-based discovery.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from devtools.ribbon_analysis.inspection.values import json_object

ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_REMOVED = (
    "Path search and seed-based discovery have been removed. "
    "Recorded results remain viewable; a replacement endpoint solver is not implemented."
)


@dataclass(frozen=True)
class Procedure:
    """
    Identify historical methods without retaining executable search settings.
    """

    identifier: str
    label: str
    detail: str
    unavailable: str
    settings: tuple[dict[str, Any], ...] = ()


CATALOG = tuple(
    Procedure(identifier, label, detail, DISCOVERY_REMOVED)
    for identifier, label, detail in (
        ("generalized", "Generalized cold search", "Retired broad seed-bank discovery."),
        ("ordinary", "Ordinary refinement", "Retired endpoint-seed fitting."),
        ("redistribution", "Bend redistribution", "Retired seeded allocation and fitting."),
        ("tightening", "Terminal tangent tightening", "Retired seeded window fitting."),
        ("combined", "Redistribution + terminal tightening", "Retired seeded combined fitting."),
        ("compatible", "Compatible shooting", "Retired 46-seed shooting search."),
        ("director", "Director shooting", "Retired seeded director-policy search."),
        ("discovery", "Family/contact-guided search", "Retired seed-family discovery."),
        ("broad", "Broad cold search", "Retired 110-seed broad search."),
    )
) + (
    Procedure(
        "quintic",
        "Archived cap-transition solver",
        "Prescribed-route constructor.",
        "Requires a prescribed master route and explicit start/end cap fits; this fixture contains endpoint poses only.",
    ),
    Procedure(
        "target-shooting",
        "Archived joint target shooting",
        "Historical material-span solver.",
        "No registered replay/capture adapter; unavailable for endpoint discovery.",
    ),
    Procedure(
        "tube",
        "Prescribed-twist tube",
        "Prescribed-route construction procedure.",
        "Requires a prescribed master route, cap fits and twist specification; those inputs are absent from this endpoint-only fixture.",
    ),
)


def catalog() -> list[dict[str, Any]]:
    """
    Describe archived methods without importing numerical search implementations.
    """
    return [asdict(procedure) for procedure in CATALOG]


def selections(value: Any) -> list[dict[str, Any]]:
    """
    Reject new discovery requests, including requests saved by an older palette.
    """
    if not isinstance(value, list) or not value:
        raise ValueError(DISCOVERY_REMOVED)
    known = {procedure.identifier: procedure for procedure in CATALOG}
    source = json_object(value[0])
    if set(source) != {"id", "settings"}:
        raise ValueError("Procedure selections require id and settings only.")
    identifier = source["id"]
    if not isinstance(identifier, str) or identifier not in known:
        raise ValueError("Unknown solver procedure.")
    raise ValueError(known[identifier].unavailable)


def demonstration() -> list[dict[str, Any]]:
    """
    Return no executable selections for clients retaining the old demonstration API.
    """
    return []


def source_pins() -> dict[str, str]:
    """
    Freeze diagnostic, historical solver and safeguard sources for authored references.
    """
    files = {
        ROOT / "cable_bundler/routing/geometry.py",
        ROOT / "cable_bundler/fusion/cable_solid_parts/ribbon_builder.py",
    }
    for package in (
        "devtools/ribbon_analysis",
        "experiments/experiment_ribbon_diagnostic_viewer",
        "experiments/experiment_ribbon_edge_pair",
        "experiments/experiment_ribbon_profile_basics",
        "experiments/experiment_ribbon_normal_route",
        "experiments/experiment_ribbon_fold_route",
        "experiments/experiment_ribbon_test_gym",
        "experiments/experiment_ribbon_cap_transition",
        "experiments/experiment_ribbon_route_discovery",
        "experiments/experiment_ribbon_bend_redistribution",
        "experiments/experiment_ribbon_tangent_tightening",
    ):
        files.update((ROOT / package).rglob("*.py"))
    files.update(
        ROOT / name
        for name in (
            "devtools/ribbon_analysis/inspection/viewer.html",
            "devtools/ribbon_analysis/gym/viewer.html",
            "experiment_testing_rules.txt",
            "rollback_end_loft_notes.txt",
        )
    )
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(files)
    }
