from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

from growwise.domain import ExperienceAxis
from growwise.storage import SQLiteProjection


class CoverageState(StrEnum):
    NOT_OBSERVED = "not_observed"
    RECENTLY_OBSERVED = "recently_observed"
    REPEATED_EXPERIENCE = "repeated_experience"
    FREQUENT_EXPERIENCE = "frequent_experience"


class AxisCoverage(BaseModel):
    axis: ExperienceAxis
    state: CoverageState
    observation_count: int = 0
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None


class GrowthMapProjection(BaseModel):
    child_id: str
    period_days: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_logs_in_period: int
    tagged_logs_in_period: int
    axes: list[AxisCoverage]


class GrowthMapService:
    """Deterministic experience-coverage projection; never an ability or percentile score."""

    def __init__(self, index: SQLiteProjection) -> None:
        self.index = index

    def project(
        self,
        *,
        child_id: str,
        period_days: int = 30,
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
        return GrowthMapProjection(
            child_id=child_id,
            period_days=period_days,
            total_logs_in_period=len(in_period),
            tagged_logs_in_period=tagged_logs,
            axes=axis_results,
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
