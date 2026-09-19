from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from growwise.curriculum_versions import (
    CurriculumResolution,
    effective_curriculum_stage,
    resolve_curriculum_version,
    resolve_external_curriculum_version,
)
from growwise.domain import ChildProfile, CurriculumTarget, MaterialKind, Stage

_EARLY_AREAS: dict[str, tuple[str, str]] = {
    "physical_health": (
        "신체운동·건강",
        "몸과 감각을 활용하고 건강하고 안전한 생활 경험과 연결합니다.",
    ),
    "communication": (
        "의사소통",
        "말·몸짓·그림·책을 통해 의미를 주고받는 경험과 연결합니다.",
    ),
    "social_relationship": (
        "사회관계",
        "자기와 다른 사람을 존중하고 함께 생활하는 경험과 연결합니다.",
    ),
    "art_experience": (
        "예술경험",
        "소리·움직임·그림·이야기를 즐기고 표현하는 경험과 연결합니다.",
    ),
    "nature_inquiry": (
        "자연탐구",
        "주변 세계에 호기심을 갖고 관찰·비교·탐색하는 경험과 연결합니다.",
    ),
}

_EARLY_KIND_AREAS: dict[MaterialKind, tuple[str, ...]] = {
    MaterialKind.ACTIVITY_GUIDE: ("physical_health", "nature_inquiry"),
    MaterialKind.READING_ACTIVITY: ("communication", "art_experience"),
    MaterialKind.ENGLISH_CARD: ("communication", "social_relationship"),
    MaterialKind.MATH_ACTIVITY: ("nature_inquiry",),
    MaterialKind.SCIENCE_INQUIRY: ("nature_inquiry",),
    MaterialKind.WRITING_PROMPT: ("communication", "art_experience"),
    MaterialKind.FIELD_TRIP: ("nature_inquiry", "social_relationship"),
}

_SCHOOL_KIND_DOMAINS: dict[MaterialKind, tuple[str, str, str]] = {
    MaterialKind.ACTIVITY_GUIDE: (
        "통합·창의적 체험",
        "생활 맥락의 탐색과 협력 활동을 통해 스스로 계획하고 돌아보는 경험과 연결합니다.",
        "integrated-activity",
    ),
    MaterialKind.READING_ACTIVITY: (
        "국어",
        "읽기 전·중·후에 내용을 이해하고 근거를 들어 생각을 표현하는 학습과 연결합니다.",
        "korean-reading",
    ),
    MaterialKind.ENGLISH_CARD: (
        "영어",
        "실생활 맥락에서 듣고 말하며 짧은 표현으로 의미를 주고받는 학습과 연결합니다.",
        "english-communication",
    ),
    MaterialKind.MATH_ACTIVITY: (
        "수학",
        "생활 속 수학적 상황을 조작·비교하고 자신의 해결 방법을 설명하는 학습과 연결합니다.",
        "math-problem-solving",
    ),
    MaterialKind.SCIENCE_INQUIRY: (
        "과학",
        "질문을 만들고 예측·관찰·탐구한 뒤 증거를 바탕으로 설명하는 학습과 연결합니다.",
        "science-inquiry",
    ),
    MaterialKind.WRITING_PROMPT: (
        "국어",
        "생각과 경험을 말·그림·글로 조직하여 표현하고 고쳐 쓰는 학습과 연결합니다.",
        "korean-expression",
    ),
    MaterialKind.FIELD_TRIP: (
        "사회·통합",
        "장소와 공동체를 직접 관찰하고 자료를 모아 경험을 해석하는 학습과 연결합니다.",
        "social-place-inquiry",
    ),
}


def curriculum_targets_for(
    stage: Stage,
    kind: MaterialKind,
    *,
    on_date: date | None = None,
) -> list[CurriculumTarget]:
    """Return conservative stage-only curriculum metadata.

    School stages can span two curriculum families during a phased rollout. Call
    curriculum_targets_for_child when learner grade or birth-date information is available.
    """
    placeholder = ChildProfile(name="curriculum-resolution", stage=stage, age_months=None)
    return curriculum_targets_for_child(placeholder, kind, on_date=on_date)


def curriculum_targets_for_child(
    child: ChildProfile,
    kind: MaterialKind,
    *,
    on_date: date | None = None,
    external_records: Sequence[Mapping[str, Any]] | None = None,
) -> list[CurriculumTarget]:
    """Resolve the effective curriculum for a learner, date and material family."""
    reference = on_date or date.today()
    stage = effective_curriculum_stage(child, on_date=reference)
    resolution = None
    if external_records:
        resolution = resolve_external_curriculum_version(
            external_records,
            child,
            on_date=reference,
        )
    if resolution is None:
        resolution = resolve_curriculum_version(child, on_date=reference)
    return _targets_for_resolution(stage=stage, kind=kind, resolution=resolution)


def _targets_for_resolution(
    *,
    stage: Stage,
    kind: MaterialKind,
    resolution: CurriculumResolution,
) -> list[CurriculumTarget]:
    namespace = _mapping_namespace(resolution.revision)

    if stage in {Stage.INFANT_0_2, Stage.PRESCHOOL_3_5}:
        targets: list[CurriculumTarget] = []
        for area_key in _EARLY_KIND_AREAS[kind]:
            domain, description = _EARLY_AREAS[area_key]
            targets.append(
                _target(
                    mapping_id=f"gw:kr:{namespace}:{area_key}",
                    framework=resolution.framework,
                    domain=domain,
                    description=description,
                    source_ref=resolution.source_ref,
                    resolution=resolution,
                )
            )
        return targets

    domain, description, domain_key = _SCHOOL_KIND_DOMAINS[kind]
    stage_key = {
        Stage.ELEMENTARY: "elementary",
        Stage.MIDDLE: "middle",
        Stage.HIGH: "high",
    }[stage]
    return [
        _target(
            mapping_id=f"gw:kr:{namespace}:{stage_key}:{domain_key}",
            framework=resolution.framework,
            domain=domain,
            description=description,
            source_ref=resolution.source_ref,
            resolution=resolution,
        )
    ]


def _target(
    *,
    mapping_id: str,
    framework: str,
    domain: str,
    description: str,
    source_ref: str,
    resolution: CurriculumResolution,
) -> CurriculumTarget:
    return CurriculumTarget(
        mapping_id=mapping_id,
        framework=framework,
        domain=domain,
        description=description,
        source_ref=source_ref,
        revision=resolution.revision,
        effective_from=resolution.effective_from,
        effective_to=resolution.effective_to,
        grade=resolution.grade,
        resolution_precision=resolution.precision,
        transition_note=resolution.transition_note,
    )


def _mapping_namespace(revision: str) -> str:
    normalized = "".join(
        char.lower() if char.isalnum() else "-"
        for char in revision
    )
    return "-".join(part for part in normalized.split("-") if part)[:50] or "unknown"
