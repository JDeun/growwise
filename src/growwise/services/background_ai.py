from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from contextlib import nullcontext, suppress
from datetime import UTC, datetime
from time import sleep

from growwise.domain import (
    AiEnhancementStatus,
    ChildProfile,
    GeneratedMaterial,
    LearningLog,
    MaterialStatus,
    ResourceRecord,
)
from growwise.generators import MaterialGenerationService, MaterialSourceEvidence
from growwise.jobs import Job, JobStatus, SQLiteJobQueue
from growwise.material_versions import material_mutation
from growwise.model import ModelProvider
from growwise.model.privacy import provider_is_loopback
from growwise.services.background_ai_lock import BACKGROUND_AI_LOCK
from growwise.services.learning_wiki import LearningWikiService
from growwise.services.material_feedback import MaterialFeedbackService
from growwise.services.observation import ObservationEnricher
from growwise.services.visibility import entity_visible_to_child
from growwise.storage import EntityStore

OBSERVATION_ENRICHMENT_JOB = "observation_enrichment"
MATERIAL_ENHANCEMENT_JOB = "material_enhancement"
_TEXT_JOB_TYPES = (OBSERVATION_ENRICHMENT_JOB, MATERIAL_ENHANCEMENT_JOB)
_MATERIAL_SOURCE_EXCERPT_CHARS = 4_000
logger = logging.getLogger(__name__)


class StaleJobClaim(RuntimeError):
    """Raised when a worker no longer owns the durable job attempt it started with."""


class BackgroundAiJobRunner:
    """Single-consumer durable worker for non-interactive text-model work.

    Parent-authored/source-of-truth records are persisted before jobs are submitted. This runner may
    enrich them later, but a failed or unavailable model never invalidates the already-saved Core
    record. Interactive chat/search intentionally remains outside this worker.

    Every claimed attempt is fenced by a unique queue token. Long-running inference renews and
    revalidates that token before writing model output, so an expired worker cannot overwrite a
    newer attempt after its lease has been reclaimed.
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
        self._submission_guard = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._guard:
            if self._thread is not None and self._thread.is_alive():
                return
            for job_type in _TEXT_JOB_TYPES:
                self.queue.recover_running(job_type=job_type, max_attempts=self.max_attempts)
            self._recover_source_statuses()
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="growwise-background-ai-worker",
                daemon=True,
            )
            self._thread.start()

    def _recover_source_statuses(self) -> None:
        store = self.store_factory()
        after_id = ""
        while payloads := store.index.pending_ai_entities(after_id=after_id):
            after_id = str(payloads[-1]["id"])
            for payload in payloads:
                entity = (GeneratedMaterial.model_validate(payload)
                          if payload["entity_type"] == "generated_material"
                          else LearningLog.model_validate(payload))
                lock = (material_mutation(entity.id) if isinstance(entity, GeneratedMaterial)
                        else nullcontext())
                with lock:
                    latest = store.index.get_entity(str(entity.id))
                    if latest is None:
                        continue
                    if payload["entity_type"] == "generated_material":
                        entity = GeneratedMaterial.model_validate(latest)
                        job_type, resource_key = MATERIAL_ENHANCEMENT_JOB, "material_id"
                    else:
                        entity = LearningLog.model_validate(latest)
                        job_type, resource_key = OBSERVATION_ENRICHMENT_JOB, "log_id"
                    job = self.queue.get(entity.ai_job_id) if entity.ai_job_id is not None else None
                    valid_job = (
                        job is not None and job.job_type == job_type
                        and str(job.payload.get(resource_key)) == str(entity.id)
                        and str(job.payload.get("child_id")) == str(entity.child_id)
                    )
                    status = AiEnhancementStatus.FAILED
                    if valid_job and job is not None:
                        status = {
                            JobStatus.PENDING: AiEnhancementStatus.QUEUED,
                            JobStatus.RUNNING: AiEnhancementStatus.RUNNING,
                            JobStatus.COMPLETED: AiEnhancementStatus.COMPLETED,
                            JobStatus.CANCELLED: AiEnhancementStatus.SKIPPED,
                            JobStatus.FAILED: AiEnhancementStatus.FAILED,
                        }[job.status]
                    if isinstance(entity, GeneratedMaterial) and entity.status not in {
                        MaterialStatus.DRAFT, MaterialStatus.REVIEW_PENDING,
                    }:
                        status = AiEnhancementStatus.SKIPPED
                    if status is not entity.ai_status:
                        entity.ai_status = status
                        entity.updated_at = datetime.now(UTC)
                        store.save(entity)

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.0)

    def submit_observation(
        self,
        *,
        child_id: str,
        log_id: str,
        on_enqueued: Callable[[Job], None] | None = None,
    ) -> Job:
        with self._submission_guard:
            job = self.queue.enqueue(
                OBSERVATION_ENRICHMENT_JOB,
                {"child_id": child_id, "log_id": log_id},
            )
            try:
                if on_enqueued is not None:
                    on_enqueued(job)
            except Exception:
                self.queue.cancel(job.id)
                raise
        self._wake.set()
        return job

    def submit_material(
        self,
        *,
        child_id: str,
        material_id: str,
        on_enqueued: Callable[[Job], None] | None = None,
    ) -> Job:
        with self._submission_guard:
            job = self.queue.enqueue(
                MATERIAL_ENHANCEMENT_JOB,
                {"child_id": child_id, "material_id": material_id},
            )
            try:
                if on_enqueued is not None:
                    on_enqueued(job)
            except Exception:
                self.queue.cancel(job.id)
                raise
        self._wake.set()
        return job

    @staticmethod
    def _claim_token(job: Job) -> str:
        if not job.claim_token:
            raise StaleJobClaim("background job has no active claim token")
        return job.claim_token

    def _renew_claim(self, job: Job) -> str:
        if self._stop.is_set():
            raise StaleJobClaim("background worker stopped")
        token = self._claim_token(job)
        if not self.queue.heartbeat(
            job.id,
            token,
            lease_seconds=self.lease_seconds,
        ):
            raise StaleJobClaim("background job claim is no longer current")
        return token

    def _heartbeat(self, job: Job, finished: threading.Event) -> None:
        interval = min(30.0, max(0.1, self.lease_seconds / 3))
        while not finished.wait(interval) and not self._stop.is_set():
            try:
                self._renew_claim(job)
            except StaleJobClaim:
                return
            except Exception:
                logger.warning("background AI lease heartbeat temporarily unavailable")

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._submission_guard:
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
        token = self._claim_token(job)
        finished = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat,
            args=(job, finished),
            name="growwise-ai-job-heartbeat",
            daemon=True,
        )
        heartbeat.start()
        try:
            if job.job_type == OBSERVATION_ENRICHMENT_JOB:
                self._enrich_observation(job)
            elif job.job_type == MATERIAL_ENHANCEMENT_JOB:
                self._enhance_material(job)
            else:
                self.queue.fail(
                    job.id,
                    token,
                    f"unknown background AI job type: {job.job_type}",
                )
                return
            self.queue.complete(job.id, token)
        except StaleJobClaim:
            # Another worker owns the reclaimed attempt. Never mutate its durable queue state.
            return
        except KeyError:
            # The child/entity may have been intentionally purged while a job was pending. Use a
            # fenced terminal transition so a stale worker cannot cancel a newer reclaimed attempt.
            self.queue.fail(job.id, token, "source entity removed while background job was running")
        except Exception as exc:
            # Provider errors can include credential-bearing URLs or private prompt fragments.
            error = f"{type(exc).__name__}: background AI enhancement failed"
            try:
                self._renew_claim(job)
                if job.attempts < self.max_attempts:
                    self._mark_retryable(job, error)
                    if self.queue.retry(job.id, token, error):
                        sleep(min(5.0, max(0.5, self.poll_interval_seconds * 2)))
                else:
                    self._mark_failed(job)
                    self.queue.fail(job.id, token, error)
            except StaleJobClaim:
                return
        finally:
            finished.set()
            heartbeat.join(timeout=1.0)

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
            self._renew_claim(job)
            log.ai_status = AiEnhancementStatus.SKIPPED
            log.updated_at = datetime.now(UTC)
            store.save(log)
            return

        self._renew_claim(job)
        log.ai_status = AiEnhancementStatus.RUNNING
        log.ai_job_id = job.id
        log.updated_at = datetime.now(UTC)
        store.save(log)

        with BACKGROUND_AI_LOCK:
            enrichment = ObservationEnricher(provider).enrich(log.parent_observation)

        # The model call may outlive the original lease. Revalidate ownership before any generated
        # content is allowed to reach the source-of-truth record.
        self._renew_claim(job)

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
            self._mark_material_status(job, AiEnhancementStatus.SKIPPED)
            return

        child_payload = store.index.get_entity(child_id, entity_type="child_profile")
        if child_payload is None:
            raise KeyError("child_not_found")
        child = ChildProfile.model_validate(child_payload)
        provider = self.provider_factory()
        if provider is None:
            self._mark_material_status(job, AiEnhancementStatus.SKIPPED)
            return

        current = self._mark_material_status(job, AiEnhancementStatus.RUNNING)
        if current is None or current.ai_status is not AiEnhancementStatus.RUNNING:
            return
        material = current

        evidence = self._material_source_evidence(material=material, store=store)
        feedback = MaterialFeedbackService(store.index).snapshot(child_id=child_id)
        guidance_parts: list[str] = []
        if material.version_note and material.version_note.strip():
            guidance_parts.append(f"부모 수정 요청: {material.version_note.strip()}")
        feedback_guidance = feedback.generation_guidance()
        if feedback_guidance:
            guidance_parts.append(feedback_guidance)
        if provider_is_loopback(provider):
            try:
                wiki = LearningWikiService(store).refresh(child_id)
                guidance_parts.append(wiki.content_markdown[:6_000])
            except Exception:
                logger.warning("Learning Wiki unavailable; retaining material fallback context")
        generation_guidance = "\n".join(guidance_parts) or None

        with BACKGROUND_AI_LOCK:
            candidate = MaterialGenerationService(provider=provider).generate(
                child=child,
                kind=material.kind,
                topic=material.request_topic or material.title,
                goal=material.request_goal,
                generation_guidance=generation_guidance,
                source_refs=material.source_refs,
                source_evidence=evidence,
            )
        if candidate.generator_mode != "llm_enhanced":
            raise RuntimeError(
                f"material enhancement did not pass review: {candidate.generator_mode}"
            )

        # The model call may outlive the original lease. Fence the generated candidate before it can
        # overwrite a record now owned by another retry attempt.
        self._renew_claim(job)

        # Re-read after inference. A parent may have approved/rejected/edited the material while the
        # model was running; background work must never mutate a record after that decision.
        with material_mutation(material.id):
            self._renew_claim(job)
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
            current.parent_guide_markdown = feedback.with_parent_guide(
                candidate.parent_guide_markdown
            )
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
            payload = store.index.get_entity(
                ref.removeprefix("resource:"),
                entity_type="resource",
            )
            if payload is None:
                continue
            if not entity_visible_to_child(
                store.index, entity_id=str(payload["id"]), child_id=str(material.child_id),
                entity_type="resource",
            ):
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
        if job.job_type == OBSERVATION_ENRICHMENT_JOB:
            store = self.store_factory()
            entity_id = str(job.payload.get("log_id", ""))
            payload = store.index.get_entity(entity_id, entity_type="learning_log")
            if payload is not None:
                log = LearningLog.model_validate(payload)
                log.ai_status = AiEnhancementStatus.QUEUED
                log.updated_at = datetime.now(UTC)
                store.save(log)
        elif job.job_type == MATERIAL_ENHANCEMENT_JOB:
            self._mark_material_status(job, AiEnhancementStatus.QUEUED)

    def _mark_failed(self, job: Job) -> None:
        if job.job_type == OBSERVATION_ENRICHMENT_JOB:
            store = self.store_factory()
            entity_id = str(job.payload.get("log_id", ""))
            payload = store.index.get_entity(entity_id, entity_type="learning_log")
            if payload is not None:
                log = LearningLog.model_validate(payload)
                log.ai_status = AiEnhancementStatus.FAILED
                log.updated_at = datetime.now(UTC)
                store.save(log)
        elif job.job_type == MATERIAL_ENHANCEMENT_JOB:
            self._mark_material_status(job, AiEnhancementStatus.FAILED)

    def _mark_material_status(
        self, job: Job, status: AiEnhancementStatus
    ) -> GeneratedMaterial | None:
        store = self.store_factory()
        entity_id = str(job.payload.get("material_id", ""))
        payload = store.index.get_entity(entity_id, entity_type="generated_material")
        if payload is None:
            return None
        material = GeneratedMaterial.model_validate(payload)
        with material_mutation(material.id):
            self._renew_claim(job)
            latest = store.index.get_entity(entity_id, entity_type="generated_material")
            if latest is None:
                return None
            material = GeneratedMaterial.model_validate(latest)
            if str(material.child_id) != str(job.payload.get("child_id")):
                raise ValueError("material enhancement child scope mismatch")
            material.ai_status = (status if material.status in {
                MaterialStatus.DRAFT, MaterialStatus.REVIEW_PENDING,
            } else AiEnhancementStatus.SKIPPED)
            if material.ai_status is AiEnhancementStatus.RUNNING:
                material.ai_job_id = job.id
            material.updated_at = datetime.now(UTC)
            store.save(material)
            return material
