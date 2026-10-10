"""CSV exporter for ScholarSync study schedules.

Exports scheduled study sessions to standard RFC 4180 CSV files with deterministic
chronological ordering and explicit column headers.
"""

import csv
import io
from collections.abc import Sequence
from pathlib import Path

from scholarsync.models.schedule import ScheduledSession, ScheduleResult
from scholarsync.pipelines.iterators import ScheduleTimelineIterator

CSV_HEADERS: tuple[str, ...] = (
    "session_id",
    "date",
    "day_of_week",
    "start_time",
    "end_time",
    "duration_hours",
    "task_id",
    "task_title",
    "subject_code",
    "is_completed_here",
)


def sessions_to_csv_rows(
    sessions: Sequence[ScheduledSession],
) -> list[list[str]]:
    """Convert scheduled sessions into deterministic, formatted CSV rows."""
    iterator = ScheduleTimelineIterator(sessions)
    rows: list[list[str]] = []

    for idx, session in enumerate(iterator, start=1):
        slot = session.slot
        time_parts = slot.format_time_range().split(" - ")
        start_time_str = time_parts[0] if len(time_parts) >= 1 else f"{slot.start_hour:.2f}"
        end_time_str = time_parts[1] if len(time_parts) >= 2 else f"{slot.end_hour:.2f}"

        rows.append(
            [
                f"{session.task_id}_S{idx}",
                slot.slot_date.isoformat(),
                slot.slot_date.strftime("%A"),
                start_time_str,
                end_time_str,
                f"{session.hours:.2f}",
                session.task_id,
                session.task_title,
                session.subject_code,
                "true" if session.is_completed_here else "false",
            ]
        )

    return rows


def schedule_to_csv(result: ScheduleResult) -> str:
    """Serialize a ScheduleResult to an RFC 4180 formatted CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(list(CSV_HEADERS))
    rows = sessions_to_csv_rows(result.sessions)
    writer.writerows(rows)
    return output.getvalue()


def export_schedule_to_csv_file(
    result: ScheduleResult,
    filepath: Path | str,
) -> int:
    """Write ScheduleResult to a CSV file.

    Args:
        result: The ScheduleResult to export.
        filepath: Target file destination.

    Returns:
        Number of scheduled session rows written (excluding header).
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = schedule_to_csv(result)
    path.write_text(content, encoding="utf-8")
    return len(result.sessions)
