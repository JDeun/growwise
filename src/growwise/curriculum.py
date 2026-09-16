from __future__ import annotations

from growwise.domain import CurriculumTarget, MaterialKind, Stage

_INFANT_FRAMEWORK = "2024 개정 표준보육과정(0~2세)"
_INFANT_SOURCE = "교육부고시 제2024-23호"
_PRESCHOOL_FRAMEWORK = "2019 개정 누리과정"
_PRESCHOOL_SOURCE = "교육부고시 제2019-189호·보건복지부고시 제2019-152호"
_NATIONAL_FRAMEWORK = "2022 개정 초·중등학교 교육과정"
_NATIONAL_SOURCE = "교육부고시 제2022-33호"


def _target(
    *,
    mapping_id: str,
    framework: str,
    domain: str,
    description: str,
    source_ref: str,
) -> CurriculumTarget:
    return CurriculumTarget(
        mapping_id=mapping_id,
        framework=framework,
        domain=domain,
        description=description,
        source_ref=source_ref,
    )


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


def curriculum_targets_for(stage: Stage, kind: MaterialKind) -> list[CurriculumTarget]:
    """Return deterministic, copyright-safe curriculum alignment metadata.

    This function maps only to official framework/area or subject families and GrowWise-authored
    paraphrases. It deliberately does not invent achievement-standard codes. Verified official
    codes can later be attached through ``standard_codes`` by curated data or an adapter.
    """
    if stage in {Stage.INFANT_0_2, Stage.PRESCHOOL_3_5}:
        framework = _INFANT_FRAMEWORK if stage is Stage.INFANT_0_2 else _PRESCHOOL_FRAMEWORK
        source = _INFANT_SOURCE if stage is Stage.INFANT_0_2 else _PRESCHOOL_SOURCE
        namespace = "2024-childcare" if stage is Stage.INFANT_0_2 else "2019-nuri"
        targets: list[CurriculumTarget] = []
        for area_key in _EARLY_KIND_AREAS[kind]:
            domain, description = _EARLY_AREAS[area_key]
            targets.append(
                _target(
                    mapping_id=f"gw:kr:{namespace}:{area_key}",
                    framework=framework,
                    domain=domain,
                    description=description,
                    source_ref=source,
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
            mapping_id=f"gw:kr:2022:{stage_key}:{domain_key}",
            framework=_NATIONAL_FRAMEWORK,
            domain=domain,
            description=description,
            source_ref=_NATIONAL_SOURCE,
        )
    ]
