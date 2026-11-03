"""
Verify optional screenshots preserve per-case evidence without allowing another failed-case launch.
"""

from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_locked_solver.tester.screenshots import (
    Screenshots,
    ScreenshotSettings,
    frame,
)
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification
from tests.test_ribbon_range_sequence import specification
from tests.test_ribbon_range_tester import make_tester, start

PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0s8AAAAASUVORK5CYII="
)


def write_png(path: Path) -> None:
    """
    Stand in for a successful native viewport export using one complete PNG fixture.
    """
    path.write_bytes(PNG)


def test_capture_frame_includes_an_excursion_without_including_distant_host_layouts() -> None:
    """
    Frame from local case bounds and include an accepted excursion outside the nominal gym cube.
    """
    assert frame(40, ()) == (Vector3(0, 0, 0), 40)
    center, span = frame(40, (Vector3(80, 0, 0), Vector3(30, 10, 4)))
    assert center == Vector3(30, 0, 0) and span == 100


def test_screenshot_settings_remain_opt_in_and_do_not_change_input_sequence() -> None:
    """
    Preserve old plans and exact gym cases while expanding the chosen home-relative destination.
    """
    payload = specification()
    del payload["screenshots"]
    before = Specification.parse(payload)
    payload["screenshots"] = {"enabled": True, "directory": "~/Pictures/testxyz"}
    after = Specification.parse(payload)
    assert not before.screenshots.enabled
    assert after.screenshots.folder == Path.home() / "Pictures/testxyz"
    assert [before.scene(i) for i in range(5)] == [after.scene(i) for i in range(5)]


@pytest.mark.parametrize(
    "payload",
    (
        {"enabled": "yes", "directory": "/tmp/test"},
        {"enabled": True, "directory": "relative"},
        {"enabled": True, "directory": ""},
        {"enabled": True, "directory": "/tmp/bad\x00name"},
        {"enabled": True},
    ),
)
def test_invalid_screenshot_preferences_reject_before_launch(payload: Any) -> None:
    """
    Refuse malformed external paths or toggles instead of silently choosing another location.
    """
    with pytest.raises(ValueError):
        ScreenshotSettings.parse(payload)


def test_export_names_separate_runs_and_never_overwrite_existing_images(tmp_path: Path) -> None:
    """
    Keep an earlier image byte-for-byte intact when the same case is requested twice.
    """
    settings = ScreenshotSettings(True, str(tmp_path / "pictures"))
    capture = Mock(side_effect=write_png)
    first = Screenshots(settings, "run-a", capture)
    saved = first.save("case-000001")
    second = Screenshots(settings, "run-b", capture).save("case-000001")
    assert saved["path"] != second["path"] and saved["seconds"] >= 0
    assert Path(saved["path"]).read_bytes() == PNG
    with pytest.raises(FileExistsError):
        first.save("case-000001")
    assert capture.call_count == 2


def test_each_completed_case_is_captured_before_cleanup_and_problem_after_presentation(
    tmp_path: Path,
) -> None:
    """
    Retain two images for two iterations, including the stopped route, without repeating Inspect.
    """
    tester, runner, present = make_tester(tmp_path, ["completed", "unresolved", "completed"])
    events: list[str] = []
    tester.cleanup = lambda: events.append("clear")
    present.side_effect = lambda *_: events.append("present")

    def capture(path: Path) -> None:
        """
        Observe that a terminal outcome exists and retain a genuine image for that exact case.
        """
        assert runner.state()["status"] in ("completed", "unresolved")
        events.append("capture")
        write_png(path)

    tester.capture = capture
    start(tester, screenshots={"enabled": True, "directory": str(tmp_path / "pictures")})
    for _ in range(4):
        tester.poll()
    assert not tester.active and tester.phase == "problem" and len(runner.jobs) == 2
    assert events == ["clear", "capture", "clear", "present", "capture"]
    assert len(list((tmp_path / "pictures").glob("*.png"))) == 2
    assert tester.journal is not None
    assert (tester.journal.directory / "cases.jsonl").read_text().count('"screenshot_saved"') == 2
    tester.inspect()
    tester.poll()
    assert events.count("capture") == 2 and len(runner.jobs) == 2


@pytest.mark.parametrize("failure", ("invalid_image", "api_failure"))
def test_export_failure_stops_without_retry_or_clearing_the_case(
    tmp_path: Path, failure: str
) -> None:
    """
    Treat image/IO failures as a stopped tester problem with the last solver result still inspectable.
    """
    tester, runner, present = make_tester(tmp_path, ["completed", "completed"])
    capture = (
        Mock(side_effect=RuntimeError("image write failed")) if failure == "api_failure" else Mock()
    )
    tester.capture = capture
    start(tester, screenshots={"enabled": True, "directory": str(tmp_path / "pictures")})
    tester.poll()
    tester.poll()
    tester.poll()
    assert not tester.active and tester.phase == "problem" and len(runner.jobs) == 1
    assert capture.call_count == 1 and present.call_count == 1
    assert tester.passed == 1 and tester.state()["screenshot"] is None
    assert tester.journal is not None
    assert '"screenshot_failed"' in (tester.journal.directory / "cases.jsonl").read_text()


def test_disabled_export_does_not_touch_screenshot_folder(tmp_path: Path) -> None:
    """
    Keep the optional feature free of viewport and output-folder work when unchecked.
    """
    tester, _, _ = make_tester(tmp_path, ["completed"])
    tester.capture = Mock(side_effect=AssertionError("disabled screenshot"))
    destination = tmp_path / "unused"
    start(tester, limit=1, screenshots={"enabled": False, "directory": str(destination)})
    tester.poll()
    tester.poll()
    assert tester.phase == "completed" and not destination.exists()


def test_input_logging_failure_cannot_reuse_the_previous_screenshot_name(tmp_path: Path) -> None:
    """
    Stop a failed case-preparation boundary without exporting an image under the earlier case ID.
    """
    tester, runner, _ = make_tester(tmp_path, ["completed", "completed"])
    capture = Mock(side_effect=write_png)
    tester.capture = capture
    start(tester, screenshots={"enabled": True, "directory": str(tmp_path / "pictures")})
    tester.poll()
    tester.poll()
    assert tester.journal is not None
    tester.journal.begin = Mock(side_effect=OSError("disk full"))
    tester.poll()
    assert not tester.active and tester.phase == "problem"
    assert capture.call_count == 1 and len(runner.jobs) == 1
    assert tester.state()["input"] is None and "disk full" in tester.reason
