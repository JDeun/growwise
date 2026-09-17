from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from enum import IntEnum


class TemporalTier(IntEnum):
    CURRENT_MONTH = 0
    CURRENT_YEAR = 1
    ARCHIVE = 2
    UNKNOWN = 3


def _as_date(value: str | datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.date()
    if isinstance(value, date):
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        try:
            return date.fromisoformat(value[:10])
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return parsed.date()


def temporal_tier(
    value: str | datetime | date | None,
    *,
    reference_date: date | None = None,
) -> TemporalTier:
    """Classify evidence into month -> year -> archive tiers.

    ``reference_date`` is injectable for deterministic tests. Production callers default to the
    desktop host's local calendar date because GrowWise's time-oriented queries are parent-facing
    ("이번 달", "올해") rather than UTC infrastructure windows.
    """

    target = _as_date(value)
    if target is None:
        return TemporalTier.UNKNOWN
    reference = reference_date or date.today()
    if target.year == reference.year and target.month == reference.month:
        return TemporalTier.CURRENT_MONTH
    if target.year == reference.year:
        return TemporalTier.CURRENT_YEAR
    return TemporalTier.ARCHIVE


def hierarchical_temporal_order[T](
    items: Iterable[T],
    *,
    timestamp: Callable[[T], str | datetime | date | None],
    limit: int,
    reference_date: date | None = None,
) -> list[T]:
    """Preserve relevance order inside each temporal tier, then fill month/year/archive.

    Callers should pass items already ordered by semantic/lexical relevance. This function does
    not replace relevance ranking; it provides a deterministic temporal navigation layer on top.
    Unknown timestamps are last so unparseable metadata can never silently outrank dated evidence.
    """

    if limit <= 0:
        return []
    buckets: dict[TemporalTier, list[T]] = {tier: [] for tier in TemporalTier}
    for item in items:
        buckets[temporal_tier(timestamp(item), reference_date=reference_date)].append(item)

    ordered: list[T] = []
    for tier in TemporalTier:
        remaining = limit - len(ordered)
        if remaining <= 0:
            break
        ordered.extend(buckets[tier][:remaining])
    return ordered
