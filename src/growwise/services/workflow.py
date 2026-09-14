from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from growwise.domain import WorkflowRun, WorkflowStatus


class InvalidWorkflowTransition(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkflowPolicy:
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")


class WorkflowRunService:
    """Domain policy for durable workflow retries and cooperative cancellation."""

    TERMINAL = {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.CANCELLED,
    }

    def __init__(self, policy: WorkflowPolicy | None = None) -> None:
        self.policy = policy or WorkflowPolicy()

    def cancel(self, run: WorkflowRun) -> WorkflowRun:
        if run.status in self.TERMINAL:
            raise InvalidWorkflowTransition(f"cannot cancel workflow in {run.status.value}")
        run.status = WorkflowStatus.CANCELLED
        run.updated_at = datetime.now(UTC)
        return run

    def complete(self, run: WorkflowRun, *, output_ref: str | None = None) -> WorkflowRun:
        if run.status is not WorkflowStatus.RUNNING:
            raise InvalidWorkflowTransition(
                f"cannot complete workflow in {run.status.value}"
            )
        run.status = WorkflowStatus.COMPLETED
        run.output_ref = output_ref
        run.last_error_code = None
        run.updated_at = datetime.now(UTC)
        return run

    def fail(self, run: WorkflowRun, *, error_code: str) -> WorkflowRun:
        if run.status is not WorkflowStatus.RUNNING:
            raise InvalidWorkflowTransition(f"cannot fail workflow in {run.status.value}")
        run.status = WorkflowStatus.FAILED
        run.last_error_code = error_code
        run.updated_at = datetime.now(UTC)
        return run

    def retry(self, run: WorkflowRun) -> WorkflowRun:
        if run.status is not WorkflowStatus.FAILED:
            raise InvalidWorkflowTransition(f"cannot retry workflow in {run.status.value}")
        if run.attempt_count >= self.policy.max_attempts:
            raise InvalidWorkflowTransition("workflow retry budget exhausted")
        run.status = WorkflowStatus.RUNNING
        run.attempt_count += 1
        run.last_error_code = None
        run.updated_at = datetime.now(UTC)
        return run

    @staticmethod
    def should_stop(run: WorkflowRun) -> bool:
        return run.status is WorkflowStatus.CANCELLED
