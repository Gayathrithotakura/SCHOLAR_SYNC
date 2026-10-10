"""CLI command handlers for ScholarSync.

Executes subcommands:
- demo: Out-of-the-box demonstration on realistic M.Tech coursework
- plan: Custom or sample schedule generation with configurable horizon and strategy
- compare: Multi-algorithm benchmark comparison on identical workload
- export: Schedule persistence to JSON or CSV
"""

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import TextIO

from scholarsync.algorithms.base import BaseSchedulerStrategy
from scholarsync.algorithms.dynamic_programming import DPKnapsackScheduler
from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.algorithms.hybrid import RollingHorizonHybridScheduler
from scholarsync.algorithms.metrics import ScheduleMetrics, evaluate_schedule
from scholarsync.cli.formatting import (
    format_agenda_view,
    format_comparison_table,
    format_metrics_summary,
)
from scholarsync.cli.sample_data import get_sample_student_profile, get_sample_tasks
from scholarsync.core.context_managers import BenchmarkTimer
from scholarsync.core.exceptions import ValidationError
from scholarsync.models.schedule import ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.task import StudyTask
from scholarsync.serialization.csv_io import export_schedule_to_csv_file
from scholarsync.serialization.json_io import (
    export_schedule_to_json_file,
    profile_from_json,
    tasks_from_json,
)

STRATEGY_REGISTRY: dict[str, type[BaseSchedulerStrategy]] = {
    "greedy": GreedyEDFScheduler,
    "dp": DPKnapsackScheduler,
    "hybrid": RollingHorizonHybridScheduler,
}


def get_scheduler(strategy_name: str) -> BaseSchedulerStrategy:
    """Instantiate a scheduler strategy by case-insensitive key name.

    Raises:
        ValidationError: If the strategy name is unrecognized.
    """
    key = strategy_name.lower().strip()
    if key not in STRATEGY_REGISTRY:
        options = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise ValidationError(
            f"Unknown scheduling strategy '{strategy_name}'. Choose from: {options}."
        )
    return STRATEGY_REGISTRY[key]()


def parse_date(date_str: str | None, default: date | None = None) -> date:
    """Parse an ISO date string (YYYY-MM-DD) or fallback to default."""
    if date_str is None:
        return default if default is not None else date.today()
    try:
        return date.fromisoformat(date_str.strip())
    except ValueError as err:
        raise ValidationError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.") from err


def load_tasks(filepath: str | None, anchor: date) -> tuple[list[StudyTask], str]:
    """Load tasks from JSON file path or provide sample tasks."""
    if filepath is None:
        return get_sample_tasks(anchor), "Built-in Sample M.Tech Workload (7 tasks)"

    path = Path(filepath)
    if not path.is_file():
        raise ValidationError(f"Tasks file not found: {filepath}")

    try:
        content = path.read_text(encoding="utf-8")
        tasks = tasks_from_json(content)
        return tasks, f"Custom tasks from {path.name} ({len(tasks)} tasks)"
    except Exception as err:
        raise ValidationError(f"Failed to load tasks from '{filepath}': {err}") from err


def load_profile(filepath: str | None) -> tuple[StudentProfile, str]:
    """Load student profile from JSON file path or provide sample profile."""
    if filepath is None:
        return get_sample_student_profile(), "Built-in Sample M.Tech Profile (Aarav Sharma)"

    path = Path(filepath)
    if not path.is_file():
        raise ValidationError(f"Profile file not found: {filepath}")

    try:
        content = path.read_text(encoding="utf-8")
        profile = profile_from_json(content)
        return profile, f"Custom profile from {path.name} ({profile.name})"
    except Exception as err:
        raise ValidationError(f"Failed to load profile from '{filepath}': {err}") from err


def export_schedule(
    result: ScheduleResult,
    filepath: str,
    export_format: str | None = None,
    student: StudentProfile | None = None,
    out: TextIO = sys.stdout,
) -> None:
    """Export schedule to target CSV or JSON destination."""
    path = Path(filepath)
    fmt = export_format.lower().strip() if export_format else path.suffix.lstrip(".").lower()

    if fmt == "csv":
        rows_count = export_schedule_to_csv_file(result, path)
        out.write(
            f"\n[Export] Successfully exported {rows_count} sessions to CSV: {path.resolve()}\n"
        )
    elif fmt == "json":
        bytes_count = export_schedule_to_json_file(result, path, student=student)
        out.write(
            f"\n[Export] Successfully exported schedule to JSON ({bytes_count} bytes): "
            f"{path.resolve()}\n"
        )
    else:
        raise ValidationError(
            f"Unsupported export format '{fmt}'. Specify '.json' or '.csv', or use --format."
        )


def handle_demo(args: argparse.Namespace, out: TextIO = sys.stdout) -> int:
    """Execute the deterministic demonstration command."""
    start_d = parse_date(getattr(args, "start_date", None))
    horizon = int(getattr(args, "horizon", 14))
    strat_name = str(getattr(args, "strategy", "hybrid"))

    student = get_sample_student_profile()
    tasks = get_sample_tasks(start_d)
    scheduler = get_scheduler(strat_name)

    out.write("\n" + "=" * 80 + "\n")
    out.write("SCHOLARSYNC: Intelligent Academic Workload Planning System\n")
    out.write("Demonstration Mode - M.Tech CSE Academic Workload\n")
    out.write("=" * 80 + "\n\n")

    out.write(f"Student:   {student.name} [{student.student_id}]\n")
    out.write(f"Strategy:  {scheduler.name}\n")
    out.write(f"Horizon:   {start_d} to {start_d} (+{horizon} days)\n")
    out.write(f"Workload:  {len(tasks)} academic tasks across 4 subjects\n\n")

    with BenchmarkTimer("Scheduling Engine") as timer:
        result = scheduler.schedule(
            tasks=tasks,
            student=student,
            start_date=start_d,
            horizon_days=horizon,
        )

    include_rest = bool(getattr(args, "include_rest_days", False))
    out.write(format_agenda_view(result, include_empty_days=include_rest))
    out.write("\n\n" + "-" * 80 + "\n")
    out.write(f"QUANTITATIVE METRICS EVALUATION ({timer})\n")
    out.write("-" * 80 + "\n")
    metrics = evaluate_schedule(result, student)
    out.write(format_metrics_summary(metrics) + "\n")

    export_path = getattr(args, "export", None)
    if export_path:
        fmt_override = getattr(args, "format", None)
        export_schedule(result, export_path, fmt_override, student=student, out=out)

    return 0


def handle_plan(args: argparse.Namespace, out: TextIO = sys.stdout) -> int:
    """Generate a study schedule for given tasks and profile."""
    start_d = parse_date(getattr(args, "start_date", None))
    horizon = int(getattr(args, "horizon", 14))
    strat_name = str(getattr(args, "strategy", "hybrid"))

    tasks, tasks_desc = load_tasks(getattr(args, "tasks", None), start_d)
    student, profile_desc = load_profile(getattr(args, "profile", None))
    scheduler = get_scheduler(strat_name)

    out.write(f"\n[ScholarSync Plan] Strategy: {scheduler.name}\n")
    out.write(f"Dataset:  {tasks_desc}\n")
    out.write(f"Profile:  {profile_desc}\n\n")

    with BenchmarkTimer("Scheduler") as timer:
        result = scheduler.schedule(
            tasks=tasks,
            student=student,
            start_date=start_d,
            horizon_days=horizon,
        )

    include_rest = bool(getattr(args, "include_rest_days", False))
    out.write(format_agenda_view(result, include_empty_days=include_rest))
    out.write("\n\n" + "-" * 80 + "\n")
    out.write(f"SCHEDULE METRICS EVALUATION ({timer})\n")
    out.write("-" * 80 + "\n")
    metrics = evaluate_schedule(result, student)
    out.write(format_metrics_summary(metrics) + "\n")

    export_path = getattr(args, "export", None)
    if export_path:
        fmt_override = getattr(args, "format", None)
        export_schedule(result, export_path, fmt_override, student=student, out=out)

    return 0


def handle_compare(args: argparse.Namespace, out: TextIO = sys.stdout) -> int:
    """Benchmark all three scheduling strategies on identical workload."""
    start_d = parse_date(getattr(args, "start_date", None))
    horizon = int(getattr(args, "horizon", 14))

    tasks, tasks_desc = load_tasks(getattr(args, "tasks", None), start_d)
    student, profile_desc = load_profile(getattr(args, "profile", None))

    out.write("\n" + "=" * 80 + "\n")
    out.write("SCHOLARSYNC: Comparative Strategy Evaluation\n")
    out.write("=" * 80 + "\n")
    out.write(f"Dataset:  {tasks_desc}\n")
    out.write(f"Profile:  {profile_desc}\n")
    out.write(f"Horizon:  {start_d} (+{horizon} days)\n\n")

    benchmarks: list[tuple[str, ScheduleMetrics, float]] = []

    for strat_cls in STRATEGY_REGISTRY.values():
        scheduler = strat_cls()
        with BenchmarkTimer(scheduler.name) as timer:
            result = scheduler.schedule(
                tasks=tasks,
                student=student,
                start_date=start_d,
                horizon_days=horizon,
            )
        metrics = evaluate_schedule(result, student)
        benchmarks.append((scheduler.name, metrics, timer.elapsed_ms))

    out.write(format_comparison_table(benchmarks) + "\n\n")
    out.write("Key Observations:\n")
    out.write(
        "- Greedy EDF-CW: Heuristic sorting with lowest computational latency (sub-ms).\n"
        "- 0/1 DP Knapsack: Maximizes discrete daily item utility within capacity limits.\n"
        "- Rolling Hybrid: Combines multi-day horizon scoping with daily dynamic programming.\n"
    )

    return 0


def handle_export(args: argparse.Namespace, out: TextIO = sys.stdout) -> int:
    """Export schedule plan directly to CSV or JSON."""
    output_path = getattr(args, "output", None)
    if not output_path:
        raise ValidationError("Missing required output file path for export (--output).")

    start_d = parse_date(getattr(args, "start_date", None))
    horizon = int(getattr(args, "horizon", 14))
    strat_name = str(getattr(args, "strategy", "hybrid"))

    tasks, _ = load_tasks(getattr(args, "tasks", None), start_d)
    student, _ = load_profile(getattr(args, "profile", None))
    scheduler = get_scheduler(strat_name)

    result = scheduler.schedule(
        tasks=tasks,
        student=student,
        start_date=start_d,
        horizon_days=horizon,
    )

    export_schedule(
        result=result,
        filepath=output_path,
        export_format=getattr(args, "format", None),
        student=student,
        out=out,
    )
    return 0


def handle_benchmark(args: argparse.Namespace, out: TextIO = sys.stdout) -> int:
    """Execute reproducible benchmarks across workloads and strategies."""
    from scholarsync.benchmarks.reporting import (
        export_benchmark_results_csv,
        export_benchmark_results_json,
        format_benchmark_summary_table,
    )
    from scholarsync.benchmarks.runner import run_full_benchmark_suite
    from scholarsync.benchmarks.workloads import (
        generate_benchmark_suite,
        get_benchmark_workload,
    )

    size_arg = str(getattr(args, "size", "all")).lower().strip()
    repetitions = int(getattr(args, "repetitions", 5))

    if size_arg == "all":
        scenarios = list(generate_benchmark_suite())
    else:
        scenarios = [get_benchmark_workload(size_arg)]

    out.write("\n" + "=" * 80 + "\n")
    out.write("SCHOLARSYNC: Reproducible Experimental Benchmark Suite\n")
    out.write("=" * 80 + "\n")
    out.write(f"Scenarios:   {len(scenarios)} ({', '.join(s.scenario_id for s in scenarios)})\n")
    out.write(f"Repetitions: {repetitions} timed trials per algorithm (with warmup)\n\n")

    results = run_full_benchmark_suite(scenarios, repetitions=repetitions)
    out.write(format_benchmark_summary_table(results) + "\n")

    json_export = getattr(args, "export_json", None)
    if json_export:
        bytes_w = export_benchmark_results_json(results, json_export)
        out.write(f"\n[Benchmark] Exported JSON results ({bytes_w} bytes): {json_export}\n")

    csv_export = getattr(args, "export_csv", None)
    if csv_export:
        rows_w = export_benchmark_results_csv(results, csv_export)
        out.write(f"\n[Benchmark] Exported CSV results ({rows_w} rows): {csv_export}\n")

    return 0
