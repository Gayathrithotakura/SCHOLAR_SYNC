"""StudyTask domain model representing a discrete academic assignment or study goal."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from scholarsync.core.exceptions import InvalidTaskError
from scholarsync.core.types import (
    MAX_DIFFICULTY,
    MAX_PRIORITY,
    MAX_STUDY_HOURS,
    MIN_DIFFICULTY,
    MIN_PRIORITY,
    MIN_STUDY_HOURS,
    Difficulty,
    Priority,
)
from scholarsync.models.subject import Subject


@dataclass(frozen=True)
class StudyTask:
    """Represents a discrete academic task, lab assignment, or exam preparation unit.

    Attributes:
        task_id: Unique string identifier for the task.
        title: Descriptive title (e.g., 'Dynamic Programming Lab Assignment').
        subject: The academic Subject this task belongs to (composition).
        estimated_hours: Required study duration in hours (e.g., 4.5).
        deadline: Hard academic deadline date.
        priority: Importance level (1 = Low to 5 = Critical).
        difficulty: Mental complexity level (1 = Easy to 5 = Very Hard).
        completed: Flag indicating if the task is finished.
        prerequisites: Tuple of task_ids that must be completed prior to this task.
        created_at: Creation date used to validate deadline feasibility.
    """

    task_id: str
    title: str
    subject: Subject
    estimated_hours: float
    deadline: date
    priority: int = Priority.MEDIUM
    difficulty: int = Difficulty.INTERMEDIATE
    completed: bool = False
    prerequisites: tuple[str, ...] = field(default_factory=tuple)
    created_at: date | None = None

    def __post_init__(self) -> None:
        """Validate all task attributes and guarantee immutable state."""
        # Validate task_id
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise InvalidTaskError("Task ID must be a non-empty string.")

        # Validate title
        if not isinstance(self.title, str) or not self.title.strip():
            raise InvalidTaskError("Task title must be a non-empty string.")

        # Validate subject composition
        if not isinstance(self.subject, Subject):
            raise InvalidTaskError(
                f"Task subject must be an instance of Subject, got {type(self.subject).__name__}."
            )

        # Validate estimated_hours
        if isinstance(self.estimated_hours, bool) or not isinstance(
            self.estimated_hours, (int, float)
        ):
            raise InvalidTaskError(
                f"Estimated hours must be numeric, got {type(self.estimated_hours).__name__}."
            )
        hours = float(self.estimated_hours)
        if hours < MIN_STUDY_HOURS:
            raise InvalidTaskError(
                f"Estimated hours ({hours}) must be at least {MIN_STUDY_HOURS}h."
            )
        if hours > MAX_STUDY_HOURS:
            raise InvalidTaskError(
                f"Estimated hours ({hours}) cannot exceed maximum task limit ({MAX_STUDY_HOURS}h)."
            )

        # Validate deadline
        if not isinstance(self.deadline, date):
            raise InvalidTaskError(
                f"Deadline must be an instance of datetime.date, "
                f"got {type(self.deadline).__name__}."
            )

        # Validate created_at and relationship with deadline
        if self.created_at is not None:
            if not isinstance(self.created_at, date):
                raise InvalidTaskError("created_at must be an instance of datetime.date.")
            if self.deadline < self.created_at:
                raise InvalidTaskError(
                    f"Deadline ({self.deadline}) cannot be earlier than "
                    f"creation date ({self.created_at})."
                )

        # Validate priority (1 to 5)
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise InvalidTaskError(
                f"Priority must be an integer, got {type(self.priority).__name__}."
            )
        if self.priority < MIN_PRIORITY or self.priority > MAX_PRIORITY:
            raise InvalidTaskError(
                f"Priority must be between {MIN_PRIORITY} (Low) and {MAX_PRIORITY} (Critical), "
                f"got {self.priority}."
            )

        # Validate difficulty (1 to 5)
        if isinstance(self.difficulty, bool) or not isinstance(self.difficulty, int):
            raise InvalidTaskError(
                f"Difficulty must be an integer, got {type(self.difficulty).__name__}."
            )
        if self.difficulty < MIN_DIFFICULTY or self.difficulty > MAX_DIFFICULTY:
            raise InvalidTaskError(
                f"Difficulty must be between {MIN_DIFFICULTY} (Easy) and "
                f"{MAX_DIFFICULTY} (Very Hard), got {self.difficulty}."
            )

        # Validate prerequisites
        prereqs_val: object = self.prerequisites
        if not isinstance(prereqs_val, Sequence) or isinstance(prereqs_val, (str, bytes)):
            raise InvalidTaskError("Prerequisites must be a sequence of task ID strings.")

        cleaned_prereqs = tuple(p.strip() for p in self.prerequisites)
        for prereq in cleaned_prereqs:
            if not prereq:
                raise InvalidTaskError("Prerequisite task ID cannot be an empty string.")

        clean_task_id = self.task_id.strip()
        if clean_task_id in cleaned_prereqs:
            raise InvalidTaskError(f"Task '{clean_task_id}' cannot list itself as a prerequisite.")

        # Normalize values into frozen instance
        object.__setattr__(self, "task_id", clean_task_id)
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "estimated_hours", round(hours, 2))
        object.__setattr__(self, "prerequisites", cleaned_prereqs)

    def days_remaining(self, current_date: date) -> int:
        """Calculate the remaining days until the deadline relative to a given date.

        Negative values indicate the deadline has passed.
        """
        return (self.deadline - current_date).days

    def is_overdue(self, current_date: date) -> bool:
        """Check if the task has passed its deadline and remains incomplete."""
        return not self.completed and self.deadline < current_date

    def compute_workload_weight(self) -> float:
        """Compute the intrinsic cognitive workload weight (Priority x Difficulty)."""
        return float(self.priority * self.difficulty)

    def __str__(self) -> str:
        status = "Done" if self.completed else "Pending"
        return (
            f"[{self.task_id}] {self.title} ({self.subject.code}) - "
            f"{self.estimated_hours}h | Due: {self.deadline} | "
            f"Pri: {self.priority} | Diff: {self.difficulty} | [{status}]"
        )
