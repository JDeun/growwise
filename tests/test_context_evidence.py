from __future__ import annotations

from growwise.services.context import _entity_text


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
