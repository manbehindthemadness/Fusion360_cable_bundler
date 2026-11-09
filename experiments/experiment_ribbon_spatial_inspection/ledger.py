"""
Persist an immutable baseline and prediction before consuming the single diagnostic probe allowance.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from time import monotonic, process_time
from typing import Any


def canonical(value: Any) -> str:
    """
    Serialize finite JSON without alternate coordinate encodings.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    """
    Fingerprint the exact shared packet used for both rendering and prediction.
    """
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def create(path: Path, payload: dict[str, Any]) -> None:
    """
    Flush one new evidence record; an existing or incomplete record cannot be overwritten.
    """
    encoded = canonical(payload)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


class Ledger:
    """
    Own one baseline, one precommitted prediction and at most one probe execution.
    """

    def __init__(self, directory: Path) -> None:
        """
        Open only an existing bounded baseline packet, without executing geometry.
        """
        self.directory = directory
        path = directory / "baseline.json"
        if path.stat().st_size > 24 * 1024 * 1024:
            raise ValueError("Inspection packet exceeds24MiB")
        self.baseline = json.loads(path.read_text())
        if (
            not isinstance(self.baseline, dict)
            or self.baseline.get("schema") != "ribbon-spatial-inspection-v1"
        ):
            raise ValueError("Choose a spatial inspection baseline")
        self.fingerprint = digest(self.baseline)
        manifest = json.loads((directory / "inspection-plan.json").read_text())
        if manifest.get("baseline_fingerprint") != self.fingerprint:
            raise ValueError("Baseline differs from the frozen inspection plan")

    def commit(self, prediction: dict[str, Any]) -> dict[str, Any]:
        """
        Validate explicit world displacement and explanation before durably locking the only prediction.
        """
        required = {
            "coordinate",
            "delta",
            "section",
            "expected_displacement_mm",
            "tolerance_mm",
            "explanation",
        }
        if not isinstance(prediction, dict) or set(prediction) != required:
            raise ValueError(
                "Supply coordinate, delta, section, expected XYZ displacement, tolerance and explanation"
            )
        measurements = self.baseline["measurements"]
        if (
            max(measurements["cap_position_error_mm"], measurements["cap_frame_vector_error"])
            >= 1e-10
        ):
            raise ValueError("A spatial probe requires an already closed ordered-cap baseline")
        for key, limit in (
            ("coordinate", len(self.baseline["coordinates"])),
            ("section", len(self.baseline["sections"])),
        ):
            if type(prediction[key]) is not int or not 0 <= prediction[key] < limit:
                raise ValueError("Prediction index is outside the frozen packet")
        vector = prediction["expected_displacement_mm"]
        if not isinstance(vector, list) or len(vector) != 3:
            raise ValueError("Predict exactly three world-coordinate displacements")
        numbers = [prediction["delta"], prediction["tolerance_mm"], *vector]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in numbers):
            raise ValueError("Prediction measurements must be finite numbers")
        coordinate = self.baseline["coordinates"][prediction["coordinate"]]
        if (
            not 0 < abs(prediction["delta"]) <= coordinate["maximum_delta"]
            or not 0 < prediction["tolerance_mm"] <= self.baseline["route"]["case"]["diameter_mm"]
        ):
            raise ValueError(
                "Use a nonzero bounded probe and a positive tolerance no larger than thickness"
            )
        explanation = prediction["explanation"]
        if not isinstance(explanation, str) or not 20 <= len(explanation.strip()) <= 4000:
            raise ValueError("Explain the spatial motion, cap compensation and what could worsen")
        record = {
            "baseline_fingerprint": self.fingerprint,
            "prediction": prediction,
            "scope": "Prediction only; no probe has run and no geometric acceptance is implied",
        }
        create(self.directory / "prediction.json", record)
        create(self.directory / "prediction-seal.json", {"fingerprint": digest(record)})
        return record

    def run_probe(self) -> dict[str, Any]:
        """
        Consume the only allowance before computation; preserve failures without allowing retries.

        A failed or interrupted probe_started record still consumes the allowance.
        The caller cannot edit/re-predict after observing the result. Each action
        rechecks the baseline bytes and its precommitted source fingerprints.
        """
        from .probe import execute

        baseline = json.loads((self.directory / "baseline.json").read_text())
        if digest(baseline) != self.fingerprint:
            raise ValueError("Inspection baseline changed")
        plan = json.loads((self.directory / "inspection-plan.json").read_text())
        root = Path(__file__).resolve().parents[2]
        for name, expected in plan["sources"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError("Frozen source drift: " + name)
        record = json.loads((self.directory / "prediction.json").read_text())
        seal = json.loads((self.directory / "prediction-seal.json").read_text())
        if digest(record) != seal.get("fingerprint"):
            raise ValueError("The committed prediction was modified")
        if record.get("baseline_fingerprint") != self.fingerprint:
            raise ValueError("Prediction belongs to another baseline")
        create(
            self.directory / "probe-started.json",
            {"prediction_fingerprint": digest(record), "baseline_fingerprint": self.fingerprint},
        )
        cpu, wall = process_time(), monotonic()
        analysis_started: float | None = None
        geometry_cpu: float | None = None

        def record_proposal(proposal: dict[str, Any]) -> None:
            """
            Retain the closed proposal and end geometry timing before separately bounded inspection.
            """
            nonlocal analysis_started, geometry_cpu
            geometry_cpu = process_time() - cpu
            create(self.directory / "probe-proposal.json", proposal)
            analysis_started = monotonic()

        def analysis_checkpoint() -> None:
            """
            Bound post-probe display/contact measurements separately to ten seconds.
            """
            if analysis_started is None or monotonic() - analysis_started > 10:
                raise TimeoutError("Post-probe inspection exceeded10seconds")
            import resource
            import sys

            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if (rss if sys.platform == "darwin" else rss * 1024) >= 4294967296:
                raise TimeoutError("Post-probe inspection reached4GiB RSS")

        def checkpoint() -> None:
            """
            Keep the diagnostic within.35CPU/2wall seconds and4GiB sampled RSS.
            """
            import resource
            import sys

            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss_bytes = rss if sys.platform == "darwin" else rss * 1024
            if process_time() - cpu > 0.35 or monotonic() - wall > 2 or rss_bytes >= 4294967296:
                raise TimeoutError("Diagnostic probe resource bound reached")

        try:
            result = execute(
                baseline,
                record["prediction"],
                checkpoint,
                record_proposal,
                analysis_checkpoint,
            )
        except (ArithmeticError, RuntimeError, ValueError, TimeoutError) as error:
            result = {"status": "stopped", "error": f"{type(error).__name__}: {error}"}
        result.update(
            cpu_seconds=process_time() - cpu,
            wall_seconds=monotonic() - wall,
            prediction_fingerprint=digest(record),
            baseline_fingerprint=self.fingerprint,
            geometry_cpu_seconds=geometry_cpu,
            analysis_wall_seconds=monotonic() - analysis_started
            if analysis_started is not None
            else None,
        )
        create(self.directory / "probe-result.json", result)
        return result

    def state(self) -> dict[str, Any]:
        """
        Return the same frozen geometry and persisted ledger state to both viewers.
        """
        result: dict[str, Any] = {"baseline": self.baseline, "fingerprint": self.fingerprint}
        for name in ("prediction", "probe-started", "probe-result"):
            path = self.directory / (name + ".json")
            result[name.replace("-", "_")] = json.loads(path.read_text()) if path.exists() else None
        return result
