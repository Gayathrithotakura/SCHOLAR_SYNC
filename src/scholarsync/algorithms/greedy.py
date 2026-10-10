"""Greedy Earliest Deadline First with Cognitive Weighting (EDF-CW) scheduler."""

from collections.abc import Sequence
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

# Default heuristic weights for EDF-CW scoring
DEFAULT_URGENCY_WEIGHT: Final[float] = 1.0
DEFAULT_PRIORITY_WEIGHT: Final[float] = 0.5
DEFAULT_DIFFICULTY_WEIGHT: Final[float] = 0.25


class GreedyEDFScheduler(BaseSchedulerStrategy):
    """Greedy Earliest Deadline First with Cognitive Weighting (EDF-CW) Scheduler.

    Allocates study sessions day-by-day using a greedy composite heuristic:
    Score = w_u * Urgency(deadline) + w_p * Priority + w_d * Difficulty

    Enforces:
    - Prerequisite precedence (tasks only scheduled after prerequisites finish)
    - Student daily availability capacity
    - Cognitive fatigue limit (max continuous session hours)
    - Non-overlapping chronological time slots
    - Hard deadlines (tasks are never scheduled after their deadline)
    """

    def __init__(
        self,
        urgency_weight: float = DEFAULT_URGENCY_WEIGHT,
        priority_weight: float = DEFAULT_PRIORITY_WEIGHT,
        difficulty_weight: float = DEFAULT_DIFFICULTY_WEIGHT,
    ) -> None:
        self.urgency_weight = urgency_weight
        self.priority_weight = priority_weight
        self.difficulty_weight = difficulty_weight

    @property
    def name(self) -> str:
        return "Greedy EDF-CW"

    def compute_heuristic_score(self, task: StudyTask, current_date: date) -> float:
        """Calculate the deterministic urgency and cognitive priority score.

        Tasks with closer deadlines, higher academic priority, and higher cognitive
        difficulty receive higher scores.
        """
        days_to_deadline = (task.deadline - current_date).days
        # If due today, urgency is high; otherwise inverse with smoothing
        clamped_days = max(0.5, float(days_to_deadline))
        urgency = 10.0 / clamped_days

        score = (
            self.urgency_weight * urgency
            + self.priority_weight * float(task.priority)
            + self.difficulty_weight * float(task.difficulty)
        )
        return round(score, 4)

    def compute_task_utility(self, task: StudyTask, current_date: date) -> float:
        """Alias for compute_heuristic_score for polymorphic API consistency."""
        return self.compute_heuristic_score(task, current_date)

    def schedule(
        self,
        tasks: Sequence[StudyTask],
        student: StudentProfile,
        start_date: date,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        day_start_hour: float = DEFAULT_DAY_START_HOUR,
    ) -> ScheduleResult:
        """Execute the greedy simulation over the specified planning horizon."""
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

        # 2. Track remaining hours and completion state
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

            # Skip days with zero student availability
            if daily_budget > 0.0:
                clock = float(day_start_hour)
                remaining_daily_budget = daily_budget

                while remaining_daily_budget >= MIN_STUDY_HOURS and clock < 24.0:
                    # Identify tasks eligible to be scheduled right now:
                    # - Must have remaining hours > 0
                    # - Deadline must not have passed (deadline >= current_date)
                    # - All prerequisites must be completed
                    eligible_tasks: list[StudyTask] = []
                    for t_id, rem_h in remaining_hours.items():
                        if rem_h <= 0.001:
                            continue
                        candidate_task = task_map[t_id]
                        if candidate_task.deadline < current_date:
                            continue  # Cannot schedule after deadline
                        # Check prerequisite completion
                        if all(p in completed_task_ids for p in candidate_task.prerequisites):
                            eligible_tasks.append(candidate_task)

                    if not eligible_tasks:
                        break  # No eligible tasks can be scheduled today

                    # Deterministic ranking:
                    # Primary: -Heuristic Score
                    # Tie-break 1: Earliest deadline
                    # Tie-break 2: Highest priority
                    # Tie-break 3: Highest difficulty
                    # Tie-break 4: Alphabetical task_id
                    ranked_tasks = sorted(
                        eligible_tasks,
                        key=lambda t: (
                            -self.compute_heuristic_score(t, current_date),
                            t.deadline,
                            -t.priority,
                            -t.difficulty,
                            t.task_id,
                        ),
                    )

                    chosen_task = ranked_tasks[0]
                    chosen_id = chosen_task.task_id

                    # Determine allowable session duration
                    needed_hours = remaining_hours[chosen_id]
                    max_by_day = remaining_daily_budget
                    max_by_continuous = student.max_continuous_hours
                    max_by_clock = 24.0 - clock

                    session_duration = min(
                        needed_hours, max_by_day, max_by_continuous, max_by_clock
                    )

                    if session_duration < MIN_STUDY_HOURS:
                        break  # Remaining daily window is too small for a study session

                    # Create non-overlapping TimeSlot
                    slot = TimeSlot(
                        slot_date=current_date,
                        start_hour=round(clock, 4),
                        duration_hours=round(session_duration, 4),
                        label=f"{chosen_task.subject.code}: {chosen_task.title}",
                        slot_id=f"SLOT_{len(scheduled_sessions) + 1:04d}",
                    )

                    # Update task progress
                    remaining_hours[chosen_id] -= session_duration
                    is_completed = remaining_hours[chosen_id] <= 0.001

                    if is_completed:
                        remaining_hours[chosen_id] = 0.0
                        completed_task_ids.add(chosen_id)
                        task_completion_dates[chosen_id] = current_date

                    scheduled_sessions.append(
                        ScheduledSession(
                            task_id=chosen_id,
                            task_title=chosen_task.title,
                            subject_code=chosen_task.subject.code,
                            slot=slot,
                            hours=round(session_duration, 4),
                            is_completed_here=is_completed,
                        )
                    )

                    # Advance clock and study budget
                    clock += session_duration
                    remaining_daily_budget -= session_duration

                    # Insert mandatory rest break before the next session
                    if remaining_daily_budget >= MIN_STUDY_HOURS and clock < 24.0:
                        clock = min(24.0, clock + break_duration_hours)

            current_date += timedelta(days=1)

        # 4. Construct final ScheduleResult
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
