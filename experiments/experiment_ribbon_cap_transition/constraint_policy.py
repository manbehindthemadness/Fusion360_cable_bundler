"""
Scope explicit diagnostic ablations while preserving the default routing policy.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator

from devtools.ribbon_analysis.pathing import PathRules
from devtools.ribbon_analysis.pinch import BendModel, PinchLimit


class Rule(Enum):
    """
    Identify implemented constraints independently of their display captions.
    """

    END_POSITION = "end_position"
    END_TANGENT = "end_tangent"
    END_WIDTH = "end_width"
    CENTRE_BEND = "centre_bend"
    LANE_BEND = "lane_bend"


@dataclass(frozen=True)
class ConstraintPolicy:
    """
    Retain the versioned pathing scope and disabled rules on each field permanently.

    Inputs, start pose, identities and independent measurements remain intact.
    The two-rule scope excludes auxiliary objectives and contact gates; positive
    material progress remains intrinsic to its local macaroni construction.
    An ablated route can fail physical checks and is never certified.
    """

    disabled: frozenset[Rule] = frozenset()
    bend_model: BendModel = BendModel.LEGACY
    pinch_percent: float = 99.6
    path_rules: PathRules = PathRules.HISTORICAL

    def __post_init__(self) -> None:
        """
        Refuse mutable or unknown rule collections before numerical execution.
        """
        if not isinstance(self.disabled, frozenset) or any(
            not isinstance(rule, Rule) for rule in self.disabled
        ):
            raise ValueError("Use an immutable set of registered constraint rules.")
        if not isinstance(self.bend_model, BendModel):
            raise ValueError("Choose a versioned bend model.")
        if not isinstance(self.path_rules, PathRules):
            raise ValueError("Choose a versioned pathing rule set.")
        if self.path_rules is PathRules.MACARONI and self.bend_model is not BendModel.PINCH:
            raise ValueError("Two-rule pathing requires the macaroni pinch-percent model.")
        PinchLimit(self.pinch_percent)

    def enabled(self, rule: Rule) -> bool:
        """
        Report the frozen search scope without changing measurement policy.
        """
        return rule not in self.disabled


FULL = ConstraintPolicy()
_active: ContextVar[ConstraintPolicy] = ContextVar("ribbon_constraint_policy", default=FULL)


def current() -> ConstraintPolicy:
    """
    Capture the explicit policy when constructing a field, defaulting to full rules.
    """
    return _active.get()


def for_field(field: object) -> ConstraintPolicy:
    """
    Read a frozen field policy or the complete legacy default, rejecting malformed data.
    """
    policy = getattr(field, "constraints", FULL)
    if not isinstance(policy, ConstraintPolicy):
        raise ValueError("A field's constraint policy is malformed.")
    return policy


def parse(value: Any) -> ConstraintPolicy:
    """
    Validate finite explicit rule identities; unknown and duplicate controls reject.
    """
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("Disabled constraints require a list of rule identifiers.")
    if len(value) != len(set(value)):
        raise ValueError("Disabled constraint identifiers must be unique.")
    try:
        return ConstraintPolicy(frozenset(Rule(item) for item in value))
    except ValueError as error:
        raise ValueError("Unknown or unimplemented constraint toggle.") from error


def configured(disabled: Any, settings: dict[str, Any]) -> ConstraintPolicy:
    """
    Freeze an explicit worker policy; absent version metadata remains historical.
    """
    policy = parse(disabled)
    model = BendModel(settings.get("bend_model", BendModel.LEGACY.value))
    if model is BendModel.PINCH and Rule.CENTRE_BEND in policy.disabled:
        raise ValueError(
            "The pinch model has one coupled material-guide limit, not a separate centre cap."
        )
    return ConstraintPolicy(
        policy.disabled,
        model,
        settings.get("pinch_percent", 99.6),
        PathRules(settings.get("path_rules", PathRules.HISTORICAL.value)),
    )


@contextmanager
def scope(policy: ConstraintPolicy) -> Iterator[None]:
    """
    Isolate one numerical run; constructed immutable fields retain their own policy.
    """
    if not isinstance(policy, ConstraintPolicy):
        raise ValueError("Choose a registered constraint policy.")
    token = _active.set(policy)
    try:
        yield
    finally:
        _active.reset(token)
