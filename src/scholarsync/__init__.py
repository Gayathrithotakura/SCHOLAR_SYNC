"""ScholarSync: An Intelligent Academic Workload Planning System.

Academic Context: M.Tech CSE - Computational Thinking and Programming.
"""

__version__ = "0.1.0"
__author__ = "ScholarSync Team"

from scholarsync.algorithms.dynamic_programming import DPKnapsackScheduler
from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.algorithms.hybrid import RollingHorizonHybridScheduler
from scholarsync.algorithms.metrics import ScheduleMetrics, evaluate_schedule
from scholarsync.core.context_managers import (
    BenchmarkTimer,
    ProfileSandbox,
    temporary_profile_override,
)
from scholarsync.models.schedule import ScheduledSession, ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask
from scholarsync.models.time_slot import TimeSlot
from scholarsync.pipelines.generators import (
    DailyAgenda,
    TaskProgressSnapshot,
    stream_daily_agendas,
    stream_task_progress,
)
from scholarsync.pipelines.iterators import ScheduleTimelineIterator

__all__ = [
    "Subject",
    "StudyTask",
    "StudentProfile",
    "TimeSlot",
    "ScheduledSession",
    "ScheduleResult",
    "GreedyEDFScheduler",
    "DPKnapsackScheduler",
    "RollingHorizonHybridScheduler",
    "ScheduleMetrics",
    "evaluate_schedule",
    "ScheduleTimelineIterator",
    "DailyAgenda",
    "TaskProgressSnapshot",
    "stream_daily_agendas",
    "stream_task_progress",
    "BenchmarkTimer",
    "ProfileSandbox",
    "temporary_profile_override",
]
