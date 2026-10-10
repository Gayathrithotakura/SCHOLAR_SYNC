"""Comprehensive tests for Greedy EDF-CW scheduler and schedule metrics.

Validates:
1. Empty input handling
2. Normal multi-task deterministic scheduling
3. Overdue task filtering (tasks past deadline are not scheduled)
4. Equal deadline tie-breaking (deterministic ordering)
5. Insufficient capacity limits (partial scheduling without exceeding budgets)
6. Prerequisites enforcement and sequential scheduling
7. Dependency cycle detection (CyclicDependencyError)
8. Unresolved prerequisite detection (UnresolvedDependencyError)
9. Cognitive constraints (max continuous hours & mandatory breaks)
10. Strict deadline enforcement (no sessions past deadline)
11. Overlapping slot verification (has_overlapping_slots == False)
12. Comprehensive metrics evaluation
"""

from datetime import date, timedelta

import pytest

from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.algorithms.metrics import evaluate_schedule
from scholarsync.core.exceptions import (
    CyclicDependencyError,
    UnresolvedDependencyError,
    ValidationError,
)
from scholarsync.core.types import Difficulty, Priority
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask


@pytest.fixture
def base_date() -> date:
    """Simulation start date for tests (a Monday)."""
    return date(2026, 10, 12)  # 2026-10-12 is Monday


@pytest.fixture
def scheduler() -> GreedyEDFScheduler:
    """Instance of GreedyEDFScheduler."""
    return GreedyEDFScheduler()


@pytest.fixture
def standard_student() -> StudentProfile:
    """Standard student profile with 4h weekdays and 6h weekends."""
    return StudentProfile(
        student_id="STU_TEST",
        name="Ananya Rao",
        max_daily_hours=8.0,
        max_continuous_hours=2.0,
        break_duration_minutes=15,
    )


class TestGreedyEDFSchedulerBasics:
    """Tests basic scheduling, empty inputs, and input validation."""

    def test_scheduler_name(self, scheduler: GreedyEDFScheduler) -> None:
        """Verify scheduler identifies itself as Greedy EDF-CW."""
        assert scheduler.name == "Greedy EDF-CW"

    def test_empty_tasks_list(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify empty task list returns empty valid ScheduleResult."""
        result = scheduler.schedule(
            tasks=[],
            student=standard_student,
            start_date=base_date,
            horizon_days=7,
        )
        assert len(result.sessions) == 0
        assert len(result.completed_tasks) == 0
        assert len(result.unscheduled_tasks) == 0
        assert result.total_scheduled_hours == 0.0
        assert result.is_fully_scheduled is True
        assert result.has_overlapping_slots() is False

    def test_invalid_start_date_raises_validation_error(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
    ) -> None:
        """Verify non-date start_date raises ValidationError."""
        with pytest.raises(ValidationError, match="start_date must be an instance"):
            scheduler.schedule(
                tasks=[],
                student=standard_student,
                start_date="2026-10-12",  # type: ignore[arg-type]
            )

    def test_invalid_horizon_days_raises_validation_error(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify non-positive horizon_days raises ValidationError."""
        with pytest.raises(ValidationError, match="horizon_days must be strictly positive"):
            scheduler.schedule(
                tasks=[],
                student=standard_student,
                start_date=base_date,
                horizon_days=0,
            )

    def test_invalid_day_start_hour_raises_validation_error(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify day_start_hour out of [0, 24) raises ValidationError."""
        with pytest.raises(ValidationError, match="day_start_hour must be in range"):
            scheduler.schedule(
                tasks=[],
                student=standard_student,
                start_date=base_date,
                day_start_hour=24.5,
            )


class TestGreedyEDFSchedulerPrerequisitesAndCycles:
    """Tests prerequisite resolution and cycle detection."""

    def test_unresolved_prerequisite_raises_error(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify depending on a non-existent task ID raises UnresolvedDependencyError."""
        task = StudyTask(
            task_id="T01",
            title="Algorithm Analysis",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=5),
            prerequisites=("MISSING_PREREQ_99",),
        )
        with pytest.raises(UnresolvedDependencyError, match="unresolved prerequisite"):
            scheduler.schedule(
                tasks=[task],
                student=standard_student,
                start_date=base_date,
            )

    def test_direct_cyclic_dependency_raises_error(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify direct mutual cycle (T01 -> T02 -> T01) raises CyclicDependencyError."""
        task1 = StudyTask(
            task_id="T01",
            title="Task 1",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=5),
            prerequisites=("T02",),
        )
        task2 = StudyTask(
            task_id="T02",
            title="Task 2",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=5),
            prerequisites=("T01",),
        )
        with pytest.raises(CyclicDependencyError, match="Cyclic dependency detected"):
            scheduler.schedule(
                tasks=[task1, task2],
                student=standard_student,
                start_date=base_date,
            )

    def test_indirect_cyclic_dependency_raises_error(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify indirect cycle (A -> B -> C -> A) raises CyclicDependencyError."""
        task_a = StudyTask(
            task_id="TA",
            title="Task A",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=5),
            prerequisites=("TB",),
        )
        task_b = StudyTask(
            task_id="TB",
            title="Task B",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=5),
            prerequisites=("TC",),
        )
        task_c = StudyTask(
            task_id="TC",
            title="Task C",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=5),
            prerequisites=("TA",),
        )
        with pytest.raises(CyclicDependencyError, match="Cyclic dependency detected"):
            scheduler.schedule(
                tasks=[task_a, task_b, task_c],
                student=standard_student,
                start_date=base_date,
            )

    def test_prerequisites_scheduled_in_strictly_valid_order(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify prerequisite task is completed before dependent task can be scheduled."""
        # Prerequisite: takes 4 hours (entire day on Monday)
        task_prereq = StudyTask(
            task_id="T_PREREQ",
            title="Prerequisite Task",
            subject=sample_subject_algorithms,
            estimated_hours=4.0,
            deadline=base_date + timedelta(days=2),
        )
        # Dependent task: requires T_PREREQ
        task_dep = StudyTask(
            task_id="T_DEP",
            title="Dependent Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=3),
            prerequisites=("T_PREREQ",),
        )

        result = scheduler.schedule(
            tasks=[task_dep, task_prereq],  # Intentionally pass dependent first in list
            student=standard_student,
            start_date=base_date,
            horizon_days=7,
        )

        assert result.is_fully_scheduled is True
        prereq_sessions = result.get_task_sessions("T_PREREQ")
        dep_sessions = result.get_task_sessions("T_DEP")

        assert len(prereq_sessions) > 0
        assert len(dep_sessions) > 0

        # Last session of prereq must complete on or before the first session of dep
        last_prereq_date = prereq_sessions[-1].slot.slot_date
        first_dep_date = dep_sessions[0].slot.slot_date
        assert last_prereq_date <= first_dep_date

        if last_prereq_date == first_dep_date:
            assert prereq_sessions[-1].slot.end_hour <= dep_sessions[0].slot.start_hour


class TestGreedyEDFSchedulerWorkloadConstraints:
    """Tests capacity limits, cognitive constraints, overdue tasks, and deadlines."""

    def test_overdue_task_is_never_scheduled(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify tasks whose deadlines have already passed are flagged as unscheduled."""
        overdue_task = StudyTask(
            task_id="T_OVERDUE",
            title="Past Due Assignment",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date - timedelta(days=1),  # Yesterday
        )
        normal_task = StudyTask(
            task_id="T_NORMAL",
            title="Active Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=2),
        )

        result = scheduler.schedule(
            tasks=[overdue_task, normal_task],
            student=standard_student,
            start_date=base_date,
            horizon_days=5,
        )

        assert overdue_task in result.unscheduled_tasks
        assert normal_task in result.completed_tasks
        assert len(result.get_task_sessions("T_OVERDUE")) == 0
        assert len(result.get_task_sessions("T_NORMAL")) > 0

    def test_equal_deadlines_deterministic_tie_breaker(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify deterministic ordering when deadlines and priorities are equal."""
        # Both due on base_date + 1, priority=4
        # Task Hard has difficulty 5; Task Easy has difficulty 2
        task_hard = StudyTask(
            task_id="T_HARD",
            title="Difficult Lab",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=1),
            priority=Priority.HIGH,
            difficulty=Difficulty.VERY_HARD,
        )
        task_easy = StudyTask(
            task_id="T_EASY",
            title="Easy Summary",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=1),
            priority=Priority.HIGH,
            difficulty=Difficulty.EASY,
        )

        result = scheduler.schedule(
            tasks=[task_easy, task_hard],
            student=standard_student,
            start_date=base_date,
            horizon_days=3,
        )

        assert len(result.sessions) >= 2
        # T_HARD has higher heuristic score due to difficulty weight, should be scheduled first
        first_session = result.sessions[0]
        assert first_session.task_id == "T_HARD"

    def test_insufficient_capacity_leaves_tasks_unscheduled(
        self,
        scheduler: GreedyEDFScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify tasks that cannot fit before deadline remain unscheduled."""
        # Low availability profile: only 1.0 hour available on Monday
        constrained_student = StudentProfile(
            student_id="STU_BUSY",
            name="Busy Student",
            daily_availability={"monday": 1.0, "tuesday": 0.0, "wednesday": 0.0},
            max_daily_hours=2.0,
            max_continuous_hours=1.0,
        )
        # Task requires 4.0 hours, due on Tuesday
        big_task = StudyTask(
            task_id="T_BIG",
            title="Heavy Research Project",
            subject=sample_subject_algorithms,
            estimated_hours=4.0,
            deadline=base_date + timedelta(days=1),
        )

        result = scheduler.schedule(
            tasks=[big_task],
            student=constrained_student,
            start_date=base_date,
            horizon_days=3,
        )

        # 1.0 hour allocated on Monday, but 3.0h needed and Tuesday is deadline with 0h available
        assert big_task in result.unscheduled_tasks
        assert result.total_scheduled_hours == 1.0
        assert result.is_fully_scheduled is False

    def test_cognitive_constraint_splits_long_task_with_break(
        self,
        scheduler: GreedyEDFScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify task exceeding max_continuous_hours is split into sessions with a break."""
        # Student allows max 2.0h continuous study, 30 min break, 5h available on Monday
        student = StudentProfile(
            student_id="STU_COG",
            name="Cognitive Test Student",
            daily_availability={"monday": 5.0},
            max_daily_hours=6.0,
            max_continuous_hours=2.0,
            break_duration_minutes=30,  # 0.5 hours
        )
        # Task requires 3.5 hours
        long_task = StudyTask(
            task_id="T_LONG",
            title="Long Study Session",
            subject=sample_subject_algorithms,
            estimated_hours=3.5,
            deadline=base_date + timedelta(days=2),
        )

        result = scheduler.schedule(
            tasks=[long_task],
            student=student,
            start_date=base_date,
            horizon_days=2,
            day_start_hour=9.0,
        )

        assert long_task in result.completed_tasks
        sessions = result.get_task_sessions("T_LONG")
        # Should be split into 2 sessions: 2.0h and 1.5h
        assert len(sessions) == 2
        assert sessions[0].hours == 2.0
        assert sessions[1].hours == 1.5

        # Verify break was inserted:
        # Session 0: 09:00 to 11:00 (end_hour = 11.0)
        # Break: 30 mins (0.5h) -> next start should be 11.5 (11:30)
        assert sessions[0].slot.start_hour == 9.0
        assert sessions[0].slot.end_hour == 11.0
        assert sessions[1].slot.start_hour == 11.5
        assert sessions[1].slot.end_hour == 13.0
        assert result.has_overlapping_slots() is False

    def test_strict_deadline_enforcement_never_schedules_past_due(
        self,
        scheduler: GreedyEDFScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify scheduler never creates slots for a task on dates after its deadline."""
        student = StudentProfile(
            student_id="STU_DEADLINE",
            name="Deadline Student",
            daily_availability={"monday": 2.0, "tuesday": 2.0, "wednesday": 2.0},
            max_daily_hours=4.0,
            max_continuous_hours=2.0,
        )
        # Task requires 5 hours, due on Tuesday (base_date + 1)
        # Monday (2h) + Tuesday (2h) = 4h total possible before deadline
        task = StudyTask(
            task_id="T_STRICT",
            title="Strict Due Date Task",
            subject=sample_subject_algorithms,
            estimated_hours=5.0,
            deadline=base_date + timedelta(days=1),  # Tuesday
        )

        result = scheduler.schedule(
            tasks=[task],
            student=student,
            start_date=base_date,
            horizon_days=5,
        )

        # Confirm no session was assigned on Wednesday or later
        for session in result.sessions:
            assert session.slot.slot_date <= task.deadline

        assert task in result.unscheduled_tasks
        assert result.total_scheduled_hours == 4.0


class TestScheduleMetricsEvaluation:
    """Tests evaluation metrics calculation on ScheduleResult."""

    def test_evaluate_schedule_metrics(
        self,
        scheduler: GreedyEDFScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        sample_subject_ml: Subject,
        base_date: date,
    ) -> None:
        """Verify metrics calculations for completion rates and workload distribution."""
        task1 = StudyTask(
            task_id="T1",
            title="Algorithms Task",
            subject=sample_subject_algorithms,
            estimated_hours=3.0,
            deadline=base_date + timedelta(days=2),
            difficulty=Difficulty.HARD,
        )
        task2 = StudyTask(
            task_id="T2",
            title="ML Task",
            subject=sample_subject_ml,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=3),
            difficulty=Difficulty.VERY_HARD,
        )

        result = scheduler.schedule(
            tasks=[task1, task2],
            student=standard_student,
            start_date=base_date,
            horizon_days=7,
        )

        metrics = evaluate_schedule(result, standard_student)

        assert metrics.total_tasks == 2
        assert metrics.completed_tasks == 2
        assert metrics.completion_rate == 1.0
        assert metrics.on_time_tasks == 2
        assert metrics.on_time_rate == 1.0
        assert metrics.total_scheduled_hours == 5.0
        assert metrics.capacity_utilization > 0.0
        assert metrics.high_difficulty_hours == 5.0
        assert metrics.cognitive_load_index > 0.0
        assert metrics.mean_daily_hours > 0.0
