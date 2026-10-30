"""
Declare real procedure settings and validate bounded, opt-in run selections.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from devtools.ribbon_analysis.inspection.values import finite_number, integer_value, json_object

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Setting:
    """
    Describe one implemented numeric or enumerated procedure parameter.
    """

    key: str
    label: str
    default: float | int | str
    minimum: float = 0
    maximum: float = 0
    choices: tuple[str, ...] = ()
    integer: bool = False

    def validate(self, value: Any) -> float | int | str:
        """
        Reject unknown choices, booleans, nonfinite values and out-of-budget inputs.
        """
        if self.choices:
            if not isinstance(value, str) or value not in self.choices:
                raise ValueError(f"Choose a registered value for {self.label}.")
            return value
        number = integer_value(value) if self.integer else finite_number(value)
        if not self.minimum <= number <= self.maximum:
            raise ValueError(f"{self.label} must be within {self.minimum:g}..{self.maximum:g}.")
        return number


@dataclass(frozen=True)
class Procedure:
    """
    Describe a callable procedure or an explicit unmet fixture requirement.
    """

    identifier: str
    label: str
    detail: str
    settings: tuple[Setting, ...] = ()
    unavailable: str = ""


LIMITS = (
    Setting("seconds", "Time limit (seconds)", 8.0, 0.1, 30),
    Setting("paths", "Maximum recorded paths", 512, 16, 4096, integer=True),
    Setting("excerpt", "Search excerpt paths (0 = complete procedure)", 0, 0, 128, integer=True),
)
FIT = (
    Setting("coarse", "Coarse fitting rounds", 10, 0, 36, integer=True),
    Setting("fine", "Fine fitting rounds", 3, 0, 6, integer=True),
    Setting("transports", "Fit transport limit", 158, 2, 512, integer=True),
)
WINDOWS = (
    Setting(
        "start_window",
        "Start tightening window",
        "0.25",
        choices=("0", "0.0625", "0.125", "0.1875", "0.25"),
    ),
    Setting(
        "end_window",
        "End tightening window",
        "0.25",
        choices=("0", "0.0625", "0.125", "0.1875", "0.25"),
    ),
)
TIGHT_FIT = (Setting("coarse", "Coarse fitting rounds", 8, 0, 36, integer=True),) + FIT[1:]
BENDING = (
    Setting("bend_model", "Bend rule", "pinch percent", choices=("pinch percent", "legacy")),
    Setting("pinch_percent", "Maximum pinch utilization (%)", 99.6, 1, 99.99),
)
CATALOG = (
    Procedure(
        "generalized",
        "Generalized cold search",
        "Fixed 110-seed broad policy, up to 16 short / 4 deep families and queued width repair; exact neutral dispatch retained.",
        LIMITS + BENDING,
    ),
    Procedure(
        "ordinary",
        "Ordinary refinement",
        "Bounded endpoint fitting from a deterministic endpoint-derived seed. No previous fitted result is assumed.",
        LIMITS + BENDING + FIT,
    ),
    Procedure(
        "redistribution",
        "Bend redistribution",
        "One existing signed-turn allocation proposal followed by bounded fitting. Allocation thresholds remain fixed.",
        LIMITS + BENDING + FIT,
    ),
    Procedure(
        "tightening",
        "Terminal tangent tightening",
        "Independent optional start/end bending windows followed by bounded fitting.",
        LIMITS + BENDING + TIGHT_FIT + WINDOWS,
    ),
    Procedure(
        "combined",
        "Redistribution + terminal tightening",
        "One allocation proposal and terminal windows share the selected fitting budget.",
        LIMITS + BENDING + TIGHT_FIT + WINDOWS,
    ),
    Procedure(
        "compatible",
        "Compatible shooting",
        "Fixed 46-seed / 18 coarse / 3 fine policy. Select its actual objective and bend mapping; inherited physics remains under investigation.",
        LIMITS
        + BENDING
        + (
            Setting(
                "objective", "Objective", "routing", choices=("routing", "legacy sphere feedback")
            ),
            Setting(
                "mapping", "Bend mapping", "near limit", choices=("near limit", "global softening")
            ),
        ),
    ),
    Procedure(
        "director",
        "Director shooting",
        "Registered historical policies retain their fixed iteration counts and legacy objectives; these are diagnostic comparisons.",
        LIMITS
        + (
            Setting(
                "policy",
                "Registered shooting policy",
                "BANK_WIDTH",
                choices=(
                    "BASELINE",
                    "ROTATION",
                    "REGULAR",
                    "CORKSCREW",
                    "FREE",
                    "BANK",
                    "BANK_PERSISTENT",
                    "BANK_WIDTH",
                ),
            ),
        ),
    ),
    Procedure(
        "discovery",
        "Family/contact-guided search",
        "Screen the existing seed bank and fit the selected number of distinct families. Contact guidance is sampled, not a clearance certificate.",
        LIMITS
        + BENDING
        + (
            Setting(
                "variant",
                "Family refinement",
                "short",
                choices=("short", "full", "plane guided", "distance guided"),
            ),
            Setting("families", "Maximum families", 3, 1, 3, integer=True),
        ),
    ),
    Procedure(
        "broad",
        "Broad cold search",
        "Run the generalized solver's broad delegate directly with its unchanged fixed policy.",
        LIMITS + BENDING,
    ),
    Procedure(
        "quintic",
        "Archived cap-transition solver",
        "The archived inventory entry points to the cap-transition constructor.",
        unavailable="Requires a prescribed master route and explicit start/end cap fits; this fixture contains endpoint poses only.",
    ),
    Procedure(
        "target-shooting",
        "Archived joint target shooting",
        "Piecewise material-span solver.",
        unavailable="Its material-span plan has no registered lossless replay/capture adapter yet. It remains available in source, rather than being represented by invented director fields.",
    ),
    Procedure(
        "tube",
        "Prescribed-twist tube",
        "Master-tube and cap construction procedure.",
        unavailable="Requires a prescribed master route, cap fits and twist specification; those inputs are absent from this endpoint-only fixture.",
    ),
)


def catalog() -> list[dict[str, Any]]:
    """
    Return a JSON-ready control specification without importing any numerical solver.
    """
    return [asdict(procedure) for procedure in CATALOG]


def selections(value: Any) -> list[dict[str, Any]]:
    """
    Normalize selected procedures and enforce a 120-second aggregate scheduling cap.
    """
    if not isinstance(value, list) or not 1 <= len(value) <= 9:
        raise ValueError("Select one to nine supported procedures.")
    known = {procedure.identifier: procedure for procedure in CATALOG}
    chosen: list[dict[str, Any]] = []
    for item in value:
        source = json_object(item)
        if set(source) != {"id", "settings"}:
            raise ValueError("Procedure selections require id and settings only.")
        identifier = source["id"]
        if not isinstance(identifier, str) or identifier not in known:
            raise ValueError("Unknown solver procedure.")
        procedure = known[identifier]
        if procedure.unavailable:
            raise ValueError(procedure.unavailable)
        if identifier in {entry["id"] for entry in chosen}:
            raise ValueError("Do not schedule the same procedure twice in one run.")
        settings = json_object(source["settings"])
        if set(settings) - {setting.key for setting in procedure.settings}:
            raise ValueError("Unknown procedure setting.")
        normalized = {
            setting.key: setting.validate(settings.get(setting.key, setting.default))
            for setting in procedure.settings
        }
        if integer_value(normalized["excerpt"]) >= integer_value(normalized["paths"]):
            raise ValueError("An excerpt must finish before the hard recording cap.")
        chosen.append({"id": identifier, "settings": normalized})
    if sum(entry["settings"]["seconds"] for entry in chosen) > 120:
        raise ValueError("Selected time limits exceed the 120-second run budget.")
    return chosen


def demonstration() -> list[dict[str, Any]]:
    """
    Register nine finite search excerpts without changing any physical constraint.

    Heavy cold searches retain their first128transports, including fitting after
    seed screening. Local strategies use one coarse fitting round and no fine
    iterations; their final512-grid evaluation remains. Resource errors still
    stop the batch. Excerpt completion is planned incomplete evidence, not a fit.
    """
    requests = []
    for procedure in CATALOG:
        if procedure.unavailable:
            continue
        settings: dict[str, Any] = {"excerpt": 128}
        if procedure.identifier in ("ordinary", "redistribution", "tightening", "combined"):
            settings.update(coarse=1, fine=0, transports=16, excerpt=32)
        requests.append({"id": procedure.identifier, "settings": settings})
    return selections(requests)


def source_pins() -> dict[str, str]:
    """
    Freeze executable routing, worker, viewer and safeguard sources for a fresh job.
    """
    files = {ROOT / "cable_bundler/routing/geometry.py"}
    for package in (
        "devtools/ribbon_analysis",
        "experiments/experiment_ribbon_diagnostic_viewer",
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
