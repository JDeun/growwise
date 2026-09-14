from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

import growwise.api.main as api
from growwise.api.main import (
    MaterialGenerateRequest,
    MaterialReviewRequest,
    MaterialRevisionRequest,
)
from growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialGenerationService
from growwise.review import InvalidMaterialTransition, MaterialReviewService
from growwise.storage import EntityStore


class UnsafeDraftProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return schema.model_validate(
            {
                "title": "발달 진단 결과",
                "content_markdown": "또래보다 뒤처졌고 자폐 진단이 필요합니다.",
                "source_refs": ["resource:allowed", "resource:invented"],
            }
        )


class SafeButFabricatedRefProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return schema.model_validate(
            {
                "title": "고양이 읽기",
                "content_markdown": "# 활동\n그림을 천천히 함께 봅니다.",
                "source_refs": ["resource:allowed", "resource:invented"],
            }
        )


class RecordingReviewGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def invoke(self, value: Any, config: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((value, config))
        if isinstance(value, dict):
            return {**value, "__interrupt__": ("review",)}
        resume = value.resume
        return {
            "decision_status": resume["status"],
            "decision_note": resume.get("note"),
        }


def _child() -> ChildProfile:
    return ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=9)


def _store_with_child(tmp_path: Path) -> tuple[EntityStore, ChildProfile]:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = _child()
    store.save(child)
    return store, child


def test_unsafe_llm_draft_is_discarded_for_template_fallback() -> None:
    material = MaterialGenerationService(provider=UnsafeDraftProvider()).generate(
        child=_child(),
        kind=MaterialKind.READING_ACTIVITY,
        topic="고양이",
        source_refs=["resource:allowed"],
    )

    assert material.status is MaterialStatus.REVIEW_PENDING
    assert material.generator_mode == "template_safety_fallback"
    assert "자폐" not in material.content_markdown
    assert material.source_refs == ["resource:allowed"]


def test_fabricated_material_source_ref_is_removed() -> None:
    material = MaterialGenerationService(provider=SafeButFabricatedRefProvider()).generate(
        child=_child(),
        kind=MaterialKind.ACTIVITY_GUIDE,
        topic="고양이",
        source_refs=["resource:allowed"],
    )

    assert material.generator_mode == "llm_enhanced"
    assert material.source_refs == ["resource:allowed"]


def test_unapproved_material_cannot_export() -> None:
    material = MaterialGenerationService(provider=None).generate(
        child=_child(),
        kind=MaterialKind.ACTIVITY_GUIDE,
        topic="촉감",
    )
    review = MaterialReviewService()

    assert review.can_export(material) is False
    review.transition(material, MaterialStatus.APPROVED)
    assert review.can_export(material) is True


def test_approved_material_cannot_return_to_review_pending() -> None:
    material = MaterialGenerationService(provider=None).generate(
        child=_child(),
        kind=MaterialKind.ACTIVITY_GUIDE,
        topic="소리",
    )
    review = MaterialReviewService()
    review.transition(material, MaterialStatus.APPROVED)

    with pytest.raises(InvalidMaterialTransition):
        review.transition(material, MaterialStatus.REVIEW_PENDING)


def test_material_api_starts_and_resumes_parent_review_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    graph = RecordingReviewGraph()
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)

    material = api.generate_material(
        child.id,
        MaterialGenerateRequest(topic="그림책", kind=MaterialKind.READING_ACTIVITY),
        store,
    )

    assert material.status is MaterialStatus.REVIEW_PENDING
    assert len(graph.calls) == 1
    _, start_config = graph.calls[0]
    expected_thread = f"material-review:{material.id}"
    assert start_config["configurable"]["thread_id"] == expected_thread

    reviewed = api.review_material(
        material.id,
        MaterialReviewRequest(status=MaterialStatus.APPROVED, note="확인함"),
        store,
    )

    assert reviewed.status is MaterialStatus.APPROVED
    assert reviewed.review_note == "확인함"
    assert len(graph.calls) == 2
    _, resume_config = graph.calls[1]
    assert resume_config["configurable"]["thread_id"] == expected_thread


def test_review_decision_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)

    class MismatchGraph(RecordingReviewGraph):
        def invoke(self, value: Any, config: dict[str, Any]) -> dict[str, Any]:
            if isinstance(value, dict):
                return {**value, "__interrupt__": ("review",)}
            return {"decision_status": "rejected", "decision_note": None}

    graph = MismatchGraph()
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)
    material = api.generate_material(
        child.id,
        MaterialGenerateRequest(topic="그림책"),
        store,
    )

    with pytest.raises(HTTPException) as exc_info:
        api.review_material(
            material.id,
            MaterialReviewRequest(status=MaterialStatus.APPROVED),
            store,
        )
    assert exc_info.value.status_code == 409



def test_revision_api_preserves_request_lineage_and_is_retry_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    graph = RecordingReviewGraph()
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)

    material = api.generate_material(
        child.id,
        MaterialGenerateRequest(
            topic="달의 모양",
            goal="관찰한 차이를 말로 설명한다.",
            kind=MaterialKind.SCIENCE_INQUIRY,
        ),
        store,
    )
    assert material.request_topic == "달의 모양"
    assert material.request_goal == "관찰한 차이를 말로 설명한다."

    requested = api.review_material(
        material.id,
        MaterialReviewRequest(
            status=MaterialStatus.REVISION_REQUESTED,
            note="질문 수를 줄이고 관찰 중심으로 바꿔주세요.",
        ),
        store,
    )
    revised = api.revise_material(
        requested.id,
        MaterialRevisionRequest(),
        store,
    )

    assert revised.status is MaterialStatus.REVIEW_PENDING
    assert revised.version == 2
    assert revised.parent_material_id == material.id
    assert revised.request_topic == "달의 모양"
    assert "관찰한 차이를 말로 설명한다." in (revised.request_goal or "")
    assert "질문 수를 줄이고 관찰 중심으로" in (revised.request_goal or "")
    assert graph.calls[-1][1]["configurable"]["thread_id"] == f"material-review:{revised.id}"

    call_count = len(graph.calls)
    retried = api.revise_material(
        requested.id,
        MaterialRevisionRequest(note="재시도에서 다른 버전이 생기면 안 됩니다."),
        store,
    )
    assert retried.id == revised.id
    assert len(graph.calls) == call_count


def test_revision_api_rejects_material_without_revision_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    graph = RecordingReviewGraph()
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)
    material = api.generate_material(
        child.id,
        MaterialGenerateRequest(topic="그림자"),
        store,
    )

    with pytest.raises(HTTPException) as exc_info:
        api.revise_material(material.id, MaterialRevisionRequest(), store)
    assert exc_info.value.status_code == 409
