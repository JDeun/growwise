from __future__ import annotations

import pytest

from growwise.domain import MaterialKind
from growwise.generators import ScaffoldGuard


@pytest.mark.parametrize(
    "content",
    [
        "남자아이는 울면 안 돼요.",
        "여자아이는 얌전히 있어야 해요.",
        "남자답게 행동하세요.",
        "여자는 원래 그런 거예요.",
        "여자아이는 수학을 못해요.",
        "Boys don't cry.",
        "Girls are bad at math.",
        "Girls are naturally quieter.",
        "Act like a man.",
    ],
)
def test_stereotype_assertions_are_flagged(content: str):
    result = ScaffoldGuard().check(
        kind=MaterialKind.READING_ACTIVITY, title="이야기", content=content
    )
    assert not result.safe
    assert "stereotype_bias" in result.violations


@pytest.mark.parametrize(
    "content",
    [
        "남자아이와 여자아이가 함께 블록을 쌓았어요.",
        "여자아이가 수학 놀이를 즐겁게 했어요.",
        "The boy and the girl explored the garden together.",
        "누구나 과학을 좋아할 수 있어요.",
    ],
)
def test_neutral_gender_mentions_are_allowed(content: str):
    result = ScaffoldGuard().check(
        kind=MaterialKind.READING_ACTIVITY, title="이야기", content=content
    )
    assert "stereotype_bias" not in result.violations
