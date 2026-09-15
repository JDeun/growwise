from datetime import date

import pytest
from pydantic import ValidationError

from growwise.domain import ChildProfile, ChildSex, Stage


def test_profile_keeps_legacy_nickname_records_loadable() -> None:
    profile = ChildProfile.model_validate(
        {
            "entity_type": "child_profile",
            "nickname": "별이",
            "stage": "infant_0_2",
            "age_months": 8,
        }
    )
    assert profile.name == "별이"
    assert profile.nickname == "별이"
    assert profile.primary_language == "ko-KR"
    assert profile.sex is ChildSex.UNSPECIFIED


def test_profile_stores_education_personalization_without_sensitive_identifiers() -> None:
    profile = ChildProfile(
        name="민준",
        nickname="준이",
        stage=Stage.ELEMENTARY,
        birth_date=date(2018, 3, 2),
        sex=ChildSex.MALE,
        grade=2,
        school_entry_year=2025,
        primary_language="ko-KR",
        additional_languages=["en-US"],
        interests=["공룡", "우주"],
        preferences={"books": ["과학"], "activities": ["만들기"]},
        learning_goals=["읽은 내용을 자기 말로 설명하기"],
        notes="부모가 필요할 때만 남기는 자유 메모",
    )
    payload = profile.model_dump(mode="json")
    assert payload["name"] == "민준"
    assert payload["grade"] == 2
    assert payload["additional_languages"] == ["en-US"]
    assert "address" not in payload
    assert "school_name" not in payload
    assert "phone" not in payload
    assert "medical" not in payload


def test_birth_date_remains_authoritative_over_stale_cached_age() -> None:
    profile = ChildProfile(
        name="아이",
        stage=Stage.INFANT_0_2,
        birth_date=date(2025, 12, 19),
        age_months=200,
    )
    assert profile.age_months_on(date(2026, 9, 19)) == 9


def test_korean_grade_advances_at_march_school_year_boundary() -> None:
    profile = ChildProfile(
        name="아이",
        stage=Stage.ELEMENTARY,
        birth_date=date(2019, 10, 10),
    )
    assert profile.grade_on(date(2026, 2, 28)) is None
    assert profile.grade_on(date(2026, 3, 1)) == 1
    assert profile.stage_on(date(2026, 3, 1)) is Stage.ELEMENTARY
    assert profile.grade_on(date(2032, 3, 1)) == 7
    assert profile.stage_on(date(2032, 3, 1)) is Stage.MIDDLE
    assert profile.grade_on(date(2035, 3, 1)) == 10
    assert profile.stage_on(date(2035, 3, 1)) is Stage.HIGH


def test_grade_override_handles_early_or_delayed_school_entry() -> None:
    profile = ChildProfile(
        name="아이",
        stage=Stage.ELEMENTARY,
        birth_date=date(2019, 10, 10),
        grade_override=2,
        grade_override_reason="조기 입학",
    )
    assert profile.grade_on(date(2026, 3, 1)) == 2
    assert profile.grade == 2


def test_profile_rejects_invalid_grade_and_future_birth_date() -> None:
    with pytest.raises(ValidationError):
        ChildProfile(name="아이", stage=Stage.ELEMENTARY, grade=13)
    with pytest.raises(ValidationError):
        ChildProfile(name="아이", stage=Stage.INFANT_0_2, birth_date=date(2200, 1, 1))
