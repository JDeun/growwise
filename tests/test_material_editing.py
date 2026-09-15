from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException
from langgraph.types import Command

import growwise.api.main as api
from growwise.api.main import MaterialEditRequest, MaterialReviewRequest
from growwise.domain import (
    ChildProfile,
    GeneratedMaterial,
    MaterialKind,
    MaterialStatus,
    Stage,
)
from growwise.storage import EntityStore


class RecordingReviewGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def invoke(self, value: Any, config: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((value, config))
        if isinstance(value, dict):
            return {**value, "__interrupt__": ("review",)}
        assert isinstance(value, Command)
        resume = value.resume
        return {
            "decision_status": resume["status"],
            "decision_note": resume.get("note"),
        }


def test_parent_edit_creates_reviewable_immutable_version(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="학생", stage=Stage.ELEMENTARY, age_months=120)
    store.save(child)
    parent = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.READING_ACTIVITY,
        title="원본 독서 활동",
        content_markdown="# 원본\n질문 하나를 고릅니다.",
        status=MaterialStatus.APPROVED,
        source_refs=["resource:00000000-0000-0000-0000-000000000001"],
        generator_mode="template",
        request_topic="고양이 그림책",
        request_goal="장면을 관찰한다.",
    )
    store.save(parent)
    graph = RecordingReviewGraph()
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)

    edited = api.edit_material(
        parent.id,
        MaterialEditRequest(
            title="부모가 다듬은 독서 활동",
            content_markdown="# 편집본\n아이의 선택을 기다립니다.",
            note="질문 수를 줄이고 표현을 다듬음",
        ),
        store,
    )

    assert edited.status is MaterialStatus.REVIEW_PENDING
    assert edited.version == 2
    assert edited.parent_material_id == parent.id
    assert edited.generator_mode == "parent_edit"
    assert edited.source_refs == parent.source_refs
    assert edited.version_note == "질문 수를 줄이고 표현을 다듬음"
    assert graph.calls[-1][1]["configurable"]["thread_id"] == f"material-review:{edited.id}"

    persisted_parent = api.get_material(parent.id, store)
    assert persisted_parent.status is MaterialStatus.APPROVED
    assert persisted_parent.content_markdown == parent.content_markdown

    with pytest.raises(HTTPException) as exc_info:
        api.edit_material(
            parent.id,
            MaterialEditRequest(
                title="분기 시도",
                content_markdown="이미 자식 버전이 있는 과거 버전을 다시 편집",
            ),
            store,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "material_has_newer_version"

    approved = api.review_material(
        edited.id,
        MaterialReviewRequest(status=MaterialStatus.APPROVED, note="최종 확인"),
        store,
    )
    assert approved.status is MaterialStatus.APPROVED


def test_archived_material_cannot_be_parent_edited(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="학생", stage=Stage.HIGH, age_months=210)
    store.save(child)
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.WRITING_PROMPT,
        title="보관된 자료",
        content_markdown="# 보관본",
        status=MaterialStatus.ARCHIVED,
    )
    store.save(material)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: RecordingReviewGraph())

    with pytest.raises(HTTPException) as exc_info:
        api.edit_material(
            material.id,
            MaterialEditRequest(title="새 제목", content_markdown="# 새 내용"),
            store,
        )
    assert exc_info.value.status_code == 409
    assert "archived" in str(exc_info.value.detail)
