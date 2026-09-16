#!/usr/bin/env python3
"""Minimum/recommended hardware benchmark harness.

Measures the host (OS, architecture, CPU count, total RAM) and the deterministic Core generation
throughput, then classifies the machine against GrowWise's documented minimum (8 GB) / recommended
(16 GB) tiers. Real guidance comes from running this on representative machines; the harness
produces the measurements and a conservative classification.

Usage:  uv run python scripts/benchmark_hardware.py
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
import time
from dataclasses import asdict, dataclass

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService

_MIN_RAM_GB = 8.0
_RECOMMENDED_RAM_GB = 16.0
_GIB = 1024**3


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _windows_total_ram_gb() -> float | None:
    """Return physical RAM through GlobalMemoryStatusEx without adding a runtime dependency."""

    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None

    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    try:
        ok = windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    except (AttributeError, OSError):
        return None
    if not ok or status.ullTotalPhys <= 0:
        return None
    return round(status.ullTotalPhys / _GIB, 2)


def _darwin_total_ram_gb() -> float | None:
    """Return macOS physical RAM via Apple's hw.memsize sysctl."""

    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        total_bytes = int(result.stdout.strip())
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    if total_bytes <= 0:
        return None
    return round(total_bytes / _GIB, 2)


def _posix_total_ram_gb() -> float | None:
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        phys_pages = int(os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError, AttributeError):
        return None
    if page_size <= 0 or phys_pages <= 0:
        return None
    return round((page_size * phys_pages) / _GIB, 2)


def _total_ram_gb() -> float | None:
    system = platform.system()
    if system == "Windows":
        return _windows_total_ram_gb()
    if system == "Darwin":
        return _darwin_total_ram_gb()
    return _posix_total_ram_gb()


@dataclass(frozen=True)
class HardwareReport:
    os_name: str
    architecture: str
    cpu_count: int
    total_ram_gb: float | None
    core_generations_per_sec: float
    tier: str
    meets_minimum: bool | None


def measure_core_throughput(iterations: int = 200) -> float:
    service = MaterialGenerationService(provider=None)
    child = ChildProfile(nickname="샘플아이", stage=Stage.ELEMENTARY, interests=["동물"])
    start = time.perf_counter()
    for i in range(iterations):
        service.generate(child=child, kind=MaterialKind.READING_ACTIVITY, topic=f"주제{i}")
    elapsed = time.perf_counter() - start
    return round(iterations / elapsed, 1) if elapsed > 0 else 0.0


def _classify(ram_gb: float | None) -> tuple[str, bool | None]:
    if ram_gb is None:
        return "unknown", None
    if ram_gb >= _RECOMMENDED_RAM_GB:
        return "recommended", True
    if ram_gb >= _MIN_RAM_GB:
        return "minimum", True
    return "below-minimum", False


def run_hardware_benchmark(iterations: int = 200) -> HardwareReport:
    ram = _total_ram_gb()
    tier, meets = _classify(ram)
    return HardwareReport(
        os_name=platform.system() or "unknown",
        architecture=platform.machine() or "unknown",
        cpu_count=os.cpu_count() or 1,
        total_ram_gb=ram,
        core_generations_per_sec=measure_core_throughput(iterations),
        tier=tier,
        meets_minimum=meets,
    )


def main() -> int:
    report = run_hardware_benchmark()
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
