"""TimeSlot domain model representing a concrete, scheduled study window."""

from dataclasses import dataclass
from datetime import date
from typing import Final

from scholarsync.core.exceptions import InvalidTimeSlotError
from scholarsync.core.types import MIN_STUDY_HOURS

HOURS_IN_DAY: Final[float] = 24.0


def _format_hour_to_time_str(decimal_hour: float) -> str:
    """Convert decimal hour (e.g., 14.5) to standard 24h clock string ('14:30')."""
    total_minutes = int(round(decimal_hour * 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


@dataclass(frozen=True)
class TimeSlot:
    """Represents a scheduled chronological interval on a specific date.

    Attributes:
        slot_date: The calendar date of the study session.
        start_hour: Start time in 24-hour decimal format (e.g., 9.5 for 09:30).
        duration_hours: Duration of the session in hours (e.g., 1.5).
        label: Descriptive label or assigned task descriptor.
        slot_id: Optional unique identifier for tracking.
    """

    slot_date: date
    start_hour: float
    duration_hours: float
    label: str = ""
    slot_id: str | None = None

    def __post_init__(self) -> None:
        """Validate chronological boundaries and enforce immutability."""
        # Validate date
        if not isinstance(self.slot_date, date):
            raise InvalidTimeSlotError(
                f"slot_date must be an instance of datetime.date, "
                f"got {type(self.slot_date).__name__}."
            )

        # Validate start_hour
        if isinstance(self.start_hour, bool) or not isinstance(self.start_hour, (int, float)):
            raise InvalidTimeSlotError("start_hour must be numeric.")
        start = float(self.start_hour)
        if start < 0.0 or start >= HOURS_IN_DAY:
            raise InvalidTimeSlotError(
                f"start_hour must be between 0.0 and 24.0 (exclusive), got {start}."
            )

        # Validate duration_hours
        if isinstance(self.duration_hours, bool) or not isinstance(
            self.duration_hours, (int, float)
        ):
            raise InvalidTimeSlotError("duration_hours must be numeric.")
        dur = float(self.duration_hours)
        if dur < MIN_STUDY_HOURS:
            raise InvalidTimeSlotError(
                f"duration_hours must be at least {MIN_STUDY_HOURS} hours (15 mins), got {dur}."
            )

        # Validate day boundary
        end = start + dur
        if end > HOURS_IN_DAY:
            raise InvalidTimeSlotError(
                f"TimeSlot exceeds the 24-hour day boundary (starts at {start}h + {dur}h = {end}h)."
            )

        # Sanitize and assign to frozen object
        object.__setattr__(self, "start_hour", round(start, 4))
        object.__setattr__(self, "duration_hours", round(dur, 4))
        object.__setattr__(self, "label", self.label.strip())
        if self.slot_id is not None:
            object.__setattr__(self, "slot_id", self.slot_id.strip())

    @property
    def end_hour(self) -> float:
        """Calculate the ending hour of the slot."""
        return self.start_hour + self.duration_hours

    def overlaps_with(self, other: object) -> bool:
        """Determine if this slot overlaps with another slot on the same date.

        Uses half-open interval overlap check: [start, end)
        """
        if not isinstance(other, TimeSlot):
            return False
        if self.slot_date != other.slot_date:
            return False
        return max(self.start_hour, other.start_hour) < min(self.end_hour, other.end_hour)

    def format_time_range(self) -> str:
        """Return formatted readable time window like '09:00 - 11:30'."""
        start_str = _format_hour_to_time_str(self.start_hour)
        end_str = _format_hour_to_time_str(self.end_hour)
        return f"{start_str} - {end_str}"

    def __str__(self) -> str:
        tag = f" [{self.label}]" if self.label else ""
        return f"{self.slot_date} {self.format_time_range()} ({self.duration_hours}h){tag}"
