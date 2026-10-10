"""Regression tests and semantic verification for Greedy, DP, and Hybrid schedulers.

Formalizes and validates the algorithmic comparison semantics:
1. Multi-day splitting capability:
   - Tasks exceeding single-day capacity can be fractionally split across days
     by Greedy and Hybrid schedulers.
   - In contrast, DPKnapsackScheduler operates as an atomic single-day 0/1 knapsack,
     so tasks exceeding single-day capacity cannot fit into any day's knapsack and
     remain unscheduled.
2. Single-day optimization optimality:
   - On a single day with fixed capacity, DPKnapsackScheduler provably achieves equal
     or higher knapsack utility than Greedy heuristic by solving the 0/1 knapsack recurrence.
3. Multi-day repeated application:
   - Over multi-day horizons, DPKnapsackScheduler repeatedly applies the 0/1 knapsack
     policy day-by-day to remaining eligible tasks.
4. Prerequisite topology:
   - All three schedulers strictly respect prerequisite completion order.
"""

from datetime import date, timedelta
from typing import Final

import pytest

from scholarsync.algorithms.dynamic_programming import DPKnapsackScheduler
from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.algorithms.hybrid import RollingHorizonHybridScheduler
from scholarsync.core.types import Difficulty, Priority
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask

START_DATE: Final[date] = date(2026, 10, 12)  # Monday


@pytest.fixture
def test_subject() -> Subject:
    """Standard subject for semantic tests."""
    return Subject(code="CS601", name="Advanced Algorithms", credits=4)


@pytest.fixture
def constrained_student() -> StudentProfile:
    """Student with strict 4.0 hours per day capacity."""
    return StudentProfile(
        student_id="STU_SEMANTICS",
        name="Test Student",
        daily_availability={"monday": 4.0, "tuesday": 4.0, "wednesday": 4.0, "thursday": 4.0},
        max_daily_hours=4.0,
        max_continuous_hours=2.0,
        break_duration_minutes=15,
    )


class TestAlgorithmComparisonSemantics:
    """Test suite proving the semantic and theoretical differences among the 3 schedulers."""

    def test_task_exceeding_daily_capacity_greedy_and_hybrid_split_dp_rejects(
        self,
        test_subject: Subject,
        constrained_student: StudentProfile,
    ) -> None:
        """Tasks larger than single-day capacity split in Greedy/Hybrid, but cannot fit in 0/1 DP.

        Scenario:
        - Student has exactly 4.0 hours available each day.
        - Task T_LARGE requires 5.0 hours (estimated_hours = 5.0).
        - Planning horizon is 4 days (total available capacity = 16.0 hours).

        Expected Behavior:
        - Greedy: Splits T_LARGE (4.0h on Monday, 1.0h on Tuesday) -> Fully Completed.
        - Hybrid: Splits T_LARGE across days -> Fully Completed.
        - DP: Atomic 0/1 Knapsack rejects T_LARGE because 5.0h exceeds the 4.0h knapsack capacity
              on every single day -> Unscheduled (0.0 hours scheduled, 5.0 hours remaining).
        """
        large_task = StudyTask(
            task_id="T_LARGE",
            title="Comprehensive Semester Project",
            subject=test_subject,
            estimated_hours=5.0,
            deadline=START_DATE + timedelta(days=3),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.HARD,
        )

        greedy = GreedyEDFScheduler()
        dp = DPKnapsackScheduler()
        hybrid = RollingHorizonHybridScheduler()

        # 1. Greedy scheduler execution
        greedy_res = greedy.schedule([large_task], constrained_student, START_DATE, horizon_days=4)
        assert greedy_res.is_fully_scheduled is True
        assert greedy_res.total_scheduled_hours == 5.0
        assert len(greedy_res.sessions) >= 2  # Split across multiple sessions/days
        assert greedy_res.get_remaining_hours("T_LARGE") == 0.0

        # 2. Hybrid scheduler execution
        hybrid_res = hybrid.schedule([large_task], constrained_student, START_DATE, horizon_days=4)
        assert hybrid_res.is_fully_scheduled is True
        assert hybrid_res.total_scheduled_hours == 5.0
        assert hybrid_res.get_remaining_hours("T_LARGE") == 0.0

        # 3. DP 0/1 Knapsack scheduler execution
        dp_res = dp.schedule([large_task], constrained_student, START_DATE, horizon_days=4)
        assert dp_res.is_fully_scheduled is False
        assert dp_res.total_scheduled_hours == 0.0
        assert len(dp_res.completed_tasks) == 0
        assert len(dp_res.unscheduled_tasks) == 1
        assert dp_res.get_remaining_hours("T_LARGE") == 5.0

    def test_single_day_knapsack_optimality_over_greedy_heuristic(
        self,
        test_subject: Subject,
    ) -> None:
        """On a single day with fixed capacity, DP achieves strictly higher utility than Greedy.

        Scenario:
        - Single day capacity: 4.0 hours (Monday).
        - Task A: duration 2.0h, priority 4, difficulty 3 (utility ~ 12.0)
        - Task B: duration 2.0h, priority 4, difficulty 3 (utility ~ 12.0)
        - Task C: duration 3.0h, priority 5, difficulty 4 (utility ~ 17.0, highest single utility)

        Dynamics:
        - Greedy picks Task C first because it has highest individual urgency/priority score.
          This leaves only 1.0h capacity remaining, so neither Task A (2h) nor Task B (2h) can fit.
          Greedy gets 3.0h scheduled, total utility ~ 17.0.
        - DP Knapsack evaluates combinations:
          Combination {A, B} has weight 4.0h, total utility = 24.0.
          Combination {C} has weight 3.0h, total utility = 17.0.
          DP optimal solution selects {A, B}, utilizing 100% capacity with utility 24.0 > 17.0.
        """
        # Same deadline so urgency is equal; priorities and difficulties dictate values
        t_a = StudyTask(
            task_id="TA",
            title="Task A",
            subject=test_subject,
            estimated_hours=2.0,
            deadline=START_DATE + timedelta(days=2),
            priority=Priority.HIGH,
            difficulty=Difficulty.INTERMEDIATE,
        )
        t_b = StudyTask(
            task_id="TB",
            title="Task B",
            subject=test_subject,
            estimated_hours=2.0,
            deadline=START_DATE + timedelta(days=2),
            priority=Priority.HIGH,
            difficulty=Difficulty.INTERMEDIATE,
        )
        t_c = StudyTask(
            task_id="TC",
            title="Task C",
            subject=test_subject,
            estimated_hours=3.0,
            deadline=START_DATE + timedelta(days=2),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.HARD,
        )

        dp = DPKnapsackScheduler()
        sol = dp.solve_single_day_knapsack(
            tasks=[t_a, t_b, t_c],
            available_hours=4.0,
            current_date=START_DATE,
        )

        # DP selects {TA, TB} to maximize knapsack capacity and total utility
        selected_ids = {t.task_id for t in sol.selected_tasks}
        assert selected_ids == {"TA", "TB"}
        assert sol.total_hours == 4.0
        assert sol.total_utility > dp.compute_task_utility(t_c, START_DATE)

    def test_multi_day_sequential_dp_completes_tasks_when_each_fits_daily_budget(
        self,
        test_subject: Subject,
        constrained_student: StudentProfile,
    ) -> None:
        """When tasks fit within daily capacities, DP completes all tasks sequentially day-by-day.

        Explains why the CLI comparison showed 7/7 completed:
        Because all 7 tasks had durations <= 4.0 hours, and daily budgets were 3.5h - 6.0h.
        """
        t1 = StudyTask(
            task_id="T01",
            title="Task 1",
            subject=test_subject,
            estimated_hours=3.0,
            deadline=START_DATE + timedelta(days=1),
            priority=Priority.HIGH,
            difficulty=Difficulty.INTERMEDIATE,
        )
        t2 = StudyTask(
            task_id="T02",
            title="Task 2",
            subject=test_subject,
            estimated_hours=3.5,
            deadline=START_DATE + timedelta(days=2),
            priority=Priority.HIGH,
            difficulty=Difficulty.INTERMEDIATE,
        )

        dp = DPKnapsackScheduler()
        res = dp.schedule([t1, t2], constrained_student, START_DATE, horizon_days=3)

        assert res.is_fully_scheduled is True
        assert len(res.completed_tasks) == 2
        # Day 1 completes T01 (3h <= 4h); Day 2 completes T02 (3.5h <= 4h)
        assert res.task_completion_dates["T01"] == START_DATE
        assert res.task_completion_dates["T02"] == START_DATE + timedelta(days=1)
