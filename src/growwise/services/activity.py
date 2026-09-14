from __future__ import annotations

from datetime import UTC, datetime

from growwise.domain import ActivityPlan, ActivityStatus


class InvalidActivityTransition(ValueError):
    pass


_ALLOWED: dict[ActivityStatus, set[ActivityStatus]] = {
    ActivityStatus.SUGGESTED: {
        ActivityStatus.ACTIVE,
        ActivityStatus.SKIPPED,
        ActivityStatus.ARCHIVED,
    },
    ActivityStatus.ACTIVE: {
        ActivityStatus.COMPLETED,
        ActivityStatus.SKIPPED,
        ActivityStatus.ARCHIVED,
    },
    ActivityStatus.COMPLETED: {ActivityStatus.ARCHIVED},
    ActivityStatus.SKIPPED: {
        ActivityStatus.ACTIVE,
        ActivityStatus.ARCHIVED,
    },
    ActivityStatus.ARCHIVED: set(),
}


class ActivityPlanService:
    """State transitions for low-pressure activity invitations.

    SKIPPED is intentionally reversible and never treated as failure. Completion timestamps are
    facts for the activity itself, not a child score or streak signal.
    """

    def transition(
        self,
        activity: ActivityPlan,
        target: ActivityStatus,
        *,
        parent_note: str | None = None,
    ) -> ActivityPlan:
        if target not in _ALLOWED[activity.status]:
            raise InvalidActivityTransition(
                f"activity transition {activity.status.value} -> {target.value} is not allowed"
            )

        activity.status = target
        activity.parent_note = parent_note
        activity.updated_at = datetime.now(UTC)
        activity.completed_at = (
            datetime.now(UTC) if target is ActivityStatus.COMPLETED else activity.completed_at
        )
        return activity
