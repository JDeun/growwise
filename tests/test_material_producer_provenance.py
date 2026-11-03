from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from growwise.api import main as api_main
from growwise.api.dependencies import get_store
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, MaterialStatus, Stage
from growwise.generators import (
    MaterialEditService,
    MaterialGenerationService,
    MaterialRevisionService,
)
from growwise.generators.material import MATERIAL_GENERATOR_VERSION
from growwise.jobs import JobStatus, SQLiteJobQueue
from growwise.review import MaterialReviewService
from growwise.services.background_ai import BackgroundAiJobRunner
from growwise.storage import EntityStore


class Provider:
    def __init__(self, model="synthetic:model-a", mode="accepted"):
        self.model = model
        self.mode = mode

    def generate_structured(self, *, schema, **kwargs):
        if self.mode == "error":
            raise RuntimeError("synthetic model failure")
        step = ("해봅니다." if self.mode == "weak" else
                "같은 블록을 다른 순서로 옮겨 세어보고 개수가 같은지 비교합니다.")
        return schema.model_validate({
            "title": "블록을 다르게 세어 보기",
            "sections": [
                {"heading": "쌓아서 세어 보기", "steps": [step], "question": "어떻게 확인했나요?"},
                {"heading": "나란히 놓아 보기", "steps": [
                    "해봅니다." if self.mode == "weak" else
                    "세었던 블록을 한 줄로 옮겨 다시 세고 처음 개수와 같은지 확인합니다.",
                ],
                 "question": "어떤 방법이 더 편했고 왜 그렇게 생각하나요?"},
            ],
            "parent_guide_markdown": "아이의 설명을 기다리고 작은 힌트만 건넵니다.",
            "source_refs": [],
        })


def _child():
    return ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY)


def _generate(provider=None, child=None):
    return MaterialGenerationService(provider=provider).generate(
        child=child or _child(), kind=MaterialKind.MATH_ACTIVITY, topic="블록 세기",
    )


def test_accepted_provider_identity_and_generator_version_survive_markdown_rebuild(tmp_path: Path):
    material = _generate(Provider())
    assert material.generator_mode == "llm_enhanced"
    assert material.model_provider == "Provider"
    assert material.model_id == "synthetic:model-a"
    assert material.generator_version == MATERIAL_GENERATOR_VERSION
    assert material.reviewed_at is None
    assert material.review_decision is None
    assert material.ai_job_id is None  # No fabricated job/workflow for a synchronous call.
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    store.save(material)
    store.index.rebuild(store.markdown.root)
    restored = GeneratedMaterial.model_validate(store.index.get_entity(str(material.id)))
    assert restored.model_dump() == material.model_dump()


@pytest.mark.parametrize("mode", ["none", "error", "weak"])
def test_fallback_does_not_claim_the_model_that_was_attempted(mode):
    material = _generate(None if mode == "none" else Provider(mode=mode))
    assert material.generator_mode != "llm_enhanced"
    assert material.model_provider is None
    assert material.model_id is None
    assert material.generator_version == MATERIAL_GENERATOR_VERSION


@pytest.mark.parametrize("decision", [MaterialStatus.APPROVED, MaterialStatus.REJECTED])
def test_archive_preserves_real_parent_decision_time_and_note(decision, tmp_path: Path):
    material = _generate()
    review = MaterialReviewService()
    review.transition(material, decision, note="부모가 내용을 확인했습니다.")
    reviewed_at = material.reviewed_at
    assert reviewed_at is not None and reviewed_at.tzinfo is not None
    review.transition(material, MaterialStatus.ARCHIVED)
    assert material.reviewed_at == reviewed_at
    assert material.review_decision == decision.value
    assert material.review_note == "부모가 내용을 확인했습니다."
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    store.save(material)
    restored = store.markdown.load(store.markdown.path_for(material), GeneratedMaterial)
    assert restored.reviewed_at == reviewed_at
    assert restored.review_decision == decision.value


def test_parent_edit_has_its_own_producer_and_keeps_ai_origin_in_immutable_lineage():
    original = _generate(Provider())
    MaterialReviewService().approve_for_use(original)
    before = original.model_dump()
    edited = MaterialEditService().create_version(
        material=original, title="부모가 고친 제목", content_markdown="## 부모가 직접 바꾼 활동",
    )
    assert edited.parent_material_id == original.id
    assert edited.generator_mode == "parent_edit"
    assert edited.generator_version == "growwise.parent-edit.v1"
    assert edited.model_provider is None and edited.model_id is None
    assert edited.reviewed_at is None and edited.review_decision is None
    assert original.model_dump() == before


def test_regeneration_records_the_new_actual_model_and_resets_parent_decision():
    child = _child()
    original = _generate(Provider(), child)
    MaterialReviewService().transition(
        original, MaterialStatus.REVISION_REQUESTED, note="단계를 줄여요",
    )
    before = original.model_dump()
    service = MaterialRevisionService(MaterialGenerationService(Provider("synthetic:model-b")))
    revised = service.revise(
        material=original, child=child,
    )
    assert revised.model_id == "synthetic:model-b"
    assert revised.parent_material_id == original.id
    assert revised.version == original.version + 1
    assert revised.reviewed_at is None and revised.review_decision is None
    assert original.model_dump() == before


def test_background_acceptance_copies_provenance_and_links_the_real_durable_job(tmp_path: Path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = _child()
    store.save(child)
    material = _generate(None, child)
    store.save(material)
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    runner = BackgroundAiJobRunner(
        queue=queue, store_factory=lambda: store, provider_factory=Provider,
        lease_seconds=60, max_attempts=1, poll_interval_seconds=0.01,
    )
    runner.submit_material(child_id=str(child.id), material_id=str(material.id))
    job = queue.claim_next(lease_seconds=60)
    assert job is not None
    runner._process(job)
    result = GeneratedMaterial.model_validate(store.index.get_entity(str(material.id)))
    assert result.model_id == "synthetic:model-a"
    assert result.model_provider == "Provider"
    assert result.generator_version == MATERIAL_GENERATOR_VERSION
    assert result.ai_job_id == job.id
    assert queue.get(job.id).status is JobStatus.COMPLETED


@pytest.mark.parametrize("accepted_ai", [True, False])
def test_http_use_edit_archive_and_rebuild_preserve_truthful_provenance(
    tmp_path: Path, monkeypatch, accepted_ai,
):
    class ReviewProjection:
        def invoke(self, *_args, **_kwargs):
            return {}  # Domain approval remains authoritative if no checkpoint is present.

    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = _child()
    material = _generate(Provider() if accepted_ai else None, child)
    store.save(child)
    store.save(material)
    monkeypatch.setattr(api_main, "get_material_review_graph", ReviewProjection)
    api_main.app.dependency_overrides[get_store] = lambda: store
    try:
        client = TestClient(api_main.app)
        route = f"/v1/materials/{material.id}"
        response = client.post(f"{route}/use")
        assert response.status_code == 200, response.text
        approved = response.json()
        assert approved["review_decision"] == "approved"
        assert approved["reviewed_at"] is not None
        assert approved["model_id"] == ("synthetic:model-a" if accepted_ai else None)
        assert client.post(f"{route}/use").json()["reviewed_at"] == approved["reviewed_at"]

        edited = client.post(f"{route}/edit", json={
            "title": "부모가 직접 바꾼 제목",
            "content_markdown": "## 직접 바꾼 활동\n함께 비교해요.",
        })
        assert edited.status_code == 200, edited.text
        assert edited.json()["parent_material_id"] == str(material.id)
        assert edited.json()["model_id"] is None
        assert edited.json()["reviewed_at"] is None
        archived = client.post(f"{route}/review", json={"status": "archived"})
        assert archived.status_code == 200, archived.text
        store.index.rebuild(store.markdown.root)
        restored = client.get(route).json()
        assert restored["status"] == "archived"
        assert restored["reviewed_at"] == approved["reviewed_at"]
        assert restored["review_decision"] == "approved"
        assert restored["model_id"] == approved["model_id"]
        assert restored["generator_version"] == MATERIAL_GENERATOR_VERSION
    finally:
        api_main.app.dependency_overrides.pop(get_store, None)
