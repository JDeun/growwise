from __future__ import annotations

from functools import lru_cache

from growwise.config import Settings
from growwise.domain import AiEnhancementStatus, GeneratedMaterial, LearningLog
from growwise.jobs import Job, SQLiteJobQueue
from growwise.model import ModelProvider, create_model_provider
from growwise.services.background_ai import BackgroundAiJobRunner
from growwise.storage import EntityStore


@lru_cache
def get_background_ai_settings() -> Settings:
    return Settings()


@lru_cache
def get_background_ai_provider() -> ModelProvider | None:
    settings = get_background_ai_settings()
    if not settings.llm_features_enabled:
        return None
    try:
        return create_model_provider(settings)
    except Exception:
        return None


@lru_cache
def get_background_ai_runner() -> BackgroundAiJobRunner:
    settings = get_background_ai_settings()
    return BackgroundAiJobRunner(
        queue=SQLiteJobQueue(settings.jobs_path),
        store_factory=lambda: EntityStore(settings.records_dir, settings.index_path),
        provider_factory=get_background_ai_provider,
        lease_seconds=settings.background_ai_job_lease_seconds,
        max_attempts=settings.background_ai_job_max_attempts,
        poll_interval_seconds=settings.background_ai_job_poll_interval_seconds,
    )


def start_background_ai_runner() -> None:
    if get_background_ai_settings().llm_features_enabled:
        get_background_ai_runner().start()


def stop_background_ai_runner() -> None:
    if get_background_ai_runner.cache_info().currsize:
        get_background_ai_runner().stop()


def queue_learning_log_enrichment(*, log: LearningLog, store: EntityStore) -> Job | None:
    if get_background_ai_provider() is None:
        log.ai_status = AiEnhancementStatus.NOT_REQUESTED
        store.save(log)
        return None
    runner = get_background_ai_runner()
    runner.start()

    def mark_queued(job: Job) -> None:
        log.ai_status = AiEnhancementStatus.QUEUED
        log.ai_job_id = job.id
        store.save(log)

    try:
        return runner.submit_observation(
            child_id=str(log.child_id),
            log_id=str(log.id),
            on_enqueued=mark_queued,
        )
    except Exception:
        log.ai_status = AiEnhancementStatus.FAILED
        store.save(log)
        return None


def queue_material_enhancement(*, material: GeneratedMaterial, store: EntityStore) -> Job | None:
    if get_background_ai_provider() is None:
        material.ai_status = AiEnhancementStatus.NOT_REQUESTED
        store.save(material)
        return None
    runner = get_background_ai_runner()
    runner.start()

    def mark_queued(job: Job) -> None:
        material.ai_status = AiEnhancementStatus.QUEUED
        material.ai_job_id = job.id
        store.save(material)

    try:
        return runner.submit_material(
            child_id=str(material.child_id),
            material_id=str(material.id),
            on_enqueued=mark_queued,
        )
    except Exception:
        material.ai_status = AiEnhancementStatus.FAILED
        store.save(material)
        return None
