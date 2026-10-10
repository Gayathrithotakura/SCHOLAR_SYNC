"""Core definitions, custom exceptions, type aliases, and context managers for ScholarSync."""

from scholarsync.core.context_managers import (
    BenchmarkTimer,
    ProfileSandbox,
    temporary_profile_override,
)
from scholarsync.core.exceptions import (
    ConfigurationError,
    CyclicDependencyError,
    InfeasibleScheduleError,
    InvalidProfileError,
    InvalidTaskError,
    InvalidTimeSlotError,
    SchedulingError,
    ScholarSyncError,
    UnresolvedDependencyError,
    ValidationError,
)

__all__ = [
    "ScholarSyncError",
    "ValidationError",
    "InvalidTaskError",
    "InvalidProfileError",
    "InvalidTimeSlotError",
    "ConfigurationError",
    "SchedulingError",
    "CyclicDependencyError",
    "UnresolvedDependencyError",
    "InfeasibleScheduleError",
    "BenchmarkTimer",
    "ProfileSandbox",
    "temporary_profile_override",
]
