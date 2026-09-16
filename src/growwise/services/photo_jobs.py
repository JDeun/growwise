from __future__ import annotations

import threading
from collections.abc import Callable
from time import sleep
from uuid import UUID

from growwise.jobs import Job, SQLiteJobQueue
from growwise.services.photo_activity import PhotoActivityService

PHOTO_ANALYSIS_JOB = "photo_activity_analysis"


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
            self._process(job)

    def _process(self, job: Job) -> None:
        record_id = str(job.payload.get("record_id", "")).strip()
        child_id = str(job.payload.get("child_id", "")).strip()
        if not record_id or not child_id:
            self.queue.fail(job.id, "photo job payload is incomplete")
            return

        service = self.service_factory()
        try:
            record = service.get_record(record_id)
            if str(record.child_id) != child_id:
                raise ValueError("photo job child scope mismatch")
            self.queue.heartbeat(job.id, lease_seconds=self.lease_seconds)
            service.process_draft(record_id)
            self.queue.complete(job.id)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if job.attempts < self.max_attempts:
                try:
                    service.mark_queued(record_id, error=error)
                finally:
                    self.queue.retry(job.id, error)
                # Avoid a tight retry loop when Ollama is temporarily unavailable.
                sleep(min(2.0, self.poll_interval_seconds))
                return
            try:
                service.mark_failed(record_id, error)
            finally:
                self.queue.fail(job.id, error)
