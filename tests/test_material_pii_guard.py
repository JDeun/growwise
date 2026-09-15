from __future__ import annotations

import pytest

from growwise.domain import MaterialKind
from growwise.generators.scaffold import ScaffoldGuard


@pytest.mark.parametrize(
    "content",
    [
        "연락처는 010-1234-5678 입니다.",
        "보호자 이메일: parent.child@example.com",
        "주민등록번호 900101-1234567",
        "Contact 02-123-4567 for details.",
    ],
)
def test_scaffold_guard_rejects_pii_in_generated_material(content: str) -> None:
    result = ScaffoldGuard().check(
        kind=MaterialKind.READING_ACTIVITY,
        title="검토 자료",
        content=content,
    )

    assert result.safe is False
    assert "pii_leakage" in result.violations


@pytest.mark.parametrize(
    "content",
    [
        "10에서 11까지 숫자를 세어 봅니다.",
        "2026년 9월의 관찰 내용을 돌아봅니다.",
        "책의 123쪽을 함께 살펴봅니다.",
    ],
)
def test_scaffold_guard_does_not_flag_ordinary_learning_numbers(content: str) -> None:
    result = ScaffoldGuard().check(
        kind=MaterialKind.READING_ACTIVITY,
        title="숫자 활동",
        content=content,
    )

    assert "pii_leakage" not in result.violations
