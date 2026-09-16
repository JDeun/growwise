from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from time import sleep
from uuid import UUID

from growwise.domain import (
    AiEnhancementStatus,
    ChildProfile,
    GeneratedMaterial,
    LearningLog,
    MaterialStatus,
    ResourceRecord,
)
from growwise.generators import MaterialGenerationService, MaterialSourceEvidence
from growwise.jobs import Job, SQLiteJobQueue
from growwise.model import ModelProvider
from growwise.services.background_ai_lock import BACKGROUND_AI_LOCK
from growwise.services.observation import ObservationEnricher
from growwise.storage import EntityStore

OBSERVATION_ENRICHMENT_JOB = "observation_enrichment"
MATERIAL_ENHANCEMENT_JOB = "material_enhancement"
_TEXT_JOB_TYPES = (OBSERVATION_ENRICHMENT_JOB, MATERIAL_ENHANCEMENT_JOB)
_MATERIAL_SOURCE_EXCERPT_CHARS = 4_000


class BackgroundAiJobRunner:
    """Single-consumer durable worker for non-interactive text-model work.

    Parent-authored/source-of-truth records are persisted before jobs are submitted. This runner may
    enrich them later, but a failed or unavailable model never invalidates the already-saved Core
    record. Interactive chat/search intentionally remains outside this worker.
    """

    def __init__(
        self,
        *,
        queue: SQLiteJobQueue,
        store_factory: Callable[[], EntityStore],
        provider_factory: Callable[[], ModelProvider | None],
        lease_seconds: int,
        max_attempts: int,
        poll_interval_seconds: float,
    ) -> None:
        self.queue = queue
        self.store_factory = store_factory
        self.provider_factory = provider_factory
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.poll_interval_seconds = poll_interval_seconds
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._guard = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._guard:
            if self._thread is not None and self._thread.is_alive():
                return
            for job_type in _TEXT_JOB_TYPES:
                self.queue.recover_running(job_type=job_type, max_attempts=self.max_attempts)
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="growwise-background-ai-worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.0)

    def submit_observation(self, *, child_id: str, log_id: str) -> Job:
        job = self.queue.enqueue(
            OBSERVATION_ENRICHMENT_JOB,
            {"child_id": child_id, "log_id": log_id},
        )
        self._wake.set()
        return job

    def submit_material(self, *, child_id: str, material_id: str) -> Job:
        job = self.queue.enqueue(
            MATERIAL_ENHANCEMENT_JOB,
            {"child_id": child_id, "material_id": material_id},
        )
        self._wake.set()
        return job

    def _run(self) -> None:
        while not self._stop.is_set():
            job = self.queue.claim_next(
                job_types=_TEXT_JOB_TYPES,
                lease_seconds=self.lease_seconds,
                max_attempts=self.max_attempts,
            )
            if job is None:
                self._wake.wait(timeout=self.poll_interval_seconds)
                self._wake.clear()
                continue
            with suppress(Exception):
                self._process(job)

    def _process(self, job: Job) -> None:
        try:
            if job.job_type == OBSERVATION_ENRICHMENT_JOB:
                self._enrich_observation(job)
            elif job.job_type == MATERIAL_ENHANCEMENT_JOB:
                self._enhance_material(job)
            else:
                self.queue.fail(job.id, f"unknown background AI job type: {job.job_type}")
                return
            self.queue.complete(job.id)
        except KeyError:
            # The child/entity may have been intentionally purged while a job was pending.
            self.queue.cancel(job.id)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if job.attempts < self.max_attempts:
                self._mark_retryable(job, error)
                self.queue.retry(job.id, error)
                sleep(min(5.0, max(0.5, self.poll_interval_seconds * 2)))
            else:
                self._mark_failed(job)
                self.queue.fail(job.id, error)

    def _enrich_observation(self, job: Job) -> None:
        child_id = str(job.payload.get("child_id", "")).strip()
        log_id = str(job.payload.get("log_id", "")).strip()
        if not child_id or not log_id:
            raise ValueError("observation enrichment payload is incomplete")

        store = self.store_factory()
        payload = store.index.get_entity(log_id, entity_type="learning_log")
        if payload is None:
            raise KeyError("learning_log_not_found")
        log = LearningLog.model_validate(payload)
        if str(log.child_id) != child_id:
            raise ValueError("observation enrichment child scope mismatch")

        provider = self.provider_factory()
        if provider is None:
            log.ai_status = AiEnhancementStatus.SKIPPED
            log.updated_at = datetime.now(UTC)
            store.save(log)
            return

        log.ai_status = AiEnhancementStatus.RUNNING
        log.ai_job_id = job.id
        log.updated_at = datetime.now(UTC)
        store.save(log)
        self.queue.heartbeat(job.id, lease_seconds=self.lease_seconds)

        with BACKGROUND_AI_LOCK:
            enrichment = ObservationEnricher(provider).enrich(log.parent_observation)

        # Parent-entered structured values win. AI only fills gaps and adds non-destructive tags/
        # experience axes so delayed enrichment cannot overwrite intentional manual data.
        log.tags = list(dict.fromkeys([*log.tags, *enrichment.tags]))
        log.experience_axes = list(
            dict.fromkeys([*log.experience_axes, *enrichment.experience_axes])
        )
        log.interest = log.interest or enrichment.interest
        log.difficulty_note = log.difficulty_note or enrichment.difficulty_note
        log.next_activity = log.next_activity or enrichment.next_activity
        log.ai_status = AiEnhancementStatus.COMPLETED
        log.updated_at = datetime.now(UTC)
        store.save(log)

    def _enhance_material(self, job: Job) -> None:
        child_id = str(job.payload.get("child_id", "")).strip()
        material_id = str(job.payload.get("material_id", "")).strip()
        if not child_id or not material_id:
            raise ValueError("material enhancement payload is incomplete")

        store = self.store_factory()
        payload = store.index.get_entity(material_id, entity_type="generated_material")
        if payload is None:
            raise KeyError("material_not_found")
        material = GeneratedMaterial.model_validate(payload)
        if str(material.child_id) != child_id:
            raise ValueError("material enhancement child scope mismatch")
        if material.status not in {MaterialStatus.DRAFT, MaterialStatus.REVIEW_PENDING}:
            material.ai_status = AiEnhancementStatus.SKIPPED
            material.updated_at = datetime.now(UTC)
            store.save(material)
            return

        child_payload = store.index.get_entity(child_id, entity_type="child_profile")
        if child_payload is None:
            raise KeyError("child_not_found")
        child = ChildProfile.model_validate(child_payload)
        provider = self.provider_factory()
        if provider is None:
            material.ai_status = AiEnhancementStatus.SKIPPED
            material.updated_at = datetime.now(UTC)
            store.save(material)
            return

        material.ai_status = AiEnhancementStatus.RUNNING
        material.ai_job_id = job.id
        material.updated_at = datetime.now(UTC)
        store.save(material)
        self.queue.heartbeat(job.id, lease_seconds=self.lease_seconds)

        evidence = self._material_source_evidence(material=material, store=store)
        with BACKGROUND_AI_LOCK:
            candidate = MaterialGenerationService(provider=provider).generate(
                child=child,
                kind=material.kind,
                topic=material.request_topic or material.title,
                goal=material.request_goal,
                source_refs=material.source_refs,
                source_evidence=evidence,
            )
        if candidate.generator_mode == "template_fallback":
            raise RuntimeError("material model generation failed")

        # Re-read after inference. A parent may have approved/rejected/edited the material while the
        # model was running; background work must never mutate a record after that decision.
        current_payload = store.index.get_entity(material_id, entity_type="generated_material")
        if current_payload is None:
            raise KeyError("material_not_found")
        current = GeneratedMaterial.model_validate(current_payload)
        if current.status not in {MaterialStatus.DRAFT, MaterialStatus.REVIEW_PENDING}:
            current.ai_status = AiEnhancementStatus.SKIPPED
            current.updated_at = datetime.now(UTC)
            store.save(current)
            return

        if current.parent_material_id is None:
            current.title = candidate.title
        current.content_markdown = candidate.content_markdown
        current.parent_guide_markdown = candidate.parent_guide_markdown
        current.source_refs = candidate.source_refs
        current.curriculum_targets = candidate.curriculum_targets
        current.generator_mode = candidate.generator_mode
        current.ai_status = AiEnhancementStatus.COMPLETED
        current.updated_at = datetime.now(UTC)
        store.save(current)

    @staticmethod
    def _material_source_evidence(
        *, material: GeneratedMaterial, store: EntityStore
    ) -> list[MaterialSourceEvidence]:
        evidence: list[MaterialSourceEvidence] = []
        for ref in material.source_refs:
            if not ref.startswith("resource:"):
                continue
            payload = store.index.get_entity(ref.removeprefix("resource:"), entity_type="resource")
            if payload is None:
                continue
            resource = ResourceRecord.model_validate(payload)
            parts: list[str] = []
            if resource.summary:
                parts.append(f"요약: {resource.summary.strip()}")
            if resource.content:
                content = resource.content.strip()
                if content and content != (resource.summary or "").strip():
                    parts.append(f"내용: {content}")
            evidence.append(
                MaterialSourceEvidence(
                    source_ref=ref,
                    title=resource.title,
                    excerpt="\n\n".join(parts)[:_MATERIAL_SOURCE_EXCERPT_CHARS],
                )
            )
        return evidence

    def _mark_retryable(self, job: Job, _error: str) -> None:
        store = self.store_factory()
        if job.job_type == OBSERVATION_ENRICHMENT_JOB:
            entity_id = str(job.payload.get("log_id", ""))
            payload = store.index.get_entity(entity_id, entity_type="learning_log")
            if payload is not None:
                log = LearningLog.model_validate(payload)
                log.ai_status = AiEnhancementStatus.QUEUED
                log.updated_at = datetime.now(UTC)
                store.save(log)
        elif job.job_type == MATERIAL_ENHANCEMENT_JOB:
            entity_id = str(job.payload.get("material_id", ""))
            payload = store.index.get_entity(entity_id, entity_type="generated_material")
            if payload is not None:
                material = GeneratedMaterial.model_validate(payload)
                material.ai_status = AiEnhancementStatus.QUEUED
                material.updated_at = datetime.now(UTC)
                store.save(material)

    def _mark_failed(self, job: Job) -> None:
        store = self.store_factory()
        if job.job_type == OBSERVATION_ENRICHMENT_JOB:
            entity_id = str(job.payload.get("log_id", ""))
            payload = store.index.get_entity(entity_id, entity_type="learning_log")
            if payload is not None:
                log = LearningLog.model_validate(payload)
                log.ai_status = AiEnhancementStatus.FAILED
                log.updated_at = datetime.now(UTC)
                store.save(log)
        elif job.job_type == MATERIAL_ENHANCEMENT_JOB:
            entity_id = str(job.payload.get("material_id", ""))
            payload = store.index.get_entity(entity_id, entity_type="generated_material")
            if payload is not None:
                material = GeneratedMaterial.model_validate(payload)
                material.ai_status = AiEnhancementStatus.FAILED
                material.updated_at = datetime.now(UTC)
                store.save(material)
