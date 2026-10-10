"""Type definitions, enums, and constants for ScholarSync.

Provides structured types for priority, difficulty, and day mappings.
"""

from enum import Enum, IntEnum
from typing import Final

# System-wide validation constants
MIN_PRIORITY: Final[int] = 1
MAX_PRIORITY: Final[int] = 5

MIN_DIFFICULTY: Final[int] = 1
MAX_DIFFICULTY: Final[int] = 5

MIN_STUDY_HOURS: Final[float] = 0.25  # 15 minutes minimum task chunk
MAX_STUDY_HOURS: Final[float] = 100.0  # reasonable upper bound for a single academic task

MAX_DAILY_HOURS: Final[float] = 24.0
DEFAULT_MAX_DAILY_STUDY_HOURS: Final[float] = 12.0  # healthy daily maximum for students
DEFAULT_MAX_CONTINUOUS_HOURS: Final[float] = 4.0  # cognitive burnout limit


class Priority(IntEnum):
    """Priority level for academic tasks (1 = Low to 5 = Critical)."""

    LOW = 1
    MEDIUM_LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class Difficulty(IntEnum):
    """Cognitive difficulty level for academic tasks (1 = Easy to 5 = Very Hard)."""

    EASY = 1
    MODERATE = 2
    INTERMEDIATE = 3
    HARD = 4
    VERY_HARD = 5


class DayOfWeek(str, Enum):
    """Standard representation of the seven days of the week."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    def __str__(self) -> str:
        return self.value
