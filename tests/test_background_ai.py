from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep

from growwise.config import Settings
from growwise.domain import AiEnhancementStatus, ChildProfile, LearningLog, Stage
from growwise.jobs import Job, SQLiteJobQueue
from growwise.services.background_ai import BackgroundAiJobRunner
from growwise.storage import EntityStore


class ImmediateObservationProvider:
    def __init__(self, store: EntityStore, log_id: str) -> None:
        self.store = store
        self.log_id = log_id

    def generate_structured(self, *, system: str, user: str, schema):
        del system, user
        payload = self.store.index.get_entity(self.log_id, entity_type="learning_log")
        assert payload is not None
        current = LearningLog.model_validate(payload)
        assert current.ai_status is AiEnhancementStatus.QUEUED
        assert current.ai_job_id is not None
        return schema(tags=["공룡"], interest="공룡")


def test_worker_cannot_claim_before_queued_state_is_persisted(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    log = LearningLog(child_id=child.id, parent_observation="공룡 책을 오래 읽었다.")
    store.save(log)

    provider = ImmediateObservationProvider(store, str(log.id))
    runner = BackgroundAiJobRunner(
        queue=SQLiteJobQueue(settings.jobs_path),
        store_factory=lambda: store,
        provider_factory=lambda: provider,
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

        assert current.ai_status is AiEnhancementStatus.COMPLETED
        assert current.tags == ["공룡"]
        assert current.interest == "공룡"
    finally:
        runner.stop()
