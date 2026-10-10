"""Reusable, filterable iterator for scheduled study sessions.

Provides deterministic, chronological traversal of study sessions with optional
filtering by date, date range, task ID, and subject code.
"""

from collections.abc import Iterator, Sequence
from datetime import date

from scholarsync.models.schedule import ScheduledSession


class ScheduleTimelineIterator(Iterator[ScheduledSession]):
    """Iterator for traversing scheduled study sessions in strict chronological order.

    Supports optional pre-filtering by calendar date, date interval, task ID,
    subject code, and minimum duration.

    Example:
        >>> iterator = ScheduleTimelineIterator(result.sessions, task_id="T01")
        >>> for session in iterator:
        ...     print(session)
    """

    def __init__(
        self,
        sessions: Sequence[ScheduledSession],
        target_date: date | None = None,
        date_range: tuple[date, date] | None = None,
        task_id: str | None = None,
        subject_code: str | None = None,
        min_duration_hours: float | None = None,
    ) -> None:
        filtered: list[ScheduledSession] = []

        # Validate date range if provided
        if date_range is not None and date_range[0] > date_range[1]:
            raise ValueError(
                f"Invalid date_range: start ({date_range[0]}) is after end ({date_range[1]})."
            )

        clean_task_id = task_id.strip() if task_id is not None else None
        clean_subj_code = subject_code.strip().upper() if subject_code is not None else None

        for session in sessions:
            slot_d = session.slot.slot_date

            # Date filter
            if target_date is not None and slot_d != target_date:
                continue

            # Date range filter (inclusive)
            if date_range is not None and not (date_range[0] <= slot_d <= date_range[1]):
                continue

            # Task ID filter
            if clean_task_id is not None and session.task_id != clean_task_id:
                continue

            # Subject code filter
            if clean_subj_code is not None and session.subject_code != clean_subj_code:
                continue

            # Minimum duration filter
            if min_duration_hours is not None and session.hours < min_duration_hours:
                continue

            filtered.append(session)

        # Sort filtered sessions deterministically in chronological order
        filtered.sort(
            key=lambda s: (
                s.slot.slot_date,
                s.slot.start_hour,
                s.task_id,
            )
        )

        self._items: tuple[ScheduledSession, ...] = tuple(filtered)
        self._index: int = 0

    def __iter__(self) -> "ScheduleTimelineIterator":
        """Return the iterator instance itself."""
        return self

    def __next__(self) -> ScheduledSession:
        """Return the next chronologically ordered ScheduledSession."""
        if self._index >= len(self._items):
            raise StopIteration
        session = self._items[self._index]
        self._index += 1
        return session

    def __len__(self) -> int:
        """Return the number of unconsumed sessions remaining in the iterator."""
        return max(0, len(self._items) - self._index)

    def __reversed__(self) -> Iterator[ScheduledSession]:
        """Support reverse chronological traversal using reversed()."""
        return iter(reversed(self._items))

    def peek(self) -> ScheduledSession | None:
        """Inspect the next session without advancing the iterator position."""
        if self._index < len(self._items):
            return self._items[self._index]
        return None

    def has_next(self) -> bool:
        """Return True if there are remaining sessions to yield."""
        return self._index < len(self._items)

    def reset(self) -> None:
        """Reset the iterator position back to the beginning."""
        self._index = 0

    def to_list(self) -> list[ScheduledSession]:
        """Consume and return all remaining sessions as a list."""
        remaining = list(self._items[self._index :])
        self._index = len(self._items)
        return remaining
