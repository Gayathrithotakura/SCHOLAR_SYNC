"""Experimental benchmark execution harness for academic workload schedulers.

Performs isolated, high-precision timing trials (with warmup and statistical aggregation)
and verifies mathematical and operational schedule constraints across Greedy, DP, and Hybrid.
"""

import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from scholarsync.algorithms.base import BaseSchedulerStrategy
from scholarsync.algorithms.dynamic_programming import DPKnapsackScheduler
from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.algorithms.hybrid import RollingHorizonHybridScheduler
from scholarsync.algorithms.metrics import evaluate_schedule
from scholarsync.benchmarks.workloads import BenchmarkScenario, generate_benchmark_suite
from scholarsync.models.schedule import ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.task import StudyTask


@dataclass(frozen=True)
class BenchmarkRunResult:
    """Comprehensive benchmark trial output for a single algorithm on a scenario.

    Attributes:
        scenario_id: Short scenario identifier (e.g., 'SMALL', 'MEDIUM', 'LARGE').
        scenario_name: Human-readable scenario name.
        task_count: Number of input tasks.
        total_task_hours: Sum of required task hours.
        horizon_days: Planning horizon duration in days.
        strategy_name: Name of evaluated scheduling algorithm.
        repetitions: Number of timed executions performed.
        trial_latencies_ms: Tuple of individual execution times in milliseconds.
        median_latency_ms: Median execution latency in milliseconds.
        mean_latency_ms: Arithmetic mean execution latency in milliseconds.
        min_latency_ms: Minimum recorded execution latency in milliseconds.
        max_latency_ms: Maximum recorded execution latency in milliseconds.
        std_latency_ms: Standard deviation of execution latency in milliseconds.
        total_scheduled_hours: Total study hours scheduled.
        remaining_hours: Unscheduled study hours remaining.
        completed_tasks_count: Number of tasks fully scheduled.
        unscheduled_tasks_count: Number of tasks not fully scheduled.
        completion_rate: Fraction of tasks fully scheduled (0.0 to 1.0).
        on_time_tasks_count: Tasks completed on or before deadline.
        on_time_rate: Fraction of tasks completed on-time (0.0 to 1.0).
        capacity_utilization: Ratio of scheduled study hours to student capacity.
        daily_mean_hours: Average study hours per active day.
        daily_std_hours: Standard deviation of study hours per active day.
        cognitive_load_index: Composite cognitive load score.
        is_valid: True if schedule satisfies all constraints (overlaps, prereqs, capacity).
        validation_notes: Issues or constraint violations detected during audit.
    """

    scenario_id: str
    scenario_name: str
    task_count: int
    total_task_hours: float
    horizon_days: int
    strategy_name: str
    repetitions: int
    trial_latencies_ms: tuple[float, ...]
    median_latency_ms: float
    mean_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    std_latency_ms: float
    total_scheduled_hours: float
    remaining_hours: float
    completed_tasks_count: int
    unscheduled_tasks_count: int
    completion_rate: float
    on_time_tasks_count: int
    on_time_rate: float
    capacity_utilization: float
    daily_mean_hours: float
    daily_std_hours: float
    cognitive_load_index: float
    is_valid: bool
    validation_notes: tuple[str, ...]


def validate_schedule_correctness(
    result: ScheduleResult,
    student: StudentProfile,
    tasks: Sequence[StudyTask],
) -> tuple[bool, list[str]]:
    """Audit mathematical correctness and constraint validity of a schedule.

    Verifies:
    1. Slot non-overlap: No two sessions overlap in time on any day.
    2. Date horizon bounds: Every session falls between start_date and end_date.
    3. Daily capacity limits: Daily allocated hours do not exceed availability.
    4. Continuous session limit: No session exceeds student.max_continuous_hours.
    5. Task duration conservation: No task receives more hours than estimated.
    6. Prerequisite dependency order: No task session occurs before its prerequisite is completed.
    7. Deadline compliance: No session is scheduled after the task's deadline.
    8. Chronological ordering: Sessions are ordered chronologically by date and start hour.

    Returns:
        (is_valid, list_of_violations)
    """
    violations: list[str] = []
    task_map = {t.task_id: t for t in tasks}

    # 1. Slot overlap check
    if result.has_overlapping_slots():
        violations.append("Detected overlapping time slots on one or more days.")

    # 2. Date horizon bounds
    for s in result.sessions:
        if not (result.start_date <= s.slot.slot_date <= result.end_date):
            violations.append(
                f"Session for task {s.task_id} on {s.slot.slot_date} outside "
                f"[{result.start_date}, {result.end_date}]."
            )

    # 3. Daily capacity limits
    curr = result.start_date
    while curr <= result.end_date:
        allocated = result.daily_allocated_hours(curr)
        limit = student.get_daily_hours(curr.strftime("%A").lower())
        if allocated > limit + 0.001:
            violations.append(
                f"Daily capacity exceeded on {curr}: "
                f"{allocated:.2f}h allocated vs {limit:.2f}h limit."
            )
        curr += timedelta(days=1)

    # 4. Continuous session limit
    for s in result.sessions:
        if s.hours > student.max_continuous_hours + 0.001:
            violations.append(
                f"Session for {s.task_id} ({s.hours}h) exceeds max continuous limit "
                f"({student.max_continuous_hours}h)."
            )

    # 5. Task duration conservation
    hours_per_task: dict[str, float] = {}
    for s in result.sessions:
        hours_per_task[s.task_id] = hours_per_task.get(s.task_id, 0.0) + s.hours

    for t_id, total_h in hours_per_task.items():
        original_t = task_map.get(t_id)
        if original_t is not None and total_h > original_t.estimated_hours + 0.001:
            violations.append(
                f"Task {t_id} received {total_h:.2f}h exceeding estimated duration "
                f"({original_t.estimated_hours:.2f}h)."
            )

    # 6. Prerequisite dependency order
    for s in result.sessions:
        target_task = task_map.get(s.task_id)
        if target_task is not None:
            for prereq_id in target_task.prerequisites:
                prereq_comp_date = result.task_completion_dates.get(prereq_id)
                if prereq_comp_date is None or prereq_comp_date > s.slot.slot_date:
                    violations.append(
                        f"Task {s.task_id} scheduled on {s.slot.slot_date} before prerequisite "
                        f"{prereq_id} completion ({prereq_comp_date})."
                    )

    # 7. Deadline compliance
    for s in result.sessions:
        target_task = task_map.get(s.task_id)
        if target_task is not None and s.slot.slot_date > target_task.deadline:
            violations.append(
                f"Task {s.task_id} scheduled on {s.slot.slot_date} after deadline "
                f"({target_task.deadline})."
            )

    # 8. Chronological ordering
    for i in range(len(result.sessions) - 1):
        s1 = result.sessions[i]
        s2 = result.sessions[i + 1]
        if (s1.slot.slot_date, s1.slot.start_hour) > (s2.slot.slot_date, s2.slot.start_hour):
            violations.append(
                f"Sessions out of chronological order: {s1.task_id} on {s1.slot.slot_date} "
                f"({s1.slot.start_hour}h) precedes {s2.task_id} on {s2.slot.slot_date} "
                f"({s2.slot.start_hour}h)."
            )

    return (len(violations) == 0, violations)


def run_scenario_benchmark(
    scenario: BenchmarkScenario,
    scheduler: BaseSchedulerStrategy,
    repetitions: int = 10,
) -> BenchmarkRunResult:
    """Execute timed benchmark trials for a specific scheduler and workload scenario.

    Args:
        scenario: Configured BenchmarkScenario.
        scheduler: BaseSchedulerStrategy implementation to evaluate.
        repetitions: Number of repeated timed runs (minimum 3).

    Returns:
        BenchmarkRunResult with detailed performance and quality metrics.
    """
    reps = max(3, repetitions)

    # 1. Warmup execution to ensure bytecode cache and JIT stability
    _ = scheduler.schedule(
        tasks=scenario.tasks,
        student=scenario.student,
        start_date=scenario.start_date,
        horizon_days=scenario.horizon_days,
    )

    # 2. Repeated timing trials measuring strictly scheduler execution
    latencies_ms: list[float] = []
    final_result: ScheduleResult | None = None

    for _ in range(reps):
        t0 = time.perf_counter()
        final_result = scheduler.schedule(
            tasks=scenario.tasks,
            student=scenario.student,
            start_date=scenario.start_date,
            horizon_days=scenario.horizon_days,
        )
        t1 = time.perf_counter()
        latencies_ms.append(round((t1 - t0) * 1000.0, 4))

    assert final_result is not None

    # 3. Statistical metrics
    median_lat = round(statistics.median(latencies_ms), 4)
    mean_lat = round(statistics.mean(latencies_ms), 4)
    min_lat = min(latencies_ms)
    max_lat = max(latencies_ms)
    std_lat = round(statistics.stdev(latencies_ms), 4) if len(latencies_ms) > 1 else 0.0

    # 4. Domain evaluation and validation
    metrics = evaluate_schedule(final_result, scenario.student)
    is_valid, violations = validate_schedule_correctness(
        final_result, scenario.student, scenario.tasks
    )

    # Calculate remaining hours
    remaining_h = round(sum(final_result.get_remaining_hours(t.task_id) for t in scenario.tasks), 2)

    return BenchmarkRunResult(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        task_count=len(scenario.tasks),
        total_task_hours=scenario.total_task_hours,
        horizon_days=scenario.horizon_days,
        strategy_name=scheduler.name,
        repetitions=reps,
        trial_latencies_ms=tuple(latencies_ms),
        median_latency_ms=median_lat,
        mean_latency_ms=mean_lat,
        min_latency_ms=min_lat,
        max_latency_ms=max_lat,
        std_latency_ms=std_lat,
        total_scheduled_hours=final_result.total_scheduled_hours,
        remaining_hours=remaining_h,
        completed_tasks_count=len(final_result.completed_tasks),
        unscheduled_tasks_count=len(final_result.unscheduled_tasks),
        completion_rate=metrics.completion_rate,
        on_time_tasks_count=metrics.on_time_tasks,
        on_time_rate=metrics.on_time_rate,
        capacity_utilization=metrics.capacity_utilization,
        daily_mean_hours=metrics.mean_daily_hours,
        daily_std_hours=metrics.std_daily_hours,
        cognitive_load_index=metrics.cognitive_load_index,
        is_valid=is_valid,
        validation_notes=tuple(violations),
    )


def run_full_benchmark_suite(
    scenarios: Sequence[BenchmarkScenario] | None = None,
    repetitions: int = 10,
) -> list[BenchmarkRunResult]:
    """Execute complete benchmark suite across workloads and all 3 schedulers."""
    bench_scenarios = scenarios if scenarios is not None else generate_benchmark_suite()
    schedulers: tuple[BaseSchedulerStrategy, ...] = (
        GreedyEDFScheduler(),
        DPKnapsackScheduler(),
        RollingHorizonHybridScheduler(),
    )

    results: list[BenchmarkRunResult] = []
    for scenario in bench_scenarios:
        for scheduler in schedulers:
            res = run_scenario_benchmark(scenario, scheduler, repetitions=repetitions)
            results.append(res)

    return results
