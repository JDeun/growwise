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

    SKIPPED is intentionally reversible and never treated as failure. Lifecycle timestamps are
    factual activity metadata only; they are not used for child scores, streaks, or penalties.
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

        now = datetime.now(UTC)
        activity.status = target
        activity.parent_note = parent_note
        activity.updated_at = now
        if target is ActivityStatus.ACTIVE and activity.started_at is None:
            activity.started_at = now
        elif target is ActivityStatus.COMPLETED:
            activity.completed_at = now
        elif target is ActivityStatus.SKIPPED:
            activity.skipped_at = now
        return activity
