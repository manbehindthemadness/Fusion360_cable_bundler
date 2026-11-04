"""
Carry frozen case inputs inside original PNG exports without changing pixel data.
"""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path
from typing import Any, Iterator

KEY: bytes = b"RibbonGymReplay"
SCHEMA = "ribbon-gym-image-replay-v1"
SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAXIMUM_BYTES = 64 * 1024 * 1024


def _chunks(data: bytes) -> Iterator[tuple[int, int, bytes, bytes]]:
    """
    Walk bounded PNG chunks, rejecting truncation or a missing final IEND.
    """
    if data[:8] != SIGNATURE or data[12:16] != b"IHDR":
        raise ValueError("Replay metadata requires a PNG image")
    offset = 8
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        end = offset + size + 12
        if end > len(data):
            raise ValueError("Truncated PNG chunk")
        kind, content = data[offset + 4 : offset + 8], data[offset + 8 : end - 4]
        yield offset, end, kind, content
        if kind == b"IEND":
            if size or end != len(data):
                raise ValueError("Malformed PNG ending")
            return
        offset = end
    raise ValueError("PNG has no complete IEND")


def _bytes(path: Path) -> bytes:
    """
    Bound local image reads before decoding replay records.
    """
    if path.stat().st_size > MAXIMUM_BYTES:
        raise ValueError("Replay PNG exceeds 64 MiB")
    return path.read_bytes()


def embed(path: Path, record: dict[str, Any]) -> None:
    """
    Add one ASCII JSON tEXt chunk, preserving every original PNG chunk byte-for-byte.

    Only newly captured images are supplied by the exporter. Reject an existing
    replay key rather than overwrite history; verify exact read-back before success.
    A failed write remains a screenshot failure and stops the tester.
    """
    data = _bytes(path)
    chunks = list(_chunks(data))
    if any(kind == b"tEXt" and content.split(b"\0", 1)[0] == KEY for _, _, kind, content in chunks):
        raise ValueError("PNG already contains a replay record")
    content = (
        KEY + b"\0" + json.dumps(record, allow_nan=False, separators=(",", ":")).encode("ascii")
    )
    chunk = b"tEXt" + content
    encoded = struct.pack(">I", len(content)) + chunk + struct.pack(">I", zlib.crc32(chunk))
    if len(data) + len(encoded) > MAXIMUM_BYTES:
        raise ValueError("Replay PNG exceeds 64 MiB")
    split = chunks[0][1]
    path.write_bytes(data[:split] + encoded + data[split:])
    if read(path) != record:
        raise RuntimeError("PNG replay metadata read-back mismatch")


def read(path: Path) -> dict[str, Any]:
    """
    Extract one versioned record from an original PNG; never evaluate embedded code.

    Validate the metadata CRC, reject duplicates and report absent/stripped metadata
    explicitly. The source fingerprints identify historical code, not bundled code.
    """
    data = _bytes(path)
    records = []
    for start, end, kind, content in _chunks(data):
        if kind != b"tEXt" or content.split(b"\0", 1)[0] != KEY:
            continue
        expected = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(data[start + 4 : end - 4]) != expected:
            raise ValueError("PNG replay metadata checksum failed")
        records.append(json.loads(content[len(KEY) + 1 :].decode("ascii")))
    if len(records) != 1 or not isinstance(records[0], dict):
        raise ValueError("PNG needs exactly one RibbonGymReplay record; metadata may be stripped")
    record = records[0]
    if record.get("schema") != SCHEMA:
        raise ValueError("Unsupported PNG replay schema")
    return record


def capture_record(input_path: Path, plan_path: Path, job: str | None) -> dict[str, Any]:
    """
    Copy immutable case/test plans and available execution policy into a portable record.

    Include exact frozen target poses, source hashes, solver settings and the range
    specification. Local log paths are convenience links, never required for extraction.
    A prepared case without a launched job explicitly has no execution policy.
    """
    execution = None
    if job is not None and (Path(job) / "plan.json").exists():
        execution = json.loads((Path(job) / "plan.json").read_text(encoding="utf-8"))
    return {
        "schema": SCHEMA,
        "input": json.loads(input_path.read_text(encoding="utf-8")),
        "test_plan": json.loads(plan_path.read_text(encoding="utf-8")),
        "job_plan": execution,
        "locations": {"input": str(input_path), "test_plan": str(plan_path), "job": job},
    }


def main() -> None:
    """
    Print a PNG's replay record as JSON without starting Fusion or a solver.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    print(json.dumps(read(args.image), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
