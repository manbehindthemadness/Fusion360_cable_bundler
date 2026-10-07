"""
Recover all six original certificate-packed fixtures without a new scale search.
"""

import json
from dataclasses import asdict, replace
from pathlib import Path

from .array_limits import scaled_case
from .faith_fixtures import FaithFixture, faith_fixtures
from .planning import ShortConnectionFixture, freeze_targets
from .screen import _fits


def frozen_sweep_fixtures(parent: Path) -> tuple[FaithFixture, ...]:
    """
    Verify original fixtures, selected curves, caps and targets against provenance.

    Restore requested winding, including -360, without changing any geometry.
    Reject incomplete or drifted plans before any Fusion document is created.
    """
    plan = json.loads(parent.read_text(encoding="utf-8"))
    originals = faith_fixtures()
    encoded = json.loads(json.dumps([asdict(item) for item in originals], default=str))
    if encoded != plan["parents"] or len(plan["selections"]) != 6 or len(plan["inputs"]) != 6:
        raise ValueError("Original sweep replay inputs are incomplete or have drifted.")
    selected = []
    for item, selection, frozen in zip(originals, plan["selections"], plan["inputs"]):
        case = scaled_case(item.case, selection["scale"])
        fixture = replace(item, case=case)
        fits = _fits(case)
        targets = freeze_targets(case, *fits, fixture=ShortConnectionFixture(case, turn_degrees=15))
        replay = {
            "fixture": asdict(fixture),
            "caps": [asdict(f) for f in fits],
            "targets": asdict(targets),
        }
        if json.loads(json.dumps(replay, default=str)) != frozen:
            raise ValueError("Packed sweep curve/cap/target provenance changed.")
        selected.append(fixture)
    return tuple(selected)
