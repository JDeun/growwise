from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from time import sleep

from growwise.domain.models import EntityBase
from growwise.jobs import Job, SQLiteJobQueue
from growwise.services.background_ai_lock import BACKGROUND_AI_LOCK
from growwise.services.photo_activity import PhotoActivityService
from growwise.storage import EntityStore

PHOTO_ANALYSIS_JOB = "photo_activity_analysis"


class _StalePhotoJobClaim(RuntimeError):
    pass


class _ClaimFencedEntityStore(EntityStore):
    """Delegate EntityStore mutations only while the worker still owns its queue lease."""

    def __init__(self, delegate: EntityStore, claim_guard: Callable[[], bool]) -> None:
        self._delegate = delegate
        self._claim_guard = claim_guard
        # Read paths inside PhotoActivityService access these attributes directly.
        self.markdown = delegate.markdown
        self.index = delegate.index

    def _require_claim(self) -> None:
        if not self._claim_guard():
            raise _StalePhotoJobClaim("photo job claim is stale")

    @contextmanager
    def mutation_window(self) -> Iterator[None]:
        self._require_claim()
        with self._delegate.mutation_window():
            self._require_claim()
            yield

    def save(self, entity: EntityBase, body: str = "") -> Path:
        self._require_claim()
        return self._delegate.save(entity, body=body)

    def delete(self, entity: EntityBase) -> bool:
        self._require_claim()
        return self._delegate.delete(entity)

    def purge_child(self, child_id: str) -> int:
        self._require_claim()
        return self._delegate.purge_child(child_id)


class PhotoJobRunner:
    """Single-consumer local worker for slow photo AI processing.

    Serial execution is intentional. Consumer machines often have limited unified memory or VRAM,
    and running multiple multimodal generations concurrently can make every task slower or trigger
    out-of-memory failures. Uploaded bytes already live in managed asset storage; queue payloads
    contain only identifiers.
    """

    def __init__(
        self,
        *,
        queue: SQLiteJobQueue,
        service_factory: Callable[[], PhotoActivityService],
        lease_seconds: int,
        max_attempts: int,
        poll_interval_seconds: float,
    ) -> None:
        self.queue = queue
        self.service_factory = service_factory
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
            self.queue.recover_running(
                job_type=PHOTO_ANALYSIS_JOB,
                max_attempts=self.max_attempts,
            )
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="growwise-photo-worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None:
            # Model calls are intentionally not force-cancelled. The daemon thread may still be
            # inside Ollama when process shutdown proceeds; startup recovery will reclaim the job.
            thread.join(timeout=1.0)

    def submit(self, *, child_id: str, record_id: str) -> Job:
        job = self.queue.enqueue(
            PHOTO_ANALYSIS_JOB,
            {"child_id": child_id, "record_id": record_id},
        )
        self._wake.set()
        return job

    def _run(self) -> None:
        while not self._stop.is_set():
            job = self.queue.claim_next(
                job_types=(PHOTO_ANALYSIS_JOB,),
                lease_seconds=self.lease_seconds,
                max_attempts=self.max_attempts,
            )
            if job is None:
                self._wake.wait(timeout=self.poll_interval_seconds)
                self._wake.clear()
                continue
            # A malformed record, concurrent child purge, or status-write failure must not kill the
            # only worker thread. _process records/cancels the job wherever possible.
            with suppress(Exception):
                self._process(job)

    def _process(self, job: Job) -> None:
        claim_token = job.claim_token
        if not claim_token:
            # claim_next always assigns a token. A tokenless RUNNING job is legacy/corrupt state and
            # must never be allowed to mutate records without a fencing identity.
            self.queue.cancel(job.id)
            return

        def renew_claim() -> bool:
            return self.queue.heartbeat(
                job.id,
                claim_token,
                lease_seconds=self.lease_seconds,
            )

        record_id = str(job.payload.get("record_id", "")).strip()
        child_id = str(job.payload.get("child_id", "")).strip()
        if not record_id or not child_id:
            self.queue.fail(job.id, claim_token, "photo job payload is incomplete")
            return

        service = self.service_factory()
        original_store = service.store
        service.store = _ClaimFencedEntityStore(original_store, renew_claim)
        try:
            self._process_with_claim(
                job=job,
                claim_token=claim_token,
                renew_claim=renew_claim,
                service=service,
                record_id=record_id,
                child_id=child_id,
            )
        finally:
            # Factories may intentionally return a shared service in tests or local callers.
            # Never leak a completed job's fencing token into later synchronous mutations.
            service.store = original_store

    def _process_with_claim(
        self,
        *,
        job: Job,
        claim_token: str,
        renew_claim: Callable[[], bool],
        service: PhotoActivityService,
        record_id: str,
        child_id: str,
    ) -> None:
        try:
            record = service.get_record(record_id)
            if str(record.child_id) != child_id:
                raise ValueError("photo job child scope mismatch")
            if not renew_claim():
                return
            # Share one background-only execution lane with text enrichment/material generation so
            # slow multimodal and text jobs do not compete for consumer VRAM/unified memory.
            with BACKGROUND_AI_LOCK:
                if not renew_claim():
                    return
                service.process_draft(record_id)
            self.queue.complete(job.id, claim_token)
            return
        except KeyError:
            # The most common reason is an intentional child purge while slow inference was still
            # running. The job row may already have been deleted; cancel is therefore best-effort.
            self.queue.cancel(job.id)
            return
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        if job.attempts < self.max_attempts:
            # Do not let an expired/reclaimed worker rewrite the domain record back to queued.
            if not renew_claim():
                return
            with suppress(Exception):
                service.mark_queued(record_id, error=error)
            self.queue.retry(job.id, claim_token, error)
            # Avoid a tight retry loop when Ollama is temporarily unavailable.
            sleep(min(5.0, max(1.0, self.poll_interval_seconds * 2)))
            return

        # AI is an enhancement, not a persistence dependency. After bounded retries, disable both
        # providers and turn the already-saved photos/parent note into a deterministic editable
        # draft. Only a failure in that local fallback is allowed to mark the record itself failed.
        try:
            if not renew_claim():
                return
            service.text_provider = None
            service.vision_provider = None
            service.mark_queued(record_id, error=error)
            service.process_draft(record_id)
            self.queue.complete(job.id, claim_token)
        except KeyError:
            self.queue.cancel(job.id)
        except Exception as fallback_exc:
            fallback_error = f"{type(fallback_exc).__name__}: {fallback_exc}"
            # A stale worker has no authority to mark the source record failed.
            if not renew_claim():
                return
            with suppress(Exception):
                service.mark_failed(record_id, fallback_error)
            self.queue.fail(job.id, claim_token, fallback_error)
