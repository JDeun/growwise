from __future__ import annotations

import logging
from functools import lru_cache

from growwise.config import Settings
from growwise.domain import AiEnhancementStatus, GeneratedMaterial, LearningLog
from growwise.jobs import Job
from growwise.maintenance import MaintenanceAwareJobQueue
from growwise.model import ModelProvider, create_model_provider
from growwise.services.background_ai import BackgroundAiJobRunner
from growwise.storage import EntityStore

logger = logging.getLogger(__name__)


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
        logger.exception("background AI provider unavailable; continuing without enhancement")
        return None


@lru_cache
def get_background_ai_runner() -> BackgroundAiJobRunner:
    settings = get_background_ai_settings()
    return BackgroundAiJobRunner(
        queue=MaintenanceAwareJobQueue(settings.jobs_path),
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


def _save_optional_status(
    entity: LearningLog | GeneratedMaterial,
    *,
    store: EntityStore,
    label: str,
) -> None:
    try:
        store.save(entity)
    except Exception:
        # The entity was already saved before enhancement scheduling. A secondary status write must
        # never make that authoritative create look failed to the caller.
        logger.exception("failed to persist optional AI status for %s", label)


def queue_learning_log_enrichment(*, log: LearningLog, store: EntityStore) -> Job | None:
    if get_background_ai_provider() is None:
        log.ai_status = AiEnhancementStatus.NOT_REQUESTED
        _save_optional_status(log, store=store, label=f"learning_log:{log.id}")
        return None
    runner = get_background_ai_runner()

    def mark_queued(job: Job) -> None:
        log.ai_status = AiEnhancementStatus.QUEUED
        log.ai_job_id = job.id
        _save_optional_status(log, store=store, label=f"learning_log:{log.id}")

    try:
        runner.start()
        return runner.submit_observation(
            child_id=str(log.child_id),
            log_id=str(log.id),
            on_enqueued=mark_queued,
        )
    except Exception:
        logger.exception("failed to queue optional observation enhancement for %s", log.id)
        log.ai_status = AiEnhancementStatus.FAILED
        _save_optional_status(log, store=store, label=f"learning_log:{log.id}")
        return None


def queue_material_enhancement(*, material: GeneratedMaterial, store: EntityStore) -> Job | None:
    if get_background_ai_provider() is None:
        material.ai_status = AiEnhancementStatus.NOT_REQUESTED
        _save_optional_status(material, store=store, label=f"generated_material:{material.id}")
        return None
    runner = get_background_ai_runner()

    def mark_queued(job: Job) -> None:
        material.ai_status = AiEnhancementStatus.QUEUED
        material.ai_job_id = job.id
        _save_optional_status(material, store=store, label=f"generated_material:{material.id}")

    try:
        runner.start()
        return runner.submit_material(
            child_id=str(material.child_id),
            material_id=str(material.id),
            on_enqueued=mark_queued,
        )
    except Exception:
        logger.exception("failed to queue optional material enhancement for %s", material.id)
        material.ai_status = AiEnhancementStatus.FAILED
        _save_optional_status(material, store=store, label=f"generated_material:{material.id}")
        return None
