"""Comprehensive tests for Dynamic Programming 0/1 Knapsack scheduler.

Validates:
1. Verifiable known optimal solution
2. Formal proof/case where Greedy is suboptimal and DP is optimal
3. Capacity and duration boundaries (zero capacity, fractional slots, exact match, oversized)
4. Prerequisite enforcement and cycle detection
5. Deterministic tie-breaking
6. Empty and infeasible inputs
7. Integration with ScheduleResult, TimeSlot, and metrics
"""

from datetime import date, timedelta

import pytest

from scholarsync.algorithms.dynamic_programming import DPKnapsackScheduler
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
    """Standard test date (Monday)."""
    return date(2026, 10, 12)


@pytest.fixture
def dp_scheduler() -> DPKnapsackScheduler:
    """Instance of DPKnapsackScheduler."""
    return DPKnapsackScheduler()


@pytest.fixture
def standard_student() -> StudentProfile:
    """Standard student profile with 4h weekdays."""
    return StudentProfile(
        student_id="STU_DP_TEST",
        name="Kavya Nair",
        daily_availability={"monday": 4.0, "tuesday": 4.0},
        max_daily_hours=6.0,
        max_continuous_hours=2.0,
        break_duration_minutes=15,
    )


class TestDPKnapsackBasicsAndBoundaries:
    """Tests basic interface, empty inputs, and capacity boundaries."""

    def test_dp_scheduler_name(self, dp_scheduler: DPKnapsackScheduler) -> None:
        """Verify scheduler strategy name."""
        assert dp_scheduler.name == "Dynamic Programming 0/1 Knapsack"

    def test_empty_tasks_input(
        self,
        dp_scheduler: DPKnapsackScheduler,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify empty task list returns valid empty ScheduleResult."""
        result = dp_scheduler.schedule(
            tasks=[],
            student=standard_student,
            start_date=base_date,
            horizon_days=1,
        )
        assert len(result.sessions) == 0
        assert len(result.completed_tasks) == 0
        assert len(result.unscheduled_tasks) == 0
        assert result.total_scheduled_hours == 0.0
        assert result.is_fully_scheduled is True
        assert result.has_overlapping_slots() is False

    def test_zero_capacity_returns_empty_solution(
        self,
        dp_scheduler: DPKnapsackScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify 0.0 available hours yields 0 selected tasks."""
        task = StudyTask(
            task_id="T01",
            title="Algorithm Task",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
        )
        solution = dp_scheduler.solve_single_day_knapsack(
            tasks=[task],
            available_hours=0.0,
            current_date=base_date,
        )
        assert len(solution.selected_tasks) == 0
        assert solution.total_utility == 0.0
        assert solution.capacity_slots == 0

    def test_oversized_task_cannot_fit(
        self,
        dp_scheduler: DPKnapsackScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify task whose duration exceeds knapsack capacity is excluded."""
        # Available capacity: 2.0h (4 slots). Task needs 3.0h (6 slots).
        oversized = StudyTask(
            task_id="T_OVERSIZED",
            title="Massive Project",
            subject=sample_subject_algorithms,
            estimated_hours=3.0,
            deadline=base_date + timedelta(days=2),
        )
        solution = dp_scheduler.solve_single_day_knapsack(
            tasks=[oversized],
            available_hours=2.0,
            current_date=base_date,
        )
        assert len(solution.selected_tasks) == 0
        assert solution.total_utility == 0.0

    def test_exact_capacity_fit(
        self,
        dp_scheduler: DPKnapsackScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify task matching exactly available capacity is selected."""
        exact_task = StudyTask(
            task_id="T_EXACT",
            title="Exact Fit Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=base_date + timedelta(days=1),
        )
        solution = dp_scheduler.solve_single_day_knapsack(
            tasks=[exact_task],
            available_hours=2.0,
            current_date=base_date,
        )
        assert len(solution.selected_tasks) == 1
        assert solution.selected_tasks[0].task_id == "T_EXACT"
        assert solution.total_slots == 4
        assert solution.capacity_slots == 4

    def test_invalid_input_validation(
        self,
        dp_scheduler: DPKnapsackScheduler,
        standard_student: StudentProfile,
        base_date: date,
    ) -> None:
        """Verify invalid parameters raise ValidationError."""
        with pytest.raises(ValidationError, match="horizon_days"):
            dp_scheduler.schedule(
                tasks=[],
                student=standard_student,
                start_date=base_date,
                horizon_days=-1,
            )


class TestDPKnapsackOptimalityVsGreedy:
    """Verifies that DP finds the global maximum where Greedy makes a suboptimal choice."""

    def test_dp_beats_greedy_suboptimal_choice(
        self,
        dp_scheduler: DPKnapsackScheduler,
        sample_subject_algorithms: Subject,
        sample_subject_ml: Subject,
        base_date: date,
    ) -> None:
        """Classic Knapsack proof: Greedy picks highest urgency task, blocking better combination.

        Setup:
        Capacity = 2.0 hours (4 slots of 0.5h).
        - Task A: duration 1.5h (3 slots), due TODAY (high urgency).
          Urgency = 10 / 0.5 = 20.0, Priority 4, Diff 4 -> Utility = 23.0
        - Task B: duration 1.0h (2 slots), due TOMORROW (medium urgency).
          Urgency = 10 / 1.0 = 10.0, Priority 5, Diff 5 -> Utility = 13.75
        - Task C: duration 1.0h (2 slots), due TOMORROW (medium urgency).
          Urgency = 10 / 1.0 = 10.0, Priority 5, Diff 5 -> Utility = 13.75

        Greedy choice:
        - Picks Task A (utility 23.0, uses 3 slots). Remaining 1 slot cannot fit Task B or C!
        - Greedy Total Utility = 23.0

        DP Knapsack choice:
        - Evaluates combinations:
          {Task A}: weight 3 slots, utility 23.0
          {Task B, Task C}: weight 2 + 2 = 4 slots, utility = 13.75 + 13.75 = 27.5
        - DP Total Utility = 27.5 > 23.0!
        """
        task_a = StudyTask(
            task_id="TASK_A",
            title="Task A - High Urgency Heavy",
            subject=sample_subject_algorithms,
            estimated_hours=1.5,
            deadline=base_date,  # Due today
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
        )
        task_b = StudyTask(
            task_id="TASK_B",
            title="Task B - High Value Medium",
            subject=sample_subject_ml,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=1),  # Due tomorrow
            priority=Priority.CRITICAL,
            difficulty=Difficulty.VERY_HARD,
        )
        task_c = StudyTask(
            task_id="TASK_C",
            title="Task C - High Value Medium",
            subject=sample_subject_ml,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=1),  # Due tomorrow
            priority=Priority.CRITICAL,
            difficulty=Difficulty.VERY_HARD,
        )

        all_tasks = [task_a, task_b, task_c]
        capacity_hours = 2.0

        # Solve via DP
        dp_solution = dp_scheduler.solve_single_day_knapsack(
            tasks=all_tasks,
            available_hours=capacity_hours,
            current_date=base_date,
        )

        # Solve via Greedy
        greedy_scheduler = GreedyEDFScheduler()
        student = StudentProfile(
            student_id="STU_CMP",
            name="Comparison Student",
            daily_availability={"monday": capacity_hours},
            max_daily_hours=4.0,
            max_continuous_hours=2.0,
        )
        greedy_result = greedy_scheduler.schedule(
            tasks=all_tasks,
            student=student,
            start_date=base_date,
            horizon_days=1,
        )

        # 1. DP selects Task B and Task C
        selected_ids = {t.task_id for t in dp_solution.selected_tasks}
        assert selected_ids == {"TASK_B", "TASK_C"}
        assert dp_solution.total_slots == 4
        assert dp_solution.total_utility == 27.5

        # 2. Greedy only scheduled Task A on this day
        greedy_completed_ids = {t.task_id for t in greedy_result.completed_tasks}
        assert greedy_completed_ids == {"TASK_A"}
        greedy_utility = dp_scheduler.compute_task_utility(task_a, base_date)

        # 3. Prove DP utility strictly exceeds Greedy utility
        assert dp_solution.total_utility > greedy_utility
        assert dp_solution.total_utility == 27.5
        assert greedy_utility == 23.0


class TestDPKnapsackPrerequisitesAndCycles:
    """Verifies prerequisite handling, cycle detection, and missing dependencies."""

    def test_unresolved_prerequisite_rejected(
        self,
        dp_scheduler: DPKnapsackScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify missing prerequisite raises UnresolvedDependencyError."""
        task = StudyTask(
            task_id="T01",
            title="Dependent Task",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
            prerequisites=("NON_EXISTENT_ID",),
        )
        with pytest.raises(UnresolvedDependencyError, match="unresolved prerequisite"):
            dp_scheduler.schedule(
                tasks=[task],
                student=standard_student,
                start_date=base_date,
                horizon_days=1,
            )

    def test_cyclic_dependency_rejected(
        self,
        dp_scheduler: DPKnapsackScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify cyclic prerequisites raise CyclicDependencyError."""
        t1 = StudyTask(
            task_id="T1",
            title="Task 1",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
            prerequisites=("T2",),
        )
        t2 = StudyTask(
            task_id="T2",
            title="Task 2",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
            prerequisites=("T1",),
        )
        with pytest.raises(CyclicDependencyError, match="Cyclic dependency detected"):
            dp_scheduler.schedule(
                tasks=[t1, t2],
                student=standard_student,
                start_date=base_date,
                horizon_days=1,
            )

    def test_uncompleted_prerequisite_blocks_task_from_knapsack(
        self,
        dp_scheduler: DPKnapsackScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify dependent task is not included if prerequisite has not yet completed."""
        prereq = StudyTask(
            task_id="PREREQ",
            title="Prerequisite Task",
            subject=sample_subject_algorithms,
            estimated_hours=4.0,  # Fills full day
            deadline=base_date + timedelta(days=2),
        )
        dependent = StudyTask(
            task_id="DEPENDENT",
            title="Dependent Task",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=2),
            prerequisites=("PREREQ",),
        )

        result = dp_scheduler.schedule(
            tasks=[dependent, prereq],
            student=standard_student,
            start_date=base_date,
            horizon_days=1,
        )

        # On day 1, only PREREQ can be selected
        assert prereq in result.completed_tasks
        assert dependent in result.unscheduled_tasks


class TestDPKnapsackTieBreakingAndScheduleIntegration:
    """Tests deterministic tie-breaking and complete schedule generation."""

    def test_deterministic_tie_breaking(
        self,
        dp_scheduler: DPKnapsackScheduler,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify deterministic selection when multiple items have identical weight and utility."""
        # Two tasks with identical duration (1.0h = 2 slots) and
        # identical deadline, priority, and difficulty
        t1 = StudyTask(
            task_id="TASK_ALPHA",
            title="Identical Alpha",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=1),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.MODERATE,
        )
        t2 = StudyTask(
            task_id="TASK_BETA",
            title="Identical Beta",
            subject=sample_subject_algorithms,
            estimated_hours=1.0,
            deadline=base_date + timedelta(days=1),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.MODERATE,
        )

        # Knapsack capacity = 1.0h (only 1 can fit)
        solution1 = dp_scheduler.solve_single_day_knapsack(
            tasks=[t1, t2],
            available_hours=1.0,
            current_date=base_date,
        )
        solution2 = dp_scheduler.solve_single_day_knapsack(
            tasks=[t2, t1],  # Reverse input order
            available_hours=1.0,
            current_date=base_date,
        )

        # Both runs must produce the exact same selected task deterministically
        assert len(solution1.selected_tasks) == 1
        assert len(solution2.selected_tasks) == 1
        assert solution1.selected_tasks[0].task_id == solution2.selected_tasks[0].task_id

    def test_full_schedule_generation_with_breaks(
        self,
        dp_scheduler: DPKnapsackScheduler,
        standard_student: StudentProfile,
        sample_subject_algorithms: Subject,
        base_date: date,
    ) -> None:
        """Verify schedule generation respects continuous limits and inserts breaks."""
        task_long = StudyTask(
            task_id="T_LONG",
            title="Algorithms Deep Dive",
            subject=sample_subject_algorithms,
            estimated_hours=3.0,  # Exceeds max_continuous_hours (2.0h)
            deadline=base_date + timedelta(days=1),
        )

        result = dp_scheduler.schedule(
            tasks=[task_long],
            student=standard_student,
            start_date=base_date,
            horizon_days=1,
            day_start_hour=9.0,
        )

        assert task_long in result.completed_tasks
        assert result.total_scheduled_hours == 3.0
        assert result.has_overlapping_slots() is False

        sessions = result.get_task_sessions("T_LONG")
        # Split into 2 sessions: 2.0h and 1.0h
        assert len(sessions) == 2
        assert sessions[0].hours == 2.0
        assert sessions[1].hours == 1.0
        assert sessions[0].slot.start_hour == 9.0
        assert sessions[0].slot.end_hour == 11.0
        # Break of 15 min (0.25h) -> starts at 11.25
        assert sessions[1].slot.start_hour == 11.25

        # Evaluate metrics
        metrics = evaluate_schedule(result, standard_student)
        assert metrics.total_tasks == 1
        assert metrics.completed_tasks == 1
        assert metrics.completion_rate == 1.0
        assert metrics.total_scheduled_hours == 3.0
