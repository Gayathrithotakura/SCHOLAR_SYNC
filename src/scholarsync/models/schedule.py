"""Schedule result models representing generated study sessions and full plans."""

from collections.abc import Generator, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from scholarsync.models.task import StudyTask
from scholarsync.models.time_slot import TimeSlot

if TYPE_CHECKING:
    from scholarsync.pipelines.generators import DailyAgenda, TaskProgressSnapshot
    from scholarsync.pipelines.iterators import ScheduleTimelineIterator


@dataclass(frozen=True)
class ScheduledSession:
    """Represents a concrete assigned study session for a specific task.

    Attributes:
        task_id: Identifier of the assigned task.
        task_title: Title of the task.
        subject_code: Academic subject code (e.g., 'CS601').
        slot: The exact chronological TimeSlot for this session.
        hours: Actual duration of this study session in hours.
        is_completed_here: True if this session brings the task to 100% completion.
    """

    task_id: str
    task_title: str
    subject_code: str
    slot: TimeSlot
    hours: float
    is_completed_here: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", self.task_id.strip())
        object.__setattr__(self, "task_title", self.task_title.strip())
        object.__setattr__(self, "subject_code", self.subject_code.strip())
        object.__setattr__(self, "hours", round(float(self.hours), 2))

    def __str__(self) -> str:
        status = " (Final)" if self.is_completed_here else ""
        return (
            f"[{self.subject_code}] {self.task_title} | "
            f"{self.slot.slot_date} {self.slot.format_time_range()} ({self.hours}h){status}"
        )


@dataclass(frozen=True)
class ScheduleResult:
    """Encapsulates the complete outcome of a scheduling run.

    Attributes:
        strategy_name: Name of the scheduling algorithm used.
        start_date: Initial date of the scheduling window.
        end_date: Final date of the scheduling window.
        sessions: Chronological tuple of scheduled study sessions.
        completed_tasks: Tuple of tasks that were completely scheduled before deadlines.
        unscheduled_tasks: Tuple of tasks that could not be fully scheduled.
        task_completion_dates: Mapping from task_id to the date when the task was finished.
    """

    strategy_name: str
    start_date: date
    end_date: date
    sessions: tuple[ScheduledSession, ...] = field(default_factory=tuple)
    completed_tasks: tuple[StudyTask, ...] = field(default_factory=tuple)
    unscheduled_tasks: tuple[StudyTask, ...] = field(default_factory=tuple)
    task_completion_dates: Mapping[str, date] = field(default_factory=dict)
    remaining_task_hours: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Guarantee immutable mapping proxy for completion dates
        if not isinstance(self.task_completion_dates, MappingProxyType):
            object.__setattr__(
                self,
                "task_completion_dates",
                MappingProxyType(dict(self.task_completion_dates)),
            )
        # Guarantee immutable mapping proxy for remaining task hours
        if not isinstance(self.remaining_task_hours, MappingProxyType):
            object.__setattr__(
                self,
                "remaining_task_hours",
                MappingProxyType(dict(self.remaining_task_hours)),
            )

    @property
    def total_scheduled_hours(self) -> float:
        """Total study hours allocated across all sessions."""
        return round(sum(session.hours for session in self.sessions), 2)

    @property
    def is_fully_scheduled(self) -> bool:
        """True if every task was completely scheduled with no unscheduled tasks."""
        return len(self.unscheduled_tasks) == 0

    def get_daily_sessions(self, target_date: date) -> tuple[ScheduledSession, ...]:
        """Retrieve all scheduled sessions occurring on a given date."""
        return tuple(s for s in self.sessions if s.slot.slot_date == target_date)

    def get_task_sessions(self, task_id: str) -> tuple[ScheduledSession, ...]:
        """Retrieve all scheduled sessions belonging to a specific task."""
        clean_id = task_id.strip()
        return tuple(s for s in self.sessions if s.task_id == clean_id)

    def daily_allocated_hours(self, target_date: date) -> float:
        """Calculate total hours allocated on a specific date."""
        return round(sum(s.hours for s in self.get_daily_sessions(target_date)), 2)

    def has_overlapping_slots(self) -> bool:
        """Verify that no two sessions overlap on the same date."""
        # Group sessions by date
        sessions_by_date: dict[date, list[ScheduledSession]] = {}
        for session in self.sessions:
            sessions_by_date.setdefault(session.slot.slot_date, []).append(session)

        for day_sessions in sessions_by_date.values():
            n = len(day_sessions)
            for i in range(n):
                for j in range(i + 1, n):
                    if day_sessions[i].slot.overlaps_with(day_sessions[j].slot):
                        return True
        return False

    def get_remaining_hours(self, task_id: str) -> float:
        """Get remaining unscheduled hours for a specific task."""
        return self.remaining_task_hours.get(task_id.strip(), 0.0)

    @property
    def partially_scheduled_tasks(self) -> tuple[StudyTask, ...]:
        """Tasks that made partial progress but were not 100% completed."""
        return tuple(
            t for t in self.unscheduled_tasks if len(self.get_task_sessions(t.task_id)) > 0
        )

    @property
    def unstarted_tasks(self) -> tuple[StudyTask, ...]:
        """Tasks that received zero scheduled study hours."""
        return tuple(
            t for t in self.unscheduled_tasks if len(self.get_task_sessions(t.task_id)) == 0
        )

    def __iter__(self) -> Iterator[ScheduledSession]:
        """Return a chronological iterator over all scheduled study sessions."""
        from scholarsync.pipelines.iterators import ScheduleTimelineIterator

        return ScheduleTimelineIterator(self.sessions)

    def iter_sessions(
        self,
        target_date: date | None = None,
        date_range: tuple[date, date] | None = None,
        task_id: str | None = None,
        subject_code: str | None = None,
        min_duration_hours: float | None = None,
    ) -> "ScheduleTimelineIterator":
        """Return a filtered, chronological iterator over scheduled study sessions."""
        from scholarsync.pipelines.iterators import ScheduleTimelineIterator

        return ScheduleTimelineIterator(
            self.sessions,
            target_date=target_date,
            date_range=date_range,
            task_id=task_id,
            subject_code=subject_code,
            min_duration_hours=min_duration_hours,
        )

    def stream_agendas(
        self,
        include_empty_days: bool = False,
    ) -> "Generator[DailyAgenda, None, None]":
        """Stream consolidated daily agendas one day at a time across the planning horizon."""
        from scholarsync.pipelines.generators import stream_daily_agendas

        return stream_daily_agendas(self, include_empty_days=include_empty_days)

    def stream_progress(
        self,
        tasks: Sequence[StudyTask],
    ) -> "Generator[TaskProgressSnapshot, None, None]":
        """Stream progressive completion snapshots as chronological study sessions unfold."""
        from scholarsync.pipelines.generators import stream_task_progress

        return stream_task_progress(self, tasks)
