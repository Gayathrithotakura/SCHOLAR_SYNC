"""Rolling-Horizon Hybrid Scheduler for academic workload planning.

Combines multi-day horizon simulation with daily Bounded-Chunk Dynamic Programming
optimization, balancing cognitive fatigue constraints and deadline feasibility.

Mathematical Formulation & Theoretical Properties:
--------------------------------------------------
1. Rolling-Horizon Decomposition:
   Decomposes the NP-hard global semester scheduling problem across a multi-day
   horizon H = [start_date, end_date].
   For each simulation day t in H:
     a. Determines available student capacity C_t in hours.
     b. Identifies the pool of eligible candidate tasks:
        Eligible(t) = { T_i in Tasks | rem_hours(T_i) > 0 and d_i >= t and
                        all p in P_i are completed }
     c. Formulates a daily Bounded-Chunk Knapsack optimization problem.
     d. Applies the optimal chunk allocation to the student's daily timeline,
        enforcing continuous session limits and inserting rest breaks.
     e. Advances to day t + 1 with updated task states.

2. Daily Bounded-Chunk DP Optimization:
   Let discrete slot resolution be delta_t = 0.5 hours (30 minutes).
   Daily slot capacity: W = floor(C_t / delta_t).
   For each eligible task T_i:
     - Remaining slots needed: r_i = ceil(rem_hours(T_i) / delta_t).
     - Maximum allowable slots today: K_i = min(r_i, W).
     - Base utility U_i is computed from deadline urgency, priority, and difficulty.
     - For each choice s in {0, ..., K_i} of slots allocated today:
         utility(T_i, s) = s * (U_i / total_slots_i) + completion_bonus (if s == r_i)

3. Recurrence:
   Let DP[i][w] be the maximum utility achievable considering the first i eligible
   tasks within daily slot budget w in {0, ..., W}:
       DP[i][w] = max_{0 <= s <= min(K_i, w)} ( DP[i-1][w - s] + utility(T_i, s) )

4. Scope Boundary & Academic Honesty:
   Daily Bounded-Chunk DP is optimal for each individual day's slot allocation.
   However, Rolling-Horizon decomposition is a bounded approximation heuristic
   and does NOT guarantee global multi-day optimality across arbitrary multi-week
   precedence graphs with dynamic deadlines (which is NP-hard).
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

DEFAULT_SLOT_STEP_HOURS: Final[float] = 0.5
DEFAULT_URGENCY_WEIGHT: Final[float] = 1.0
DEFAULT_PRIORITY_WEIGHT: Final[float] = 0.5
DEFAULT_DIFFICULTY_WEIGHT: Final[float] = 0.25
DEFAULT_COMPLETION_BONUS_RATIO: Final[float] = 0.2


@dataclass(frozen=True)
class DailyChunkAllocation:
    """Represents the optimal number of slots allocated to a task on a single day."""

    task: StudyTask
    allocated_slots: int
    allocated_hours: float
    is_completing_task: bool


class RollingHorizonHybridScheduler(BaseSchedulerStrategy):
    """Rolling-Horizon Hybrid Scheduler.

    Iterates across a multi-day horizon, using Bounded-Chunk Dynamic Programming
    to optimize daily task selections while supporting partial task progress,
    prerequisite precedence, and cognitive rest constraints.
    """

    def __init__(
        self,
        slot_step_hours: float = DEFAULT_SLOT_STEP_HOURS,
        urgency_weight: float = DEFAULT_URGENCY_WEIGHT,
        priority_weight: float = DEFAULT_PRIORITY_WEIGHT,
        difficulty_weight: float = DEFAULT_DIFFICULTY_WEIGHT,
        completion_bonus_ratio: float = DEFAULT_COMPLETION_BONUS_RATIO,
    ) -> None:
        self.slot_step_hours = slot_step_hours
        self.urgency_weight = urgency_weight
        self.priority_weight = priority_weight
        self.difficulty_weight = difficulty_weight
        self.completion_bonus_ratio = completion_bonus_ratio

    @property
    def name(self) -> str:
        return "Rolling-Horizon Hybrid Strategy"

    def compute_task_utility(self, task: StudyTask, current_date: date) -> float:
        """Calculate continuous utility score for an eligible task on a given date."""
        days_to_deadline = (task.deadline - current_date).days
        clamped_days = max(0.5, float(days_to_deadline))
        urgency = 10.0 / clamped_days

        utility = (
            self.urgency_weight * urgency
            + self.priority_weight * float(task.priority)
            + self.difficulty_weight * float(task.difficulty)
        )
        return round(utility, 4)

    def optimize_daily_bounded_chunks(
        self,
        eligible_tasks: Sequence[StudyTask],
        remaining_hours: dict[str, float],
        available_hours: float,
        current_date: date,
    ) -> list[DailyChunkAllocation]:
        """Solve the Bounded-Chunk DP Knapsack problem for a single day.

        Allows partial progress by allocating between 0 and K_i discrete slots
        to each eligible task without exceeding daily capacity or remaining task needs.
        """
        capacity_slots = int(available_hours / self.slot_step_hours)
        if capacity_slots <= 0 or not eligible_tasks:
            return []

        # Filter tasks that still require study hours
        active_candidates: list[StudyTask] = []
        for task in eligible_tasks:
            rem_h = remaining_hours.get(task.task_id, 0.0)
            if rem_h > 0.001 and task.deadline >= current_date:
                active_candidates.append(task)

        if not active_candidates:
            return []

        # Sort candidate tasks deterministically:
        # Earliest deadline, highest priority, highest difficulty, task_id
        sorted_candidates = sorted(
            active_candidates,
            key=lambda t: (
                t.deadline,
                -t.priority,
                -t.difficulty,
                t.task_id,
            ),
        )

        n = len(sorted_candidates)
        w_cap = capacity_slots

        # Precompute bounds and utility curves for each candidate task
        task_info: list[tuple[StudyTask, int, int, list[int]]] = []
        for task in sorted_candidates:
            rem_h = remaining_hours[task.task_id]
            needed_slots = max(1, math.ceil(round(float(rem_h), 4) / self.slot_step_hours))
            max_slots_today = min(needed_slots, w_cap)

            base_util = self.compute_task_utility(task, current_date)
            total_slots_orig = max(
                1, math.ceil(round(float(task.estimated_hours), 4) / self.slot_step_hours)
            )
            unit_util = base_util / total_slots_orig
            completion_bonus = base_util * self.completion_bonus_ratio

            # precompute scaled utilities for s in 0..max_slots_today
            scaled_utils: list[int] = [0]
            for s in range(1, max_slots_today + 1):
                raw_u = s * unit_util
                if s == needed_slots:
                    raw_u += completion_bonus
                scaled_utils.append(int(round(raw_u * 10000)))

            task_info.append((task, needed_slots, max_slots_today, scaled_utils))

        # DP Table: dp[i][w] = max scaled utility using first i tasks within capacity w
        # choice[i][w] = number of slots allocated to task i to achieve dp[i][w]
        dp = [[0] * (w_cap + 1) for _ in range(n + 1)]
        choice = [[0] * (w_cap + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            task, needed_slots, max_k, scaled_utils = task_info[i - 1]

            for w in range(w_cap + 1):
                best_val = dp[i - 1][w]
                best_s = 0

                limit_s = min(max_k, w)
                for s in range(1, limit_s + 1):
                    val = dp[i - 1][w - s] + scaled_utils[s]
                    if val > best_val:
                        best_val = val
                        best_s = s

                dp[i][w] = best_val
                choice[i][w] = best_s

        # Backtrack to reconstruct daily allocations
        allocations: list[DailyChunkAllocation] = []
        rem_w = w_cap
        for i in range(n, 0, -1):
            s = choice[i][rem_w]
            if s > 0:
                task, needed_slots, max_k, _ = task_info[i - 1]
                rem_h = remaining_hours[task.task_id]
                chunk_h = min(rem_h, round(s * self.slot_step_hours, 4))
                is_done = chunk_h >= rem_h - 0.001

                allocations.append(
                    DailyChunkAllocation(
                        task=task,
                        allocated_slots=s,
                        allocated_hours=round(chunk_h, 4),
                        is_completing_task=is_done,
                    )
                )
                rem_w -= s

        # Re-sort allocations deterministically for daily scheduling order:
        # Priority: earliest deadline, highest priority, highest difficulty, task_id
        allocations.sort(
            key=lambda alloc: (
                alloc.task.deadline,
                -alloc.task.priority,
                -alloc.task.difficulty,
                alloc.task.task_id,
            )
        )
        return allocations

    def schedule(
        self,
        tasks: Sequence[StudyTask],
        student: StudentProfile,
        start_date: date,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        day_start_hour: float = DEFAULT_DAY_START_HOUR,
    ) -> ScheduleResult:
        """Execute rolling-horizon hybrid scheduling across the planning horizon."""
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
                remaining_task_hours={},
            )

        end_date = start_date + timedelta(days=horizon_days - 1)

        # 2. Track remaining hours and completed tasks
        remaining_hours: dict[str, float] = {
            task.task_id: float(task.estimated_hours) for task in tasks if not task.completed
        }
        completed_task_ids: set[str] = {task.task_id for task in tasks if task.completed}
        task_completion_dates: dict[str, date] = {}
        task_map: dict[str, StudyTask] = {task.task_id: task for task in tasks}

        scheduled_sessions: list[ScheduledSession] = []
        break_duration_hours = student.break_duration_minutes / 60.0

        # 3. Simulate day-by-day across the planning horizon
        current_date = start_date
        while current_date <= end_date:
            weekday_name = current_date.strftime("%A").lower()
            daily_budget = student.get_daily_hours(weekday_name)

            if daily_budget > 0.0:
                # Find eligible tasks:
                # - Not yet completed (rem_hours > 0)
                # - Deadline not passed (deadline >= current_date)
                # - All prerequisites completed
                eligible_tasks = [
                    task_map[t_id]
                    for t_id, rem_h in remaining_hours.items()
                    if rem_h > 0.001
                    and task_map[t_id].deadline >= current_date
                    and all(p in completed_task_ids for p in task_map[t_id].prerequisites)
                ]

                # Run Bounded-Chunk DP optimization for today
                daily_allocations = self.optimize_daily_bounded_chunks(
                    eligible_tasks=eligible_tasks,
                    remaining_hours=remaining_hours,
                    available_hours=daily_budget,
                    current_date=current_date,
                )

                # Place allocated chunks onto the daily chronological timeline
                clock = float(day_start_hour)

                for alloc in daily_allocations:
                    task = alloc.task
                    chunk_to_schedule = alloc.allocated_hours

                    # Enforce student.max_continuous_hours by splitting long chunks
                    while chunk_to_schedule > 0.0 and clock < 24.0:
                        session_dur = min(
                            chunk_to_schedule,
                            student.max_continuous_hours,
                            24.0 - clock,
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

                        chunk_to_schedule -= session_dur
                        remaining_hours[task.task_id] -= session_dur
                        clock += session_dur

                        # Check if task is now 100% completed
                        is_finished = remaining_hours[task.task_id] <= 0.001
                        if is_finished:
                            remaining_hours[task.task_id] = 0.0
                            completed_task_ids.add(task.task_id)
                            task_completion_dates[task.task_id] = current_date

                        scheduled_sessions.append(
                            ScheduledSession(
                                task_id=task.task_id,
                                task_title=task.title,
                                subject_code=task.subject.code,
                                slot=slot,
                                hours=round(session_dur, 4),
                                is_completed_here=is_finished,
                            )
                        )

                        # Insert mandatory rest break before next session
                        if clock < 24.0 and (chunk_to_schedule > 0.0 or break_duration_hours > 0.0):
                            clock = min(24.0, clock + break_duration_hours)

            current_date += timedelta(days=1)

        # 4. Construct final ScheduleResult with explicit task status tracking
        completed_tasks_list = [task for task in tasks if task.task_id in completed_task_ids]
        unscheduled_tasks_list = [task for task in tasks if task.task_id not in completed_task_ids]

        final_remaining_hours: dict[str, float] = {
            task.task_id: round(remaining_hours.get(task.task_id, 0.0), 2) for task in tasks
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
