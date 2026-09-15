from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, Field

from growwise.domain.models import ResourceRecord
from growwise.domain.study import MistakeRecord, StudyProgressState, StudyReflection
from growwise.storage.sqlite import SQLiteProjection


class WeakMapEntry(BaseModel):
    subject: str
    unit: str
    evidence_count: int = Field(ge=1)
    recurring_mistake_types: list[str] = Field(default_factory=list)
    recent_difficulties: list[str] = Field(default_factory=list)
    progress_state: StudyProgressState | None = None
    parent_support_points: list[str] = Field(default_factory=list)


class WeakMap(BaseModel):
    child_id: str
    entries: list[WeakMapEntry] = Field(default_factory=list)
    peer_comparison_used: bool = False
    interpretation: str = (
        "반복해서 기록된 어려움과 복습 신호를 정리한 자기비교 지도입니다. "
        "점수·등수·또래 비교를 사용하지 않습니다."
    )


class StudyResourceRecommendation(BaseModel):
    resource_id: str
    title: str
    reason: str
    source_ref: str


class StudyTrackingService:
    """Deterministic middle/high-school tracking over the local projection."""

    def __init__(self, index: SQLiteProjection) -> None:
        self.index = index

    def weak_map(self, *, child_id: str, limit: int = 12) -> WeakMap:
        mistakes = [
            MistakeRecord.model_validate(item)
            for item in self.index.list_entities(
                entity_type="mistake_record",
                child_id=child_id,
            )
        ]
        reflections = [
            StudyReflection.model_validate(item)
            for item in self.index.list_entities(
                entity_type="study_reflection",
                child_id=child_id,
            )
        ]
        progress = self.index.list_entities(
            entity_type="study_unit_progress",
            child_id=child_id,
        )

        mistake_groups: dict[tuple[str, str], list[MistakeRecord]] = defaultdict(list)
        for item in mistakes:
            mistake_groups[(item.subject, item.unit)].append(item)
        reflection_groups: dict[tuple[str, str], list[StudyReflection]] = defaultdict(list)
        for item in reflections:
            reflection_groups[(item.subject, item.unit)].append(item)
        progress_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for item in progress:
            key = (str(item.get("subject", "")), str(item.get("unit", "")))
            progress_by_key.setdefault(key, item)

        keys = set(mistake_groups) | set(reflection_groups) | set(progress_by_key)
        entries: list[WeakMapEntry] = []
        for subject, unit in keys:
            grouped_mistakes = mistake_groups.get((subject, unit), [])
            grouped_reflections = reflection_groups.get((subject, unit), [])
            progress_payload = progress_by_key.get((subject, unit))
            state = (
                StudyProgressState(str(progress_payload["state"]))
                if progress_payload is not None and progress_payload.get("state")
                else None
            )
            difficulties = [
                item.difficult_point.strip()
                for item in grouped_reflections
                if item.difficult_point and item.difficult_point.strip()
            ][:3]
            type_counts = Counter(item.mistake_type.value for item in grouped_mistakes)
            recurring_types = [
                name
                for name, count in sorted(
                    type_counts.items(),
                    key=lambda pair: (-pair[1], pair[0]),
                )
                if count >= 2
            ]
            evidence_count = len(grouped_mistakes) + len(difficulties)
            if state in {StudyProgressState.REVIEW, StudyProgressState.REVISIT}:
                evidence_count += 1
            if evidence_count == 0:
                continue
            entries.append(
                WeakMapEntry(
                    subject=subject,
                    unit=unit,
                    evidence_count=evidence_count,
                    recurring_mistake_types=recurring_types,
                    recent_difficulties=difficulties,
                    progress_state=state,
                    parent_support_points=self._support_points(
                        mistake_count=len(grouped_mistakes),
                        recurring_types=recurring_types,
                        difficulties=difficulties,
                        state=state,
                    ),
                )
            )

        entries.sort(
            key=lambda item: (-item.evidence_count, item.subject.casefold(), item.unit.casefold())
        )
        return WeakMap(child_id=child_id, entries=entries[:limit])

    def recommend_resources(
        self,
        *,
        child_id: str,
        subject: str,
        unit: str,
        limit: int = 5,
    ) -> list[StudyResourceRecommendation]:
        terms = {term.casefold() for term in f"{subject} {unit}".split() if term.strip()}
        candidates: list[tuple[int, ResourceRecord]] = []
        for payload in self.index.list_entities(entity_type="resource"):
            resource = ResourceRecord.model_validate(payload)
            if resource.child_id is not None and str(resource.child_id) != child_id:
                continue
            searchable = " ".join(
                [
                    resource.title,
                    resource.summary or "",
                    resource.content or "",
                    *resource.tags,
                ]
            ).casefold()
            hits = sum(1 for term in terms if term in searchable)
            if hits:
                candidates.append((hits, resource))
        candidates.sort(key=lambda pair: (-pair[0], pair[1].title.casefold()))
        return [
            StudyResourceRecommendation(
                resource_id=str(resource.id),
                title=resource.title,
                reason=f"{subject} · {unit}와 연결되는 로컬 자료입니다.",
                source_ref=f"resource:{resource.id}",
            )
            for _, resource in candidates[:limit]
        ]

    @staticmethod
    def _support_points(
        *,
        mistake_count: int,
        recurring_types: list[str],
        difficulties: list[str],
        state: StudyProgressState | None,
    ) -> list[str]:
        points: list[str] = []
        if recurring_types:
            points.append(
                "같은 유형이 반복됩니다. 정답을 바로 알려주기보다 풀이 과정의 어느 단계에서 "
                "흐름이 끊기는지 함께 확인합니다."
            )
        elif mistake_count:
            points.append(
                "한 번의 실수를 약점으로 확정하지 말고 다음 학습에서 같은 개념을 다시 확인합니다."
            )
        if difficulties:
            points.append(
                "아이의 회고에 적힌 어려움을 다음 학습 시작점으로 사용하고, 해결 방법을 먼저 "
                "스스로 설명하게 합니다."
            )
        if state in {StudyProgressState.REVIEW, StudyProgressState.REVISIT}:
            points.append(
                "복습 신호가 있습니다. 짧은 예시 하나로 이해를 확인한 뒤 필요한 부분만 다시 봅니다."
            )
        return points[:3]
