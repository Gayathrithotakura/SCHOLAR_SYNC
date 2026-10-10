"""Pipelines package for ScholarSync: custom iterators, generators, and stream processors."""

from scholarsync.pipelines.generators import (
    DailyAgenda,
    TaskProgressSnapshot,
    stream_daily_agendas,
    stream_task_progress,
)
from scholarsync.pipelines.iterators import ScheduleTimelineIterator

__all__ = [
    "ScheduleTimelineIterator",
    "DailyAgenda",
    "TaskProgressSnapshot",
    "stream_daily_agendas",
    "stream_task_progress",
]
