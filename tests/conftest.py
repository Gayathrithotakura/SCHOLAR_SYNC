"""Pytest fixtures for ScholarSync domain models."""

from datetime import date, timedelta
from typing import Final

import pytest

from scholarsync.core.types import DayOfWeek, Difficulty, Priority
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask
from scholarsync.models.time_slot import TimeSlot

TODAY: Final[date] = date(2026, 10, 10)


@pytest.fixture
def sample_subject_algorithms() -> Subject:
    """Fixture providing an Algorithms subject."""
    return Subject(
        code="CS601",
        name="Advanced Data Structures and Algorithms",
        credits=4,
        description="Core M.Tech algorithmic thinking module",
    )


@pytest.fixture
def sample_subject_ml() -> Subject:
    """Fixture providing a Machine Learning subject."""
    return Subject(
        code="AI702",
        name="Machine Learning Systems",
        credits=3,
        description="Statistical learning and optimization",
    )


@pytest.fixture
def sample_task(sample_subject_algorithms: Subject) -> StudyTask:
    """Fixture providing a valid standard study task."""
    return StudyTask(
        task_id="T001",
        title="Dynamic Programming Lab Assignment",
        subject=sample_subject_algorithms,
        estimated_hours=4.0,
        deadline=TODAY + timedelta(days=5),
        priority=Priority.HIGH,
        difficulty=Difficulty.HARD,
        completed=False,
        prerequisites=(),
        created_at=TODAY,
    )


@pytest.fixture
def sample_student_profile() -> StudentProfile:
    """Fixture providing a valid student profile."""
    availability = {
        DayOfWeek.MONDAY.value: 3.5,
        DayOfWeek.TUESDAY.value: 4.0,
        DayOfWeek.WEDNESDAY.value: 3.0,
        DayOfWeek.THURSDAY.value: 4.0,
        DayOfWeek.FRIDAY.value: 2.5,
        DayOfWeek.SATURDAY.value: 6.0,
        DayOfWeek.SUNDAY.value: 5.0,
    }
    return StudentProfile(
        student_id="STU2026_01",
        name="Aarav Sharma",
        daily_availability=availability,
        max_daily_hours=8.0,
        max_continuous_hours=3.5,
        break_duration_minutes=20,
    )


@pytest.fixture
def sample_time_slot() -> TimeSlot:
    """Fixture providing a valid time slot."""
    return TimeSlot(
        slot_date=TODAY,
        start_hour=9.0,
        duration_hours=2.0,
        label="Morning Algorithms Study Block",
        slot_id="SLOT_01",
    )
