#!/usr/bin/env python3
"""Local model latency/quality benchmark harness.

Runs representative parent-facing generation requests through the configured model provider and
reports timed samples plus the exact synthetic material output needed for manual quality review.
Real numbers require a real local model (e.g. Ollama); the harness itself is provider-agnostic and
offline-testable via a stub.

Recommended real run:
  uv run python scripts/benchmark_model.py --warmup-rounds 1 --repeats 3

The decision "keep local vs switch remote" is the operator's — this only produces the evidence.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from growwise.config import Settings
from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService
from growwise.model import ModelProvider, create_model_provider

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
    sample: int
    kind: str
    topic: str
    latency_ms: float
    generator_mode: str
    title: str
    content_markdown: str
    content_chars: int
    llm_used: bool


@dataclass(frozen=True)
class BenchmarkReport:
    rows: list[BenchmarkRow]
    count: int
    repeats: int
    warmup_rounds: int
    stage: str
    avg_latency_ms: float
    p95_latency_ms: float
    llm_used_ratio: float
    generator_mode_counts: dict[str, int]


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
    warmup_rounds: int = 0,
) -> BenchmarkReport:
    measured_repeats = max(1, repeats)
    warmups = max(0, warmup_rounds)
    child = ChildProfile(nickname="샘플아이", stage=stage, interests=["동물"])
    service = MaterialGenerationService(provider=provider)

    for _ in range(warmups):
        for kind, topic in _PROMPTS:
            service.generate(child=child, kind=kind, topic=topic)

    rows: list[BenchmarkRow] = []
    for sample in range(1, measured_repeats + 1):
        for kind, topic in _PROMPTS:
            start = time.perf_counter()
            material = service.generate(child=child, kind=kind, topic=topic)
            latency_ms = (time.perf_counter() - start) * 1000.0
            rows.append(
                BenchmarkRow(
                    sample=sample,
                    kind=kind.value,
                    topic=topic,
                    latency_ms=round(latency_ms, 3),
                    generator_mode=material.generator_mode,
                    title=material.title,
                    content_markdown=material.content_markdown,
                    content_chars=len(material.content_markdown),
                    llm_used=material.generator_mode == "llm_enhanced",
                )
            )

    latencies = [row.latency_ms for row in rows]
    llm_used = sum(1 for row in rows if row.llm_used)
    mode_counts = dict(Counter(row.generator_mode for row in rows))
    return BenchmarkReport(
        rows=rows,
        count=len(rows),
        repeats=measured_repeats,
        warmup_rounds=warmups,
        stage=stage.value,
        avg_latency_ms=round(sum(latencies) / len(latencies), 3),
        p95_latency_ms=round(_percentile(latencies, 95), 3),
        llm_used_ratio=round(llm_used / len(rows), 3),
        generator_mode_counts=mode_counts,
    )


def _provider_from_settings(settings: Settings) -> ModelProvider | None:
    if not settings.llm_features_enabled:
        return None
    return create_model_provider(settings)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark GrowWise material generation.")
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Measured rounds; each round runs all prompts",
    )
    parser.add_argument(
        "--warmup-rounds",
        type=int,
        default=0,
        help="Untimed rounds before measurement to remove model-load effects",
    )
    parser.add_argument(
        "--stage",
        choices=tuple(stage.value for stage in Stage),
        default=Stage.ELEMENTARY.value,
        help="Child stage used for deterministic curriculum/material context",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.warmup_rounds < 0:
        parser.error("--warmup-rounds must be at least 0")

    settings = Settings()
    provider = _provider_from_settings(settings)
    report = run_model_benchmark(
        provider,
        stage=Stage(args.stage),
        repeats=args.repeats,
        warmup_rounds=args.warmup_rounds,
    )
    payload = {
        "provider": "configured" if provider is not None else "core-only",
        "provider_kind": settings.model_provider,
        "model_id": settings.model_id,
        "llm_features_enabled": settings.llm_features_enabled,
        **{key: value for key, value in asdict(report).items() if key != "rows"},
        "rows": [asdict(row) for row in report.rows],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
