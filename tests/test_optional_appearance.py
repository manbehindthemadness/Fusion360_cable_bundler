"""
Verify the supported deferred-color contract without a Fusion runtime.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_optional_appearance.bake import source_map
from experiments.experiment_optional_appearance.bitmap import Bitmap, ColorMap, read_png
from experiments.experiment_optional_appearance.boundary import crease_coordinates
from experiments.experiment_optional_appearance.files import restore_offline_directory
from experiments.experiment_optional_appearance.material import material_coordinates
from experiments.experiment_optional_appearance.raster import SIZE, png, raster, sample
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose
from experiments.experiment_ribbon_fold_route.material_profile import material_profile


def descriptor(path: Path) -> dict[str, Any]:
    """
    Define the supported image-map state emitted by the native source reader.
    """
    return {
        "type": 1,
        "path": str(path),
        "alternate_image": str(path),
        "properties": {
            "texture_RealWorldScaleX": 1.2,
            "texture_RealWorldScaleY": 0.3,
            "texture_RealWorldOffsetX": 0.0,
            "texture_RealWorldOffsetY": 0.0,
            "texture_WAngle": 0.0,
            "texture_URepeat": True,
            "texture_VRepeat": True,
        },
    }


def write_pixel(path: Path, color: tuple[int, int, int]) -> None:
    """
    Store an opaque image with known bytes and no external imaging dependency.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png(bytes(color), 1))


def test_source_can_be_selected_later_and_replaced(tmp_path: Path) -> None:
    """
    Resolve a later source, preserve physical scale and detect changed source bytes.
    """
    path = tmp_path / "color.png"
    with pytest.raises(FileNotFoundError):
        source_map(descriptor(path), False)
    write_pixel(path, (70, 90, 110))
    first, resolved = source_map(descriptor(path), False)
    assert first.scale_mm == (12.0, 3.0)
    assert resolved == path
    assert first.sample(3, -2) == (70, 90, 110)
    write_pixel(path, (150, 30, 20))
    second, _ = source_map(descriptor(path), False)
    assert second.sample(3, -2) == (150, 30, 20)
    assert first.bitmap != second.bitmap


def test_library_relative_source_requires_explicit_root(tmp_path: Path) -> None:
    """
    Resolve library-relative asset paths without guessing an unrelated local file.
    """
    path = tmp_path / "1/Mats/color.png"
    write_pixel(path, (1, 2, 3))
    row = descriptor(Path("1/Mats/color.png"))
    with pytest.raises(ValueError, match="explicit asset root"):
        source_map(row, False)
    mapped, resolved = source_map(row, False, tmp_path)
    assert resolved == path
    assert mapped.sample(0, 0) == (1, 2, 3)
    row["path"] = "../outside.png"
    with pytest.raises(ValueError):
        source_map(row, False, tmp_path)


@pytest.mark.parametrize("texture_type", [0, 2, 3, 4, 5, 6, 7, 8, 9])
def test_procedural_or_unknown_source_is_rejected(texture_type: int) -> None:
    """
    Reject unsupported native generators before producing misleading substitute pixels.
    """
    row = descriptor(Path("unread.png"))
    row["type"] = texture_type
    with pytest.raises(ValueError, match="procedural/unknown"):
        source_map(row, False)


@pytest.mark.parametrize(
    "property_name,value",
    [
        ("texture_RealWorldOffsetX", 0.1),
        ("texture_RealWorldOffsetY", -0.1),
        ("texture_WAngle", 0.2),
        ("texture_URepeat", False),
        ("texture_VRepeat", False),
    ],
)
def test_unsupported_source_transform_is_rejected(property_name: str, value: float | bool) -> None:
    """
    Avoid silently interpreting source placement modes outside the live trial.
    """
    row = descriptor(Path("unread.png"))
    row["properties"][property_name] = value
    with pytest.raises(ValueError):
        source_map(row, False)


@pytest.mark.parametrize("scale", [(0.0, 1.0), (1.0, -1.0), (math.nan, 1.0), (1.0, math.inf)])
def test_invalid_texture_dimensions_are_rejected(scale: tuple[float, float]) -> None:
    """
    Reject singular/nonfinite repeated color maps.
    """
    with pytest.raises(ValueError):
        ColorMap(Bitmap(1, 1, b"\x00\x00\x00"), scale)


def test_png_roundtrip_and_corrupt_asset(tmp_path: Path) -> None:
    """
    Preserve actual RGB pixels while rejecting a damaged asset checksum.
    """
    path = tmp_path / "test.png"
    raw = bytes((10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120))
    path.write_bytes(png(raw, 2))
    image = read_png(path)
    assert image == Bitmap(2, 2, raw)
    assert image.sample(0.25, 0.75) == (10, 20, 30)
    assert image.sample(1.25, -0.25) == (10, 20, 30)
    damaged = bytearray(path.read_bytes())
    damaged[20] ^= 1
    path.write_bytes(damaged)
    with pytest.raises(ValueError, match="checksum"):
        read_png(path)


def test_translucent_source_requires_separate_support(tmp_path: Path) -> None:
    """
    Reject nonopaque alpha instead of silently discarding transparency.
    """

    def chunk(kind: bytes, payload: bytes) -> bytes:
        """
        Frame a minimal valid PNG chunk for an unsupported input fixture.
        """
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\x01\x02\x03\x80"))
        + chunk(b"IEND", b"")
    )
    path = tmp_path / "alpha.png"
    path.write_bytes(data)
    with pytest.raises(ValueError, match="Translucent"):
        read_png(path)


def test_face_images_retain_continuous_source_coordinates() -> None:
    """
    Map two unrelated native UV domains to the same material image coordinates.
    """

    def color(s: float, q: float) -> tuple[int, int, int]:
        """
        Encode independently known affine material values for interpolation checks.
        """
        return round(50 + 80 * s), round(50 + 80 * q), 130

    points = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    face = {"uv": points, "triangles": [0, 1, 2, 0, 2, 3]}
    shifted = {
        "uv": [(10 + 3 * x, -7 + 0.3 * y) for x, y in points],
        "triangles": face["triangles"],
    }
    first, first_bounds, coverage = raster(face, points, color)
    second, second_bounds, _ = raster(shifted, points, color)
    assert len(first) == SIZE * SIZE * 3 and coverage > 0
    for u, v in ((0.1, 0.2), (0.5, 0.5), (0.8, 0.6)):
        a = sample(first, first_bounds, [u, v])
        b = sample(second, second_bounds, [10 + 3 * u, -7 + 0.3 * v])
        assert max(abs(x - y) for x, y in zip(a, b)) < 1e-10
        assert max(abs(x - y) for x, y in zip(a, color(u, v))) <= 1


@pytest.mark.parametrize("bank,angle", [(0.6, 1.7), (-0.5, -2.4), (0.0, -math.pi)])
def test_material_inverse_preserves_both_fold_senses(bank: float, angle: float) -> None:
    """
    Recover chosen material positions and thickness offsets through oblique folds.
    """
    fold = CylindricalFold(2, angle, bank, 4, 2, 2)
    piece = PlacedPiece(
        Pose(Vector3(3, -2, 1), Vector3(1, 0, 0), Vector3(0, 1, 0)), fold, "synthetic"
    )
    for q in (-1.7, 0.0, 1.6):
        low, high = fold.bend_interval(q)
        for fraction in (0.1, 0.4, 0.9):
            u = low + fraction * (high - low)
            point, velocity, across, _ = piece.surface(u, q)
            point = point.translated(unit(cross(velocity, across)), 0.3)
            s, actual_q, height = material_coordinates(piece, "bend", point)
            assert abs(s - u * fold.material_length_mm) < 1e-12
            assert abs(actual_q - q) < 1e-12
            assert abs(height - 0.3) < 1e-12


def test_display_roundoff_near_crease_keeps_the_entry_branch() -> None:
    """
    Keep a slightly negative entry phase at entry rather than the opposite endpoint.
    """
    fold = CylindricalFold(
        0.3765060244728916, math.pi, 0.5684854844628979, 0.9, 0.2874752469842925, 0.2874752469842925
    )
    piece = PlacedPiece(Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), fold, "crease")
    q = 0.45
    low, _ = fold.bend_interval(q)
    point, velocity, across, _ = piece.surface(low, q)
    point = point.translated(unit(cross(velocity, across)), 0.375)
    point = point.translated(
        Vector3(math.cos(fold.bank_radians), math.sin(fold.bank_radians), 0), -1e-7
    )
    s, actual_q, height = material_coordinates(piece, "bend", point)
    assert abs(actual_q - q) < 1e-12
    assert abs(s - low * fold.material_length_mm) < 1e-12
    assert abs(height - 0.375) < 1e-10


@pytest.mark.parametrize("angle", [math.pi, -math.pi])
def test_known_crease_recovers_float_boundary_phase(angle: float) -> None:
    """
    Use the authored crease/profile to recover phase near a highly pinched skin.
    """
    fold = CylindricalFold(0.7530120489457832, angle, 0.7, 4.8, 2.1, 2.1)
    piece = PlacedPiece(
        Pose(Vector3(60, -35, 20), Vector3(1, 0, 0), Vector3(0, 1, 0)), fold, "pinched"
    )
    arcs = material_profile(3, 1.5)
    arc = arcs[0] if angle > 0 else next(a for a in arcs if a.label == "bottom-0")
    q, height = arc.point(0.5)
    low, high = fold.bend_interval(q)
    for u in (low, high):
        point, velocity, across, _ = piece.surface(u, q)
        point = point.translated(unit(cross(velocity, across)), height)
        floats = [
            struct.unpack("f", struct.pack("f", v / 10))[0] for v in (point.x, point.y, point.z)
        ]
        recovered = crease_coordinates(piece, arc, floats)
        assert recovered is not None
        s, actual_q, actual_height = recovered
        assert abs(s - u * fold.material_length_mm) < 1e-5
        assert abs(actual_q - q) < 1e-5
        assert abs(actual_height - height) < 1e-5
    point, velocity, across, _ = piece.surface((low + high) / 2, q)
    point = point.translated(unit(cross(velocity, across)), height)
    assert crease_coordinates(piece, arc, [point.x / 10, point.y / 10, point.z / 10]) is None


def test_offline_source_restoration(tmp_path: Path) -> None:
    """
    Restore the exact original source bytes after a completed or failed import.
    """
    folder, offline = tmp_path / "images", tmp_path / "images-offline"
    offline.mkdir()
    (offline / "source.png").write_bytes(b"original")
    restore_offline_directory(folder, offline)
    assert (folder / "source.png").read_bytes() == b"original"
    assert not offline.exists()


@pytest.mark.parametrize("existing_recovery", [False, True])
def test_restoration_preserves_import_created_files(
    tmp_path: Path, existing_recovery: bool
) -> None:
    """
    Preserve importer-created files and prior recovery folders while restoring sources.
    """
    folder, offline = tmp_path / "images", tmp_path / "images-offline"
    folder.mkdir()
    offline.mkdir()
    (offline / "source.png").write_bytes(b"original")
    (folder / "extracted.png").write_bytes(b"imported")
    if existing_recovery:
        old = tmp_path / "images-import-created-0"
        old.mkdir()
        (old / "retained.png").write_bytes(b"older")
    restore_offline_directory(folder, offline)
    assert (folder / "source.png").read_bytes() == b"original"
    recovery = tmp_path / (
        "images-import-created-1" if existing_recovery else "images-import-created-0"
    )
    assert (recovery / "extracted.png").read_bytes() == b"imported"
    if existing_recovery:
        assert (tmp_path / "images-import-created-0/retained.png").read_bytes() == b"older"


def test_missing_retained_sources_do_not_move_current_files(tmp_path: Path) -> None:
    """
    Fail safely if the expected original source directory is unavailable.
    """
    folder = tmp_path / "images"
    folder.mkdir()
    (folder / "imported.png").write_bytes(b"kept")
    with pytest.raises(RuntimeError, match="missing"):
        restore_offline_directory(folder, tmp_path / "missing")
    assert (folder / "imported.png").read_bytes() == b"kept"
