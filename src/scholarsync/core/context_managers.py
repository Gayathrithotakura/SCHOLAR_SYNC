"""Context managers for safe schedule evaluation, scenario sandboxing, and benchmarking.

Enables safe 'what-if' capacity simulations without mutating existing domain models,
with guaranteed cleanup on normal completion and exceptions.
"""

import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from types import TracebackType
from typing import TYPE_CHECKING, Any

from scholarsync.models.student import StudentProfile

if TYPE_CHECKING:
    from scholarsync.algorithms.base import BaseSchedulerStrategy
    from scholarsync.models.schedule import ScheduleResult
    from scholarsync.models.task import StudyTask


class BenchmarkTimer:
    """High-resolution context manager for benchmarking algorithm execution.

    Guarantees that elapsed execution time is accurately captured and recorded
    regardless of whether the enclosed block completes normally or raises an exception.

    Example:
        >>> with BenchmarkTimer("Greedy Scheduler") as timer:
        ...     result = scheduler.schedule(tasks, profile, start, end)
        >>> print(timer.elapsed_ms)
    """

    def __init__(self, label: str = "Execution") -> None:
        """Initialize the benchmark timer with a descriptive label."""
        self.label: str = label.strip()
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.elapsed_seconds: float = 0.0
        self.is_running: bool = False
        self.had_exception: bool = False

    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds, rounded to 3 decimal places."""
        return round(self.elapsed_seconds * 1000.0, 3)

    def __enter__(self) -> "BenchmarkTimer":
        """Start the timer on context entry."""
        self.is_running = True
        self.had_exception = False
        self.start_time = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop the timer on context exit and record duration even upon failure."""
        self.end_time = time.perf_counter()
        self.is_running = False
        if self.start_time is not None:
            self.elapsed_seconds = round(self.end_time - self.start_time, 6)
        if exc_type is not None:
            self.had_exception = True

    def __str__(self) -> str:
        """Return formatted execution time string."""
        status = " (Failed)" if self.had_exception else ""
        return f"[{self.label}] {self.elapsed_ms:.3f} ms{status}"


class ProfileSandbox:
    """Safe evaluation sandbox for testing hypothetical student profile modifications.

    Allows schedulers or advisors to simulate changes in student availability,
    daily caps, or continuous study limits without mutating the original profile.
    Guarantees state cleanup and error tracking on both success and exceptions.

    Example:
        >>> with ProfileSandbox(profile, max_daily_hours=2.0) as sandbox:
        ...     res = sandbox.evaluate(scheduler, tasks, start_d, end_d)
        ...     print(res.is_fully_scheduled)
    """

    def __init__(
        self,
        original_profile: StudentProfile,
        *,
        availability_overrides: Mapping[str, float] | None = None,
        max_daily_hours: float | None = None,
        max_continuous_hours: float | None = None,
        break_duration_minutes: int | None = None,
        clamp_to_limits: bool = True,
    ) -> None:
        """Initialize the sandbox with base profile and desired overrides."""
        self.original_profile: StudentProfile = original_profile
        self.availability_overrides: Mapping[str, float] | None = availability_overrides
        self.max_daily_hours: float | None = max_daily_hours
        self.max_continuous_hours: float | None = max_continuous_hours
        self.break_duration_minutes: int | None = break_duration_minutes
        self.clamp_to_limits: bool = clamp_to_limits

        self._trial_profile: StudentProfile | None = None
        self._is_active: bool = False
        self._evaluation_results: list[Any] = []
        self._error: BaseException | None = None
        self._cleaned_up: bool = False

    @property
    def is_active(self) -> bool:
        """True if currently inside the sandbox context block."""
        return self._is_active

    @property
    def trial_profile(self) -> StudentProfile:
        """Return the prepared trial profile with applied overrides."""
        if self._trial_profile is None:
            raise RuntimeError("Sandbox trial profile is only available after context entry.")
        return self._trial_profile

    @property
    def evaluation_results(self) -> tuple[Any, ...]:
        """Return all evaluation results recorded during this sandbox session."""
        return tuple(self._evaluation_results)

    @property
    def had_error(self) -> bool:
        """True if an exception occurred during sandbox execution."""
        return self._error is not None

    @property
    def error(self) -> BaseException | None:
        """Return the exception encountered, if any."""
        return self._error

    @property
    def is_cleaned_up(self) -> bool:
        """True if the sandbox has exited and performed state cleanup."""
        return self._cleaned_up

    def evaluate(
        self,
        scheduler: "BaseSchedulerStrategy",
        tasks: Sequence["StudyTask"],
        start_date: date,
        horizon_days: int = 30,
        day_start_hour: float = 9.0,
    ) -> "ScheduleResult":
        """Execute a scheduling algorithm using the sandboxed trial profile.

        Args:
            scheduler: Schedulers instance implementing BaseSchedulerStrategy.
            tasks: Sequence of study tasks to schedule.
            start_date: Scheduling window start date.
            horizon_days: Planning horizon in days.
            day_start_hour: Start hour of the study day.

        Returns:
            ScheduleResult evaluated against the sandboxed profile.
        """
        if not self._is_active or self._trial_profile is None:
            raise RuntimeError("Evaluation can only be run inside an active sandbox context.")

        result = scheduler.schedule(
            tasks=tasks,
            student=self._trial_profile,
            start_date=start_date,
            horizon_days=horizon_days,
            day_start_hour=day_start_hour,
        )
        self._evaluation_results.append(result)
        return result

    def record_result(self, result: Any) -> None:
        """Manually record a simulation or metric outcome into the sandbox history."""
        if not self._is_active:
            raise RuntimeError("Cannot record results to an inactive sandbox.")
        self._evaluation_results.append(result)

    def __enter__(self) -> "ProfileSandbox":
        """Enter the sandbox: validate overrides and construct the trial profile."""
        if self._is_active:
            raise RuntimeError("ProfileSandbox is already active.")

        target_max_daily = (
            self.max_daily_hours
            if self.max_daily_hours is not None
            else self.original_profile.max_daily_hours
        )

        # Inherit baseline availability, optionally clamping if max_daily_hours lowered
        trial_availability = dict(self.original_profile.daily_availability)
        if self.clamp_to_limits and self.max_daily_hours is not None:
            for day, hours in trial_availability.items():
                if hours > target_max_daily:
                    trial_availability[day] = target_max_daily

        # Apply explicit availability overrides
        if self.availability_overrides is not None:
            for day, hours in self.availability_overrides.items():
                trial_availability[day] = hours

        # Determine continuous study session limit
        if self.max_continuous_hours is not None:
            target_max_continuous = self.max_continuous_hours
        else:
            target_max_continuous = (
                min(self.original_profile.max_continuous_hours, target_max_daily)
                if self.clamp_to_limits
                else self.original_profile.max_continuous_hours
            )

        # Prepare trial profile (StudentProfile.__post_init__ enforces validations)
        self._trial_profile = StudentProfile(
            student_id=f"{self.original_profile.student_id}_sandbox",
            name=f"{self.original_profile.name} (Sandbox)",
            daily_availability=trial_availability,
            max_daily_hours=target_max_daily,
            max_continuous_hours=target_max_continuous,
            break_duration_minutes=(
                self.break_duration_minutes
                if self.break_duration_minutes is not None
                else self.original_profile.break_duration_minutes
            ),
        )

        self._is_active = True
        self._cleaned_up = False
        self._error = None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the sandbox: finalize state, record errors, and guarantee cleanup."""
        self._is_active = False
        self._cleaned_up = True

        if exc_type is not None:
            self._error = exc_val


@contextmanager
def temporary_profile_override(
    profile: StudentProfile,
    *,
    availability_overrides: Mapping[str, float] | None = None,
    max_daily_hours: float | None = None,
    max_continuous_hours: float | None = None,
    break_duration_minutes: int | None = None,
    clamp_to_limits: bool = True,
) -> Iterator[StudentProfile]:
    """Convenience context manager yielding a temporary modified StudentProfile.

    Guarantees that the caller's environment and original profile remain untouched,
    unwinding temporary state upon exit or failure.

    Example:
        >>> with temporary_profile_override(profile, max_daily_hours=3.0) as temp_profile:
        ...     res = scheduler.schedule(tasks, temp_profile, start, end)
    """
    sandbox = ProfileSandbox(
        original_profile=profile,
        availability_overrides=availability_overrides,
        max_daily_hours=max_daily_hours,
        max_continuous_hours=max_continuous_hours,
        break_duration_minutes=break_duration_minutes,
        clamp_to_limits=clamp_to_limits,
    )
    with sandbox:
        yield sandbox.trial_profile
