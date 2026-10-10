"""Custom exceptions for the ScholarSync system.

Using a clear exception hierarchy enables precise error handling,
informative feedback for students, and structured debugging.
"""


class ScholarSyncError(Exception):
    """Base exception for all domain errors within ScholarSync."""


class ValidationError(ScholarSyncError):
    """Raised when an entity fails domain validation rules."""


class InvalidTaskError(ValidationError):
    """Raised when a StudyTask or Subject contains invalid parameters."""


class InvalidProfileError(ValidationError):
    """Raised when a StudentProfile contains invalid availability or constraint parameters."""


class InvalidTimeSlotError(ValidationError):
    """Raised when a TimeSlot has invalid start/end times or impossible duration."""


class ConfigurationError(ScholarSyncError):
    """Raised when project configuration or environment settings are invalid."""


class SchedulingError(ScholarSyncError):
    """Base exception for errors during schedule generation."""


class CyclicDependencyError(SchedulingError):
    """Raised when task prerequisites contain cyclic dependencies."""


class UnresolvedDependencyError(SchedulingError):
    """Raised when a task depends on a prerequisite that does not exist."""


class InfeasibleScheduleError(SchedulingError):
    """Raised when scheduling constraints cannot be satisfied."""
