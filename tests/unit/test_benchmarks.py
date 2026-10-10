"""Unit tests for the reproducible benchmark module.

Tests:
- Workload generation for small, medium, and large scenarios.
- Strict constraint validation: session overlap detection, daily capacity, prerequisite DAG order.
- Benchmark runner timing isolation, statistics calculation (median, min, max, std dev).
- JSON and CSV reporting and serialization.
- Markdown experimental analysis generation.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.benchmarks.reporting import (
    export_benchmark_results_csv,
    export_benchmark_results_json,
    format_benchmark_summary_table,
    generate_experimental_report_markdown,
)
from scholarsync.benchmarks.runner import (
    BenchmarkRunResult,
    run_full_benchmark_suite,
    run_scenario_benchmark,
    validate_schedule_correctness,
)
from scholarsync.benchmarks.workloads import (
    create_large_workload,
    create_medium_workload,
    create_small_workload,
    generate_benchmark_suite,
    get_benchmark_workload,
)
from scholarsync.models.schedule import ScheduledSession, ScheduleResult
from scholarsync.models.time_slot import TimeSlot


class TestBenchmarkWorkloads:
    """Test suite for deterministic benchmark scenario generation."""

    def test_create_small_workload(self) -> None:
        """Small scenario has 6 tasks, 7-day horizon, and fixed total hours."""
        scenario = create_small_workload()
        assert scenario.scenario_id == "SMALL"
        assert scenario.horizon_days == 7
        assert len(scenario.tasks) == 6
        assert scenario.total_task_hours == 17.5
        assert scenario.student.get_daily_hours("monday") == 4.0

        # Check for task exceeding single-day weekday capacity (S05 = 5.0h)
        oversized = [
            t
            for t in scenario.tasks
            if t.estimated_hours > scenario.student.get_daily_hours("monday")
        ]
        assert len(oversized) == 1
        assert oversized[0].task_id == "S05"

    def test_create_medium_workload(self) -> None:
        """Medium scenario has 16 tasks, 14-day horizon, and multi-tier DAG."""
        scenario = create_medium_workload()
        assert scenario.scenario_id == "MEDIUM"
        assert scenario.horizon_days == 14
        assert len(scenario.tasks) == 16
        assert scenario.total_task_hours == 48.5

        # Check prerequisite dependencies
        tasks_with_prereqs = [t for t in scenario.tasks if t.prerequisites]
        assert len(tasks_with_prereqs) >= 5

    def test_create_large_workload(self) -> None:
        """Large scenario has 32 tasks, 30-day horizon, and comprehensive workload."""
        scenario = create_large_workload()
        assert scenario.scenario_id == "LARGE"
        assert scenario.horizon_days == 30
        assert len(scenario.tasks) == 32
        assert scenario.total_task_hours == 101.0

    def test_get_benchmark_workload_lookup(self) -> None:
        """Lookup by name returns expected workload scenario."""
        for size in ("small", "SMALL", "medium", "MEDIUM", "large", "LARGE"):
            scen = get_benchmark_workload(size)
            assert scen.scenario_id.lower() == size.lower()

    def test_get_benchmark_workload_invalid_raises_error(self) -> None:
        """Invalid scenario size raises ValueError with available choices."""
        with pytest.raises(ValueError, match="Unknown benchmark workload size"):
            get_benchmark_workload("extra_huge")

    def test_generate_benchmark_suite(self) -> None:
        """Full suite yields all 3 scenarios in order."""
        suite = list(generate_benchmark_suite())
        assert len(suite) == 3
        assert [s.scenario_id for s in suite] == ["SMALL", "MEDIUM", "LARGE"]


class TestScheduleValidation:
    """Test suite for validate_schedule_correctness auditor."""

    def test_valid_greedy_schedule_passes_validation(self) -> None:
        """Schedules produced by GreedyEDFScheduler on small workload pass validation."""
        scenario = create_small_workload()
        scheduler = GreedyEDFScheduler()
        res = scheduler.schedule(
            tasks=scenario.tasks,
            student=scenario.student,
            start_date=scenario.start_date,
            horizon_days=scenario.horizon_days,
        )

        is_valid, violations = validate_schedule_correctness(res, scenario.student, scenario.tasks)
        assert is_valid is True
        assert len(violations) == 0

    def test_validation_detects_slot_overlap(self) -> None:
        """Validation fails if two scheduled sessions overlap in time on the same date."""
        scenario = create_small_workload()
        task_a = scenario.tasks[0]
        task_b = scenario.tasks[1]
        sched_date = scenario.start_date

        slot_1 = TimeSlot(slot_date=sched_date, start_hour=9.0, duration_hours=2.0)
        slot_2 = TimeSlot(slot_date=sched_date, start_hour=10.0, duration_hours=2.0)  # Overlaps!

        session_1 = ScheduledSession(
            task_id=task_a.task_id,
            task_title=task_a.title,
            subject_code=task_a.subject.code,
            slot=slot_1,
            hours=2.0,
        )
        session_2 = ScheduledSession(
            task_id=task_b.task_id,
            task_title=task_b.title,
            subject_code=task_b.subject.code,
            slot=slot_2,
            hours=2.0,
        )

        res = ScheduleResult(
            sessions=(session_1, session_2),
            unscheduled_tasks=(),
            strategy_name="MockStrategy",
            start_date=sched_date,
            end_date=sched_date,
        )

        is_valid, violations = validate_schedule_correctness(res, scenario.student, scenario.tasks)
        assert is_valid is False
        assert any("overlapping time slots" in v for v in violations)

    def test_validation_detects_daily_capacity_violation(self) -> None:
        """Validation fails if scheduled hours exceed student daily limit."""
        scenario = create_small_workload()
        task = scenario.tasks[0]
        sched_date = scenario.start_date  # Student monday limit is 4.0h

        # 5 hours on Monday
        slot = TimeSlot(slot_date=sched_date, start_hour=9.0, duration_hours=5.0)
        sess = ScheduledSession(
            task_id=task.task_id,
            task_title=task.title,
            subject_code=task.subject.code,
            slot=slot,
            hours=5.0,
        )

        res = ScheduleResult(
            sessions=(sess,),
            unscheduled_tasks=(),
            strategy_name="MockStrategy",
            start_date=sched_date,
            end_date=sched_date,
        )

        is_valid, violations = validate_schedule_correctness(res, scenario.student, scenario.tasks)
        assert is_valid is False
        assert any("Daily capacity exceeded" in v for v in violations)

    def test_validation_detects_prerequisite_order_violation(self) -> None:
        """Validation fails if a dependent task is scheduled before its prerequisite."""
        scenario = create_small_workload()
        # In small scenario, S02 depends on S01
        task_prereq = [t for t in scenario.tasks if t.task_id == "S01"][0]
        task_dependent = [t for t in scenario.tasks if t.task_id == "S02"][0]

        # Schedule dependent on Day 1, prereq on Day 2
        slot_dep = TimeSlot(
            slot_date=scenario.start_date,
            start_hour=9.0,
            duration_hours=1.5,
        )
        slot_pre = TimeSlot(
            slot_date=scenario.start_date + timedelta(days=1),
            start_hour=9.0,
            duration_hours=2.0,
        )

        sess_dep = ScheduledSession(
            task_id=task_dependent.task_id,
            task_title=task_dependent.title,
            subject_code=task_dependent.subject.code,
            slot=slot_dep,
            hours=1.5,
            is_completed_here=True,
        )
        sess_pre = ScheduledSession(
            task_id=task_prereq.task_id,
            task_title=task_prereq.title,
            subject_code=task_prereq.subject.code,
            slot=slot_pre,
            hours=2.0,
            is_completed_here=True,
        )

        res = ScheduleResult(
            sessions=(sess_dep, sess_pre),
            unscheduled_tasks=(),
            strategy_name="MockStrategy",
            start_date=scenario.start_date,
            end_date=scenario.start_date + timedelta(days=1),
            task_completion_dates={
                task_dependent.task_id: scenario.start_date,
                task_prereq.task_id: scenario.start_date + timedelta(days=1),
            },
        )

        is_valid, violations = validate_schedule_correctness(res, scenario.student, scenario.tasks)
        assert is_valid is False
        assert any("before prerequisite" in v for v in violations)

    def test_validation_detects_deadline_violation(self) -> None:
        """Validation fails if a session is scheduled past the task's deadline."""
        scenario = create_small_workload()
        task = scenario.tasks[0]  # deadline is scenario.start_date + 2 days
        past_deadline_date = task.deadline + timedelta(days=1)

        slot = TimeSlot(
            slot_date=past_deadline_date,
            start_hour=9.0,
            duration_hours=1.5,
        )
        sess = ScheduledSession(
            task_id=task.task_id,
            task_title=task.title,
            subject_code=task.subject.code,
            slot=slot,
            hours=1.5,
        )

        res = ScheduleResult(
            sessions=(sess,),
            unscheduled_tasks=(),
            strategy_name="MockStrategy",
            start_date=scenario.start_date,
            end_date=past_deadline_date,
        )

        is_valid, violations = validate_schedule_correctness(res, scenario.student, scenario.tasks)
        assert is_valid is False
        assert any("after deadline" in v for v in violations)

    def test_validation_detects_chronological_ordering_violation(self) -> None:
        """Validation fails if sessions are stored out of chronological order."""
        scenario = create_small_workload()
        task_a = scenario.tasks[0]
        task_b = scenario.tasks[1]

        # sess_later is on Day 2, sess_earlier is on Day 1
        slot_later = TimeSlot(
            slot_date=scenario.start_date + timedelta(days=1),
            start_hour=9.0,
            duration_hours=1.0,
        )
        slot_earlier = TimeSlot(
            slot_date=scenario.start_date,
            start_hour=9.0,
            duration_hours=1.0,
        )

        sess_later = ScheduledSession(
            task_id=task_a.task_id,
            task_title=task_a.title,
            subject_code=task_a.subject.code,
            slot=slot_later,
            hours=1.0,
        )
        sess_earlier = ScheduledSession(
            task_id=task_b.task_id,
            task_title=task_b.title,
            subject_code=task_b.subject.code,
            slot=slot_earlier,
            hours=1.0,
        )

        # Store in reversed chronological order: [later, earlier]
        res = ScheduleResult(
            sessions=(sess_later, sess_earlier),
            unscheduled_tasks=(),
            strategy_name="MockStrategy",
            start_date=scenario.start_date,
            end_date=scenario.start_date + timedelta(days=1),
        )

        is_valid, violations = validate_schedule_correctness(res, scenario.student, scenario.tasks)
        assert is_valid is False
        assert any("out of chronological order" in v for v in violations)


class TestBenchmarkRunner:
    """Test suite for benchmark execution, timing isolation, and stats."""

    def test_run_scenario_benchmark_computes_stats(self) -> None:
        """run_scenario_benchmark computes valid timing spread and metrics."""
        scenario = create_small_workload()
        res = run_scenario_benchmark(scenario, GreedyEDFScheduler(), repetitions=3)

        assert isinstance(res, BenchmarkRunResult)
        assert res.scenario_id == "SMALL"
        assert res.repetitions == 3
        assert len(res.trial_latencies_ms) == 3
        assert res.min_latency_ms <= res.median_latency_ms <= res.max_latency_ms
        assert res.mean_latency_ms > 0
        assert res.is_valid is True
        assert res.task_count == 6
        assert 0.0 <= res.completion_rate <= 1.0

    def test_run_full_benchmark_suite(self) -> None:
        """Full suite runs across provided scenarios with 2 trials."""
        scenario = create_small_workload()
        results = run_full_benchmark_suite([scenario], repetitions=2)
        assert len(results) == 3  # Greedy, DP, Hybrid


class TestBenchmarkReporting:
    """Test suite for benchmark JSON, CSV, and markdown export."""

    def test_export_benchmark_json_and_csv(self, tmp_path: Path) -> None:
        """Benchmark results export cleanly to JSON and CSV with correct format."""
        scenario = create_small_workload()
        results = run_full_benchmark_suite([scenario], repetitions=2)

        json_path = tmp_path / "output.json"
        csv_path = tmp_path / "output.csv"

        bytes_written = export_benchmark_results_json(results, json_path)
        assert bytes_written > 0
        assert json_path.is_file()

        # Validate JSON content
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "metadata" in data
        assert "results" in data
        assert len(data["results"]) == 3
        first_entry = data["results"][0]
        assert "latencies_ms" in first_entry
        assert "median" in first_entry["latencies_ms"]
        assert "schedule_performance" in first_entry

        # Validate CSV content
        rows = export_benchmark_results_csv(results, csv_path)
        assert rows == 3
        assert csv_path.is_file()
        csv_text = csv_path.read_text(encoding="utf-8")
        assert "scenario_id,strategy_name,task_count" in csv_text
        assert "SMALL" in csv_text

    def test_markdown_report_formatting(self) -> None:
        """Markdown report contains overview, summary table, and trade-off analysis."""
        scenario = create_small_workload()
        results = run_full_benchmark_suite([scenario], repetitions=2)

        table_str = format_benchmark_summary_table(results)
        assert "SMALL" in table_str
        assert "Greedy EDF-CW" in table_str
        assert "Dynamic Programming 0/1 Knapsack" in table_str
        assert "Rolling-Horizon Hybrid Strategy" in table_str

        report_md = generate_experimental_report_markdown(results)
        assert "# ScholarSync: Experimental Evaluation of Scheduling Algorithms" in report_md
        assert "## 1. Experimental Methodology & Benchmark Setup" in report_md
        assert "## 3. Comparative Observations & Empirical Analysis" in report_md
        assert "Greedy Earliest Deadline First" in report_md
        assert "Dynamic Programming 0/1 Knapsack" in report_md
        assert "Rolling-Horizon Hybrid Scheduler" in report_md
