from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException

from growwise.jobs import JobStatus, SQLiteJobQueue, utc_now_iso


class MaintenanceInProgress(HTTPException):
    """Signal a concurrent exclusive maintenance request."""

    def __init__(self, message: str = "data maintenance is in progress") -> None:
        super().__init__(
            status_code=503,
            detail="data_maintenance_in_progress",
            headers={"Retry-After": "1"},
        )
        self.message = message


class StaleDataGeneration(HTTPException):
    """Signal work that must be retried against the current restored data generation."""

    def __init__(self, message: str = "data generation changed") -> None:
        super().__init__(
            status_code=503,
            detail="stale_data_generation",
            headers={"Retry-After": "1"},
        )
        self.message = message


class DataMaintenanceCoordinator:
    """Quiesce source mutations for backup/restore without serializing normal writes.

    Normal mutation windows register as active readers. Maintenance marks itself active first and
    waits for mutations that already started to finish. New mutations wait behind maintenance. If a
    destructive restore advances the data generation, those waiting callers are rejected as stale
    instead of applying an operation that was prepared against the pre-restore state.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._maintenance_active = False
        self._active_mutations = 0
        self._generation = 0
        self._local = threading.local()

    def _mutation_depth(self) -> int:
        return int(getattr(self._local, "mutation_depth", 0))

    @property
    def active(self) -> bool:
        with self._condition:
            return self._maintenance_active

    @property
    def generation(self) -> int:
        with self._condition:
            return self._generation

    def bind_current_generation(self) -> None:
        """Fence subsequent mutations on this worker thread to the current data generation."""
        with self._condition:
            self._local.bound_generation = self._generation

    def clear_bound_generation(self) -> None:
        if hasattr(self._local, "bound_generation"):
            del self._local.bound_generation

    def _require_current_generation(self, expected_generation: int | None) -> None:
        bound_generation = getattr(self._local, "bound_generation", None)
        current = self._generation
        if expected_generation is not None and expected_generation != current:
            raise StaleDataGeneration("entity store belongs to a stale data generation")
        if bound_generation is not None and bound_generation != current:
            raise StaleDataGeneration("worker belongs to a stale data generation")

    @contextmanager
    def mutation(self, *, expected_generation: int | None = None) -> Iterator[None]:
        depth = self._mutation_depth()
        if depth > 0:
            self._require_current_generation(expected_generation)
            self._local.mutation_depth = depth + 1
            try:
                yield
            finally:
                self._local.mutation_depth = depth
            return

        with self._condition:
            while self._maintenance_active:
                self._condition.wait()
            self._require_current_generation(expected_generation)
            self._active_mutations += 1
        self._local.mutation_depth = 1
        try:
            yield
        finally:
            self._local.mutation_depth = 0
            with self._condition:
                self._active_mutations -= 1
                if self._active_mutations == 0:
                    self._condition.notify_all()

    @contextmanager
    def maintenance(self, *, invalidate_generation: bool = False) -> Iterator[None]:
        if self._mutation_depth() > 0:
            raise RuntimeError("cannot start maintenance from inside a data mutation")
        with self._condition:
            if self._maintenance_active:
                raise MaintenanceInProgress("data maintenance is already in progress")
            self._maintenance_active = True
            while self._active_mutations:
                self._condition.wait()
        try:
            yield
        finally:
            with self._condition:
                if invalidate_generation:
                    self._generation += 1
                self._maintenance_active = False
                self._condition.notify_all()


DATA_MAINTENANCE = DataMaintenanceCoordinator()


class MaintenanceAwareJobQueue(SQLiteJobQueue):
    """Job queue that couples successful leases to the active data generation."""

    def heartbeat(
        self,
        job_id: UUID,
        claim_token: str,
        *,
        lease_seconds: int = 3600,
        now: datetime | None = None,
    ) -> bool:
        renewed = super().heartbeat(
            job_id,
            claim_token,
            lease_seconds=lease_seconds,
            now=now,
        )
        if renewed:
            DATA_MAINTENANCE.bind_current_generation()
        return renewed

    def cancel_active(
        self,
        *,
        job_types: tuple[str, ...],
        reason: str = "job cancelled because active data was restored",
    ) -> int:
        """Cancel queued/running work whose payload belongs to the pre-restore data generation."""
        if not job_types:
            return 0
        now = utc_now_iso()
        placeholders = ",".join("?" for _ in job_types)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, last_error = ?,
                    lease_expires_at = NULL, claim_token = NULL
                WHERE status IN (?, ?) AND job_type IN ({placeholders})
                """,
                (
                    JobStatus.CANCELLED,
                    now,
                    now,
                    reason[:2000],
                    JobStatus.PENDING,
                    JobStatus.RUNNING,
                    *job_types,
                ),
            )
        return cursor.rowcount
