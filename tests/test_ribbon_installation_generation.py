"""
Verify selectable assembly fixtures,replay and connector semantics without routing.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from devtools.ribbon_analysis.case_generation import (
    FAMILIES,
    GenerationMode,
    RandomBounds,
    fingerprint,
    generate,
    read,
    write,
)
from devtools.ribbon_analysis.case_generation.__main__ import main


def test_modes_share_controls_but_keep_distinct_dynamic_inputs() -> None:
    """
    Retain the old default and all controls while allocating a separate family matrix.
    """
    original = generate(seed=42)
    explicit = generate(seed=42, mode="random")
    installations = generate(seed=42, mode="installation")
    assert original == explicit
    assert installations.version == 2 and installations.mode == "installation"
    assert installations.cases[:32] == original.cases[:32]
    dynamic = installations.cases[32:]
    assert len(dynamic) == 32 and all(case.stratum == "random" for case in dynamic)
    assert [case.identifier for case in dynamic] == [f"I{i:03}" for i in range(1, 33)]
    counts = Counter(case.installation.family for case in dynamic if case.installation)
    assert set(counts) == set(FAMILIES)
    assert max(counts.values()) - min(counts.values()) == 1
    assert all(case.installation is None for case in original.cases)
    external_options = json.loads('{"mode": "unrecognized"}')
    with pytest.raises(ValueError, match="mode"):
        generate(**external_options)


def test_installation_prefix_and_seed_independence_of_controls() -> None:
    """
    Enlarging a batch preserves each dynamic input;changing seed affects only that half.
    """
    small = generate(size=48, seed=9, mode="installation")
    large = generate(size=80, seed=9, mode="installation")
    other = generate(size=48, seed=10, mode="installation")
    assert small.cases[24:] == large.cases[40:64]
    assert small.cases[:24] == other.cases[:24]
    assert small.cases[24:] != other.cases[24:]
    assert small == generate(size=48, seed=9, mode="installation")


def test_installation_geometry_couples_departures_to_mounts_and_preserves_pin_order() -> None:
    """
    Freeze mounting relationships and ordered frames with the correct arrival sign.
    """
    manifest = generate(size=256, seed=77, mode="installation")
    different_mating = 0
    for case in manifest.cases[128:]:
        context = case.installation
        assert context is not None
        t = case.targets
        width = t.lines * t.diameter_mm
        assert 2 - 1e-12 <= magnitude(difference(t.end, t.start)) / width <= 12 + 1e-12
        assert context.feasibility == "unknown"
        assert t.start == context.start.exit_point and t.end == context.end.exit_point
        assert t.start_tangent == context.start.exit_direction
        assert t.end_tangent == Vector3(
            -context.end.exit_direction.x,
            -context.end.exit_direction.y,
            -context.end.exit_direction.z,
        )
        for connector, ordered_width in (
            (context.start, t.start_width),
            (context.end, t.end_width),
        ):
            assert ordered_width == connector.width_direction
            assert magnitude(connector.exit_direction) == pytest.approx(1)
            assert dot(ordered_width, connector.exit_direction) == pytest.approx(0, abs=1e-12)
            assert (
                dot(difference(connector.exit_point, connector.mount_point), connector.mount_normal)
                > 0
            )
            different_mating += abs(dot(connector.exit_direction, connector.mating_direction)) < 0.5
        normal_dot = dot(context.start.mount_normal, context.end.mount_normal)
        if context.family in ("same-board", "reversed-connector"):
            assert normal_dot == pytest.approx(1)
            assert dot(
                difference(context.end.mount_point, context.start.mount_point),
                context.start.mount_normal,
            ) == pytest.approx(0, abs=1e-12)
        elif context.family == "parallel-boards":
            assert normal_dot == pytest.approx(-1)
        else:
            assert normal_dot == pytest.approx(0, abs=1e-12)
        assert context.end.mount_kind == (
            "panel" if context.family == "board-to-panel" else "board"
        )
        if context.family == "reversed-connector":
            assert dot(t.start_width, t.end_width) == pytest.approx(-1)
    assert different_mating > 0


def test_explicit_relative_bounds_override_installation_defaults() -> None:
    """
    Honor exact dimensional/chord bounds,including counts outside the preferred list.
    """
    bounds = RandomBounds(3, 3, 0.8, 0.8, 3, 3)
    manifest = generate(seed=17, bounds=bounds, mode="installation")
    for case in manifest.cases[32:]:
        t = case.targets
        assert t.lines == 3 and t.diameter_mm == pytest.approx(0.8)
        assert magnitude(difference(t.end, t.start)) == pytest.approx(3 * 3 * 0.8)


def test_installation_roundtrip_freezes_context_and_detects_edits(tmp_path: Path) -> None:
    """
    Replay all connector/context data exactly and fingerprint even contextual edits.
    """
    manifest = generate(seed=19, mode="installation")
    path = tmp_path / "installation.json"
    write(manifest, path)
    assert read(path) == manifest
    assert fingerprint(read(path)) == fingerprint(manifest)
    with pytest.raises(FileExistsError):
        write(manifest, path)
    data = json.loads(path.read_text())
    data["cases"][-1]["installation"]["room_max"]["x"] += 1
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="digest"):
        read(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("family", "known family"),
        ("context", "context disagrees"),
        ("vector", "finite numeric"),
        ("departure", "outside its mounting plane"),
        ("target", "disagree with frozen targets"),
        ("room", "positive extent"),
        ("feasibility", "unknown feasibility"),
        ("mode", "version disagrees"),
        ("extra", "Malformed connector"),
    ),
)
def test_inconsistent_installation_data_is_rejected(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    """
    Refuse missing,malformed or unsupported physical claims before solver handoff.
    """
    path = tmp_path / "bad.json"
    write(generate(seed=1, mode="installation"), path)
    data = json.loads(path.read_text())
    case = data["cases"][32]
    context = case["installation"]
    if mutation == "family":
        context["family"] = "unrecognized"
    elif mutation == "context":
        case["installation"] = None
    elif mutation == "vector":
        context["start"]["exit_point"]["x"] = True
    elif mutation == "departure":
        context["start"]["exit_direction"] = {"x": 0, "y": 0, "z": -1}
    elif mutation == "target":
        case["targets"]["end"]["x"] += 0.1
    elif mutation == "room":
        context["room_min"] = context["room_max"]
    elif mutation == "feasibility":
        context["feasibility"] = "known-feasible"
    elif mutation == "mode":
        data["mode"] = "random"
    else:
        context["start"]["unknown_field"] = 1
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message):
        read(path)


def test_context_cannot_be_detached_or_attached_to_legacy_manifest() -> None:
    """
    Prevent silent loss of fixture context through direct Python construction.
    """
    manifest = generate(seed=1, mode="installation")
    with pytest.raises(ValueError, match="context"):
        replace(
            manifest,
            cases=manifest.cases[:32]
            + (replace(manifest.cases[32], installation=None),)
            + manifest.cases[33:],
        )
    with pytest.raises(ValueError, match="context"):
        replace(manifest, version=1, mode="random")


@pytest.mark.parametrize("mode", ("random", "installation"))
def test_cli_selects_and_inspects_both_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: GenerationMode,
) -> None:
    """
    Expose an explicit mode choice and carry it through saved-manifest inspection.
    """
    path = tmp_path / (mode + ".json")
    monkeypatch.setattr(
        "sys.argv",
        ["case_generation", "generate", "--mode", mode, "--seed", "3", "--output", str(path)],
    )
    main()
    generated = json.loads(capsys.readouterr().out)
    monkeypatch.setattr("sys.argv", ["case_generation", "inspect", str(path)])
    main()
    inspected = json.loads(capsys.readouterr().out)
    assert inspected == generated
    assert inspected["mode"] == mode
    assert inspected["strata"] == {"normal": 16, "stress": 16, "random": 32}
    assert inspected["solver_calls"] == inspected["native_attempts"] == 0
    if mode == "installation":
        assert set(inspected["installation_families"]) == set(FAMILIES)
    else:
        assert inspected["installation_families"] == {}
