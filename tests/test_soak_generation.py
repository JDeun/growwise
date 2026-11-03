"""Long-running soak for the material generation + safety-guard path.

Rotates safe, unsafe, and malformed provider outputs across many iterations and asserts the
service never raises, always returns a REVIEW_PENDING draft, and always selects the correct
fallback mode. Guards against slow degradation (state leakage between calls, guard drift).
"""

from __future__ import annotations

from typing import Any

from material_quality_fixtures import observed_draft_for_request

from growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialDraft, MaterialGenerationService

_CYCLES = 1500
_KINDS = list(MaterialKind)

# (payload, expected generator_mode) — a rotating mix exercising every guard branch.
_CASES: list[tuple[dict[str, Any] | None, str]] = [
    (
        {
            "title": "안전 자료",
            "content_markdown": (
                "## 함께 살펴보기\n"
                "1. 관심 있는 대상을 하나 고르고 모양과 색을 아이의 속도에 맞추어 관찰합니다.\n"
                "2. 비슷한 다른 대상과 나란히 놓고 어떤 점이 같고 다른지 천천히 살펴봅니다.\n"
                "## 생각 이어가기\n"
                "무엇을 더 살펴보고 싶나요? "
                "아이가 말이나 손짓으로 고른 방향에 따라 짧게 이어갑니다."
            ),
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
        if self.payload is _CASES[0][0]:
            return observed_draft_for_request(user)
        return MaterialDraft.model_validate(self.payload)


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
