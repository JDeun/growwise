#!/usr/bin/env python3
"""Local model latency/quality benchmark harness.

Runs a set of representative parent-facing generation requests through a model provider and
reports per-request latency plus a lightweight quality proxy (does the draft survive the
scaffold safety guard, and is it non-trivial). Real numbers require a real local model
(e.g. Ollama); the harness itself is provider-agnostic and offline-testable via a stub.

Usage (real):  uv run python scripts/benchmark_model.py
The decision "keep local vs switch remote" is the operator's — this only produces the data.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService
from growwise.model import ModelProvider

_PROMPTS: tuple[tuple[MaterialKind, str], ...] = (
    (MaterialKind.READING_ACTIVITY, "고양이 그림책"),
    (MaterialKind.ENGLISH_CARD, "아침 인사"),
    (MaterialKind.MATH_ACTIVITY, "블록으로 수 세기"),
    (MaterialKind.SCIENCE_INQUIRY, "얼음이 녹는 관찰"),
    (MaterialKind.WRITING_PROMPT, "오늘 있었던 일"),
    (MaterialKind.FIELD_TRIP, "동네 도서관 방문"),
)


@dataclass(frozen=True)
class BenchmarkRow:
    kind: str
    topic: str
    latency_ms: float
    generator_mode: str
    content_chars: int
    llm_used: bool


@dataclass(frozen=True)
class BenchmarkReport:
    rows: list[BenchmarkRow]
    count: int
    avg_latency_ms: float
    p95_latency_ms: float
    llm_used_ratio: float


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def run_model_benchmark(
    provider: ModelProvider | None,
    *,
    stage: Stage = Stage.ELEMENTARY,
    repeats: int = 1,
) -> BenchmarkReport:
    child = ChildProfile(nickname="샘플아이", stage=stage, interests=["동물"])
    service = MaterialGenerationService(provider=provider)
    rows: list[BenchmarkRow] = []
    for _ in range(max(1, repeats)):
        for kind, topic in _PROMPTS:
            start = time.perf_counter()
            material = service.generate(child=child, kind=kind, topic=topic)
            latency_ms = (time.perf_counter() - start) * 1000.0
            rows.append(
                BenchmarkRow(
                    kind=kind.value,
                    topic=topic,
                    latency_ms=round(latency_ms, 3),
                    generator_mode=material.generator_mode,
                    content_chars=len(material.content_markdown),
                    llm_used=material.generator_mode == "llm_enhanced",
                )
            )
    latencies = [r.latency_ms for r in rows]
    llm_used = sum(1 for r in rows if r.llm_used)
    return BenchmarkReport(
        rows=rows,
        count=len(rows),
        avg_latency_ms=round(sum(latencies) / len(latencies), 3),
        p95_latency_ms=round(_percentile(latencies, 95), 3),
        llm_used_ratio=round(llm_used / len(rows), 3),
    )


def main() -> int:
    try:
        from growwise.model import build_provider  # type: ignore[attr-defined]

        provider = build_provider()
    except Exception:  # noqa: BLE001 - no local model configured → Core-only baseline
        provider = None
    report = run_model_benchmark(provider)
    payload = {
        "provider": "configured" if provider is not None else "core-only",
        **{k: v for k, v in asdict(report).items() if k != "rows"},
        "rows": [asdict(r) for r in report.rows],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
