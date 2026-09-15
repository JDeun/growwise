"""Property-style round-trip coverage for the Markdown source-of-truth invariant.

The storage contract is "Markdown = Source of Truth, SQLite = rebuildable projection". These
tests exercise that contract over a wide, diverse set of generated entities. ``hypothesis`` is not
a project dependency, so instead of adding one we enumerate a large, deliberately varied case set
(unicode, long-but-valid text, edge ages 0/240/None, empty vs multiple interests, several entity
types) and assert the same invariants a property test would:

* an entity saved through :class:`EntityStore` reloads from Markdown byte-for-field identical;
* the SQLite projection payload matches the entity's canonical JSON dump;
* deleting the SQLite index and rebuilding it purely from Markdown reproduces every entity.

All generated free text is neutral, non-PII placeholder content.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from growwise.domain import (
    ActivityPlan,
    ActivityStatus,
    ChildProfile,
    ExperienceAxis,
    GeneratedMaterial,
    LearningLog,
    MaterialKind,
    ResourceKind,
    ResourceRecord,
    Stage,
    WorkflowRun,
    WorkflowStatus,
)
from growwise.domain.models import EntityBase
from growwise.storage import EntityStore, SQLiteProjection

# Neutral, non-PII placeholder nicknames (unicode + ascii + a long-but-valid value).
_NICKNAMES: list[str] = ["아이", "sample", "테스트아이", "child-01", "닉네임" * 20]
_AGES: list[int | None] = [0, 12, 240, None]
_INTERESTS: list[list[str]] = [
    [],
    ["math"],
    ["독서", "놀이", "그림"],
    ["a-very-long-interest-label-still-within-reason " * 3],
]
_NOTES: list[str | None] = [None, "관찰 메모 — 유니코드 포함 ✏️"]


def _build_child_profiles() -> list[ChildProfile]:
    """Cartesian product of the varied fields → a broad ChildProfile population."""
    profiles: list[ChildProfile] = []
    combos = itertools.product(Stage, _AGES, _INTERESTS, _NICKNAMES, _NOTES)
    for stage, age_months, interests, nickname, notes in combos:
        profiles.append(
            ChildProfile(
                nickname=nickname,
                stage=stage,
                age_months=age_months,
                interests=list(interests),
                notes=notes,
            )
        )
    return profiles


def _build_mixed_entities() -> list[EntityBase]:
    """A hand-built spread across the other entity types to widen round-trip coverage."""
    child_id = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY, age_months=84).id
    return [
        LearningLog(
            child_id=child_id,
            parent_observation="책 표지를 오래 바라봄 — 관심 신호 ✨",
            process="함께 페이지를 넘김",
            tags=["관찰", "reading"],
            experience_axes=[ExperienceAxis.READING, ExperienceAxis.THINKING_INQUIRY],
        ),
        LearningLog(child_id=child_id, parent_observation=""),
        ActivityPlan(
            child_id=child_id,
            title="숲 산책 탐험",
            description=None,
            status=ActivityStatus.ACTIVE,
            source_refs=["ref-1", "ref-2"],
            experience_axes=[ExperienceAxis.PHYSICAL, ExperienceAxis.EXPLORATION],
        ),
        GeneratedMaterial(
            child_id=child_id,
            kind=MaterialKind.READING_ACTIVITY,
            title="가을 잎 관찰 카드",
            content_markdown="# 제목\n\n본문 내용 — 여러 줄\n- 항목1\n- 항목2\n",
            source_refs=["book:leaf-guide"],
            version=3,
        ),
        ResourceRecord(
            child_id=child_id,
            kind=ResourceKind.BOOK,
            title="아기 그림책",
            summary="짧은 요약",
            tags=["board-book"],
            stage_tags=[Stage.INFANT_0_2, Stage.PRESCHOOL_3_5],
            provenance={"source": "library", "shelf": "A-3"},
        ),
        ResourceRecord(kind=ResourceKind.NOTE, title="child_id 없는 리소스"),
        WorkflowRun(
            child_id=child_id,
            workflow_type="material_generation",
            thread_id="thread-xyz",
            status=WorkflowStatus.WAITING_REVIEW,
            attempt_count=2,
        ),
    ]


_CHILD_PROFILES = _build_child_profiles()
_MIXED = _build_mixed_entities()
_ALL_ENTITIES: list[EntityBase] = [*_CHILD_PROFILES, *_MIXED]


def _case_id(entity: EntityBase) -> str:
    return f"{entity.entity_type}-{entity.id}"


@pytest.mark.parametrize("entity", _ALL_ENTITIES, ids=_case_id)
def test_markdown_roundtrip_is_lossless(entity: EntityBase, tmp_path: Path) -> None:
    """Saving then reloading from Markdown yields an identical entity, and the index agrees."""
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    path = store.save(entity)

    reloaded = store.markdown.load(path, type(entity))
    assert reloaded == entity
    assert reloaded.model_dump(mode="json") == entity.model_dump(mode="json")

    indexed = store.index.get_entity(str(entity.id), entity_type=entity.entity_type)
    assert indexed == entity.model_dump(mode="json")


def test_projection_rebuild_matches_markdown_for_full_population(tmp_path: Path) -> None:
    """Delete the SQLite index, rebuild purely from Markdown, and match every entity."""
    records = tmp_path / "records"
    db = tmp_path / "index.sqlite3"
    store = EntityStore(records, db)

    for entity in _ALL_ENTITIES:
        store.save(entity)

    # SQLite is a disposable projection: drop it and rebuild from the Markdown SoT alone.
    db.unlink()
    projection = SQLiteProjection(db)
    indexed = projection.rebuild(records)
    assert indexed == len(_ALL_ENTITIES)

    for entity in _ALL_ENTITIES:
        rebuilt = projection.get_entity(str(entity.id), entity_type=entity.entity_type)
        assert rebuilt == entity.model_dump(mode="json")


def test_case_population_is_wide() -> None:
    """Guard that the generated population stays broad (dozens of cases)."""
    assert len(_CHILD_PROFILES) >= 100
    assert len(_ALL_ENTITIES) >= 100
    # Every stage and every edge age is represented.
    assert {p.stage for p in _CHILD_PROFILES} == set(Stage)
    assert {p.age_months for p in _CHILD_PROFILES} == {0, 12, 240, None}
