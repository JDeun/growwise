import pytest

from growwise.domain import WorkflowRun, WorkflowStatus
from growwise.services import (
    InvalidWorkflowTransition,
    WorkflowPolicy,
    WorkflowRunService,
)


def make_run() -> WorkflowRun:
    return WorkflowRun(
        child_id="01900000-0000-7000-8000-000000000001",
        workflow_type="test",
        thread_id="thread-1",
    )


def test_failed_workflow_can_retry_with_bounded_attempt_budget():
    service = WorkflowRunService(WorkflowPolicy(max_attempts=2))
    run = make_run()

    service.fail(run, error_code="transient")
    service.retry(run)

    assert run.status is WorkflowStatus.RUNNING
    assert run.attempt_count == 2
    service.fail(run, error_code="again")
    with pytest.raises(InvalidWorkflowTransition, match="budget exhausted"):
        service.retry(run)


def test_cancelled_workflow_is_terminal():
    service = WorkflowRunService()
    run = make_run()

    service.cancel(run)

    assert run.status is WorkflowStatus.CANCELLED
    assert service.should_stop(run)
    with pytest.raises(InvalidWorkflowTransition):
        service.complete(run)
