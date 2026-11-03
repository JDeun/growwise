from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(module_name: str, *, script_name: str | None = None) -> Any:
    script = script_name or module_name
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPTS / f"{script}.py")
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
                "content_markdown": (
                    "## 함께 살펴보기\n"
                    "1. 주변에서 관심 있는 대상을 하나 고르고 모양과 색을 충분히 관찰해 봅니다.\n"
                    "2. 비슷한 다른 대상과 나란히 놓아 어떤 점이 같고 다른지 비교해 봅니다.\n"
                    "## 생각 이어가기\n"
                    "다른 방법으로 살펴보면 무엇을 더 발견할 수 있을까요? "
                    "말이나 손짓으로 생각을 나눕니다."
                ),
                "source_refs": [],
            }
        )


def test_model_benchmark_reports_latency_and_reviewable_output() -> None:
    bench = _load("benchmark_model")
    report = bench.run_model_benchmark(_StubProvider(), repeats=2, warmup_rounds=1)
    assert report.count == 12
    assert report.repeats == 2
    assert report.warmup_rounds == 1
    assert report.stage
    assert report.avg_latency_ms >= 0.0
    assert report.p95_latency_ms >= 0.0
    assert report.llm_used_ratio == 1.0  # stub returns a safe draft → llm_enhanced
    assert report.generator_mode_counts == {"llm_enhanced": 12}
    assert {row.sample for row in report.rows} == {1, 2}
    assert all(row.title == "샘플" for row in report.rows)
    assert all("## 오늘의 목표" in row.content_markdown for row in report.rows)
    assert all("## 활동 자료" in row.content_markdown for row in report.rows)
    assert all(row.content_chars == len(row.content_markdown) for row in report.rows)
    assert all("## 진행 시나리오" in row.parent_guide_markdown for row in report.rows)


def test_model_benchmark_core_only_baseline() -> None:
    bench = _load("benchmark_model")
    report = bench.run_model_benchmark(None)
    assert report.count == 6
    assert report.llm_used_ratio == 0.0  # no provider → deterministic template
    assert report.generator_mode_counts == {"template": 6}
    assert all(row.content_markdown for row in report.rows)


def test_model_benchmark_can_reproduce_one_kind_without_other_model_calls() -> None:
    from growwise.domain import MaterialKind

    bench = _load("benchmark_model_single", script_name="benchmark_model")

    class CountingProvider(_StubProvider):
        def __init__(self):
            self.calls = 0

        def generate_structured(self, **kwargs):
            self.calls += 1
            return super().generate_structured(**kwargs)

    provider = CountingProvider()
    report = bench.run_model_benchmark(provider, kind=MaterialKind.MATH_ACTIVITY,
                                       repeats=2, warmup_rounds=1)
    assert report.count == 2
    assert provider.calls == 3
    assert all(row.kind == "math_activity" for row in report.rows)


def test_model_benchmark_cli_uses_configured_provider(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bench = _load("benchmark_model_cli", script_name="benchmark_model")
    settings = SimpleNamespace(
        llm_features_enabled=True,
        model_provider="ollama",
        model_id="test-model:4b",
        model_timeout_seconds=12,
        model_max_output_tokens=768,
        background_ai_model_timeout_seconds=240,
        background_ai_max_output_tokens=8192,
        background_ai_reasoning_enabled=False,
        background_ai_model_context_tokens=8192,
    )
    calls: list[Any] = []

    def create_provider(received: Any, *, background: bool = False) -> _StubProvider:
        calls.append((received, background))
        return _StubProvider()

    monkeypatch.setattr(bench, "Settings", lambda: settings)
    monkeypatch.setattr(bench, "create_model_provider", create_provider)

    assert bench.main(["--repeats", "2", "--warmup-rounds", "1"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert calls == [(settings, True)]
    assert payload["provider"] == "configured"
    assert payload["provider_kind"] == "ollama"
    assert payload["model_id"] == "test-model:4b"
    assert payload["llm_features_enabled"] is True
    assert payload["inference_profile"] == "background_material"
    assert payload["effective_timeout_seconds"] == 240
    assert payload["effective_max_output_tokens"] == 8192
    assert payload["reasoning"] is False
    assert payload["effective_context_tokens"] == 8192
    assert payload["repeats"] == 2
    assert payload["warmup_rounds"] == 1
    assert payload["count"] == 12
    assert payload["llm_used_ratio"] == 1.0
    assert payload["generator_mode_counts"] == {"llm_enhanced": 12}
    assert len(payload["rows"]) == 12
    assert all(row["title"] == "샘플" for row in payload["rows"])
    assert all("## 오늘의 목표" in row["content_markdown"] for row in payload["rows"])
    assert all("## 활동 자료" in row["content_markdown"] for row in payload["rows"])
    assert all("## 진행 시나리오" in row["parent_guide_markdown"] for row in payload["rows"])


def test_model_benchmark_cli_respects_disabled_llm(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bench = _load("benchmark_model_disabled", script_name="benchmark_model")
    settings = SimpleNamespace(
        llm_features_enabled=False,
        model_provider="ollama",
        model_id="disabled-model",
    )
    monkeypatch.setattr(bench, "Settings", lambda: settings)
    monkeypatch.setattr(
        bench,
        "create_model_provider",
        lambda _settings: pytest.fail("disabled benchmark must not construct a provider"),
    )

    assert bench.main([]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "core-only"
    assert payload["inference_profile"] == "core_only"
    assert payload["effective_timeout_seconds"] is None
    assert payload["effective_max_output_tokens"] is None
    assert payload["reasoning"] is None
    assert payload["effective_context_tokens"] is None
    assert payload["llm_features_enabled"] is False
    assert payload["llm_used_ratio"] == 0.0
    assert payload["generator_mode_counts"] == {"template": 6}


def test_model_benchmark_distinguishes_called_provider_from_accepted_model_output() -> None:
    bench = _load("benchmark_model_quality", script_name="benchmark_model")

    class WeakProvider(_StubProvider):
        def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
            return schema.model_validate(
                {
                    "title": "샘플",
                    "content_markdown": "# 활동\n짧음",
                    "source_refs": [],
                }
            )

    report = bench.run_model_benchmark(WeakProvider())
    assert report.count == 6
    assert report.llm_used_ratio == 0.0
    assert report.generator_mode_counts == {"template_quality_fallback": 6}
    assert all(not row.llm_used for row in report.rows)
    assert all("## 오늘의 목표" in row.content_markdown for row in report.rows)


def test_model_benchmark_cli_rejects_invalid_round_counts() -> None:
    bench = _load("benchmark_model_invalid_args", script_name="benchmark_model")
    with pytest.raises(SystemExit, match="2"):
        bench.main(["--repeats", "0"])
    with pytest.raises(SystemExit, match="2"):
        bench.main(["--warmup-rounds", "-1"])


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
    bench = _load("benchmark_hardware_windows", script_name="benchmark_hardware")

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


def test_hardware_benchmark_reads_macos_physical_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bench = _load("benchmark_hardware_macos", script_name="benchmark_hardware")
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(stdout=str(16 * bench._GIB))

    monkeypatch.setattr(bench.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(bench.subprocess, "run", run)

    assert bench._total_ram_gb() == 16.0
    assert bench._classify(bench._total_ram_gb()) == ("recommended", True)
    assert calls == [["sysctl", "-n", "hw.memsize"], ["sysctl", "-n", "hw.memsize"]]


def test_hardware_benchmark_macos_probe_timeout_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bench = _load("benchmark_hardware_macos_timeout", script_name="benchmark_hardware")
    monkeypatch.setattr(bench.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        bench.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd="sysctl", timeout=2)
        ),
    )

    assert bench._total_ram_gb() is None
    assert bench._classify(None) == ("unknown", None)


def test_hardware_benchmark_reads_posix_physical_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bench = _load("benchmark_hardware_posix", script_name="benchmark_hardware")
    values = {
        "SC_PAGE_SIZE": 4096,
        "SC_PHYS_PAGES": 4 * 1024 * 1024,
    }
    monkeypatch.setattr(bench.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bench.os, "sysconf", lambda name: values[name], raising=False)

    assert bench._total_ram_gb() == 16.0
    assert bench._classify(bench._total_ram_gb()) == ("recommended", True)


def test_hardware_benchmark_rejects_invalid_memory_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bench = _load("benchmark_hardware_invalid", script_name="benchmark_hardware")
    monkeypatch.setattr(bench.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bench.os, "sysconf", lambda _name: -1, raising=False)

    assert bench._total_ram_gb() is None
    assert bench._classify(None) == ("unknown", None)
