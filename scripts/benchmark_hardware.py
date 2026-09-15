#!/usr/bin/env python3
"""Minimum/recommended hardware benchmark harness.

Measures the host (CPU count, total RAM) and the deterministic Core generation throughput,
then classifies the machine against GrowWise's documented minimum (8 GB) / recommended (16 GB)
tiers. Real guidance comes from running this on representative machines; the harness produces
the measurements and a conservative classification.

Usage:  uv run python scripts/benchmark_hardware.py
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService

_MIN_RAM_GB = 8.0
_RECOMMENDED_RAM_GB = 16.0


def _total_ram_gb() -> float | None:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        phys_pages = os.sysconf("SC_PHYS_PAGES")
        return round((page_size * phys_pages) / (1024**3), 2)
    except (ValueError, OSError, AttributeError):
        return None


@dataclass(frozen=True)
class HardwareReport:
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
