"""Deterministic sample dataset representing a realistic M.Tech CSE semester workload.

Provides built-in academic tasks, subjects, and student availability so demo
and quick evaluation commands work out of the box without external data files.
"""

from datetime import date, timedelta

from scholarsync.core.types import DayOfWeek, Difficulty, Priority
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask


def get_sample_student_profile() -> StudentProfile:
    """Return a representative M.Tech student profile with realistic availability."""
    availability = {
        DayOfWeek.MONDAY.value: 4.0,
        DayOfWeek.TUESDAY.value: 4.0,
        DayOfWeek.WEDNESDAY.value: 3.5,
        DayOfWeek.THURSDAY.value: 4.0,
        DayOfWeek.FRIDAY.value: 3.0,
        DayOfWeek.SATURDAY.value: 6.0,
        DayOfWeek.SUNDAY.value: 5.0,
    }
    return StudentProfile(
        student_id="STU_MTECH_2026",
        name="Aarav Sharma (M.Tech CSE)",
        daily_availability=availability,
        max_daily_hours=8.0,
        max_continuous_hours=3.5,
        break_duration_minutes=20,
    )


def get_sample_subjects() -> dict[str, Subject]:
    """Return core M.Tech CSE subjects across algorithms, systems, and AI."""
    return {
        "CS601": Subject(
            code="CS601",
            name="Advanced Data Structures and Algorithms",
            credits=4,
            description="Core theoretical algorithms and dynamic programming",
        ),
        "AI702": Subject(
            code="AI702",
            name="Machine Learning Systems",
            credits=4,
            description="Statistical optimization, neural networks, and vision models",
        ),
        "CS603": Subject(
            code="CS603",
            name="Advanced Operating Systems",
            credits=3,
            description="Kernel synchronization, concurrency, and virtual memory",
        ),
        "CS699": Subject(
            code="CS699",
            name="M.Tech Research Seminar",
            credits=2,
            description="Literature survey and academic research preparation",
        ),
    }


def get_sample_tasks(anchor_date: date | None = None) -> list[StudyTask]:
    """Return a deterministic suite of academic tasks with realistic prerequisites and deadlines.

    Args:
        anchor_date: Reference calendar date (defaults to today).

    Returns:
        List of StudyTask instances with varied difficulty, priority, and dependencies.
    """
    base_date = anchor_date if anchor_date is not None else date.today()
    subjects = get_sample_subjects()

    return [
        StudyTask(
            task_id="T01",
            title="Algorithm Complexity Analysis & Recurrences",
            subject=subjects["CS601"],
            estimated_hours=3.0,
            deadline=base_date + timedelta(days=4),
            priority=Priority.HIGH,
            difficulty=Difficulty.INTERMEDIATE,
            prerequisites=(),
            created_at=base_date,
        ),
        StudyTask(
            task_id="T02",
            title="Dynamic Programming Optimization Lab",
            subject=subjects["CS601"],
            estimated_hours=4.0,
            deadline=base_date + timedelta(days=8),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.HARD,
            prerequisites=("T01",),
            created_at=base_date,
        ),
        StudyTask(
            task_id="T03",
            title="Neural Network Backprop Implementation",
            subject=subjects["AI702"],
            estimated_hours=3.5,
            deadline=base_date + timedelta(days=5),
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
            prerequisites=(),
            created_at=base_date,
        ),
        StudyTask(
            task_id="T04",
            title="Deep Learning Lab - CNN Vision Model",
            subject=subjects["AI702"],
            estimated_hours=4.0,
            deadline=base_date + timedelta(days=11),
            priority=Priority.HIGH,
            difficulty=Difficulty.VERY_HARD,
            prerequisites=("T03",),
            created_at=base_date,
        ),
        StudyTask(
            task_id="T05",
            title="Kernel Synchronization & Mutex Locking Lab",
            subject=subjects["CS603"],
            estimated_hours=3.5,
            deadline=base_date + timedelta(days=7),
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
            prerequisites=(),
            created_at=base_date,
        ),
        StudyTask(
            task_id="T06",
            title="Virtual Memory & Paging Simulator",
            subject=subjects["CS603"],
            estimated_hours=4.0,
            deadline=base_date + timedelta(days=12),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.HARD,
            prerequisites=("T05",),
            created_at=base_date,
        ),
        StudyTask(
            task_id="T07",
            title="Literature Survey on Workload Schedulers",
            subject=subjects["CS699"],
            estimated_hours=3.0,
            deadline=base_date + timedelta(days=13),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.MODERATE,
            prerequisites=(),
            created_at=base_date,
        ),
    ]
