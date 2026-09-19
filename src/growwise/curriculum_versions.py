from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlsplit

from growwise.domain import ChildProfile, Stage

_NOTICE_RE = re.compile(
    r"^(?:교육부고시|국가교육위원회고시)\s*제\d{4}-\d+호$"
)
_TRUSTED_CURRICULUM_HOSTS = frozenset(
    {
        "moe.go.kr",
        "www.moe.go.kr",
        "ncic.go.kr",
        "www.ncic.go.kr",
        "ne.go.kr",
        "www.ne.go.kr",
        "i-nuri.go.kr",
        "www.i-nuri.go.kr",
    }
)
_SCHOOL_TRANSITION_START: dict[int, date] = {
    1: date(2024, 3, 1),
    2: date(2024, 3, 1),
    3: date(2025, 3, 1),
    4: date(2025, 3, 1),
    5: date(2026, 3, 1),
    6: date(2026, 3, 1),
    7: date(2025, 3, 1),
    8: date(2026, 3, 1),
    9: date(2027, 3, 1),
    10: date(2025, 3, 1),
    11: date(2026, 3, 1),
    12: date(2027, 3, 1),
}


@dataclass(frozen=True)
class CurriculumResolution:
    """Effective curriculum version for one learner and reference date."""

    framework: str
    revision: str
    source_ref: str
    effective_from: date | None
    effective_to: date | None = None
    grade: int | None = None
    precision: str = "stage"
    transition_note: str | None = None


def resolve_curriculum_version(
    child: ChildProfile,
    *,
    on_date: date | None = None,
) -> CurriculumResolution:
    reference = on_date or date.today()
    stage = child.stage_on(reference)
    grade = child.grade_on(reference)

    if stage is Stage.INFANT_0_2:
        return CurriculumResolution(
            framework="2024 개정 표준보육과정(0~2세)",
            revision="2024-childcare",
            source_ref="교육부고시 제2024-23호",
            effective_from=date(2025, 3, 1),
            precision="age_band",
        )

    if stage is Stage.PRESCHOOL_3_5:
        return CurriculumResolution(
            framework="2019 개정 누리과정",
            revision="2019-nuri",
            source_ref="교육부고시 제2019-189호·보건복지부고시 제2019-152호",
            effective_from=date(2020, 3, 1),
            precision="age_band",
        )

    if grade is not None:
        return _school_resolution_for_grade(grade, reference)

    return _school_resolution_for_stage(stage, reference)


def resolve_external_curriculum_version(
    records: Sequence[Mapping[str, Any]],
    child: ChildProfile,
    *,
    on_date: date | None = None,
) -> CurriculumResolution | None:
    """Resolve a newer structured record only when its activation metadata is trustworthy.

    External curriculum endpoints can update without a GrowWise release, but automatic activation is
    deliberately strict: the record must point at an official Korean curriculum host, carry an
    official notice identifier, declare a framework/revision and effective date, and match the
    learner's current stage and grade. Ambiguous or future-dated records are ignored.
    """

    reference = on_date or date.today()
    stage = child.stage_on(reference)
    grade = child.grade_on(reference)
    candidates: list[tuple[date, CurriculumResolution]] = []

    for record in records:
        if str(record.get("stage", "")).strip() != stage.value:
            continue

        metadata_raw = record.get("metadata", {})
        metadata = metadata_raw if isinstance(metadata_raw, Mapping) else {}
        source_url = _text(record.get("source_url") or metadata.get("source_url"))
        if not _trusted_source_url(source_url):
            continue

        framework = _text(record.get("framework") or metadata.get("framework"))
        revision = _text(record.get("revision") or metadata.get("revision"))
        notice = _normalize_notice(
            _text(record.get("official_notice") or metadata.get("official_notice"))
        )
        effective_from = _date_value(
            record.get("effective_from") or metadata.get("effective_from")
        )
        effective_to = _date_value(
            record.get("effective_to") or metadata.get("effective_to")
        )
        grades = _grade_values(record.get("grades") or metadata.get("grades"))

        if not framework or not revision or not notice or effective_from is None:
            continue
        if effective_from > reference:
            continue
        if effective_to is not None and reference > effective_to:
            continue
        if grade is not None and grades and grade not in grades:
            continue
        if grade is None and grades:
            # Grade-scoped updates cannot safely activate when the profile only tells us a stage.
            continue

        candidates.append(
            (
                effective_from,
                CurriculumResolution(
                    framework=framework,
                    revision=revision,
                    source_ref=notice,
                    effective_from=effective_from,
                    effective_to=effective_to,
                    grade=grade,
                    precision="external_verified_metadata",
                    transition_note=(
                        "공식 도메인 출처와 적용일·학년 메타데이터가 확인된 "
                        "외부 교육과정 레코드를 적용했습니다."
                    ),
                ),
            )
        )

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].revision), reverse=True)
    return candidates[0][1]


def school_transition_start(grade: int) -> date:
    try:
        return _SCHOOL_TRANSITION_START[grade]
    except KeyError as exc:
        raise ValueError("grade must be 1..12") from exc


def _school_resolution_for_grade(grade: int, reference: date) -> CurriculumResolution:
    transition = school_transition_start(grade)
    if reference >= transition:
        if reference >= date(2025, 3, 1):
            return CurriculumResolution(
                framework="2022 개정 초·중등학교 교육과정(2024 일부개정)",
                revision="2022-rev-2024-3",
                source_ref="국가교육위원회고시 제2024-3호",
                effective_from=max(transition, date(2025, 3, 1)),
                grade=grade,
                precision="grade",
            )
        return CurriculumResolution(
            framework="2022 개정 초·중등학교 교육과정",
            revision="2022",
            source_ref="교육부고시 제2022-33호",
            effective_from=transition,
            grade=grade,
            precision="grade",
        )

    source_ref = (
        "국가교육위원회고시 제2024-1호"
        if reference >= date(2025, 3, 1)
        else "교육부고시 제2022-2호"
    )
    framework = (
        "2015 개정 초·중등학교 교육과정(2024 일부개정)"
        if reference >= date(2025, 3, 1)
        else "2015 개정 초·중등학교 교육과정"
    )
    return CurriculumResolution(
        framework=framework,
        revision="2015-rev-2024-1" if reference >= date(2025, 3, 1) else "2015",
        source_ref=source_ref,
        effective_from=date(2025, 3, 1) if reference >= date(2025, 3, 1) else None,
        effective_to=transition - timedelta(days=1),
        grade=grade,
        precision="grade",
        transition_note=(
            f"{grade}학년은 {transition.isoformat()}부터 2022 개정 교육과정으로 전환됩니다."
        ),
    )


def _school_resolution_for_stage(stage: Stage, reference: date) -> CurriculumResolution:
    grades = {
        Stage.ELEMENTARY: range(1, 7),
        Stage.MIDDLE: range(7, 10),
        Stage.HIGH: range(10, 13),
    }[stage]
    families = {
        "2022" if reference >= school_transition_start(grade) else "2015"
        for grade in grades
    }
    if len(families) == 1:
        family = next(iter(families))
        representative = min(grades) if family == "2022" else max(grades)
        resolved = _school_resolution_for_grade(representative, reference)
        return CurriculumResolution(
            framework=resolved.framework,
            revision=resolved.revision,
            source_ref=resolved.source_ref,
            effective_from=resolved.effective_from,
            effective_to=resolved.effective_to,
            precision="stage_common",
            transition_note=(
                "학년 정보는 없지만 이 학교급의 모든 학년에 같은 교육과정 계열이 "
                "적용되는 시점입니다."
            ),
        )

    return CurriculumResolution(
        framework="2015·2022 개정 초·중등학교 교육과정 전환기",
        revision="transition-unresolved",
        source_ref="국가교육위원회고시 제2024-1호·제2024-3호",
        effective_from=None,
        precision="stage_transition",
        transition_note=(
            "현재 학교급은 학년별 교육과정 전환기입니다. 정확한 교육과정 적용을 위해 "
            "생년월일 또는 학년 정보를 입력해야 합니다."
        ),
    )


def _trusted_source_url(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme.casefold() == "https" and (parsed.hostname or "").casefold() in (
        _TRUSTED_CURRICULUM_HOSTS
    )


def _normalize_notice(value: str) -> str:
    normalized = " ".join(value.split()).replace("제 ", "제")
    if not _NOTICE_RE.fullmatch(normalized):
        return ""
    return normalized


def _date_value(value: object) -> date | None:
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _grade_values(value: object) -> set[int]:
    if isinstance(value, int):
        return {value} if 1 <= value <= 12 else set()
    if isinstance(value, str):
        raw_values = re.split(r"[,;/\s]+", value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        raw_values = list(value)
    else:
        return set()

    grades: set[int] = set()
    for raw in raw_values:
        try:
            grade = int(raw)
        except (TypeError, ValueError):
            continue
        if 1 <= grade <= 12:
            grades.add(grade)
    return grades


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""
