"""Dynamic Programming 0/1 Knapsack scheduler for academic workload planning.

Mathematical Formulation & Theoretical Properties:
--------------------------------------------------
1. Discrete Slot Representation:
   Daily student availability C_hours is discretized into integer slot units of
   size delta_t = 0.5 hours (30 minutes):
       W = floor(C_hours / delta_t)
   Each candidate academic task T_i has an integer slot weight:
       w_i = ceil(T_i.estimated_hours / delta_t)

2. Academic Utility Function (Objective):
   Let d_i = (T_i.deadline - current_date).days.
   For eligible tasks (d_i >= 0), task utility u_i is computed from urgency,
   academic priority p_i, and cognitive difficulty c_i:
       urgency_i = 10.0 / max(0.5, float(d_i))
       u_i = w_urgency * urgency_i + w_priority * p_i + w_difficulty * c_i

3. Single-Day 0/1 Knapsack Optimization Problem:
       Maximize:   sum_{i=1}^N u_i * x_i
       Subject to: sum_{i=1}^N w_i * x_i <= W
                   x_i in {0, 1} for all i in {1, ..., N}

4. Dynamic Programming Recurrence:
   Let DP[i][w] be the maximum utility achievable using a subset of the first i
   tasks within capacity w in {0, ..., W}:
       DP[0][w] = 0   for all w in {0, ..., W}
       DP[i][w] = DP[i-1][w]                                    if w < w_i
       DP[i][w] = max(DP[i-1][w], DP[i-1][w - w_i] + u_i)       if w >= w_i

5. Space Optimization (Rolling Array):
   Since DP[i][w] depends only on the previous stage DP[i-1][...], the state array
   can be compressed to 1D of size (W + 1) traversed in reverse (from W down to w_i).

6. Proof of Optimality & Scope Boundary:
   By Bellman's Principle of Optimality, every sub-problem exhibits optimal substructure
   and overlapping subproblems. Thus, the DP recurrence is provably optimal for the
   discrete single-day 0/1 Knapsack problem.
   LIMITATION: This does NOT claim global optimality across arbitrary multi-day horizons
   with evolving inter-day precedence and deadline cascades, which is NP-hard.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from scholarsync.algorithms.base import (
    DEFAULT_DAY_START_HOUR,
    DEFAULT_HORIZON_DAYS,
    BaseSchedulerStrategy,
)
from scholarsync.core.types import MIN_STUDY_HOURS
from scholarsync.models.schedule import ScheduledSession, ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.task import StudyTask
from scholarsync.models.time_slot import TimeSlot

# Default slot resolution (30 minutes)
DEFAULT_SLOT_STEP_HOURS: Final[float] = 0.5

# Heuristic weights for utility calculation
DEFAULT_URGENCY_WEIGHT: Final[float] = 1.0
DEFAULT_PRIORITY_WEIGHT: Final[float] = 0.5
DEFAULT_DIFFICULTY_WEIGHT: Final[float] = 0.25


@dataclass(frozen=True)
class KnapsackItem:
    """Internal representation of a task mapped to discrete knapsack slots."""

    task: StudyTask
    weight_slots: int
    utility: float
    scaled_utility: int  # Integer utility for strict, float-safe DP comparisons


@dataclass(frozen=True)
class KnapsackDaySolution:
    """Result of single-day knapsack optimization."""

    selected_tasks: tuple[StudyTask, ...]
    total_utility: float
    total_slots: int
    total_hours: float
    capacity_slots: int


class DPKnapsackScheduler(BaseSchedulerStrategy):
    """Deterministic Dynamic Programming 0/1 Knapsack academic scheduler.

    Selects an optimal subset of tasks for daily study capacity using discrete
    knapsack optimization, maximizing total academic utility.
    """

    def __init__(
        self,
        slot_step_hours: float = DEFAULT_SLOT_STEP_HOURS,
        urgency_weight: float = DEFAULT_URGENCY_WEIGHT,
        priority_weight: float = DEFAULT_PRIORITY_WEIGHT,
        difficulty_weight: float = DEFAULT_DIFFICULTY_WEIGHT,
    ) -> None:
        self.slot_step_hours = slot_step_hours
        self.urgency_weight = urgency_weight
        self.priority_weight = priority_weight
        self.difficulty_weight = difficulty_weight

    @property
    def name(self) -> str:
        return "Dynamic Programming 0/1 Knapsack"

    def compute_task_utility(self, task: StudyTask, current_date: date) -> float:
        """Calculate continuous utility score for a task on a given evaluation date."""
        days_to_deadline = (task.deadline - current_date).days
        clamped_days = max(0.5, float(days_to_deadline))
        urgency = 10.0 / clamped_days

        utility = (
            self.urgency_weight * urgency
            + self.priority_weight * float(task.priority)
            + self.difficulty_weight * float(task.difficulty)
        )
        return round(utility, 4)

    def solve_single_day_knapsack(
        self,
        tasks: Sequence[StudyTask],
        available_hours: float,
        current_date: date,
    ) -> KnapsackDaySolution:
        """Solve the 0/1 Knapsack problem for a single day using dynamic programming.

        Args:
            tasks: Eligible candidate tasks for the day.
            available_hours: Available study hours on this day.
            current_date: Calendar date of the day.

        Returns:
            KnapsackDaySolution with optimal subset of tasks and total utility.
        """
        # Calculate discrete capacity in slots
        capacity_slots = int(available_hours / self.slot_step_hours)
        if capacity_slots <= 0 or not tasks:
            return KnapsackDaySolution(
                selected_tasks=(),
                total_utility=0.0,
                total_slots=0,
                total_hours=0.0,
                capacity_slots=capacity_slots,
            )

        # Convert eligible tasks to knapsack items
        items: list[KnapsackItem] = []
        for task in tasks:
            # Task weight in discrete slots (at least 1 slot)
            w_slots = max(
                1, math.ceil(round(float(task.estimated_hours), 4) / self.slot_step_hours)
            )
            # If item weight exceeds capacity, it cannot be selected
            if w_slots <= capacity_slots:
                util = self.compute_task_utility(task, current_date)
                # Scale utility by 10,000 for integer DP table precision
                scaled_u = int(round(util * 10000))
                items.append(
                    KnapsackItem(
                        task=task,
                        weight_slots=w_slots,
                        utility=util,
                        scaled_utility=scaled_u,
                    )
                )

        if not items:
            return KnapsackDaySolution(
                selected_tasks=(),
                total_utility=0.0,
                total_slots=0,
                total_hours=0.0,
                capacity_slots=capacity_slots,
            )

        # Deterministic ordering of items before DP to guarantee stable backtracking:
        # Sort items primarily by scaled_utility desc, then weight asc, then task_id asc
        items.sort(key=lambda it: (-it.scaled_utility, it.weight_slots, it.task.task_id))

        num_items = len(items)
        w_cap = capacity_slots

        # DP Table: dp[i][w] stores maximum scaled utility
        # keep[i][w] tracks if item i was included to achieve dp[i][w]
        dp = [[0] * (w_cap + 1) for _ in range(num_items + 1)]
        keep = [[False] * (w_cap + 1) for _ in range(num_items + 1)]

        for i in range(1, num_items + 1):
            item = items[i - 1]
            wt = item.weight_slots
            val = item.scaled_utility

            for w in range(w_cap + 1):
                if wt > w:
                    # Item cannot fit in capacity w
                    dp[i][w] = dp[i - 1][w]
                else:
                    without_item = dp[i - 1][w]
                    with_item = dp[i - 1][w - wt] + val

                    if with_item > without_item:
                        dp[i][w] = with_item
                        keep[i][w] = True
                    else:
                        # Deterministic tie-breaker: keep the existing allocation without item
                        dp[i][w] = without_item

        # Backtrack to reconstruct selected tasks
        selected_items: list[KnapsackItem] = []
        rem_w = w_cap
        for i in range(num_items, 0, -1):
            if keep[i][rem_w]:
                selected_items.append(items[i - 1])
                rem_w -= items[i - 1].weight_slots

        # Re-sort selected tasks chronologically/deterministically:
        # Higher priority, then earliest deadline, then task_id
        selected_items.sort(
            key=lambda it: (
                it.task.deadline,
                -it.task.priority,
                -it.task.difficulty,
                it.task.task_id,
            )
        )

        selected_tasks = tuple(it.task for it in selected_items)
        total_util = sum(it.utility for it in selected_items)
        total_slots = sum(it.weight_slots for it in selected_items)
        total_hours = sum(it.task.estimated_hours for it in selected_items)

        return KnapsackDaySolution(
            selected_tasks=selected_tasks,
            total_utility=round(total_util, 4),
            total_slots=total_slots,
            total_hours=round(total_hours, 2),
            capacity_slots=capacity_slots,
        )

    def schedule(
        self,
        tasks: Sequence[StudyTask],
        student: StudentProfile,
        start_date: date,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        day_start_hour: float = DEFAULT_DAY_START_HOUR,
    ) -> ScheduleResult:
        """Execute the Dynamic Programming 0/1 Knapsack scheduler.

        For each day in the planning horizon, solves the 0/1 knapsack on eligible
        tasks within that day's student study capacity.
        """
        # 1. Validate inputs and task dependency graph
        self.validate_inputs(tasks, student, start_date, horizon_days, day_start_hour)

        # Empty tasks boundary check
        if not tasks:
            return ScheduleResult(
                strategy_name=self.name,
                start_date=start_date,
                end_date=start_date + timedelta(days=horizon_days - 1),
                sessions=(),
                completed_tasks=(),
                unscheduled_tasks=(),
                task_completion_dates={},
            )

        end_date = start_date + timedelta(days=horizon_days - 1)

        # Track completed tasks and dates
        completed_task_ids: set[str] = {task.task_id for task in tasks if task.completed}
        task_completion_dates: dict[str, date] = {}
        scheduled_sessions: list[ScheduledSession] = []

        break_duration_hours = student.break_duration_minutes / 60.0

        # Simulate day-by-day across horizon
        current_date = start_date
        while current_date <= end_date:
            weekday_name = current_date.strftime("%A").lower()
            daily_budget = student.get_daily_hours(weekday_name)

            if daily_budget > 0.0:
                # Filter tasks eligible for today's knapsack:
                # - Not yet completed
                # - Deadline not passed (deadline >= current_date)
                # - All prerequisites completed
                eligible_tasks = [
                    task
                    for task in tasks
                    if task.task_id not in completed_task_ids
                    and task.deadline >= current_date
                    and all(p in completed_task_ids for p in task.prerequisites)
                ]

                # Run DP 0/1 Knapsack on today's budget
                knapsack_solution = self.solve_single_day_knapsack(
                    tasks=eligible_tasks,
                    available_hours=daily_budget,
                    current_date=current_date,
                )

                # Generate chronological TimeSlots for selected tasks
                clock = float(day_start_hour)

                for task in knapsack_solution.selected_tasks:
                    task_hours = task.estimated_hours
                    # Respect max_continuous_hours: if task duration exceeds continuous limit,
                    # split it into continuous sessions separated by mandatory rest breaks
                    rem_task_hours = task_hours

                    while rem_task_hours > 0.0 and clock < 24.0:
                        session_dur = min(
                            rem_task_hours, student.max_continuous_hours, 24.0 - clock
                        )
                        if session_dur < MIN_STUDY_HOURS:
                            break

                        slot = TimeSlot(
                            slot_date=current_date,
                            start_hour=round(clock, 4),
                            duration_hours=round(session_dur, 4),
                            label=f"{task.subject.code}: {task.title}",
                            slot_id=f"SLOT_{len(scheduled_sessions) + 1:04d}",
                        )

                        rem_task_hours -= session_dur
                        clock += session_dur
                        is_final_chunk = rem_task_hours <= 0.001

                        scheduled_sessions.append(
                            ScheduledSession(
                                task_id=task.task_id,
                                task_title=task.title,
                                subject_code=task.subject.code,
                                slot=slot,
                                hours=round(session_dur, 4),
                                is_completed_here=is_final_chunk,
                            )
                        )

                        # Insert rest break if more chunks or tasks remain today
                        if clock < 24.0 and (rem_task_hours > 0.0 or break_duration_hours > 0.0):
                            clock = min(24.0, clock + break_duration_hours)

                    # Mark task as completed in this 0/1 knapsack day
                    completed_task_ids.add(task.task_id)
                    task_completion_dates[task.task_id] = current_date

            current_date += timedelta(days=1)

        completed_tasks_list = [task for task in tasks if task.task_id in completed_task_ids]
        unscheduled_tasks_list = [task for task in tasks if task.task_id not in completed_task_ids]

        final_remaining_hours: dict[str, float] = {
            task.task_id: (
                0.0 if task.task_id in completed_task_ids else round(float(task.estimated_hours), 2)
            )
            for task in tasks
        }

        return ScheduleResult(
            strategy_name=self.name,
            start_date=start_date,
            end_date=end_date,
            sessions=tuple(scheduled_sessions),
            completed_tasks=tuple(completed_tasks_list),
            unscheduled_tasks=tuple(unscheduled_tasks_list),
            task_completion_dates=task_completion_dates,
            remaining_task_hours=final_remaining_hours,
        )
