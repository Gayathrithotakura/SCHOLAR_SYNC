"""Memory-efficient generator pipelines for streaming daily agendas and task progress.

Enables lazy evaluation and streaming rendering of large multi-day semester schedules
without allocating intermediate full-schedule data structures in memory.
"""

from collections.abc import Generator, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from scholarsync.models.schedule import ScheduledSession, ScheduleResult
from scholarsync.models.task import StudyTask


@dataclass(frozen=True)
class DailyAgenda:
    """Represents a day's consolidated schedule overview.

    Attributes:
        date: The calendar date.
        weekday: Name of the day of the week (e.g., 'Monday').
        sessions: Tuple of scheduled study sessions occurring on this date.
        total_hours: Sum of all study hours scheduled on this date.
        tasks_involved: Ordered unique tuple of task IDs being worked on.
        is_rest_day: True if zero study sessions are scheduled on this date.
    """

    date: date
    weekday: str
    sessions: tuple[ScheduledSession, ...]
    total_hours: float
    tasks_involved: tuple[str, ...]
    is_rest_day: bool

    def __str__(self) -> str:
        if self.is_rest_day:
            return f"[{self.date} {self.weekday}] Rest Day (0.0h)"
        tasks_str = ", ".join(self.tasks_involved)
        return (
            f"[{self.date} {self.weekday}] {self.total_hours}h "
            f"({len(self.sessions)} sessions, tasks: {tasks_str})"
        )


@dataclass(frozen=True)
class TaskProgressSnapshot:
    """Snapshot of a task's progress immediately following a scheduled study session.

    Attributes:
        session: The specific ScheduledSession that just completed.
        task_id: Unique identifier of the task.
        task_title: Title of the task.
        hours_completed_so_far: Cumulative study hours completed up to and including this session.
        total_required_hours: Total required study duration for the task.
        progress_percentage: Completion ratio expressed as a percentage (0.0% to 100.0%).
        is_task_complete: True if this session brings the task to full completion.
    """

    session: ScheduledSession
    task_id: str
    task_title: str
    hours_completed_so_far: float
    total_required_hours: float
    progress_percentage: float
    is_task_complete: bool

    def __str__(self) -> str:
        status = "COMPLETE" if self.is_task_complete else f"{self.progress_percentage}%"
        return (
            f"[{self.task_id}] {self.task_title}: "
            f"{self.hours_completed_so_far}h / {self.total_required_hours}h ({status})"
        )


def stream_daily_agendas(
    result: ScheduleResult,
    include_empty_days: bool = False,
) -> Generator[DailyAgenda, None, None]:
    """Stream consolidated daily agendas one day at a time across the planning horizon.

    Args:
        result: The ScheduleResult containing scheduled sessions and planning horizon.
        include_empty_days: If True, yields DailyAgenda for rest days with 0 hours.

    Yields:
        DailyAgenda objects for each active (or all) calendar days.
    """
    curr_date = result.start_date
    while curr_date <= result.end_date:
        daily_sessions = result.get_daily_sessions(curr_date)
        total_h = round(sum(s.hours for s in daily_sessions), 2)
        tasks_involved = tuple(dict.fromkeys(s.task_id for s in daily_sessions))
        is_rest = len(daily_sessions) == 0

        if not is_rest or include_empty_days:
            yield DailyAgenda(
                date=curr_date,
                weekday=curr_date.strftime("%A"),
                sessions=daily_sessions,
                total_hours=total_h,
                tasks_involved=tasks_involved,
                is_rest_day=is_rest,
            )

        curr_date += timedelta(days=1)


def stream_task_progress(
    result: ScheduleResult,
    tasks: Sequence[StudyTask],
) -> Generator[TaskProgressSnapshot, None, None]:
    """Stream progressive completion snapshots as chronological study sessions unfold.

    Args:
        result: The ScheduleResult to trace chronologically.
        tasks: Sequence of StudyTask instances providing original estimated durations.

    Yields:
        TaskProgressSnapshot after each scheduled study session.
    """
    task_map = {t.task_id: t for t in tasks}
    accumulated_hours: dict[str, float] = {}

    for session in result.sessions:
        t_id = session.task_id
        current_cum = accumulated_hours.get(t_id, 0.0) + session.hours
        accumulated_hours[t_id] = round(current_cum, 2)

        matched_task = task_map.get(t_id)
        total_needed = matched_task.estimated_hours if matched_task is not None else session.hours
        ratio = (current_cum / total_needed) if total_needed > 0 else 1.0
        pct = min(100.0, round(ratio * 100.0, 1))
        is_complete = session.is_completed_here or (current_cum >= total_needed - 0.001)

        yield TaskProgressSnapshot(
            session=session,
            task_id=t_id,
            task_title=session.task_title,
            hours_completed_so_far=round(current_cum, 2),
            total_required_hours=total_needed,
            progress_percentage=pct,
            is_task_complete=is_complete,
        )
