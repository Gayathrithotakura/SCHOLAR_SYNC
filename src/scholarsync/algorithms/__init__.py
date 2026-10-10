"""Scheduling algorithms and performance evaluation metrics for ScholarSync."""

from scholarsync.algorithms.base import BaseSchedulerStrategy, validate_task_dependencies
from scholarsync.algorithms.dynamic_programming import (
    DPKnapsackScheduler,
    KnapsackDaySolution,
)
from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.algorithms.hybrid import (
    DailyChunkAllocation,
    RollingHorizonHybridScheduler,
)
from scholarsync.algorithms.metrics import ScheduleMetrics, evaluate_schedule

__all__ = [
    "BaseSchedulerStrategy",
    "validate_task_dependencies",
    "GreedyEDFScheduler",
    "DPKnapsackScheduler",
    "KnapsackDaySolution",
    "RollingHorizonHybridScheduler",
    "DailyChunkAllocation",
    "ScheduleMetrics",
    "evaluate_schedule",
]
