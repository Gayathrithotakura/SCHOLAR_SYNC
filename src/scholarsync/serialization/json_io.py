"""JSON serialization and deserialization for ScholarSync domain entities.

Provides validated conversion between JSON documents and domain models:
- StudyTask and Subject collections
- StudentProfile
- ScheduleResult and execution summaries

Enforces strict domain validation on deserialization.
"""

import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from scholarsync.algorithms.metrics import evaluate_schedule
from scholarsync.core.exceptions import ValidationError
from scholarsync.core.types import Difficulty, Priority
from scholarsync.models.schedule import ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask


def task_to_dict(task: StudyTask) -> dict[str, Any]:
    """Serialize a StudyTask instance to a dictionary."""
    return {
        "task_id": task.task_id,
        "title": task.title,
        "subject": {
            "code": task.subject.code,
            "name": task.subject.name,
            "credits": task.subject.credits,
            "description": task.subject.description,
        },
        "estimated_hours": task.estimated_hours,
        "deadline": task.deadline.isoformat(),
        "priority": int(task.priority),
        "difficulty": int(task.difficulty),
        "completed": task.completed,
        "prerequisites": list(task.prerequisites),
        "created_at": task.created_at.isoformat() if task.created_at is not None else None,
    }


def task_from_dict(data: dict[str, Any]) -> StudyTask:
    """Deserialize a dictionary to a validated StudyTask instance.

    Raises:
        ValidationError: If mandatory fields are missing or formats are invalid.
    """
    if not isinstance(data, dict):
        raise ValidationError(f"Task data must be an object, got {type(data).__name__}.")

    required = ("task_id", "title", "subject", "estimated_hours", "deadline")
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(f"Task is missing required fields: {', '.join(missing)}.")

    subj_data = data["subject"]
    if not isinstance(subj_data, dict):
        raise ValidationError("Task 'subject' must be an object.")
    if "code" not in subj_data or "name" not in subj_data:
        raise ValidationError("Subject object must contain at least 'code' and 'name'.")

    subject = Subject(
        code=str(subj_data["code"]),
        name=str(subj_data["name"]),
        credits=int(subj_data.get("credits", 3)),
        description=str(subj_data.get("description", "")),
    )

    try:
        deadline = date.fromisoformat(str(data["deadline"]))
    except ValueError as err:
        raise ValidationError(f"Invalid deadline date format '{data['deadline']}': {err}") from err

    created_at = (
        date.fromisoformat(str(data["created_at"]))
        if "created_at" in data and data["created_at"]
        else None
    )

    try:
        priority_val = int(data.get("priority", Priority.MEDIUM))
        priority = Priority(priority_val)
    except (ValueError, TypeError) as err:
        raise ValidationError(f"Invalid priority '{data.get('priority')}': {err}") from err

    try:
        difficulty_val = int(data.get("difficulty", Difficulty.INTERMEDIATE))
        difficulty = Difficulty(difficulty_val)
    except (ValueError, TypeError) as err:
        raise ValidationError(f"Invalid difficulty '{data.get('difficulty')}': {err}") from err

    prereqs = tuple(str(p).strip() for p in data.get("prerequisites", ()))

    kwargs: dict[str, Any] = {
        "task_id": str(data["task_id"]),
        "title": str(data["title"]),
        "subject": subject,
        "estimated_hours": float(data["estimated_hours"]),
        "deadline": deadline,
        "priority": priority,
        "difficulty": difficulty,
        "completed": bool(data.get("completed", False)),
        "prerequisites": prereqs,
    }
    if created_at is not None:
        kwargs["created_at"] = created_at

    return StudyTask(**kwargs)


def tasks_to_json(tasks: Sequence[StudyTask], indent: int = 2) -> str:
    """Serialize a sequence of StudyTasks into a formatted JSON string."""
    payload = [task_to_dict(t) for t in tasks]
    return json.dumps(payload, indent=indent)


def tasks_from_json(json_content: str) -> list[StudyTask]:
    """Parse and validate a list of StudyTasks from a JSON string.

    Raises:
        ValidationError: If JSON is malformed or invalid task structures are detected.
    """
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as err:
        raise ValidationError(f"Invalid JSON syntax in tasks payload: {err}") from err

    if not isinstance(data, list):
        raise ValidationError(f"Root task payload must be a JSON array, got {type(data).__name__}.")

    return [task_from_dict(item) for item in data]


def profile_to_dict(profile: StudentProfile) -> dict[str, Any]:
    """Serialize a StudentProfile instance to a dictionary."""
    return {
        "student_id": profile.student_id,
        "name": profile.name,
        "daily_availability": dict(profile.daily_availability),
        "max_daily_hours": profile.max_daily_hours,
        "max_continuous_hours": profile.max_continuous_hours,
        "break_duration_minutes": profile.break_duration_minutes,
    }


def profile_from_dict(data: dict[str, Any]) -> StudentProfile:
    """Deserialize a dictionary to a validated StudentProfile instance.

    Raises:
        ValidationError: If required fields are missing or constraints are violated.
    """
    if not isinstance(data, dict):
        raise ValidationError(f"Profile data must be an object, got {type(data).__name__}.")

    required = ("student_id", "name", "daily_availability")
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(f"Profile is missing required fields: {', '.join(missing)}.")

    avail_raw = data["daily_availability"]
    if not isinstance(avail_raw, dict):
        raise ValidationError("'daily_availability' must be a mapping of day names to hours.")

    avail_parsed: dict[str, float] = {}
    for day, hours in avail_raw.items():
        try:
            avail_parsed[str(day)] = float(hours)
        except (ValueError, TypeError) as err:
            raise ValidationError(f"Availability hours for '{day}' must be numeric: {err}") from err

    return StudentProfile(
        student_id=str(data["student_id"]),
        name=str(data["name"]),
        daily_availability=avail_parsed,
        max_daily_hours=float(data.get("max_daily_hours", 12.0)),
        max_continuous_hours=float(data.get("max_continuous_hours", 4.0)),
        break_duration_minutes=int(data.get("break_duration_minutes", 15)),
    )


def profile_to_json(profile: StudentProfile, indent: int = 2) -> str:
    """Serialize a StudentProfile to a formatted JSON string."""
    return json.dumps(profile_to_dict(profile), indent=indent)


def profile_from_json(json_content: str) -> StudentProfile:
    """Parse and validate a StudentProfile from a JSON string."""
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as err:
        raise ValidationError(f"Invalid JSON syntax in profile payload: {err}") from err

    return profile_from_dict(data)


def schedule_to_dict(
    result: ScheduleResult,
    student: StudentProfile | None = None,
) -> dict[str, Any]:
    """Convert a ScheduleResult and optional student evaluation into an export dictionary."""
    sessions_data = []
    for idx, s in enumerate(result.sessions, start=1):
        sessions_data.append(
            {
                "session_id": f"{s.task_id}_S{idx}",
                "task_id": s.task_id,
                "task_title": s.task_title,
                "subject_code": s.subject_code,
                "date": s.slot.slot_date.isoformat(),
                "day_of_week": s.slot.slot_date.strftime("%A"),
                "time_range": s.slot.format_time_range(),
                "start_hour": s.slot.start_hour,
                "duration_hours": s.hours,
                "is_completed_here": s.is_completed_here,
            }
        )

    completed_data = [
        {
            "task_id": t.task_id,
            "title": t.title,
            "subject_code": t.subject.code,
            "estimated_hours": t.estimated_hours,
            "deadline": t.deadline.isoformat(),
            "completion_date": (
                result.task_completion_dates[t.task_id].isoformat()
                if t.task_id in result.task_completion_dates
                else None
            ),
        }
        for t in result.completed_tasks
    ]

    unscheduled_data = [
        {
            "task_id": t.task_id,
            "title": t.title,
            "subject_code": t.subject.code,
            "estimated_hours": t.estimated_hours,
            "remaining_hours": result.get_remaining_hours(t.task_id),
            "deadline": t.deadline.isoformat(),
        }
        for t in result.unscheduled_tasks
    ]

    payload: dict[str, Any] = {
        "metadata": {
            "strategy": result.strategy_name,
            "start_date": result.start_date.isoformat(),
            "end_date": result.end_date.isoformat(),
            "total_scheduled_hours": result.total_scheduled_hours,
            "total_sessions": len(result.sessions),
            "is_fully_scheduled": result.is_fully_scheduled,
        },
        "sessions": sessions_data,
        "completed_tasks": completed_data,
        "unscheduled_tasks": unscheduled_data,
    }

    if student is not None:
        metrics = evaluate_schedule(result, student)
        payload["metrics"] = {
            "total_tasks": metrics.total_tasks,
            "completed_tasks": metrics.completed_tasks,
            "completion_rate": metrics.completion_rate,
            "on_time_tasks": metrics.on_time_tasks,
            "on_time_rate": metrics.on_time_rate,
            "total_available_hours": metrics.total_available_hours,
            "capacity_utilization": metrics.capacity_utilization,
            "mean_daily_hours": metrics.mean_daily_hours,
            "std_daily_hours": metrics.std_daily_hours,
            "high_difficulty_hours": metrics.high_difficulty_hours,
            "cognitive_load_index": metrics.cognitive_load_index,
        }

    return payload


def schedule_to_json(
    result: ScheduleResult,
    student: StudentProfile | None = None,
    indent: int = 2,
) -> str:
    """Serialize a ScheduleResult to a formatted JSON string."""
    return json.dumps(schedule_to_dict(result, student), indent=indent)


def export_schedule_to_json_file(
    result: ScheduleResult,
    filepath: Path | str,
    student: StudentProfile | None = None,
) -> int:
    """Write ScheduleResult to a JSON file.

    Returns:
        Number of bytes written.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = schedule_to_json(result, student)
    path.write_text(content, encoding="utf-8")
    return len(content.encode("utf-8"))
