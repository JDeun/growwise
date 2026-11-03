from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep

import pytest

from growwise.config import Settings
from growwise.domain import (
    AiEnhancementStatus,
    ChildProfile,
    GeneratedMaterial,
    LearningLog,
    LearningRecordKind,
    MaterialKind,
    MaterialStatus,
    ResourceKind,
    ResourceRecord,
    Stage,
)
from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.jobs import Job, JobStatus, SQLiteJobQueue
from growwise.material_versions import material_mutation
from growwise.services import background_ai
from growwise.services.background_ai import BackgroundAiJobRunner
from growwise.storage import EntityStore


class ImmediateObservationProvider:
    def generate_structured(self, *, system: str, user: str, schema):
        del system, user
        return schema(tags=["공룡"], interest="공룡")


class InspectingMaterialProvider:
    def __init__(self) -> None:
        self.last_user = ""

    def generate_structured(self, *, system: str, user: str, schema):
        del system
        self.last_user = user
        return schema(
            title="후속 나누기 활동",
            content_markdown=(
                "## 실물을 같은 수씩 모으기\n"
                "1. 작은 물건을 준비하고 아이가 직접 같은 수씩 모아 봅니다.\n"
                "2. 묶음의 크기를 바꾸면 무엇이 달라질지 예상하고 다시 나누어 봅니다.\n"
                "## 생각을 설명하기\n"
                "어떤 방법으로 같은 수인지 확인했나요? 그림이나 말로 자기 방법을 설명하고 "
                "다른 방법과 비교해 봅니다."
            ),
            parent_guide_markdown="# 부모 교안\n\n아이의 설명을 먼저 들어보세요.",
            source_refs=[],
        )


class InspectingJobQueue(SQLiteJobQueue):
    def __init__(self, path: Path, *, store: EntityStore, log_id: str) -> None:
        super().__init__(path)
        self.store = store
        self.log_id = log_id
        self.observed_queued_before_claim = False

    def claim_next(
        self,
        *,
        job_types: tuple[str, ...] | None = None,
        lease_seconds: int = 3600,
        max_attempts: int = 3,
    ) -> Job | None:
        job = super().claim_next(
            job_types=job_types,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
        )
        if job is None:
            return None
        payload = self.store.index.get_entity(self.log_id, entity_type="learning_log")
        assert payload is not None
        current = LearningLog.model_validate(payload)
        assert current.ai_status is AiEnhancementStatus.QUEUED
        assert current.ai_job_id == job.id
        self.observed_queued_before_claim = True
        return job


def test_worker_cannot_claim_before_queued_state_is_persisted(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    log = LearningLog(child_id=child.id, parent_observation="공룡 책을 오래 읽었다.")
    store.save(log)

    queue = InspectingJobQueue(
        settings.jobs_path,
        store=store,
        log_id=str(log.id),
    )
    runner = BackgroundAiJobRunner(
        queue=queue,
        store_factory=lambda: store,
        provider_factory=ImmediateObservationProvider,
        lease_seconds=60,
        max_attempts=1,
        poll_interval_seconds=0.01,
    )

    def mark_queued(job: Job) -> None:
        log.ai_status = AiEnhancementStatus.QUEUED
        log.ai_job_id = job.id
        store.save(log)

    runner.start()
    try:
        runner.submit_observation(
            child_id=str(child.id),
            log_id=str(log.id),
            on_enqueued=mark_queued,
        )
        deadline = monotonic() + 2.0
        while monotonic() < deadline:
            payload = store.index.get_entity(str(log.id), entity_type="learning_log")
            assert payload is not None
            current = LearningLog.model_validate(payload)
            if current.ai_status is AiEnhancementStatus.COMPLETED:
                break
            sleep(0.01)
        else:
            raise AssertionError("background observation enrichment did not complete")

        assert queue.observed_queued_before_claim is True
        assert current.ai_status is AiEnhancementStatus.COMPLETED
        assert current.tags == ["공룡"]
        assert current.interest == "공룡"
    finally:
        runner.stop()


def _runner_with_material(tmp_path: Path, *, lease_seconds: int = 60):
    settings = Settings(data_dir=tmp_path, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="테스트아이", stage=Stage.ELEMENTARY)
    store.save(child)
    material = GeneratedMaterial(
        child_id=child.id, kind=MaterialKind.MATH_ACTIVITY, title="원본 활동",
        content_markdown="부모에게 먼저 제공한 원본 활동", parent_guide_markdown="원본 부모 교안",
        generator_mode="template", status=MaterialStatus.REVIEW_PENDING,
    )
    store.save(material)
    queue = SQLiteJobQueue(settings.jobs_path)
    runner = BackgroundAiJobRunner(
        queue=queue, store_factory=lambda: store, provider_factory=InspectingMaterialProvider,
        lease_seconds=lease_seconds, max_attempts=1, poll_interval_seconds=0.01,
    )
    runner.submit_material(child_id=str(child.id), material_id=str(material.id))
    job = queue.claim_next(lease_seconds=lease_seconds)
    assert job is not None
    return runner, queue, store, material, job


@pytest.mark.parametrize("mode", ["template", "template_fallback", "template_quality_fallback",
                                 "template_safety_fallback", "template_malformed_fallback"])
def test_rejected_model_modes_fail_fenced_job_without_replacing_initial_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    runner, queue, store, material, job = _runner_with_material(tmp_path)

    class Generator:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            return material.model_copy(update={"generator_mode": mode,
                                                "content_markdown": "검토에 실패한 모델 출력"})

    monkeypatch.setattr(background_ai, "MaterialGenerationService", Generator)
    runner._process(job)
    saved = store.index.get_entity(str(material.id), entity_type="generated_material")
    assert saved is not None
    assert saved["content_markdown"] == material.content_markdown
    assert saved["parent_guide_markdown"] == material.parent_guide_markdown
    assert saved["generator_mode"] == "template"
    assert saved["ai_status"] == "failed"
    terminal = queue.get(job.id)
    assert terminal is not None
    assert terminal.status is JobStatus.FAILED
    assert terminal.claim_token is None
    assert not queue.complete(job.id, job.claim_token)


def test_provider_failure_does_not_persist_secret_exception_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, queue, _store, _material, job = _runner_with_material(tmp_path)

    class Generator:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            raise RuntimeError("https://example.test/?key=synthetic-private-key&prompt=private-text")

    monkeypatch.setattr(background_ai, "MaterialGenerationService", Generator)
    runner._process(job)
    terminal = queue.get(job.id)
    assert terminal is not None and terminal.status is JobStatus.FAILED
    assert "synthetic-private-key" not in terminal.last_error
    assert "private-text" not in terminal.last_error


@pytest.mark.parametrize("cancel", [False, True])
def test_long_inference_heartbeats_lease_and_stops_after_completion_or_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    runner, queue, store, material, job = _runner_with_material(tmp_path, lease_seconds=1)
    entered = threading.Event()
    release = threading.Event()
    lost_claim = threading.Event()
    heartbeats: list[bool] = []
    original_heartbeat = queue.heartbeat

    def heartbeat(*args, **kwargs):
        result = original_heartbeat(*args, **kwargs)
        heartbeats.append(result)
        if not result:
            lost_claim.set()
        return result

    class Generator:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            entered.set()
            assert release.wait(timeout=5)
            return material.model_copy(update={"generator_mode": "llm_enhanced",
                                                "content_markdown": "검토를 통과한 모델 활동"})

    monkeypatch.setattr(background_ai, "MaterialGenerationService", Generator)
    monkeypatch.setattr(queue, "heartbeat", heartbeat)
    worker = threading.Thread(target=runner._process, args=(job,), daemon=True)
    worker.start()
    try:
        assert entered.wait(timeout=2)
        sleep(1.2)  # Longer than the original lease; the active worker must retain its claim.
        current = queue.get(job.id)
        assert current is not None
        assert datetime.fromisoformat(current.lease_expires_at) > datetime.now(UTC)
        assert queue.claim_next(lease_seconds=1) is None
        assert len(heartbeats) >= 3
        if cancel:
            queue.cancel(job.id)
            assert lost_claim.wait(timeout=2)
            calls = len(heartbeats)
            sleep(0.4)
            assert len(heartbeats) == calls
        release.set()
        worker.join(timeout=3)
        assert not worker.is_alive()
        calls = len(heartbeats)
        sleep(0.4)
        assert len(heartbeats) == calls
        terminal = queue.get(job.id)
        assert terminal is not None
        assert terminal.status is (JobStatus.CANCELLED if cancel else JobStatus.COMPLETED)
        saved = store.index.get_entity(str(material.id), entity_type="generated_material")
        assert saved is not None
        assert saved["content_markdown"] == (material.content_markdown if cancel
                                              else "검토를 통과한 모델 활동")
    finally:
        release.set()
        worker.join(timeout=3)


def test_background_api_uses_quality_budget_provider_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from growwise.api import background_ai as api

    settings = Settings(data_dir=tmp_path)
    captured = {}
    expected = InspectingMaterialProvider()

    def create_provider(received, *, background=False):
        captured.update(settings=received, background=background)
        return expected

    monkeypatch.setattr(api, "get_background_ai_settings", lambda: settings)
    monkeypatch.setattr(api, "create_model_provider", create_provider)
    api.get_background_ai_provider.cache_clear()
    try:
        assert api.get_background_ai_provider() is expected
        assert captured == {"settings": settings, "background": True}
    finally:
        api.get_background_ai_provider.cache_clear()


@pytest.mark.parametrize("scenario, expected", [
    ("exhausted", "failed"), ("missing", "failed"), ("retryable", "queued"),
    ("cancelled", "skipped"), ("reviewed", "skipped"),
])
def test_startup_reconciles_source_ai_status_without_touching_reviewed_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, expected: str
) -> None:
    runner, queue, store, material, job = _runner_with_material(tmp_path)
    material.ai_status = AiEnhancementStatus.RUNNING
    material.ai_job_id = None if scenario == "missing" else job.id
    if scenario == "reviewed":
        material.status = MaterialStatus.APPROVED
    if scenario == "retryable":
        runner.max_attempts = 2
    if scenario == "cancelled":
        queue.cancel(job.id)
    store.save(material)
    monkeypatch.setattr(runner, "_run", lambda: None)
    runner.start()
    runner.stop()
    saved = store.index.get_entity(str(material.id), entity_type="generated_material")
    assert saved is not None
    assert saved["ai_status"] == expected
    assert saved["content_markdown"] == material.content_markdown
    assert saved["status"] == material.status.value


def test_recovery_pages_only_unfinished_ai_sources(tmp_path: Path) -> None:
    from growwise.storage.sqlite import _PENDING_AI_WHERE

    runner, _queue, store, material, _job = _runner_with_material(tmp_path)
    for _ in range(103):
        store.save(LearningLog(child_id=material.child_id, parent_observation="복원한 원본 관찰",
                               ai_status=AiEnhancementStatus.RUNNING))
    batch = store.index.pending_ai_entities()
    assert len(batch) == 100
    assert len(store.index.pending_ai_entities(after_id=batch[-1]["id"])) == 3
    with store.index._connection() as connection:
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM entities INDEXED BY idx_entities_pending_ai "
            f"WHERE {_PENDING_AI_WHERE} "
            "AND id > ? ORDER BY id LIMIT 100", ("",),
        ).fetchall()
    assert "idx_entities_pending_ai" in str([tuple(row) for row in plan])
    runner._recover_source_statuses()
    assert store.index.pending_ai_entities() == []
    assert all(payload["ai_status"] == "failed"
               for payload in store.index.list_entities(entity_type="learning_log"))


def test_parent_approval_serializes_against_late_background_material_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, _queue, store, material, job = _runner_with_material(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    generated = threading.Event()
    finished = threading.Event()

    class Generator:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            entered.set()
            assert release.wait(timeout=3)
            generated.set()
            return material.model_copy(update={"generator_mode": "llm_enhanced",
                                                "content_markdown": "늦게 도착한 모델 내용"})

    def process() -> None:
        try:
            runner._process(job)
        finally:
            finished.set()

    monkeypatch.setattr(background_ai, "MaterialGenerationService", Generator)
    worker = threading.Thread(target=process, daemon=True)
    worker.start()
    try:
        assert entered.wait(timeout=2)
        with material_mutation(material.id):
            release.set()
            assert generated.wait(timeout=2)
            assert not finished.wait(timeout=0.1)
            material.status = MaterialStatus.APPROVED
            material.content_markdown = "부모가 확인하고 승인한 내용"
            store.save(material)
        worker.join(timeout=3)
        assert not worker.is_alive()
        saved = store.index.get_entity(str(material.id), entity_type="generated_material")
        assert saved is not None
        assert saved["status"] == "approved"
        assert saved["content_markdown"] == "부모가 확인하고 승인한 내용"
        assert saved["ai_status"] == "skipped"
    finally:
        release.set()
        worker.join(timeout=3)


@pytest.mark.parametrize("provider_available", [True, False])
def test_parent_approval_before_initial_worker_status_write_is_preserved(
    tmp_path: Path, provider_available: bool,
) -> None:
    runner, _queue, store, material, job = _runner_with_material(tmp_path)

    def provider():
        with material_mutation(material.id):
            material.status = MaterialStatus.APPROVED
            material.content_markdown = "부모가 직접 검토한 최종 내용"
            store.save(material)
        return InspectingMaterialProvider() if provider_available else None

    runner.provider_factory = provider
    runner._process(job)
    saved = store.index.get_entity(str(material.id), entity_type="generated_material")
    assert saved is not None
    assert saved["status"] == "approved"
    assert saved["content_markdown"] == "부모가 직접 검토한 최종 내용"
    assert saved["ai_status"] == "skipped"


@pytest.mark.parametrize("status", [AiEnhancementStatus.QUEUED, AiEnhancementStatus.FAILED])
def test_worker_error_status_preserves_parent_review(tmp_path: Path, status) -> None:
    runner, _queue, store, material, job = _runner_with_material(tmp_path)
    with material_mutation(material.id):
        material.status = MaterialStatus.APPROVED
        material.content_markdown = "실패한 AI보다 부모가 검토한 내용이 우선입니다"
        store.save(material)
    if status is AiEnhancementStatus.QUEUED:
        runner._mark_retryable(job, "failure")
    else:
        runner._mark_failed(job)
    saved = store.index.get_entity(str(material.id), entity_type="generated_material")
    assert saved is not None
    assert saved["status"] == "approved"
    assert saved["content_markdown"] == material.content_markdown
    assert saved["ai_status"] == "skipped"


def test_revoked_shared_source_is_not_refreshed_into_material_context(tmp_path: Path) -> None:
    runner, _queue, store, material, _job = _runner_with_material(tmp_path)
    owner = ChildProfile(nickname="다른 아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    resource = ResourceRecord(child_id=owner.id, title="가족 자료", kind=ResourceKind.NOTE,
                              content="공유한 관찰")
    store.save(resource)
    share = EntityLink(child_id=material.child_id, source_id=resource.id,
                       target_id=material.child_id, relation=EntityLinkRelation.CHILD_SCOPE)
    store.save(share)
    material.source_refs = [f"resource:{resource.id}"]
    evidence = runner._material_source_evidence(material=material, store=store)
    assert "공유한 관찰" in evidence[0].excerpt
    store.delete(share)
    resource.content = "공유 취소 후 추가한 비공개 관찰"
    store.save(resource)
    assert runner._material_source_evidence(material=material, store=store) == []


@pytest.mark.parametrize("endpoint", ["http://127.0.0.1:11434", "https://remote.example.test/v1"])
@pytest.mark.parametrize("wiki_unavailable", [False, True])
def test_desktop_material_worker_uses_local_wiki_without_remote_leakage_or_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    wiki_unavailable: bool,
) -> None:
    settings = Settings(data_dir=tmp_path, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="다른아이", stage=Stage.ELEMENTARY)
    store.save(child)
    store.save(sibling)
    store.save(LearningLog(child_id=child.id, parent_observation="민들레 씨앗을 관찰했다.",
                           next_activity="종이 씨앗 날리기"))
    store.save(LearningLog(child_id=sibling.id, parent_observation="형제 비공개 관찰",
                           next_activity="형제 비공개 계획"))
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.SCIENCE_INQUIRY,
        title="씨앗",
        content_markdown="기본 활동",
        status=MaterialStatus.REVIEW_PENDING,
        generator_mode="template",
    )
    store.save(material)
    provider = InspectingMaterialProvider()
    provider.base_url = endpoint
    captured: dict = {}

    class Generator:
        def __init__(self, *, provider):
            pass

        def generate(self, **kwargs):
            captured.update(kwargs)
            return material.model_copy(update={"generator_mode": "llm_enhanced"})

    monkeypatch.setattr(background_ai, "MaterialGenerationService", Generator)
    if wiki_unavailable:
        def unavailable(self, child_id):
            raise OSError("derived wiki temporarily unavailable")
        monkeypatch.setattr(background_ai.LearningWikiService, "refresh", unavailable)

    queue = SQLiteJobQueue(settings.jobs_path)
    runner = BackgroundAiJobRunner(
        queue=queue,
        store_factory=lambda: store,
        provider_factory=lambda: provider,
        lease_seconds=60,
        max_attempts=1,
        poll_interval_seconds=0.01,
    )
    runner.submit_material(child_id=str(child.id), material_id=str(material.id))
    job = queue.claim_next(lease_seconds=60)
    assert job is not None
    runner._process(job)
    current = store.index.get_entity(str(material.id), entity_type="generated_material")
    assert current is not None
    assert current["ai_status"] == "completed"
    guidance = captured["generation_guidance"] or ""
    assert ("종이 씨앗 날리기" in guidance) == (
        endpoint.startswith("http://127.0.0.1") and not wiki_unavailable
    )
    assert "형제 비공개" not in guidance


def test_material_worker_uses_generalized_feedback_and_keeps_raw_activity_data_local(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    learner_work = "아이 원문: 사과 여섯 개를 세 개씩 두 묶음으로 그렸다."
    process = "사과 그림을 하나씩 옮기면서 두 묶음의 개수가 같은지 확인했다."
    store.save(
        LearningLog(
            child_id=child.id,
            record_kind=LearningRecordKind.MATERIAL_USE,
            title="이전 나누기 활동",
            parent_observation="실물을 직접 옮겨가며 풀었다.",
            learner_work=learner_work,
            process=process,
        )
    )
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.MATH_ACTIVITY,
        title="생활 속 나누기",
        content_markdown="# 기본 초안",
        parent_guide_markdown="# 기본 부모 교안",
        status=MaterialStatus.REVIEW_PENDING,
        generator_mode="template",
        request_topic="생활 속 나누기",
        request_goal="실물로 나누는 방법을 탐색한다",
        ai_status=AiEnhancementStatus.QUEUED,
    )
    store.save(material)

    provider = InspectingMaterialProvider()
    queue = SQLiteJobQueue(settings.jobs_path)
    runner = BackgroundAiJobRunner(
        queue=queue,
        store_factory=lambda: store,
        provider_factory=lambda: provider,
        lease_seconds=60,
        max_attempts=1,
        poll_interval_seconds=0.01,
    )

    def mark_queued(job: Job) -> None:
        material.ai_status = AiEnhancementStatus.QUEUED
        material.ai_job_id = job.id
        store.save(material)

    runner.start()
    try:
        runner.submit_material(
            child_id=str(child.id),
            material_id=str(material.id),
            on_enqueued=mark_queued,
        )
        deadline = monotonic() + 2.0
        while monotonic() < deadline:
            payload = store.index.get_entity(str(material.id), entity_type="generated_material")
            assert payload is not None
            current = GeneratedMaterial.model_validate(payload)
            if current.ai_status is AiEnhancementStatus.COMPLETED:
                break
            sleep(0.01)
        else:
            raise AssertionError("background material enhancement did not complete")

        assert "Goal: 실물로 나누는 방법을 탐색한다" in provider.last_user
        assert "Internal generation guidance" in provider.last_user
        assert "최근 아이 산출물이 있으면" in provider.last_user
        assert "최근 활동 과정이 기록돼 있으면" in provider.last_user
        assert "개인화 원칙" not in provider.last_user
        assert learner_work not in provider.last_user
        assert process not in provider.last_user
        assert learner_work not in current.content_markdown
        assert process not in current.content_markdown
        assert "개인화 원칙" not in current.content_markdown
        assert learner_work in current.parent_guide_markdown
        assert process in current.parent_guide_markdown
        assert current.ai_status is AiEnhancementStatus.COMPLETED
    finally:
        runner.stop()
