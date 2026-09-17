from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep

from growwise.config import Settings
from growwise.domain import (
    AiEnhancementStatus,
    ChildProfile,
    GeneratedMaterial,
    LearningLog,
    LearningRecordKind,
    MaterialKind,
    MaterialStatus,
    Stage,
)
from growwise.jobs import Job, SQLiteJobQueue
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
            content_markdown="# 후속 활동\n\n실물을 나누어 보고 방법을 설명해 보세요.",
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