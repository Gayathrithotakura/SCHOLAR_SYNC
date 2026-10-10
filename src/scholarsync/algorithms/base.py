"""Abstract scheduler strategy interface and common dependency graph validators."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from typing import Final

from scholarsync.core.exceptions import (
    CyclicDependencyError,
    UnresolvedDependencyError,
    ValidationError,
)
from scholarsync.core.types import MAX_DAILY_HOURS
from scholarsync.models.schedule import ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.task import StudyTask

DEFAULT_HORIZON_DAYS: Final[int] = 30
DEFAULT_DAY_START_HOUR: Final[float] = 9.0  # 09:00 AM standard study start


def validate_task_dependencies(tasks: Sequence[StudyTask]) -> None:
    """Validate that task prerequisites exist and contain no circular dependencies.

    Uses depth-first cycle detection (3-color DFS):
    - 0: Unvisited
    - 1: Visiting (currently in DFS call stack)
    - 2: Visited (fully explored, cycle-free)

    Raises:
        UnresolvedDependencyError: If a task depends on a prerequisite ID not in `tasks`.
        CyclicDependencyError: If a prerequisite dependency cycle is detected.
    """
    task_map: dict[str, StudyTask] = {task.task_id: task for task in tasks}

    # 1. Check for unresolved dependencies
    for task in tasks:
        for prereq_id in task.prerequisites:
            if prereq_id not in task_map:
                raise UnresolvedDependencyError(
                    f"Task '{task.task_id}' depends on unresolved prerequisite '{prereq_id}'."
                )

    # 2. Check for dependency cycles using DFS
    visited: dict[str, int] = {task.task_id: 0 for task in tasks}
    cycle_stack: list[str] = []

    def dfs(current_id: str) -> None:
        visited[current_id] = 1
        cycle_stack.append(current_id)

        current_task = task_map[current_id]
        for neighbor_id in current_task.prerequisites:
            state = visited.get(neighbor_id, 0)
            if state == 1:
                # Cycle found: extract cycle loop for descriptive error reporting
                loop_start = cycle_stack.index(neighbor_id)
                cycle_path = " -> ".join(cycle_stack[loop_start:] + [neighbor_id])
                raise CyclicDependencyError(
                    f"Cyclic dependency detected in task prerequisites: {cycle_path}."
                )
            if state == 0:
                dfs(neighbor_id)

        cycle_stack.pop()
        visited[current_id] = 2

    for task in tasks:
        if visited[task.task_id] == 0:
            dfs(task.task_id)


class BaseSchedulerStrategy(ABC):
    """Abstract Base Class for academic scheduling strategies (Strategy Pattern)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier of the scheduling strategy."""

    @abstractmethod
    def schedule(
        self,
        tasks: Sequence[StudyTask],
        student: StudentProfile,
        start_date: date,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        day_start_hour: float = DEFAULT_DAY_START_HOUR,
    ) -> ScheduleResult:
        """Generate a complete schedule plan for given tasks and student profile.

        Args:
            tasks: Sequence of StudyTask instances to be scheduled.
            student: StudentProfile with availability and session limits.
            start_date: Calendar start date for planning.
            horizon_days: Maximum number of days into the future to plan.
            day_start_hour: Clock hour (24h decimal) to begin daily study sessions.

        Returns:
            ScheduleResult containing scheduled sessions, completed tasks, and unscheduled tasks.

        Raises:
            ValidationError: If input parameters or horizons are invalid.
            UnresolvedDependencyError: If a task has an unknown prerequisite.
            CyclicDependencyError: If a prerequisite cycle exists.
        """

    def validate_inputs(
        self,
        tasks: Sequence[StudyTask],
        student: StudentProfile,
        start_date: date,
        horizon_days: int,
        day_start_hour: float,
    ) -> None:
        """Common pre-condition validation for scheduling algorithms."""
        if not isinstance(start_date, date):
            raise ValidationError("start_date must be an instance of datetime.date.")

        if isinstance(horizon_days, bool) or not isinstance(horizon_days, int):
            raise ValidationError("horizon_days must be an integer.")
        if horizon_days <= 0:
            raise ValidationError(
                f"horizon_days must be strictly positive (> 0), got {horizon_days}."
            )

        if isinstance(day_start_hour, bool) or not isinstance(day_start_hour, (int, float)):
            raise ValidationError("day_start_hour must be numeric.")
        start_hour = float(day_start_hour)
        if start_hour < 0.0 or start_hour >= MAX_DAILY_HOURS:
            raise ValidationError(
                f"day_start_hour must be in range [0.0, {MAX_DAILY_HOURS}), got {start_hour}."
            )

        # Validate task prerequisites and detect cycles
        validate_task_dependencies(tasks)
