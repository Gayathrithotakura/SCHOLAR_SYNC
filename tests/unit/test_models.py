"""Comprehensive unit tests for ScholarSync domain models.

Validates:
1. Normal/valid input instantiation
2. Invalid inputs and proper error raising
3. Exact boundary cases for priority, difficulty, duration, availability, deadlines
4. Immutability guarantees (FrozenInstanceError / read-only MappingProxy)
5. Model composition, string representations, and equality
"""

from dataclasses import FrozenInstanceError
from datetime import date
from typing import Any

import pytest

from scholarsync.core.exceptions import (
    InvalidProfileError,
    InvalidTaskError,
    InvalidTimeSlotError,
)
from scholarsync.core.types import (
    MAX_DIFFICULTY,
    MAX_PRIORITY,
    MAX_STUDY_HOURS,
    MIN_DIFFICULTY,
    MIN_PRIORITY,
    MIN_STUDY_HOURS,
    DayOfWeek,
    Difficulty,
    Priority,
)
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask
from scholarsync.models.time_slot import TimeSlot


# ============================================================================
# SUBJECT TESTS
# ============================================================================
class TestSubjectModel:
    """Unit tests for the Subject domain entity."""

    def test_valid_subject_creation(self) -> None:
        """Verify normal creation and normalization of a Subject."""
        subject = Subject(code=" cs601 ", name="  Advanced Algorithms  ", credits=4)
        assert subject.code == "CS601"
        assert subject.name == "Advanced Algorithms"
        assert subject.credits == 4
        assert str(subject) == "CS601: Advanced Algorithms (4 credits)"

    @pytest.mark.parametrize(
        "invalid_code",
        ["", "   ", 123, None],
    )
    def test_invalid_subject_code(self, invalid_code: Any) -> None:
        """Verify empty or non-string subject code raises InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Subject code"):
            Subject(code=invalid_code, name="Algorithms")

    @pytest.mark.parametrize(
        "invalid_name",
        ["", "   ", 456, None],
    )
    def test_invalid_subject_name(self, invalid_name: Any) -> None:
        """Verify empty or non-string subject name raises InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Subject name"):
            Subject(code="CS101", name=invalid_name)

    @pytest.mark.parametrize(
        "invalid_credits",
        [0, -1, 3.5, True, False, "four", None],
    )
    def test_invalid_subject_credits(self, invalid_credits: Any) -> None:
        """Verify credits must be integer >= 1 and not boolean."""
        with pytest.raises(InvalidTaskError, match="credits"):
            Subject(code="CS101", name="Algorithms", credits=invalid_credits)

    def test_subject_immutability(self, sample_subject_algorithms: Subject) -> None:
        """Verify Subject is frozen and cannot be modified after instantiation."""
        with pytest.raises(FrozenInstanceError):
            sample_subject_algorithms.credits = 5  # type: ignore[misc]

    def test_subject_equality_and_hashability(self) -> None:
        """Verify Subject instances can be stored in sets and compared by value."""
        s1 = Subject(code="CS601", name="Advanced Algorithms", credits=4)
        s2 = Subject(code="cs601", name="Advanced Algorithms", credits=4)
        assert s1 == s2
        assert len({s1, s2}) == 1


# ============================================================================
# STUDY TASK TESTS
# ============================================================================
class TestStudyTaskModel:
    """Unit tests for the StudyTask domain entity."""

    def test_valid_task_creation(self, sample_subject_algorithms: Subject) -> None:
        """Verify valid task creation with default and explicit parameters."""
        task = StudyTask(
            task_id="T101",
            title="Greedy Algorithms Homework",
            subject=sample_subject_algorithms,
            estimated_hours=3.5,
            deadline=date(2026, 10, 20),
            priority=Priority.HIGH,
            difficulty=Difficulty.MODERATE,
            created_at=date(2026, 10, 10),
        )
        assert task.task_id == "T101"
        assert task.estimated_hours == 3.5
        assert task.priority == 4
        assert task.difficulty == 2
        assert task.compute_workload_weight() == 8.0
        assert task.days_remaining(date(2026, 10, 10)) == 10
        assert not task.is_overdue(date(2026, 10, 10))

    def test_task_subject_composition_type_check(self) -> None:
        """Verify that task subject must be an instance of Subject."""
        with pytest.raises(InvalidTaskError, match="must be an instance of Subject"):
            StudyTask(
                task_id="T01",
                title="Invalid Subject Task",
                subject="NotASubjectObject",  # type: ignore[arg-type]
                estimated_hours=2.0,
                deadline=date(2026, 10, 15),
            )

    @pytest.mark.parametrize("invalid_id", ["", "   ", None, 123])
    def test_invalid_task_id(self, sample_subject_algorithms: Subject, invalid_id: Any) -> None:
        """Verify invalid task IDs raise InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Task ID"):
            StudyTask(
                task_id=invalid_id,
                title="Task",
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline=date(2026, 10, 15),
            )

    @pytest.mark.parametrize("invalid_title", ["", "   ", None, 999])
    def test_invalid_task_title(
        self, sample_subject_algorithms: Subject, invalid_title: Any
    ) -> None:
        """Verify invalid titles raise InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Task title"):
            StudyTask(
                task_id="T01",
                title=invalid_title,
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline=date(2026, 10, 15),
            )

    # Priority Boundary Tests
    @pytest.mark.parametrize("valid_priority", [MIN_PRIORITY, 3, MAX_PRIORITY])
    def test_priority_boundary_valid(
        self, sample_subject_algorithms: Subject, valid_priority: int
    ) -> None:
        """Verify priority within [1, 5] succeeds."""
        task = StudyTask(
            task_id="T01",
            title="Boundary Priority Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=date(2026, 10, 15),
            priority=valid_priority,
        )
        assert task.priority == valid_priority

    @pytest.mark.parametrize("invalid_priority", [0, 6, -1, 100, 2.5, True, "high", None])
    def test_priority_boundary_invalid(
        self, sample_subject_algorithms: Subject, invalid_priority: Any
    ) -> None:
        """Verify priority outside [1, 5] or non-integer raises InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Priority"):
            StudyTask(
                task_id="T01",
                title="Invalid Priority",
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline=date(2026, 10, 15),
                priority=invalid_priority,
            )

    # Difficulty Boundary Tests
    @pytest.mark.parametrize("valid_difficulty", [MIN_DIFFICULTY, 3, MAX_DIFFICULTY])
    def test_difficulty_boundary_valid(
        self, sample_subject_algorithms: Subject, valid_difficulty: int
    ) -> None:
        """Verify difficulty within [1, 5] succeeds."""
        task = StudyTask(
            task_id="T01",
            title="Boundary Difficulty Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=date(2026, 10, 15),
            difficulty=valid_difficulty,
        )
        assert task.difficulty == valid_difficulty

    @pytest.mark.parametrize("invalid_difficulty", [0, 6, -5, 3.2, False, "easy", None])
    def test_difficulty_boundary_invalid(
        self, sample_subject_algorithms: Subject, invalid_difficulty: Any
    ) -> None:
        """Verify difficulty outside [1, 5] or non-integer raises InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Difficulty"):
            StudyTask(
                task_id="T01",
                title="Invalid Difficulty",
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline=date(2026, 10, 15),
                difficulty=invalid_difficulty,
            )

    # Study Duration Boundary Tests
    @pytest.mark.parametrize("valid_hours", [MIN_STUDY_HOURS, 1.0, 50.0, MAX_STUDY_HOURS])
    def test_study_hours_boundary_valid(
        self, sample_subject_algorithms: Subject, valid_hours: float
    ) -> None:
        """Verify study hours within valid range [0.25, 100.0] succeed."""
        task = StudyTask(
            task_id="T01",
            title="Valid Hours Task",
            subject=sample_subject_algorithms,
            estimated_hours=valid_hours,
            deadline=date(2026, 10, 15),
        )
        assert task.estimated_hours == valid_hours

    @pytest.mark.parametrize(
        "invalid_hours",
        [0.0, -1.0, 0.1, 100.5, True, False, "two", None],
    )
    def test_study_hours_boundary_invalid(
        self, sample_subject_algorithms: Subject, invalid_hours: Any
    ) -> None:
        """Verify study hours <= 0, below 0.25h, or exceeding maximum raise InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Estimated hours"):
            StudyTask(
                task_id="T01",
                title="Invalid Hours",
                subject=sample_subject_algorithms,
                estimated_hours=invalid_hours,
                deadline=date(2026, 10, 15),
            )

    # Deadline & Overdue Tests
    def test_deadline_must_be_date_instance(self, sample_subject_algorithms: Subject) -> None:
        """Verify string or non-date deadline raises InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="Deadline must be an instance of datetime.date"):
            StudyTask(
                task_id="T01",
                title="Task",
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline="2026-10-15",  # type: ignore[arg-type]
            )

    def test_deadline_earlier_than_created_at_fails(
        self, sample_subject_algorithms: Subject
    ) -> None:
        """Verify deadline prior to creation date raises InvalidTaskError."""
        with pytest.raises(InvalidTaskError, match="cannot be earlier than"):
            StudyTask(
                task_id="T01",
                title="Task",
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline=date(2026, 10, 5),
                created_at=date(2026, 10, 10),
            )

    def test_task_is_overdue_logic(self, sample_subject_algorithms: Subject) -> None:
        """Verify is_overdue correctly detects passed deadlines for incomplete tasks."""
        task = StudyTask(
            task_id="T01",
            title="Overdue Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=date(2026, 10, 5),
            completed=False,
        )
        assert task.is_overdue(date(2026, 10, 10)) is True
        assert task.days_remaining(date(2026, 10, 10)) == -5

        # Completed tasks are not overdue even if deadline has passed
        completed_task = StudyTask(
            task_id="T02",
            title="Completed Task",
            subject=sample_subject_algorithms,
            estimated_hours=2.0,
            deadline=date(2026, 10, 5),
            completed=True,
        )
        assert completed_task.is_overdue(date(2026, 10, 10)) is False

    # Prerequisites Tests
    def test_prerequisites_self_dependency_rejected(
        self, sample_subject_algorithms: Subject
    ) -> None:
        """Verify task cannot list itself as a prerequisite."""
        with pytest.raises(InvalidTaskError, match="cannot list itself as a prerequisite"):
            StudyTask(
                task_id="T01",
                title="Self Dependent Task",
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline=date(2026, 10, 15),
                prerequisites=("T01",),
            )

    def test_prerequisites_empty_string_rejected(self, sample_subject_algorithms: Subject) -> None:
        """Verify prerequisite task ID cannot be an empty string."""
        with pytest.raises(InvalidTaskError, match="cannot be an empty string"):
            StudyTask(
                task_id="T01",
                title="Task",
                subject=sample_subject_algorithms,
                estimated_hours=2.0,
                deadline=date(2026, 10, 15),
                prerequisites=("T00", "  "),
            )

    def test_study_task_immutability(self, sample_task: StudyTask) -> None:
        """Verify StudyTask is frozen and cannot be modified."""
        with pytest.raises(FrozenInstanceError):
            sample_task.priority = Priority.CRITICAL  # type: ignore[misc]


# ============================================================================
# STUDENT PROFILE TESTS
# ============================================================================
class TestStudentProfileModel:
    """Unit tests for the StudentProfile domain entity."""

    def test_default_profile_creation(self) -> None:
        """Verify student profile initializes with sensible defaults."""
        profile = StudentProfile(student_id="STU01", name="Priya Patel")
        assert profile.student_id == "STU01"
        assert profile.name == "Priya Patel"
        assert profile.max_daily_hours == 12.0
        assert profile.max_continuous_hours == 4.0
        assert profile.break_duration_minutes == 15
        assert profile.get_daily_hours("monday") == 4.0
        assert profile.get_daily_hours("saturday") == 6.0
        assert profile.total_weekly_capacity() == 32.0

    def test_custom_daily_availability(self) -> None:
        """Verify custom daily availability mapping."""
        custom_map = {
            DayOfWeek.MONDAY.value: 2.0,
            DayOfWeek.TUESDAY.value: 3.0,
            DayOfWeek.WEDNESDAY.value: 2.0,
            DayOfWeek.THURSDAY.value: 3.0,
            DayOfWeek.FRIDAY.value: 1.0,
            DayOfWeek.SATURDAY.value: 5.0,
            DayOfWeek.SUNDAY.value: 4.0,
        }
        profile = StudentProfile(
            student_id="STU02",
            name="Rahul Varma",
            daily_availability=custom_map,
            max_daily_hours=6.0,
            max_continuous_hours=3.0,
        )
        assert profile.get_daily_hours(DayOfWeek.MONDAY) == 2.0
        assert profile.total_weekly_capacity() == 20.0

    @pytest.mark.parametrize("invalid_id", ["", "  ", None, 123])
    def test_invalid_student_id(self, invalid_id: Any) -> None:
        """Verify invalid student_id raises InvalidProfileError."""
        with pytest.raises(InvalidProfileError, match="Student ID"):
            StudentProfile(student_id=invalid_id, name="Rahul")

    @pytest.mark.parametrize("invalid_name", ["", "  ", None, 456])
    def test_invalid_student_name(self, invalid_name: Any) -> None:
        """Verify invalid name raises InvalidProfileError."""
        with pytest.raises(InvalidProfileError, match="Student name"):
            StudentProfile(student_id="STU01", name=invalid_name)

    # Max Daily Hours Boundary Tests
    @pytest.mark.parametrize("valid_max_daily", [1.0, 12.0, 24.0])
    def test_max_daily_hours_valid(self, valid_max_daily: float) -> None:
        """Verify valid max_daily_hours in (0, 24]."""
        profile = StudentProfile(
            student_id="STU01",
            name="Rahul",
            max_daily_hours=valid_max_daily,
            max_continuous_hours=min(3.0, valid_max_daily),
            daily_availability={"monday": min(2.0, valid_max_daily)},
        )
        assert profile.max_daily_hours == valid_max_daily

    @pytest.mark.parametrize("invalid_max_daily", [0.0, -2.0, 25.0, True, "twelve", None])
    def test_max_daily_hours_invalid(self, invalid_max_daily: Any) -> None:
        """Verify max_daily_hours outside (0, 24] or non-numeric raises error."""
        with pytest.raises(InvalidProfileError, match="max_daily_hours"):
            StudentProfile(student_id="STU01", name="Rahul", max_daily_hours=invalid_max_daily)

    # Max Continuous Hours Boundary Tests
    def test_max_continuous_hours_cannot_exceed_max_daily(self) -> None:
        """Verify max_continuous_hours > max_daily_hours raises error."""
        with pytest.raises(InvalidProfileError, match="cannot exceed max_daily_hours"):
            StudentProfile(
                student_id="STU01",
                name="Rahul",
                max_daily_hours=4.0,
                max_continuous_hours=5.0,
            )

    @pytest.mark.parametrize("invalid_cont", [0.0, -1.0, True, "three", None])
    def test_max_continuous_hours_invalid(self, invalid_cont: Any) -> None:
        """Verify non-positive or non-numeric max_continuous_hours raises error."""
        with pytest.raises(InvalidProfileError, match="max_continuous_hours"):
            StudentProfile(
                student_id="STU01",
                name="Rahul",
                max_continuous_hours=invalid_cont,
            )

    # Break Duration Tests
    @pytest.mark.parametrize("valid_break", [0, 15, 60, 120])
    def test_break_duration_boundary_valid(self, valid_break: int) -> None:
        """Verify break durations between 0 and 120 minutes succeed."""
        profile = StudentProfile(
            student_id="STU01", name="Rahul", break_duration_minutes=valid_break
        )
        assert profile.break_duration_minutes == valid_break

    @pytest.mark.parametrize("invalid_break", [-1, 121, 15.5, True, "ten", None])
    def test_break_duration_boundary_invalid(self, invalid_break: Any) -> None:
        """Verify break durations < 0 or > 120 or non-int raise error."""
        with pytest.raises(InvalidProfileError, match="break_duration_minutes"):
            StudentProfile(student_id="STU01", name="Rahul", break_duration_minutes=invalid_break)

    # Availability Map Edge Cases
    def test_availability_exceeding_max_daily_raises_error(self) -> None:
        """Verify assigning day availability higher than max_daily_hours raises error."""
        with pytest.raises(InvalidProfileError, match="exceeds max_daily_hours"):
            StudentProfile(
                student_id="STU01",
                name="Rahul",
                max_daily_hours=5.0,
                daily_availability={"monday": 6.0},
            )

    def test_negative_availability_raises_error(self) -> None:
        """Verify negative availability hours raise error."""
        with pytest.raises(InvalidProfileError, match="cannot be negative"):
            StudentProfile(
                student_id="STU01",
                name="Rahul",
                daily_availability={"monday": -1.0},
            )

    def test_all_zero_availability_raises_error(self) -> None:
        """Verify a profile with zero available hours across all days is rejected."""
        all_zero = {day.value: 0.0 for day in DayOfWeek}
        with pytest.raises(InvalidProfileError, match="at least some study availability"):
            StudentProfile(
                student_id="STU01",
                name="Rahul",
                daily_availability=all_zero,
            )

    def test_invalid_day_name_raises_error(self) -> None:
        """Verify invalid day of week name raises InvalidProfileError."""
        with pytest.raises(InvalidProfileError, match="Invalid day of week"):
            StudentProfile(
                student_id="STU01",
                name="Rahul",
                daily_availability={"funday": 4.0},
            )

    def test_student_profile_immutability(self, sample_student_profile: StudentProfile) -> None:
        """Verify profile attributes and daily_availability map are strictly immutable."""
        with pytest.raises(FrozenInstanceError):
            sample_student_profile.max_daily_hours = 10.0  # type: ignore[misc]

        with pytest.raises(TypeError):
            sample_student_profile.daily_availability["monday"] = 8.0  # type: ignore[index]


# ============================================================================
# TIME SLOT TESTS
# ============================================================================
class TestTimeSlotModel:
    """Unit tests for the TimeSlot domain entity."""

    def test_valid_time_slot_creation(self) -> None:
        """Verify valid TimeSlot initialization and derived end_hour."""
        slot = TimeSlot(
            slot_date=date(2026, 10, 10),
            start_hour=9.5,
            duration_hours=2.0,
            label="Machine Learning Study Block",
            slot_id="S01",
        )
        assert slot.slot_date == date(2026, 10, 10)
        assert slot.start_hour == 9.5
        assert slot.duration_hours == 2.0
        assert slot.end_hour == 11.5
        assert slot.format_time_range() == "09:30 - 11:30"
        assert "Machine Learning Study Block" in str(slot)

    def test_time_slot_requires_date_instance(self) -> None:
        """Verify non-date slot_date raises InvalidTimeSlotError."""
        with pytest.raises(InvalidTimeSlotError, match="slot_date must be an instance"):
            TimeSlot(
                slot_date="2026-10-10",  # type: ignore[arg-type]
                start_hour=9.0,
                duration_hours=1.0,
            )

    @pytest.mark.parametrize("invalid_start", [-0.5, 24.0, 25.0, True, "nine", None])
    def test_time_slot_invalid_start_hour(self, invalid_start: Any) -> None:
        """Verify start_hour outside [0.0, 24.0) or non-numeric raises error."""
        with pytest.raises(InvalidTimeSlotError, match="start_hour"):
            TimeSlot(
                slot_date=date(2026, 10, 10),
                start_hour=invalid_start,
                duration_hours=1.0,
            )

    @pytest.mark.parametrize("invalid_dur", [0.0, -1.0, 0.1, True, "two", None])
    def test_time_slot_invalid_duration(self, invalid_dur: Any) -> None:
        """Verify duration below 0.25h or non-numeric raises error."""
        with pytest.raises(InvalidTimeSlotError, match="duration_hours"):
            TimeSlot(
                slot_date=date(2026, 10, 10),
                start_hour=10.0,
                duration_hours=invalid_dur,
            )

    def test_time_slot_exceeding_24_hour_day_limit(self) -> None:
        """Verify slot extending past midnight (24.0) raises InvalidTimeSlotError."""
        with pytest.raises(InvalidTimeSlotError, match="exceeds the 24-hour day boundary"):
            TimeSlot(
                slot_date=date(2026, 10, 10),
                start_hour=23.0,
                duration_hours=2.0,  # 23.0 + 2.0 = 25.0 > 24.0
            )

    def test_time_slot_exact_boundary_up_to_midnight(self) -> None:
        """Verify a slot ending exactly at 24:00 is valid."""
        slot = TimeSlot(
            slot_date=date(2026, 10, 10),
            start_hour=22.0,
            duration_hours=2.0,
        )
        assert slot.end_hour == 24.0
        assert slot.format_time_range() == "22:00 - 24:00"

    # Overlap Detection Tests
    def test_time_slot_overlap_detection_same_day(self) -> None:
        """Verify half-open interval overlap logic on the same date."""
        target_date = date(2026, 10, 10)
        slot1 = TimeSlot(slot_date=target_date, start_hour=9.0, duration_hours=2.0)  # 09:00 - 11:00
        slot2 = TimeSlot(
            slot_date=target_date, start_hour=10.0, duration_hours=2.0
        )  # 10:00 - 12:00 (overlaps)
        slot3 = TimeSlot(
            slot_date=target_date, start_hour=11.0, duration_hours=2.0
        )  # 11:00 - 13:00 (adjacent touches, does NOT overlap)
        slot4 = TimeSlot(
            slot_date=target_date, start_hour=13.0, duration_hours=1.0
        )  # 13:00 - 14:00 (disjoint)

        # Overlapping check
        assert slot1.overlaps_with(slot2) is True
        assert slot2.overlaps_with(slot1) is True

        # Adjacent boundaries [9-11) and [11-13) must not overlap
        assert slot1.overlaps_with(slot3) is False
        assert slot3.overlaps_with(slot1) is False

        # Disjoint check
        assert slot1.overlaps_with(slot4) is False

    def test_time_slot_no_overlap_on_different_days(self) -> None:
        """Verify slots at the exact same hours on different days do not overlap."""
        slot_day1 = TimeSlot(slot_date=date(2026, 10, 10), start_hour=9.0, duration_hours=2.0)
        slot_day2 = TimeSlot(slot_date=date(2026, 10, 11), start_hour=9.0, duration_hours=2.0)
        assert slot_day1.overlaps_with(slot_day2) is False

    def test_time_slot_immutability(self, sample_time_slot: TimeSlot) -> None:
        """Verify TimeSlot is frozen and cannot be mutated."""
        with pytest.raises(FrozenInstanceError):
            sample_time_slot.start_hour = 14.0  # type: ignore[misc]
