from __future__ import annotations

from typing import Any

import pytest

from growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialDraft, MaterialGenerationService


def _child() -> ChildProfile:
    return ChildProfile(nickname="아이", stage=Stage.ELEMENTARY, interests=["동물"])


class _StructuredProvider:
    """Returns a schema-valid but caller-controlled structured payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return MaterialDraft.model_validate(self.payload)


class _RaisingProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        raise ValueError("model returned unparseable output")


def _generate(provider: Any):
    return MaterialGenerationService(provider=provider).generate(
        child=_child(),
        kind=MaterialKind.READING_ACTIVITY,
        topic="고양이 그림책",
        source_refs=["resource:book-1"],
    )


def test_raising_provider_falls_back_to_template():
    material = _generate(_RaisingProvider())
    assert material.status == MaterialStatus.REVIEW_PENDING
    assert material.generator_mode == "template_fallback"
    assert material.content_markdown.strip()


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "content_markdown": "# 활동\n내용", "source_refs": []},
        {"title": "제목", "content_markdown": "   ", "source_refs": []},
        {"title": "제목", "content_markdown": "# 활동\n" + "가" * 20_001, "source_refs": []},
        {"title": "가" * 201, "content_markdown": "# 활동\n내용", "source_refs": []},
        {"title": "제목\x00변조", "content_markdown": "# 활동\n내용", "source_refs": []},
        {"title": "제목", "content_markdown": "# 활동\x07\n내용", "source_refs": []},
    ],
)
def test_malformed_but_valid_draft_degrades_to_template(payload: dict[str, Any]):
    material = _generate(_StructuredProvider(payload))
    assert material.status == MaterialStatus.REVIEW_PENDING
    assert material.generator_mode == "template_malformed_fallback"
    # 폴백은 결정적 템플릿이라 항상 비어있지 않고 제어문자가 없다.
    assert material.content_markdown.strip()
    assert "\x00" not in material.content_markdown and "\x07" not in material.content_markdown


def test_wellformed_draft_is_accepted():
    material = _generate(
        _StructuredProvider(
            {
                "title": "고양이 읽기",
                "content_markdown": (
                    "## 그림에서 질문 찾기\n"
                    "1. 그림책을 함께 보고 아이가 궁금한 장면을 하나 골라 충분히 살펴봅니다.\n"
                    "2. 앞뒤 장면을 비교하고 눈에 띄는 차이를 아이가 자기 말로 설명해 봅니다.\n"
                    "## 생각 이어가기\n"
                    "다음 장면에서는 어떤 일이 일어날까요? "
                    "그림 속 단서와 다른 가능성을 함께 찾아봅니다."
                ),
                "source_refs": ["resource:book-1"],
            }
        )
    )
    assert material.generator_mode == "llm_enhanced"
    assert material.title == "고양이 읽기"
