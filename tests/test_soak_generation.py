"""Long-running soak for the material generation + safety-guard path.

Rotates safe, unsafe, and malformed provider outputs across many iterations and asserts the
service never raises, always returns a REVIEW_PENDING draft, and always selects the correct
fallback mode. Guards against slow degradation (state leakage between calls, guard drift).
"""

from __future__ import annotations

from typing import Any

from growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialGenerationService

_CYCLES = 1500
_KINDS = list(MaterialKind)

# (payload, expected generator_mode) — a rotating mix exercising every guard branch.
_CASES: list[tuple[dict[str, Any] | None, str]] = [
    (
        {
            "title": "안전 자료",
            "content_markdown": "# 활동\n그림을 함께 보고 열린 질문을 하나만 합니다.",
            "source_refs": [],
        },
        "llm_enhanced",
    ),
    (
        {
            "title": "발달 진단",
            "content_markdown": "또래보다 뒤처졌고 자폐 진단이 필요합니다.",
            "source_refs": [],
        },
        "template_safety_fallback",
    ),
    (
        {
            "title": "정답 자료",
            "content_markdown": "정답은 42입니다. 그대로 따라 쓰세요.",
            "source_refs": [],
        },
        "template_safety_fallback",
    ),
    (
        {"title": "", "content_markdown": "# 활동\n내용", "source_refs": []},
        "template_malformed_fallback",
    ),
    (
        {"title": "제목", "content_markdown": "# 활동\x07\n내용", "source_refs": []},
        "template_malformed_fallback",
    ),
    (None, "template_fallback"),  # provider raises
]


class _RotatingProvider:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        if self.payload is None:
            raise ValueError("model returned unparseable output")
        return schema.model_validate(self.payload)


def test_generation_soak_stays_safe_and_stable() -> None:
    child = ChildProfile(nickname="샘플아이", stage=Stage.ELEMENTARY, interests=["동물"])
    provider = _RotatingProvider()
    service = MaterialGenerationService(provider=provider)

    for cycle in range(_CYCLES):
        payload, expected_mode = _CASES[cycle % len(_CASES)]
        provider.payload = payload
        kind = _KINDS[cycle % len(_KINDS)]

        material = service.generate(child=child, kind=kind, topic=f"주제{cycle}")

        assert material.status == MaterialStatus.REVIEW_PENDING
        assert material.content_markdown.strip()
        assert material.generator_mode == expected_mode, (
            f"cycle {cycle}: expected {expected_mode}, got {material.generator_mode}"
        )
        # Safety invariant: no control chars ever reach a parent-reviewable draft.
        assert "\x07" not in material.content_markdown
