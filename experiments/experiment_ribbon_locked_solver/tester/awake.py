"""
Hold temporary macOS display and idle-sleep assertions for one explicitly started test.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
from typing import Any


class KeepAwake:
    """
    Own one caffeinate process, releasing it on Stop, failure or interpreter shutdown.

    The parent-PID watch also releases assertions if Fusion exits unexpectedly.
    This changes no persistent power, screen-lock or automatic-logout settings.
    """

    def __init__(self) -> None:
        """
        Start inactive; constructing a diagnostic workspace has no power-management effects.
        """
        self.process: subprocess.Popen[bytes] | None = None

    def acquire(self) -> None:
        """
        Prevent idle system/display sleep on macOS without launching duplicate helpers.
        """
        if sys.platform != "darwin":
            raise RuntimeError("Keep Mac awake is available only on macOS.")
        if self.process is not None:
            self.check()
            return
        self.process = subprocess.Popen(
            ["/usr/bin/caffeinate", "-d", "-i", "-w", str(os.getpid())],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        atexit.register(self.release)
        try:
            self.check()
        except RuntimeError:
            self.release()
            raise

    def check(self) -> None:
        """
        Refuse to silently continue after a requested keep-awake helper has exited.
        """
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("The keep-awake helper is no longer running.")

    def release(self) -> None:
        """
        Remove this lease with bounded waits; terminate only the helper owned by this instance.
        """
        process = self.process
        if process is None:
            return
        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("The keep-awake helper did not exit after termination.") from error
        self.process = None
        atexit.unregister(self.release)

    def state(self) -> dict[str, Any]:
        """
        Expose actual helper ownership without acquiring or extending an assertion.
        """
        process = self.process
        return {
            "active": process is not None and process.poll() is None,
            "pid": process.pid if process is not None else None,
        }
