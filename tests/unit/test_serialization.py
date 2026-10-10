"""Unit tests for ScholarSync JSON and CSV serialization and persistence."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from scholarsync.core.exceptions import ValidationError
from scholarsync.core.types import Difficulty, Priority
from scholarsync.models.schedule import ScheduledSession, ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask
from scholarsync.models.time_slot import TimeSlot
from scholarsync.serialization.csv_io import (
    CSV_HEADERS,
    export_schedule_to_csv_file,
    schedule_to_csv,
)
from scholarsync.serialization.json_io import (
    export_schedule_to_json_file,
    profile_from_dict,
    profile_from_json,
    profile_to_dict,
    profile_to_json,
    schedule_to_json,
    task_from_dict,
    task_to_dict,
    tasks_from_json,
    tasks_to_json,
)

TODAY: Final[date] = date(2026, 10, 10)


@pytest.fixture
def sample_study_task(sample_subject_algorithms: Subject) -> StudyTask:
    """Fixture providing a standard study task for serialization."""
    return StudyTask(
        task_id="T01",
        title="Dynamic Programming Homework",
        subject=sample_subject_algorithms,
        estimated_hours=3.5,
        deadline=TODAY + timedelta(days=5),
        priority=Priority.HIGH,
        difficulty=Difficulty.HARD,
        completed=False,
        prerequisites=("T00",),
        created_at=TODAY,
    )


class TestTaskSerialization:
    """Test suite for StudyTask JSON serialization."""

    def test_task_roundtrip_dict(self, sample_study_task: StudyTask) -> None:
        """StudyTask converts to dict and back preserving all fields."""
        d = task_to_dict(sample_study_task)
        restored = task_from_dict(d)
        assert restored.task_id == sample_study_task.task_id
        assert restored.title == sample_study_task.title
        assert restored.subject.code == sample_study_task.subject.code
        assert restored.estimated_hours == sample_study_task.estimated_hours
        assert restored.deadline == sample_study_task.deadline
        assert restored.priority == sample_study_task.priority
        assert restored.difficulty == sample_study_task.difficulty
        assert restored.prerequisites == sample_study_task.prerequisites
        assert restored.created_at == sample_study_task.created_at

    def test_tasks_roundtrip_json(self, sample_study_task: StudyTask) -> None:
        """Sequence of tasks serializes to JSON string and parses identically."""
        json_str = tasks_to_json([sample_study_task])
        restored_list = tasks_from_json(json_str)
        assert len(restored_list) == 1
        assert restored_list[0].task_id == "T01"

    def test_task_from_dict_missing_fields_raises_validation_error(self) -> None:
        """Missing mandatory fields raises ValidationError."""
        incomplete = {"task_id": "T01", "title": "Missing fields"}
        with pytest.raises(ValidationError, match="missing required fields"):
            task_from_dict(incomplete)

    def test_task_from_dict_invalid_subject_raises_validation_error(self) -> None:
        """Invalid subject structure raises ValidationError."""
        bad_subject = {
            "task_id": "T01",
            "title": "Title",
            "subject": "not a dict",
            "estimated_hours": 2.0,
            "deadline": "2026-10-15",
        }
        with pytest.raises(ValidationError, match="must be an object"):
            task_from_dict(bad_subject)

    def test_tasks_from_json_invalid_syntax_raises_validation_error(self) -> None:
        """Invalid JSON syntax raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid JSON syntax"):
            tasks_from_json("{broken: json,")

    def test_tasks_from_json_non_list_raises_validation_error(self) -> None:
        """JSON payload that is not an array raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a JSON array"):
            tasks_from_json('{"task_id": "T01"}')


class TestProfileSerialization:
    """Test suite for StudentProfile JSON serialization."""

    def test_profile_roundtrip_dict(self, sample_student_profile: StudentProfile) -> None:
        """StudentProfile converts to dict and back preserving constraints."""
        d = profile_to_dict(sample_student_profile)
        restored = profile_from_dict(d)
        assert restored.student_id == sample_student_profile.student_id
        assert restored.name == sample_student_profile.name
        assert restored.max_daily_hours == sample_student_profile.max_daily_hours
        assert restored.max_continuous_hours == sample_student_profile.max_continuous_hours
        assert restored.get_daily_hours("monday") == sample_student_profile.get_daily_hours(
            "monday"
        )

    def test_profile_roundtrip_json(self, sample_student_profile: StudentProfile) -> None:
        """StudentProfile serializes to JSON string and parses identically."""
        json_str = profile_to_json(sample_student_profile)
        restored = profile_from_json(json_str)
        assert restored.student_id == sample_student_profile.student_id

    def test_profile_missing_fields_raises_validation_error(self) -> None:
        """Missing required profile fields raises ValidationError."""
        with pytest.raises(ValidationError, match="missing required fields"):
            profile_from_dict({"student_id": "S1"})

    def test_profile_non_dict_raises_validation_error(self) -> None:
        """Non-dictionary payload raises ValidationError."""
        with pytest.raises(ValidationError, match="must be an object"):
            profile_from_dict("invalid")  # type: ignore[arg-type]


class TestScheduleExport:
    """Test suite for ScheduleResult JSON and CSV exports."""

    @pytest.fixture
    def sample_schedule_result(
        self,
        sample_study_task: StudyTask,
    ) -> ScheduleResult:
        """Fixture providing a populated ScheduleResult."""
        s1 = ScheduledSession(
            task_id=sample_study_task.task_id,
            task_title=sample_study_task.title,
            subject_code=sample_study_task.subject.code,
            slot=TimeSlot(slot_date=TODAY, start_hour=9.0, duration_hours=2.0),
            hours=2.0,
            is_completed_here=False,
        )
        s2 = ScheduledSession(
            task_id=sample_study_task.task_id,
            task_title=sample_study_task.title,
            subject_code=sample_study_task.subject.code,
            slot=TimeSlot(slot_date=TODAY + timedelta(days=1), start_hour=10.0, duration_hours=1.5),
            hours=1.5,
            is_completed_here=True,
        )
        return ScheduleResult(
            strategy_name="GreedyEDFScheduler",
            start_date=TODAY,
            end_date=TODAY + timedelta(days=6),
            sessions=(s1, s2),
            completed_tasks=(sample_study_task,),
            unscheduled_tasks=(),
            task_completion_dates={sample_study_task.task_id: TODAY + timedelta(days=1)},
            remaining_task_hours={sample_study_task.task_id: 0.0},
        )

    def test_schedule_to_json_structure(
        self,
        sample_schedule_result: ScheduleResult,
        sample_student_profile: StudentProfile,
    ) -> None:
        """Schedule JSON export contains metadata, sessions, tasks, and metrics."""
        json_str = schedule_to_json(sample_schedule_result, student=sample_student_profile)
        payload = json.loads(json_str)

        assert "metadata" in payload
        assert payload["metadata"]["strategy"] == "GreedyEDFScheduler"
        assert payload["metadata"]["total_scheduled_hours"] == 3.5
        assert len(payload["sessions"]) == 2
        assert len(payload["completed_tasks"]) == 1
        assert "metrics" in payload
        assert payload["metrics"]["completion_rate"] == 1.0

    def test_export_schedule_to_json_file(
        self,
        sample_schedule_result: ScheduleResult,
        tmp_path: Path,
    ) -> None:
        """export_schedule_to_json_file writes valid file and returns byte count."""
        target_file = tmp_path / "subdir" / "plan.json"
        bytes_written = export_schedule_to_json_file(sample_schedule_result, target_file)
        assert bytes_written > 0
        assert target_file.is_file()

        parsed = json.loads(target_file.read_text(encoding="utf-8"))
        assert parsed["metadata"]["total_sessions"] == 2

    def test_schedule_to_csv_headers_and_rows(
        self,
        sample_schedule_result: ScheduleResult,
    ) -> None:
        """schedule_to_csv exports RFC 4180 CSV with deterministic headers and values."""
        csv_str = schedule_to_csv(sample_schedule_result)
        lines = csv_str.strip().split("\n")

        assert len(lines) == 3  # Header + 2 rows
        headers = lines[0].split(",")
        assert tuple(headers) == CSV_HEADERS

        row1 = lines[1].split(",")
        assert row1[1] == TODAY.isoformat()
        assert row1[5] == "2.00"
        assert row1[6] == "T01"

    def test_export_schedule_to_csv_file(
        self,
        sample_schedule_result: ScheduleResult,
        tmp_path: Path,
    ) -> None:
        """export_schedule_to_csv_file writes CSV file and returns session count."""
        target_file = tmp_path / "exports" / "schedule.csv"
        rows_count = export_schedule_to_csv_file(sample_schedule_result, target_file)
        assert rows_count == 2
        assert target_file.is_file()
        content = target_file.read_text(encoding="utf-8")
        assert "T01_S1" in content
