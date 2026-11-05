"""
Read current macOS resident memory without launching a child process at every checkpoint.
"""

from __future__ import annotations

import ctypes
import os
from functools import lru_cache
from typing import Any

from .provenance import mark_loaded


class _TaskInfo(ctypes.Structure):
    """
    Match Apple's proc_taskinfo ABI: six64-bit counters followed by twelve32-bit fields.
    """

    _fields_ = [
        ("virtual_size", ctypes.c_uint64),
        ("resident_size", ctypes.c_uint64),
        ("total_user", ctypes.c_uint64),
        ("total_system", ctypes.c_uint64),
        ("threads_user", ctypes.c_uint64),
        ("threads_system", ctypes.c_uint64),
        ("policy", ctypes.c_int32),
        ("faults", ctypes.c_int32),
        ("pageins", ctypes.c_int32),
        ("cow_faults", ctypes.c_int32),
        ("messages_sent", ctypes.c_int32),
        ("messages_received", ctypes.c_int32),
        ("syscalls_mach", ctypes.c_int32),
        ("syscalls_unix", ctypes.c_int32),
        ("context_switches", ctypes.c_int32),
        ("thread_count", ctypes.c_int32),
        ("running_count", ctypes.c_int32),
        ("priority", ctypes.c_int32),
    ]


@lru_cache(maxsize=1)
def _task_query() -> Any:
    """
    Bind libproc once while retaining a fresh kernel query for every memory sample.

    The signature and structure follow the macOS SDK's libproc.h and
    sys/proc_info.h, PROC_PIDTASKINFO. Loading/query errors propagate; no peak
    memory substitution, stale sample or fail-open fallback is permitted.
    """
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    query = library.proc_pidinfo
    query.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    query.restype = ctypes.c_int
    return query


def darwin_resident_kib() -> int:
    """
    Return this process's current RSS in KiB, rounding upward and rejecting incomplete reads.

    Resident size excludes compressed memory and physical-footprint accounting,
    preserving the existing RSS ceiling. No child process is started, no sample
    is cached and no memory or time limit is changed.
    """
    info = _TaskInfo()
    size = ctypes.sizeof(info)
    received = _task_query()(os.getpid(), 4, 0, ctypes.byref(info), size)
    if received != size or info.resident_size <= 0:
        raise RuntimeError(
            f"Fusion RSS measurement is unavailable: proc_pidinfo returned {received}/{size} bytes "
            f"(errno {ctypes.get_errno()})."
        )
    return (info.resident_size + 1023) // 1024


mark_loaded(__file__)
