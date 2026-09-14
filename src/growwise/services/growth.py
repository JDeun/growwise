from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

from growwise.domain import ExperienceAxis, Stage
from growwise.storage import SQLiteProjection

WHOLE_PERSON_AXES: tuple[ExperienceAxis, ...] = (
    ExperienceAxis.PHYSICAL,
    ExperienceAxis.EMOTIONAL_CHARACTER,
    ExperienceAxis.EXPRESSION_ART,
    ExperienceAxis.THINKING_INQUIRY,
    ExperienceAxis.SOCIAL,
)
LEARNING_AXES: tuple[ExperienceAxis, ...] = (
    ExperienceAxis.READING,
    ExperienceAxis.SPEAKING,
    ExperienceAxis.WRITING,
    ExperienceAxis.MATH,
    ExperienceAxis.EXPLORATION,
    ExperienceAxis.SOCIAL,
)
STAGE_FOCUS_AXES: dict[Stage, tuple[ExperienceAxis, ...]] = {
    Stage.INFANT_0_2: (
        ExperienceAxis.PHYSICAL,
        ExperienceAxis.EMOTIONAL_CHARACTER,
        ExperienceAxis.EXPRESSION_ART,
        ExperienceAxis.SOCIAL,
        ExperienceAxis.SPEAKING,
        ExperienceAxis.EXPLORATION,
    ),
    Stage.PRESCHOOL_3_5: (
        ExperienceAxis.PHYSICAL,
        ExperienceAxis.EMOTIONAL_CHARACTER,
        ExperienceAxis.EXPRESSION_ART,
        ExperienceAxis.THINKING_INQUIRY,
        ExperienceAxis.SOCIAL,
        ExperienceAxis.SPEAKING,
    ),
    Stage.ELEMENTARY: LEARNING_AXES,
    Stage.MIDDLE: LEARNING_AXES,
    Stage.HIGH: LEARNING_AXES,
}


class CoverageState(StrEnum):
    NOT_OBSERVED = "not_observed"
    RECENTLY_OBSERVED = "recently_observed"
    REPEATED_EXPERIENCE = "repeated_experience"
    FREQUENT_EXPERIENCE = "frequent_experience"


class DiversityState(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    VARIED = "varied"
    MIXED = "mixed"
    CONCENTRATED = "concentrated"


class AxisCoverage(BaseModel):
    axis: ExperienceAxis
    state: CoverageState
    observation_count: int = 0
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None


class GrowthLayer(BaseModel):
    key: str
    label: str
    axes: list[AxisCoverage]


class CoverageDiversity(BaseModel):
    state: DiversityState
    observed_axis_count: int = 0
    focus_axes: list[ExperienceAxis] = Field(default_factory=list)
    note: str


class GrowthMapProjection(BaseModel):
    child_id: str
    period_days: int
    stage: Stage | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_logs_in_period: int
    tagged_logs_in_period: int
    axes: list[AxisCoverage]
    layers: list[GrowthLayer] = Field(default_factory=list)
    diversity: CoverageDiversity


class GrowthMapService:
    """Deterministic experience-coverage projection; never an ability or percentile score."""

    def __init__(self, index: SQLiteProjection) -> None:
        self.index = index

    def project(
        self,
        *,
        child_id: str,
        period_days: int = 30,
        stage: Stage | None = None,
        now: datetime | None = None,
    ) -> GrowthMapProjection:
        reference = now or datetime.now(UTC)
        cutoff = reference - timedelta(days=period_days)
        logs = self.index.list_entities(entity_type="learning_log", child_id=child_id)

        in_period: list[dict] = []
        for log in logs:
            created_at = self._parse_datetime(log.get("created_at"))
            if created_at is not None and created_at >= cutoff:
                in_period.append(log)

        counts: Counter[ExperienceAxis] = Counter()
        moments: dict[ExperienceAxis, list[datetime]] = {
            axis: [] for axis in ExperienceAxis
        }
        tagged_logs = 0

        for log in in_period:
            axes = self._parse_axes(log.get("experience_axes", []))
            if axes:
                tagged_logs += 1
            created_at = self._parse_datetime(log.get("created_at"))
            for axis in set(axes):
                counts[axis] += 1
                if created_at is not None:
                    moments[axis].append(created_at)

        axis_results = [
            AxisCoverage(
                axis=axis,
                state=self._state_for_count(counts[axis]),
                observation_count=counts[axis],
                first_observed_at=min(moments[axis]) if moments[axis] else None,
                last_observed_at=max(moments[axis]) if moments[axis] else None,
            )
            for axis in ExperienceAxis
        ]
        by_axis = {item.axis: item for item in axis_results}
        stage_axes = STAGE_FOCUS_AXES[stage] if stage is not None else tuple(ExperienceAxis)
        layers = [
            self._layer("whole_person", "전인 경험", WHOLE_PERSON_AXES, by_axis),
            self._layer("learning", "학습 경험", LEARNING_AXES, by_axis),
            self._layer("stage_focus", self._stage_label(stage), stage_axes, by_axis),
        ]
        return GrowthMapProjection(
            child_id=child_id,
            period_days=period_days,
            stage=stage,
            total_logs_in_period=len(in_period),
            tagged_logs_in_period=tagged_logs,
            axes=axis_results,
            layers=layers,
            diversity=self._diversity_for(in_period, stage_axes),
        )

    @staticmethod
    def _layer(
        key: str,
        label: str,
        axes: tuple[ExperienceAxis, ...],
        by_axis: dict[ExperienceAxis, AxisCoverage],
    ) -> GrowthLayer:
        return GrowthLayer(key=key, label=label, axes=[by_axis[axis] for axis in axes])

    @staticmethod
    def _stage_label(stage: Stage | None) -> str:
        return {
            Stage.INFANT_0_2: "영아기 경험 렌즈",
            Stage.PRESCHOOL_3_5: "유아기 경험 렌즈",
            Stage.ELEMENTARY: "초등 학습 렌즈",
            Stage.MIDDLE: "중등 학습 렌즈",
            Stage.HIGH: "고등 학습 렌즈",
            None: "현재 단계 경험 렌즈",
        }[stage]

    @classmethod
    def _diversity_for(
        cls,
        logs: list[dict],
        focus_axes: tuple[ExperienceAxis, ...],
    ) -> CoverageDiversity:
        focus_set = set(focus_axes)
        per_log: list[set[ExperienceAxis]] = []
        for log in logs:
            axes = set(cls._parse_axes(log.get("experience_axes", []))) & focus_set
            if axes:
                per_log.append(axes)

        counts: Counter[ExperienceAxis] = Counter(
            axis for axes in per_log for axis in axes
        )
        observed = len(counts)
        if len(per_log) < 5:
            return CoverageDiversity(
                state=DiversityState.INSUFFICIENT_DATA,
                observed_axis_count=observed,
                note=(
                    "기록이 더 쌓인 뒤 경험의 분포를 설명합니다. "
                    "기록 부족을 발달이나 능력의 부족으로 해석하지 않습니다."
                ),
            )

        top_axis, top_count = counts.most_common(1)[0]
        concentration = top_count / len(per_log)
        if top_count >= 4 and concentration >= (2 / 3):
            return CoverageDiversity(
                state=DiversityState.CONCENTRATED,
                observed_axis_count=observed,
                focus_axes=[top_axis],
                note=(
                    "최근 기록이 일부 경험 축에 상대적으로 많이 모여 있습니다. "
                    "선호나 생활 맥락일 수 있으며 능력 평가가 아닙니다."
                ),
            )
        if observed >= min(4, len(focus_axes)):
            return CoverageDiversity(
                state=DiversityState.VARIED,
                observed_axis_count=observed,
                note="최근 기록이 여러 경험 축에 걸쳐 나타납니다.",
            )
        return CoverageDiversity(
            state=DiversityState.MIXED,
            observed_axis_count=observed,
            note="최근 기록은 여러 축에 나타나며 일부 축의 반복도 보입니다.",
        )

    @staticmethod
    def _state_for_count(count: int) -> CoverageState:
        if count == 0:
            return CoverageState.NOT_OBSERVED
        if count <= 2:
            return CoverageState.RECENTLY_OBSERVED
        if count <= 5:
            return CoverageState.REPEATED_EXPERIENCE
        return CoverageState.FREQUENT_EXPERIENCE

    @staticmethod
    def _parse_axes(values: object) -> list[ExperienceAxis]:
        if not isinstance(values, list):
            return []
        result: list[ExperienceAxis] = []
        for value in values:
            try:
                result.append(ExperienceAxis(str(value)))
            except ValueError:
                continue
        return result

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
