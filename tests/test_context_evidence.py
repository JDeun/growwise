from __future__ import annotations

import pytest
from pydantic import ValidationError

from growwise.services.context import ContextAnswer, _entity_text


def test_entity_text_keeps_parent_summary_and_learner_work() -> None:
    text = _entity_text(
        {
            "record_kind": "reading_reflection",
            "title": "어린 왕자 독서감상",
            "subject": "국어",
            "parent_observation": "책을 읽고 책임에 대해 이야기했다.",
            "learner_work": "장미를 떠나온 것이 가장 슬펐다.",
            "interest": "등장인물의 선택",
        }
    )

    assert "제목: 어린 왕자 독서감상" in text
    assert "부모 기록: 책을 읽고 책임에 대해 이야기했다." in text
    assert "아이 글·결과물: 장미를 떠나온 것이 가장 슬펐다." in text
    assert "흥미: 등장인물의 선택" in text



def test_context_answer_bounds_generated_text_and_source_ids() -> None:
    with pytest.raises(ValidationError):
        ContextAnswer(answer="x" * 20_001)
    with pytest.raises(ValidationError):
        ContextAnswer(answer="ok", source_ids=["record:x"] * 101)
    with pytest.raises(ValidationError):
        ContextAnswer(answer="ok", source_ids=["x" * 501])
