"""StudentProfile domain model representing a student's availability and study constraints."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from scholarsync.core.exceptions import InvalidProfileError
from scholarsync.core.types import (
    DEFAULT_MAX_CONTINUOUS_HOURS,
    DEFAULT_MAX_DAILY_STUDY_HOURS,
    MAX_DAILY_HOURS,
    DayOfWeek,
)

VALID_DAYS: Final[frozenset[str]] = frozenset(day.value for day in DayOfWeek)

DEFAULT_AVAILABILITY: Final[dict[str, float]] = {
    DayOfWeek.MONDAY.value: 4.0,
    DayOfWeek.TUESDAY.value: 4.0,
    DayOfWeek.WEDNESDAY.value: 4.0,
    DayOfWeek.THURSDAY.value: 4.0,
    DayOfWeek.FRIDAY.value: 4.0,
    DayOfWeek.SATURDAY.value: 6.0,
    DayOfWeek.SUNDAY.value: 6.0,
}


@dataclass(frozen=True)
class StudentProfile:
    """Represents a student's study capacity, daily schedule limits, and cognitive constraints.

    Attributes:
        student_id: Unique identifier for the student.
        name: Full student name.
        daily_availability: Mapping from day name ('monday'..'sunday') to study hours available.
        max_daily_hours: Maximum allowable study hours in any single day (burnout prevention).
        max_continuous_hours: Maximum allowable continuous session before a break.
        break_duration_minutes: Recommended break duration between intense study blocks.
    """

    student_id: str
    name: str
    daily_availability: Mapping[str, float] = field(
        default_factory=lambda: MappingProxyType(dict(DEFAULT_AVAILABILITY))
    )
    max_daily_hours: float = DEFAULT_MAX_DAILY_STUDY_HOURS
    max_continuous_hours: float = DEFAULT_MAX_CONTINUOUS_HOURS
    break_duration_minutes: int = 15

    def __post_init__(self) -> None:
        """Validate student profile parameters and enforce immutability."""
        # Validate student_id
        if not isinstance(self.student_id, str) or not self.student_id.strip():
            raise InvalidProfileError("Student ID must be a non-empty string.")

        # Validate name
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidProfileError("Student name must be a non-empty string.")

        # Validate max_daily_hours
        if isinstance(self.max_daily_hours, bool) or not isinstance(
            self.max_daily_hours, (int, float)
        ):
            raise InvalidProfileError("max_daily_hours must be numeric.")
        max_daily = float(self.max_daily_hours)
        if max_daily <= 0.0 or max_daily > MAX_DAILY_HOURS:
            raise InvalidProfileError(
                f"max_daily_hours must be in the range (0.0, {MAX_DAILY_HOURS}], got {max_daily}."
            )

        # Validate max_continuous_hours
        if isinstance(self.max_continuous_hours, bool) or not isinstance(
            self.max_continuous_hours, (int, float)
        ):
            raise InvalidProfileError("max_continuous_hours must be numeric.")
        max_cont = float(self.max_continuous_hours)
        if max_cont <= 0.0:
            raise InvalidProfileError(
                f"max_continuous_hours must be strictly positive, got {max_cont}."
            )
        if max_cont > max_daily:
            raise InvalidProfileError(
                f"max_continuous_hours ({max_cont}h) cannot exceed max_daily_hours ({max_daily}h)."
            )

        # Validate break_duration_minutes
        if isinstance(self.break_duration_minutes, bool) or not isinstance(
            self.break_duration_minutes, int
        ):
            raise InvalidProfileError("break_duration_minutes must be an integer.")
        if self.break_duration_minutes < 0 or self.break_duration_minutes > 120:
            raise InvalidProfileError(
                f"break_duration_minutes must be between 0 and 120, got "
                f"{self.break_duration_minutes}."
            )

        # Validate and clean daily_availability
        if not isinstance(self.daily_availability, Mapping):
            raise InvalidProfileError("daily_availability must be a dictionary/mapping.")

        cleaned_map: dict[str, float] = {}
        for day_key, hours in self.daily_availability.items():
            if not isinstance(day_key, (str, DayOfWeek)):
                raise InvalidProfileError(f"Day key must be a valid day name, got {day_key!r}.")
            day_str = day_key.value if isinstance(day_key, DayOfWeek) else str(day_key)
            normalized_day = day_str.lower().strip()
            if normalized_day not in VALID_DAYS:
                raise InvalidProfileError(
                    f"Invalid day of week: '{normalized_day}'. Must be one of {sorted(VALID_DAYS)}."
                )

            if isinstance(hours, bool) or not isinstance(hours, (int, float)):
                raise InvalidProfileError(
                    f"Availability hours for {normalized_day} must be numeric."
                )
            day_hours = float(hours)
            if day_hours < 0.0:
                raise InvalidProfileError(
                    f"Availability hours for {normalized_day} cannot be negative ({day_hours}h)."
                )
            if day_hours > max_daily:
                raise InvalidProfileError(
                    f"Availability for {normalized_day} ({day_hours}h) exceeds "
                    f"max_daily_hours ({max_daily}h)."
                )
            cleaned_map[normalized_day] = round(day_hours, 2)

        # Fill any missing days with 0.0 to ensure complete 7-day mapping
        for day in VALID_DAYS:
            if day not in cleaned_map:
                cleaned_map[day] = 0.0

        # Ensure total weekly availability is > 0
        total_avail = sum(cleaned_map.values())
        if total_avail <= 0.0:
            raise InvalidProfileError(
                "Student must have at least some study availability across the week."
            )

        # Store immutable MappingProxyType and sanitized scalars
        object.__setattr__(self, "student_id", self.student_id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "max_daily_hours", max_daily)
        object.__setattr__(self, "max_continuous_hours", max_cont)
        object.__setattr__(self, "daily_availability", MappingProxyType(cleaned_map))

    def get_daily_hours(self, day: str | DayOfWeek) -> float:
        """Get available hours for a specific day of the week."""
        day_str = day.value if isinstance(day, DayOfWeek) else str(day)
        normalized = day_str.lower().strip()
        return self.daily_availability.get(normalized, 0.0)

    def total_weekly_capacity(self) -> float:
        """Calculate total study hours available per week."""
        return sum(self.daily_availability.values())

    def __str__(self) -> str:
        return (
            f"StudentProfile[{self.student_id}] {self.name} "
            f"(Weekly: {self.total_weekly_capacity()}h, "
            f"Max Continuous: {self.max_continuous_hours}h)"
        )
