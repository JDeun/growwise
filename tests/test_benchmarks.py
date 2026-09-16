from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPTS / f"{module_name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _StubProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return schema.model_validate(
            {
                "title": "샘플",
                "content_markdown": "# 활동\n그림을 함께 보고 질문을 하나만 합니다.",
                "source_refs": [],
            }
        )


def test_model_benchmark_reports_latency_and_quality() -> None:
    bench = _load("benchmark_model")
    report = bench.run_model_benchmark(_StubProvider())
    assert report.count == 6
    assert report.avg_latency_ms >= 0.0
    assert report.p95_latency_ms >= 0.0
    assert 0.0 <= report.llm_used_ratio <= 1.0
    assert report.llm_used_ratio == 1.0  # stub returns a safe draft → llm_enhanced
    assert all(row.content_chars > 0 for row in report.rows)


def test_model_benchmark_core_only_baseline() -> None:
    bench = _load("benchmark_model")
    report = bench.run_model_benchmark(None)
    assert report.count == 6
    assert report.llm_used_ratio == 0.0  # no provider → deterministic template


def test_hardware_benchmark_measures_and_classifies() -> None:
    bench = _load("benchmark_hardware")
    report = bench.run_hardware_benchmark(iterations=25)
    assert report.os_name
    assert report.architecture
    assert report.cpu_count >= 1
    assert report.core_generations_per_sec > 0.0
    assert report.tier in {"recommended", "minimum", "below-minimum", "unknown"}


def test_hardware_benchmark_reads_windows_physical_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bench = _load("benchmark_hardware_windows")

    class Kernel32:
        @staticmethod
        def GlobalMemoryStatusEx(pointer: Any) -> int:
            pointer._obj.ullTotalPhys = 12 * bench._GIB
            return 1

    monkeypatch.setattr(
        bench.ctypes,
        "windll",
        SimpleNamespace(kernel32=Kernel32()),
        raising=False,
    )
    monkeypatch.setattr(bench.platform, "system", lambda: "Windows")

    assert bench._total_ram_gb() == 12.0
    assert bench._classify(bench._total_ram_gb()) == ("minimum", True)


def test_hardware_benchmark_reads_posix_physical_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bench = _load("benchmark_hardware_posix")
    values = {
        "SC_PAGE_SIZE": 4096,
        "SC_PHYS_PAGES": 4 * 1024 * 1024,
    }
    monkeypatch.setattr(bench.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(bench.os, "sysconf", lambda name: values[name])

    assert bench._total_ram_gb() == 16.0
    assert bench._classify(bench._total_ram_gb()) == ("recommended", True)


def test_hardware_benchmark_rejects_invalid_memory_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bench = _load("benchmark_hardware_invalid")
    monkeypatch.setattr(bench.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bench.os, "sysconf", lambda _name: -1)

    assert bench._total_ram_gb() is None
    assert bench._classify(None) == ("unknown", None)
