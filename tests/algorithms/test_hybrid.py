"""Comprehensive tests for Rolling-Horizon Hybrid Scheduler.

Validates:
1. Multi-day task spanning with accurate progress tracking
2. Multi-day prerequisite unlocking
3. Capacity competition and utility maximization
4. Deadline adherence and overdue task reporting
5. Insufficient capacity limits and partial completion tracking
6. Empty inputs and zero-capacity days
7. Cognitive constraints (max continuous hours and rest breaks)
8. Deterministic schedule generation
9. Prevention of duplicate allocation or excess hours
10. Prerequisite cycle and missing dependency validation
"""

from datetime import date, timedelta

import pytest

from scholarsync.algorithms.hybrid import RollingHorizonHybridScheduler
from scholarsync.algorithms.metrics import evaluate_schedule
from scholarsync.core.exceptions import (
    CyclicDependencyError,
    UnresolvedDependencyError,
)
from scholarsync.core.types import Difficulty, Priority
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask


@pytest.fixture
def base_date() -> date:
    """Simulation start date (Monday)."""
    return date(2026, 10, 12)


@pytest.fixture
def hybrid_scheduler() -> RollingHorizonHybridScheduler:
    """Instance of RollingHorizonHybridScheduler."""
    return RollingHorizonHybridScheduler()


@pytest.fixture
def standard_student() -> StudentProfile:
    """Student with 3.0h available per day and 2.0h continuous limit."""
    return StudentProfile(
        student_id="STU_HYBRID",
        name="Vikram Seth",
        daily_availability={
            "monday": 3.0,
            "tuesday": 3.0,
            "wednesday": 3.0,
            "thursday": 3.0,
            "friday": 3.0,
            "saturday": 5.0,
            "sunday": 5.0,
        },
        max_daily_hours=6.0,
        max_continuous_hours=2.0,
        break_duration_minutes=15,
    )


class TestHybridSchedulerMultiDaySpanning:
    """Tests tasks that span multiple days and track partial progress."""

    def test_single_task_spanning_multiple_days(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify 6.0h task is scheduled 3.0h on Monday and 3.0h on Tuesday."""
        student = StudentProfile(
            student_id="STU_SPAN",
            name="Spanning Student",
            daily_availability={"monday": 3.0, "tuesday": 3.0, "wednesday": 0.0},
            max_daily_hours=4.0,
            max_continuous_hours=2.0,
            break_duration_minutes=15,
        )
        task = StudyTask(
            task_id="T_SPAN",
            title="Comprehensive Algorithm Review",
            subject=sample_subject_algorithms,
            estimated_hours=6.0,
            deadline=base_date + timedelta(days=2),  # Wednesday
        )

        result = hybrid_scheduler.schedule(
            tasks=[task],
            student=student,
            start_date=base_date,
            horizon_days=3,
        )

        assert task in result.completed_tasks
        assert result.total_scheduled_hours == 6.0
        assert result.get_remaining_hours("T_SPAN") == 0.0
        assert result.task_completion_dates["T_SPAN"] == base_date + timedelta(days=1)

        sessions = result.get_task_sessions("T_SPAN")
        # Monday (3.0h split into 2.0h + 1.0h due to continuous limit)
        # Tuesday (3.0h split into 2.0h + 1.0h)
        assert len(sessions) == 4
        monday_sessions = [s for s in sessions if s.slot.slot_date == base_date]
        tuesday_sessions = [
            s for s in sessions if s.slot.slot_date == base_date + timedelta(days=1)
        ]

        assert round(sum(s.hours for s in monday_sessions), 2) == 3.0
        assert round(sum(s.hours for s in tuesday_sessions), 2) == 3.0

        # Monday sessions must not mark the task complete
        for s in monday_sessions:
            assert s.is_completed_here is False

        # Final Tuesday session must mark the task complete
        assert tuesday_sessions[-1].is_completed_here is True

    def test_prerequisites_completing_across_different_days(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify dependent task is unlocked only after prerequisite completes across days."""
        # Student has 2.0h per day
        student = StudentProfile(
            student_id="STU_PREREQ",
            name="Prereq Student",
            daily_availability={"monday": 2.0, "tuesday": 2.0, "wednesday": 2.0},
            max_daily_hours=4.0,
            max_continuous_hours=2.0,
        )
        # Task A takes 3.0h (Monday: 2.0h, Tuesday: 1.0h, completing on Tuesday)
        task_a = StudyTask(
            task_id="TASK_A",
            title="Foundational Data Structures",
            subject=sample_subject_algorithms,
            estimated_hours=3.0,
            deadline=base_date + timedelta(days=3),
        )
        # Task B takes 2.0h, depends on Task A
        task_b = StudyTask(
            task_id="TASK_B",
            title="Advanced Graph Algorithms",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=3),
            prerequisites=("TASK_A",),
        )

        result = hybrid_scheduler.schedule(
            tasks=[task_b, task_a],  # Intentionally pass dependent first
            student=student,
            start_date=base_date,
            horizon_days=3,
        )

        assert task_a in result.completed_tasks
        assert task_b in result.completed_tasks

        a_sessions = result.get_task_sessions("TASK_A")
        b_sessions = result.get_task_sessions("TASK_B")

        # Task A completes on Tuesday (base_date + 1)
        assert result.task_completion_dates["TASK_A"] == base_date + timedelta(days=1)

        # Task B sessions must never start before Task A completes
        for b_sess in b_sessions:
            assert b_sess.slot.slot_date >= result.task_completion_dates["TASK_A"]

        # If Task B starts on Tuesday, it must start after Task A's last session
        tuesday_a = [s for s in a_sessions if s.slot.slot_date == base_date + timedelta(days=1)]
        tuesday_b = [s for s in b_sessions if s.slot.slot_date == base_date + timedelta(days=1)]
        if tuesday_a and tuesday_b:
            assert tuesday_a[-1].slot.end_hour <= tuesday_b[0].slot.start_hour


class TestHybridSchedulerWorkloadAndConstraints:
    """Tests competing tasks, deadlines, insufficient capacity, and cognitive limits."""

    def test_tasks_competing_for_daily_capacity(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        sample_subject_algorithms: Subject,
        sample_subject_ml: Subject,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify multiple tasks share daily capacity effectively."""
        task1 = StudyTask(
            task_id="T1",
            title="Urgent Coursework",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=1),
            priority=Priority.CRITICAL,
        )
        task2 = StudyTask(
            task_id="T2",
            title="Normal Lab",
            subject=sample_subject_ml,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=2),
            priority=Priority.MEDIUM,
        )

        result = hybrid_scheduler.schedule(
            tasks=[task1, task2],
            student=standard_student,
            start_date=base_date,
            horizon_days=2,
        )

        assert task1 in result.completed_tasks
        assert task2 in result.completed_tasks
        assert result.total_scheduled_hours == 4.0
        assert result.has_overlapping_slots() is False

    def test_overdue_task_not_scheduled_and_reported(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        sample_subject_algorithms: Subject,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify tasks with past deadlines are excluded and tracked as unscheduled."""
        overdue_task = StudyTask(
            task_id="T_PAST",
            title="Expired Assignment",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date - timedelta(days=1),
        )
        valid_task = StudyTask(
            task_id="T_VALID",
            title="Current Assignment",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=1),
        )

        result = hybrid_scheduler.schedule(
            tasks=[overdue_task, valid_task],
            student=standard_student,
            start_date=base_date,
            horizon_days=2,
        )

        assert overdue_task in result.unscheduled_tasks
        assert valid_task in result.completed_tasks
        assert result.get_remaining_hours("T_PAST") == 2.0
        assert result.get_remaining_hours("T_VALID") == 0.0
        assert overdue_task in result.unstarted_tasks

    def test_insufficient_total_capacity_reports_partial_progress(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify scheduler handles shortage of time and tracks partially scheduled tasks."""
        # Total capacity across 2 days is 3.0h
        student = StudentProfile(
            student_id="STU_TIGHT",
            name="Tight Student",
            daily_availability={"monday": 1.5, "tuesday": 1.5, "wednesday": 0.0},
            max_daily_hours=2.0,
            max_continuous_hours=1.5,
        )
        # Task requires 5.0h, due on Tuesday
        heavy_task = StudyTask(
            task_id="T_HEAVY",
            title="Heavy Project",
            subject=sample_subject_algorithms,
            estimated_hours=5.0,
            deadline=base_date + timedelta(days=1),
        )

        result = hybrid_scheduler.schedule(
            tasks=[heavy_task],
            student=student,
            start_date=base_date,
            horizon_days=2,
        )

        assert heavy_task in result.unscheduled_tasks
        assert heavy_task in result.partially_scheduled_tasks
        assert result.total_scheduled_hours == 3.0
        assert result.get_remaining_hours("T_HEAVY") == 2.0
        assert result.is_fully_scheduled is False

    def test_no_duplicate_allocation_or_excess_hours(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        sample_subject_algorithms: Subject,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify scheduler never allocates more hours than a task requires."""
        task = StudyTask(
            task_id="T_EXACT_HOURS",
            title="Bounded Study",
            subject=sample_subject_algorithms,
            estimated_hours=3.5,
            deadline=base_date + timedelta(days=5),
        )

        result = hybrid_scheduler.schedule(
            tasks=[task],
            student=standard_student,
            start_date=base_date,
            horizon_days=5,
        )

        assert task in result.completed_tasks
        task_sessions = result.get_task_sessions("T_EXACT_HOURS")
        total_task_hours = sum(s.hours for s in task_sessions)
        assert round(total_task_hours, 2) == 3.5
        assert result.get_remaining_hours("T_EXACT_HOURS") == 0.0

    def test_empty_tasks_and_zero_capacity_days(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify empty inputs and zero availability do not cause infinite loops or crashes."""
        # Empty tasks
        res_empty = hybrid_scheduler.schedule(
            tasks=[],
            student=standard_student,
            start_date=base_date,
            horizon_days=5,
        )
        assert len(res_empty.sessions) == 0
        assert res_empty.is_fully_scheduled is True

        # Student with zero capacity on Mon-Wed (but available on weekend)
        zero_student = StudentProfile(
            student_id="STU_ZERO",
            name="Zero Availability",
            daily_availability={
                "monday": 0.0,
                "tuesday": 0.0,
                "wednesday": 0.0,
                "saturday": 4.0,
            },
            max_daily_hours=4.0,
            max_continuous_hours=1.0,
        )
        task = StudyTask(
            task_id="T01",
            title="Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=2),
        )
        res_zero = hybrid_scheduler.schedule(
            tasks=[task],
            student=zero_student,
            start_date=base_date,
            horizon_days=3,
        )
        assert len(res_zero.sessions) == 0
        assert task in res_zero.unscheduled_tasks

    def test_deterministic_schedule_generation(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        sample_subject_ml: Subject,
        base_date: date,
    ) -> None:
        """Verify two independent runs on identical inputs generate identical schedules."""
        tasks = [
            StudyTask(
                task_id="TA",
                title="Task Alpha",
                subject=sample_subject_algorithms,
                estimated_hours=2.5,
                deadline=base_date + timedelta(days=2),
                priority=Priority.HIGH,
            ),
            StudyTask(
                task_id="TB",
                title="Task Beta",
                subject=sample_subject_ml,
                estimated_hours=2.0,
                deadline=base_date + timedelta(days=2),
                priority=Priority.HIGH,
            ),
        ]

        run1 = hybrid_scheduler.schedule(
            tasks=tasks, student=standard_student, start_date=base_date
        )
        run2 = hybrid_scheduler.schedule(
            tasks=tasks, student=standard_student, start_date=base_date
        )

        assert len(run1.sessions) == len(run2.sessions)
        for s1, s2 in zip(run1.sessions, run2.sessions, strict=True):
            assert s1.task_id == s2.task_id
            assert s1.slot.slot_date == s2.slot.slot_date
            assert s1.slot.start_hour == s2.slot.start_hour
            assert s1.hours == s2.hours

    def test_dependency_errors_prevent_scheduling(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify unresolved and cyclic prerequisites raise domain exceptions."""
        unresolved_task = StudyTask(
            task_id="T_BAD",
            title="Bad Task",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
            prerequisites=("NON_EXISTENT_ID",),
        )
        with pytest.raises(UnresolvedDependencyError):
            hybrid_scheduler.schedule(
                tasks=[unresolved_task],
                student=standard_student,
                start_date=base_date,
            )

        cycle_a = StudyTask(
            task_id="CA",
            title="Cycle A",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
            prerequisites=("CB",),
        )
        cycle_b = StudyTask(
            task_id="CB",
            title="Cycle B",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
            prerequisites=("CA",),
        )
        with pytest.raises(CyclicDependencyError):
            hybrid_scheduler.schedule(
                tasks=[cycle_a, cycle_b],
                student=standard_student,
                start_date=base_date,
            )

    def test_metrics_evaluation_on_hybrid_result(
        self,
        hybrid_scheduler: RollingHorizonHybridScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify schedule metrics correctly evaluate a hybrid schedule."""
        task = StudyTask(
            task_id="T_METRIC",
            title="Metric Test Task",
            subject=sample_subject_algorithms,
            estimated_hours=4.0,
            deadline=base_date + timedelta(days=3),
            difficulty=Difficulty.HARD,
        )

        result = hybrid_scheduler.schedule(
            tasks=[task],
            student=standard_student,
            start_date=base_date,
            horizon_days=5,
        )

        metrics = evaluate_schedule(result, standard_student)
        assert metrics.total_tasks == 1
        assert metrics.completed_tasks == 1
        assert metrics.completion_rate == 1.0
        assert metrics.total_scheduled_hours == 4.0
        assert metrics.high_difficulty_hours == 4.0
