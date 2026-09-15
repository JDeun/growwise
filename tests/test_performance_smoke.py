"""Performance / memory smoke guard.

Deterministic Core generation must stay fast and must not leak memory across many iterations.
Bounds are deliberately generous so the test guards against gross regressions (e.g. an O(n^2)
loop or an unbounded cache) without being flaky on shared CI runners.
"""

from __future__ import annotations

import time
import tracemalloc

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService

_ITERATIONS = 300
_MAX_SECONDS = 10.0
_MAX_PEAK_BYTES = 64 * 1024 * 1024


def _child() -> ChildProfile:
    return ChildProfile(nickname="샘플아이", stage=Stage.ELEMENTARY, interests=["동물"])


def test_template_generation_is_bounded_time_and_memory() -> None:
    service = MaterialGenerationService(provider=None)  # deterministic template, no network
    child = _child()

    tracemalloc.start()
    start = time.perf_counter()
    for i in range(_ITERATIONS):
        material = service.generate(
            child=child, kind=MaterialKind.READING_ACTIVITY, topic=f"주제{i}"
        )
        assert material.content_markdown.strip()
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert elapsed < _MAX_SECONDS, f"{_ITERATIONS} generations took {elapsed:.2f}s"
    assert peak < _MAX_PEAK_BYTES, f"peak memory {peak / 1024 / 1024:.1f} MB"


def test_generation_memory_does_not_grow_with_iterations() -> None:
    """Peak memory of a large batch must not scale linearly vs a small batch (leak guard)."""
    service = MaterialGenerationService(provider=None)
    child = _child()

    def _peak(iterations: int) -> int:
        tracemalloc.start()
        for i in range(iterations):
            service.generate(child=child, kind=MaterialKind.MATH_ACTIVITY, topic=f"t{i}")
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak

    small = _peak(50)
    large = _peak(500)
    # A leak would make 10x the work use ~10x memory. Allow generous headroom (< 4x).
    assert large < small * 4 + 2 * 1024 * 1024, f"small={small} large={large}"
