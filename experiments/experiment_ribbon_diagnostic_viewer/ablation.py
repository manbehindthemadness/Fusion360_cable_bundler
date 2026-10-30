"""
Declare truthful per-procedure constraint controls and matched comparison workloads.
"""

from __future__ import annotations

from typing import Any

from experiments.experiment_ribbon_cap_transition.constraint_policy import (
    ConstraintPolicy,
    Rule,
    parse,
)

CAPTIONS = {
    Rule.END_POSITION: "Fixed endpoint position",
    Rule.END_TANGENT: "Fixed endpoint tangent",
    Rule.END_WIDTH: "Terminal width frame",
    Rule.CENTRE_BEND: "Legacy centre reach cap",
    Rule.LANE_BEND: "Material-guide bend cap",
}
_CHART = {"ordinary", "tightening", "compatible", "discovery"}
_POSE = _CHART | {"redistribution", "combined"}


def supported(procedure: str) -> frozenset[Rule]:
    """
    Expose only constraints fully wired through a procedure's chart and objective.
    """
    if procedure in _CHART:
        return frozenset(Rule)
    if procedure in _POSE:
        return frozenset((Rule.END_POSITION, Rule.END_TANGENT, Rule.END_WIDTH))
    return frozenset()


def controls(procedure: str) -> list[dict[str, Any]]:
    """
    Explain unsupported ablations rather than supplying ineffective checkboxes.
    """
    available = supported(procedure)
    return [
        {
            "id": rule.value,
            "name": caption,
            "supported": rule in available,
            "reason": "Omit the end fitting objective; the start remains structurally anchored."
            if rule in available and rule in (Rule.END_POSITION, Rule.END_TANGENT, Rule.END_WIDTH)
            else "Remove this limit from both the compatible chart and its fitting penalty."
            if rule in available
            else "This procedure's structural/search gates have no complete ablation adapter for this rule.",
        }
        for rule, caption in CAPTIONS.items()
    ]


def validate(procedure: str, disabled: Any) -> ConstraintPolicy:
    """
    Reject unknown, unsupported or empty comparisons before archiving or launching.
    """
    policy = parse(disabled)
    if not policy.disabled or not policy.disabled <= supported(procedure):
        raise ValueError(
            "Choose implemented constraint toggles supported by the selected procedure."
        )
    return policy


def workloads(
    selections: list[dict[str, Any]], comparison: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Pair fresh baseline and ablation with identical settings, inputs and initialization.
    """
    if comparison is None:
        return [dict(item, role="normal", disabled_rules=[]) for item in selections]
    if len(selections) != 1 or set(comparison) != {"origin", "disabled_rules"}:
        raise ValueError("A comparison requires one selected procedure and explicit origin/rules.")
    origin = comparison["origin"]
    if not isinstance(origin, str) or not origin.strip() or len(origin) > 256:
        raise ValueError("Comparison origin must identify the selected recorded method.")
    item = selections[0]
    policy = validate(item["id"], comparison["disabled_rules"])
    if (
        item["settings"].get("bend_model") == "pinch percent"
        and Rule.CENTRE_BEND in policy.disabled
    ):
        raise ValueError("Pinch bending has one coupled material-guide constraint.")
    disabled = sorted(rule.value for rule in policy.disabled)
    return [
        dict(item, role="baseline", disabled_rules=[]),
        dict(item, role="ablation", disabled_rules=disabled),
    ]
