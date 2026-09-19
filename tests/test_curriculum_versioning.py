from __future__ import annotations

from datetime import date

from growwise.curriculum_versions import (
    effective_curriculum_stage,
    resolve_curriculum_version,
    resolve_external_curriculum_version,
    school_transition_start,
)
from growwise.domain import ChildProfile, Stage


def _student(*, grade: int, stage: Stage) -> ChildProfile:
    return ChildProfile(name="합성학생", stage=stage, grade=grade)


def test_effective_stage_uses_grade_or_birth_date_but_not_static_age_snapshot() -> None:
    explicit = ChildProfile(
        name="명시단계",
        stage=Stage.ELEMENTARY,
        age_months=48,
    )
    by_grade = ChildProfile(
        name="학년우선",
        stage=Stage.PRESCHOOL_3_5,
        grade=8,
    )
    by_birth = ChildProfile(
        name="생년월일",
        stage=Stage.PRESCHOOL_3_5,
        birth_date=date(2018, 4, 1),
    )

    assert (
        effective_curriculum_stage(explicit, on_date=date(2026, 9, 19))
        is Stage.ELEMENTARY
    )
    assert (
        effective_curriculum_stage(by_grade, on_date=date(2026, 9, 19))
        is Stage.MIDDLE
    )
    assert (
        effective_curriculum_stage(by_birth, on_date=date(2026, 9, 19))
        is Stage.ELEMENTARY
    )


def test_2026_rollout_resolves_each_school_grade_correctly() -> None:
    reference = date(2026, 9, 19)

    elementary = resolve_curriculum_version(
        _student(grade=5, stage=Stage.ELEMENTARY),
        on_date=reference,
    )
    middle_2 = resolve_curriculum_version(
        _student(grade=8, stage=Stage.MIDDLE),
        on_date=reference,
    )
    middle_3 = resolve_curriculum_version(
        _student(grade=9, stage=Stage.MIDDLE),
        on_date=reference,
    )
    high_2 = resolve_curriculum_version(
        _student(grade=11, stage=Stage.HIGH),
        on_date=reference,
    )
    high_3 = resolve_curriculum_version(
        _student(grade=12, stage=Stage.HIGH),
        on_date=reference,
    )

    assert elementary.source_ref == "국가교육위원회고시 제2024-3호"
    assert middle_2.source_ref == "국가교육위원회고시 제2024-3호"
    assert high_2.source_ref == "국가교육위원회고시 제2026-1호"
    assert middle_3.source_ref == "국가교육위원회고시 제2024-1호"
    assert high_3.source_ref == "국가교육위원회고시 제2024-1호"
    assert middle_3.effective_to == date(2027, 2, 28)
    assert high_3.effective_to == date(2027, 2, 28)


def test_final_transition_happens_on_2027_school_year() -> None:
    reference = date(2027, 3, 1)

    for grade, stage in ((9, Stage.MIDDLE), (12, Stage.HIGH)):
        resolution = resolve_curriculum_version(
            _student(grade=grade, stage=stage),
            on_date=reference,
        )
        expected_notice = (
            "국가교육위원회고시 제2024-3호"
            if grade == 9
            else "국가교육위원회고시 제2026-1호"
        )
        expected_revision = "2022-rev-2024-3" if grade == 9 else "2022-rev-2026-1"
        assert resolution.source_ref == expected_notice
        assert resolution.revision == expected_revision


def test_2026_amendment_has_its_own_grade_effective_dates() -> None:
    high_1 = resolve_curriculum_version(
        _student(grade=10, stage=Stage.HIGH),
        on_date=date(2026, 3, 1),
    )
    elem_1_before = resolve_curriculum_version(
        _student(grade=1, stage=Stage.ELEMENTARY),
        on_date=date(2027, 9, 1),
    )
    elem_1_after = resolve_curriculum_version(
        _student(grade=1, stage=Stage.ELEMENTARY),
        on_date=date(2028, 3, 1),
    )

    assert high_1.source_ref == "국가교육위원회고시 제2026-1호"
    assert elem_1_before.source_ref == "국가교육위원회고시 제2024-3호"
    assert elem_1_after.source_ref == "국가교육위원회고시 제2026-1호"


def test_live_endpoint_cannot_downgrade_newer_bundled_notice() -> None:
    child = _student(grade=11, stage=Stage.HIGH)
    records = [
        {
            "stage": "high",
            "framework": "2022 개정 고등학교 교육과정",
            "revision": "2022-rev-2024-3",
            "official_notice": "국가교육위원회고시 제2024-3호",
            "effective_from": "2025-03-01",
            "grades": [11],
            "source_url": "https://ncic.re.kr/curriculum/2024-3",
        }
    ]

    assert (
        resolve_external_curriculum_version(
            records,
            child,
            on_date=date(2026, 9, 19),
        )
        is None
    )


def test_stage_only_profile_fails_safe_during_mixed_rollout() -> None:
    child = ChildProfile(name="학년미상", stage=Stage.MIDDLE)

    resolution = resolve_curriculum_version(child, on_date=date(2026, 9, 19))

    assert resolution.revision == "transition-unresolved"
    assert resolution.precision == "stage_transition"
    assert resolution.transition_note
    assert "학년 정보" in resolution.transition_note


def test_elementary_stage_is_unambiguous_after_2026_rollout() -> None:
    child = ChildProfile(name="학년미상", stage=Stage.ELEMENTARY)

    resolution = resolve_curriculum_version(child, on_date=date(2026, 9, 19))

    assert resolution.revision == "2022-rev-2024-3"
    assert resolution.precision == "stage_common"


def test_school_transition_schedule_is_locked() -> None:
    assert school_transition_start(1) == date(2024, 3, 1)
    assert school_transition_start(7) == date(2025, 3, 1)
    assert school_transition_start(8) == date(2026, 3, 1)
    assert school_transition_start(9) == date(2027, 3, 1)
    assert school_transition_start(12) == date(2027, 3, 1)


def test_trusted_external_revision_can_activate_without_code_release() -> None:
    child = _student(grade=8, stage=Stage.MIDDLE)
    records = [
        {
            "stage": "middle",
            "framework": "차기 개정 중학교 교육과정",
            "revision": "future-2028",
            "official_notice": "국가교육위원회고시 제2028-7호",
            "effective_from": "2028-03-01",
            "grades": [8],
            "source_url": "https://ncic.go.kr/curriculum/future",
            "metadata": {},
        },
        {
            "stage": "middle",
            "framework": "2022 개정 중학교 교육과정 최신 정정",
            "revision": "2026-correction",
            "official_notice": "국가교육위원회고시 제2026-9호",
            "effective_from": "2026-09-01",
            "grades": [8],
            "source_url": "https://ncic.go.kr/curriculum/2026-9",
            "metadata": {},
        },
    ]

    resolution = resolve_external_curriculum_version(
        records,
        child,
        on_date=date(2026, 9, 19),
    )

    assert resolution is not None
    assert resolution.revision == "2026-correction"
    assert resolution.source_ref == "국가교육위원회고시 제2026-9호"
    assert resolution.precision == "external_verified_metadata"


def test_untrusted_or_ambiguous_external_revision_is_never_auto_activated() -> None:
    child = _student(grade=8, stage=Stage.MIDDLE)
    records = [
        {
            "stage": "middle",
            "framework": "위조 교육과정",
            "revision": "fake",
            "official_notice": "국가교육위원회고시 제2026-99호",
            "effective_from": "2026-03-01",
            "grades": [8],
            "source_url": "https://example.invalid/fake",
        },
        {
            "stage": "middle",
            "framework": "학년 미지정 개정",
            "revision": "ambiguous",
            "official_notice": "국가교육위원회고시 제2026-8호",
            "effective_from": "2026-03-01",
            "grades": [7],
            "source_url": "https://ncic.go.kr/curriculum/2026-8",
        },
    ]

    assert (
        resolve_external_curriculum_version(
            records,
            child,
            on_date=date(2026, 9, 19),
        )
        is None
    )
