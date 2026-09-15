from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

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
    assert report.cpu_count >= 1
    assert report.core_generations_per_sec > 0.0
    assert report.tier in {"recommended", "minimum", "below-minimum", "unknown"}
