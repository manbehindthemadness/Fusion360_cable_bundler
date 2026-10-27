"""
Create solver-independent25/25/50batches with fixed controls and free random poses.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import secrets
from dataclasses import replace
from pathlib import Path

from cable_bundler.routing.geometry import Vector3, cross

from ..contracts import Targets
from .codec import target_from_data
from .models import Case, Manifest, RandomBounds
from .recipes import BASICS, COMBINATIONS, compile_pose


def known_stress() -> tuple[Case, ...]:
    """
    Read portable exact historical inputs without accessing ignored reports at run time.
    """
    inventory = json.loads(Path(__file__).with_name("stress_inventory.json").read_text())
    if inventory["version"] != 1:
        raise ValueError("Unknown stress inventory version.")
    return tuple(
        Case(
            f"S{i:03}",
            "stress",
            target_from_data(item["targets"]),
            (),
            item["reference"],
            f"{item['note']} Source:{item['source']} sha256:{item['sha256']}",
        )
        for i, item in enumerate(inventory["cases"], 1)
    )


def _frame(rng: random.Random) -> tuple[Vector3, Vector3]:
    """
    Sample a uniform rotation using a unit quaternion,avoiding Euler-angle bias.
    """
    u, v, w = rng.random(), rng.random(), rng.random()
    q = Vector3(
        math.sqrt(1 - u) * math.sin(2 * math.pi * v),
        math.sqrt(1 - u) * math.cos(2 * math.pi * v),
        math.sqrt(u) * math.sin(2 * math.pi * w),
    )
    scalar = math.sqrt(u) * math.cos(2 * math.pi * w)

    def apply(vector: Vector3) -> Vector3:
        """
        Apply the sampled unit quaternion to a canonical frame axis.
        """
        a = cross(q, vector)
        b = cross(q, a)
        return Vector3(
            vector.x + 2 * (scalar * a.x + b.x),
            vector.y + 2 * (scalar * a.y + b.y),
            vector.z + 2 * (scalar * a.z + b.z),
        )

    return apply(Vector3(1, 0, 0)), apply(Vector3(0, 1, 0))


def _random_case(seed: int, index: int, bounds: RandomBounds) -> Case:
    """
    Sample independent full3Dend frames,positions and dimensions without solve filtering.
    """
    digest = hashlib.sha256(f"ribbon-cases-v1:{seed}:random:{index}".encode()).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    lines = rng.randint(bounds.minimum_lines, bounds.maximum_lines)
    diameter = math.exp(
        rng.uniform(math.log(bounds.minimum_diameter_mm), math.log(bounds.maximum_diameter_mm))
    )
    width = lines * diameter
    start = Vector3(*(rng.uniform(-3, 3) * width for _ in range(3)))
    z, phi = rng.uniform(-1, 1), rng.uniform(0, 2 * math.pi)
    radial = math.sqrt(1 - z * z)
    direction = Vector3(radial * math.cos(phi), radial * math.sin(phi), z)
    chord = width * math.exp(
        rng.uniform(math.log(bounds.minimum_chord_widths), math.log(bounds.maximum_chord_widths))
    )
    tangent, lateral = _frame(rng)
    end_tangent, end_width = _frame(rng)
    identifier = f"R{index:03}"
    targets = Targets.capture(
        Targets(
            identifier + " random boundary",
            start,
            start.translated(direction, chord),
            tangent,
            end_tangent,
            lateral,
            end_width,
            lines,
            diameter,
        )
    )
    return Case(
        identifier,
        "random",
        targets,
        (),
        "independent-uniform-frames",
        "Unknown feasibility;uniformSO(3)frames/spherical direction;log-uniform diameter/chord;no solver-conditioned rejection.",
    )


def generate(
    *, size: int = 64, seed: int | None = None, bounds: RandomBounds | None = None
) -> Manifest:
    """
    Freeze normal quarter,stress quarter and independent random half before solving.

    First12normal cases always contain eight solos and four compounds;first eight
    stress cases retain exact known inputs. Larger quarters extend these without
    replacing them. Baselines and stress inputs are seed-independent. A missing
    seed obtains64bits of system entropy,which the manifest saves for replay.
    """
    if isinstance(size, bool) or not isinstance(size, int) or not 48 <= size <= 4096 or size % 4:
        raise ValueError("Choose48..4096cases in multiples of4.")
    seed = secrets.randbits(64) if seed is None else seed
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError("Seed must be an unsigned64-bit integer.")
    bounds = RandomBounds() if bounds is None else bounds
    quarter = size // 4
    cases: list[Case] = []
    for index in range(quarter):
        if index < len(BASICS):
            events = (BASICS[index],)
        elif index < 12:
            events = COMBINATIONS[index - 8]
        else:
            events = tuple(reversed(COMBINATIONS[(index - 12) % len(COMBINATIONS)]))
        identifier = f"N{index + 1:03}"
        targets = compile_pose(
            identifier + " " + " + ".join(f"{e.kind}{e.degrees:g}" for e in events),
            events,
            lines=13 if index < 12 else 5 + index % 60,
            radius_widths=2.5 if index < 12 else 2.5 + index / 100,
        )
        cases.append(
            Case(
                identifier,
                "normal",
                targets,
                events,
                "common-solo" if len(events) == 1 else "common-combination",
                "Normal regression expectation;events are endpoint-pose intent,not interior constraints or physical certification.",
            )
        )
    inventory = known_stress()
    if len(inventory) > quarter:
        raise ValueError("Increase batch size to retain every known stress case in its quarter.")
    cases.extend(inventory)
    for index in range(len(inventory), quarter):
        parent = inventory[(index - len(inventory)) % len(inventory)]
        factor = 0.55 + 0.003 * ((index - len(inventory)) // len(inventory))
        t = parent.targets
        end = Vector3(
            t.start.x + factor * (t.end.x - t.start.x),
            t.start.y + factor * (t.end.y - t.start.y),
            t.start.z + factor * (t.end.z - t.start.z),
        )
        identifier = f"S{index + 1:03}"
        targets = replace(t, name=identifier + " compact " + parent.reference, end=end)
        cases.append(
            Case(
                identifier,
                "stress",
                targets,
                (),
                parent.reference + f"/chord-scale-{factor:g}",
                "Generated compact stress variation;unknown feasibility. Parent:" + parent.note,
            )
        )
    cases.extend(_random_case(seed, index, bounds) for index in range(1, 2 * quarter + 1))
    directory = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted((*directory.glob("*.py"), directory / "stress_inventory.json")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return Manifest(1, seed, bounds, tuple(cases), digest.hexdigest())
