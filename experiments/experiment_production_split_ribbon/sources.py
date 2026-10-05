"""
Validate and load unedited production copies without replacing production modules.

Source files retain their original bytes and relative imports. Private module
names preserve the original package context; copied ribbon dependencies are
wired only inside those private modules. Stable geometry/Fusion helpers remain
shared. A changed source or production file prevents the comparison from running.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REVISION = "09d9e60"


@dataclass(frozen=True)
class SourceCopy:
    """
    Identify a pinned production source and its private executable copy.
    """

    name: str
    original: str
    package: str
    sha256: str


SOURCES = (
    SourceCopy(
        "frames",
        "routing/ribbon.py",
        "cable_bundler.routing",
        "33135930a99ed0e2e8552418db851c61a4b752cacb0d48a4927d8ad4d1e9910a",
    ),
    SourceCopy(
        "bank",
        "routing/ribbon_bank.py",
        "cable_bundler.routing",
        "3aec42126af61b00b3a88204348b8a92949691838e4346b88de669cdb57e6986",
    ),
    SourceCopy(
        "shape",
        "routing/ribbon_shape.py",
        "cable_bundler.routing",
        "661cc2c4848e860b809f429295d9ae917f6041049535e1e3dba869238c31bf05",
    ),
    SourceCopy(
        "guides",
        "fusion/ribbon_geometry.py",
        "cable_bundler.fusion",
        "0d507d5d5dfd46b01f671753a94604b09c821055a3edc82a3a2784717589cbc7",
    ),
    SourceCopy(
        "builder",
        "fusion/cable_solid_parts/ribbon_builder.py",
        "cable_bundler.fusion.cable_solid_parts",
        "21b412cdc226649696555d0faec60a981eff0b0c65a92c1a0575b04c7c41a673",
    ),
    SourceCopy(
        "exits",
        "fusion/cable_solid_parts/ribbon_exit_loft.py",
        "cable_bundler.fusion.cable_solid_parts",
        "d43ce7011ef6ef0c5b438dd53b3875a4b1444a7adc3fad636ee489ce328c777b",
    ),
)


def verify_sources(project_root: Path = PROJECT_ROOT) -> dict[str, str]:
    """
    Reject drift in either source copies or the production dependency baseline.
    """
    hashes: dict[str, str] = {}
    for source in SOURCES:
        copy = Path(__file__).parent / "snapshot" / f"{source.name}.py.source"
        original = project_root / "cable_bundler" / source.original
        for path in (copy, original):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != source.sha256:
                raise RuntimeError(f"Production comparison source drift: {path}")
        hashes[source.name] = source.sha256
    return hashes


def _load_copy(source: SourceCopy) -> ModuleType:
    """
    Execute one validated copy under a new name in its original package context.
    """
    name = source.package + ".__experiment_split_" + source.name
    path = Path(__file__).parent / "snapshot" / f"{source.name}.py.source"
    loader = SourceFileLoader(name, str(path))
    specification = importlib.util.spec_from_file_location(name, path, loader=loader)
    if specification is None:
        raise RuntimeError(f"Could not load production copy: {source.name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def load_sources() -> dict[str, ModuleType]:
    """
    Wire the copied algorithms together without changing a production binding.
    """
    verify_sources()
    modules = {source.name: _load_copy(source) for source in SOURCES}
    bindings = {
        "bank": {"RibbonFrame": ("frames", "RibbonFrame")},
        "shape": {
            "RibbonFrame": ("frames", "RibbonFrame"),
            "ribbon_lane_points": ("frames", "ribbon_lane_points"),
        },
        "guides": {
            "RibbonFrame": ("frames", "RibbonFrame"),
            "ribbon_frames": ("frames", "ribbon_frames"),
            "ribbon_has_hard_axis_bend": ("frames", "ribbon_has_hard_axis_bend"),
            "RibbonBankGate": ("bank", "RibbonBankGate"),
            "bank_ribbon_frames": ("bank", "bank_ribbon_frames"),
            "RibbonEndFit": ("shape", "RibbonEndFit"),
            "RibbonShape": ("shape", "RibbonShape"),
            "solve_ribbon_shape": ("shape", "solve_ribbon_shape"),
        },
        "builder": {
            "RibbonFrame": ("frames", "RibbonFrame"),
            "ribbon_lane_points": ("frames", "ribbon_lane_points"),
            "RibbonEndFit": ("shape", "RibbonEndFit"),
            "RibbonShape": ("shape", "RibbonShape"),
            "ribbon_line_lengths": ("shape", "ribbon_line_lengths"),
            "RibbonGuidePlane": ("guides", "RibbonGuidePlane"),
        },
        "exits": {
            "RibbonFrame": ("frames", "RibbonFrame"),
            "RibbonEndFit": ("shape", "RibbonEndFit"),
            "RibbonGuidePlane": ("guides", "RibbonGuidePlane"),
            "_lane_section_point": ("builder", "_lane_section_point"),
        },
    }
    for target, attributes in bindings.items():
        for attribute, (origin, symbol) in attributes.items():
            setattr(modules[target], attribute, getattr(modules[origin], symbol))
    return modules
