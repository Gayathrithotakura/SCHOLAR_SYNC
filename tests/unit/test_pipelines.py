"""Unit tests for Phase 4: Iterators, Generators, and Context Managers.

Validates:
- ScheduleTimelineIterator: chronological traversal, multi-filter combinations, peek, reset.
- Generators: stream_daily_agendas, stream_task_progress, lazy evaluation, memory efficiency.
- Context Managers: BenchmarkTimer, ProfileSandbox, temporary_profile_override.
- Integration: ScheduleResult.__iter__, iter_sessions, stream_agendas, stream_progress.
"""

from datetime import date
from typing import Final

import pytest

from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.core.context_managers import (
    BenchmarkTimer,
    ProfileSandbox,
    temporary_profile_override,
)
from scholarsync.core.exceptions import InvalidProfileError
from scholarsync.core.types import Difficulty, Priority
from scholarsync.models.schedule import ScheduledSession, ScheduleResult
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask
from scholarsync.models.time_slot import TimeSlot
from scholarsync.pipelines.generators import (
    DailyAgenda,
    TaskProgressSnapshot,
    stream_daily_agendas,
    stream_task_progress,
)
from scholarsync.pipelines.iterators import ScheduleTimelineIterator

D0: Final[date] = date(2026, 10, 10)
D1: Final[date] = date(2026, 10, 11)
D2: Final[date] = date(2026, 10, 12)


@pytest.fixture
def multi_session_result(
    sample_subject_algorithms: Subject,
    sample_subject_ml: Subject,
) -> ScheduleResult:
    """Fixture providing a ScheduleResult with multiple sessions across multiple days."""
    s1 = ScheduledSession(
        task_id="T01",
        task_title="Algorithms Lab 1",
        subject_code=sample_subject_algorithms.code,
        slot=TimeSlot(slot_date=D0, start_hour=9.0, duration_hours=2.0),
        hours=2.0,
        is_completed_here=False,
    )
    s2 = ScheduledSession(
        task_id="T02",
        task_title="ML Reading",
        subject_code=sample_subject_ml.code,
        slot=TimeSlot(slot_date=D0, start_hour=14.0, duration_hours=1.5),
        hours=1.5,
        is_completed_here=True,
    )
    s3 = ScheduledSession(
        task_id="T01",
        task_title="Algorithms Lab 1",
        subject_code=sample_subject_algorithms.code,
        slot=TimeSlot(slot_date=D2, start_hour=10.0, duration_hours=2.0),
        hours=2.0,
        is_completed_here=True,
    )

    t1 = StudyTask(
        task_id="T01",
        title="Algorithms Lab 1",
        subject=sample_subject_algorithms,
        estimated_hours=4.0,
        deadline=D2,
        priority=Priority.HIGH,
        difficulty=Difficulty.HARD,
    )
    t2 = StudyTask(
        task_id="T02",
        title="ML Reading",
        subject=sample_subject_ml,
        estimated_hours=1.5,
        deadline=D1,
        priority=Priority.MEDIUM,
        difficulty=Difficulty.INTERMEDIATE,
    )

    return ScheduleResult(
        strategy_name="MockScheduler",
        start_date=D0,
        end_date=D2,
        sessions=(s1, s2, s3),
        completed_tasks=(t1, t2),
        unscheduled_tasks=(),
        task_completion_dates={"T01": D2, "T02": D0},
        remaining_task_hours={"T01": 0.0, "T02": 0.0},
    )


# ==============================================================================
# 1. ScheduleTimelineIterator Tests
# ==============================================================================


class TestScheduleTimelineIterator:
    """Test suite for ScheduleTimelineIterator."""

    def test_empty_sessions_iteration(self) -> None:
        """Empty session sequence initializes safely and terminates immediately."""
        it = ScheduleTimelineIterator([])
        assert len(it) == 0
        assert not it.has_next()
        assert it.peek() is None
        assert it.to_list() == []
        with pytest.raises(StopIteration):
            next(it)

    def test_chronological_ordering(self, multi_session_result: ScheduleResult) -> None:
        """Sessions are yielded in strict chronological order."""
        # Intentionally reverse sessions to verify iterator sorts them
        shuffled = list(reversed(multi_session_result.sessions))
        it = ScheduleTimelineIterator(shuffled)

        assert len(it) == 3
        s1 = next(it)
        assert s1.task_id == "T01"
        assert s1.slot.slot_date == D0
        assert s1.slot.start_hour == 9.0

        s2 = next(it)
        assert s2.task_id == "T02"
        assert s2.slot.slot_date == D0
        assert s2.slot.start_hour == 14.0

        s3 = next(it)
        assert s3.task_id == "T01"
        assert s3.slot.slot_date == D2

        with pytest.raises(StopIteration):
            next(it)

    def test_target_date_filtering(self, multi_session_result: ScheduleResult) -> None:
        """Filtering by target_date only returns sessions for that date."""
        it = ScheduleTimelineIterator(multi_session_result.sessions, target_date=D0)
        items = list(it)
        assert len(items) == 2
        assert all(s.slot.slot_date == D0 for s in items)

        empty_it = ScheduleTimelineIterator(multi_session_result.sessions, target_date=D1)
        assert len(empty_it) == 0
        assert list(empty_it) == []

    def test_date_range_filtering(self, multi_session_result: ScheduleResult) -> None:
        """Filtering by date_range includes only sessions within [start, end]."""
        it = ScheduleTimelineIterator(
            multi_session_result.sessions,
            date_range=(D1, D2),
        )
        items = list(it)
        assert len(items) == 1
        assert items[0].slot.slot_date == D2

    def test_invalid_date_range_raises_error(
        self,
        multi_session_result: ScheduleResult,
    ) -> None:
        """Date range where start > end raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date_range"):
            ScheduleTimelineIterator(
                multi_session_result.sessions,
                date_range=(D2, D0),
            )

    def test_task_id_and_subject_filtering(
        self,
        multi_session_result: ScheduleResult,
    ) -> None:
        """Filtering by task_id and subject_code matches accurately."""
        # By task_id
        t01_it = ScheduleTimelineIterator(multi_session_result.sessions, task_id=" T01 ")
        t01_items = list(t01_it)
        assert len(t01_items) == 2
        assert all(s.task_id == "T01" for s in t01_items)

        # By subject code (case insensitive)
        ml_it = ScheduleTimelineIterator(
            multi_session_result.sessions,
            subject_code="ai702",
        )
        ml_items = list(ml_it)
        assert len(ml_items) == 1
        assert ml_items[0].subject_code == "AI702"

    def test_min_duration_filtering(self, multi_session_result: ScheduleResult) -> None:
        """Filtering by min_duration_hours excludes shorter sessions."""
        it = ScheduleTimelineIterator(
            multi_session_result.sessions,
            min_duration_hours=2.0,
        )
        items = list(it)
        assert len(items) == 2
        assert all(s.hours >= 2.0 for s in items)

    def test_peek_and_has_next(self, multi_session_result: ScheduleResult) -> None:
        """peek() inspects the next item without consuming it; has_next() tracks availability."""
        it = ScheduleTimelineIterator(multi_session_result.sessions)
        assert it.has_next()
        first_peek = it.peek()
        assert first_peek is not None
        assert first_peek.task_id == "T01"

        # Peek again does not advance
        assert it.peek() == first_peek
        assert len(it) == 3

        # Consume first
        consumed = next(it)
        assert consumed == first_peek
        assert len(it) == 2

        # Peek next
        second_peek = it.peek()
        assert second_peek is not None
        assert second_peek.task_id == "T02"

    def test_reset_and_to_list(self, multi_session_result: ScheduleResult) -> None:
        """reset() returns iterator to beginning; to_list() consumes all remaining items."""
        it = ScheduleTimelineIterator(multi_session_result.sessions)
        next(it)  # consume 1
        assert len(it) == 2

        it.reset()
        assert len(it) == 3
        all_items = it.to_list()
        assert len(all_items) == 3
        assert len(it) == 0
        assert it.peek() is None

    def test_reversed_iteration(self, multi_session_result: ScheduleResult) -> None:
        """reversed() traverses sessions in reverse chronological order."""
        it = ScheduleTimelineIterator(multi_session_result.sessions)
        rev_items = list(reversed(it))
        assert len(rev_items) == 3
        assert rev_items[0].slot.slot_date == D2
        assert rev_items[-1].slot.slot_date == D0

    def test_schedule_result_integration(
        self,
        multi_session_result: ScheduleResult,
    ) -> None:
        """ScheduleResult directly supports `for s in result:` and `result.iter_sessions()`."""
        direct_sessions = list(multi_session_result)
        assert len(direct_sessions) == 3
        assert direct_sessions[0].task_id == "T01"

        # Filtered through ScheduleResult method
        filtered_it = multi_session_result.iter_sessions(target_date=D2)
        assert len(filtered_it) == 1
        assert next(filtered_it).slot.slot_date == D2


# ==============================================================================
# 2. Generator Pipelines Tests
# ==============================================================================


class TestGeneratorPipelines:
    """Test suite for stream_daily_agendas and stream_task_progress generators."""

    def test_stream_daily_agendas_active_days_only(
        self,
        multi_session_result: ScheduleResult,
    ) -> None:
        """Default stream_daily_agendas yields only active days (omits D1)."""
        agendas = list(stream_daily_agendas(multi_session_result, include_empty_days=False))
        assert len(agendas) == 2

        d0_agenda = agendas[0]
        assert isinstance(d0_agenda, DailyAgenda)
        assert d0_agenda.date == D0
        assert d0_agenda.weekday == "Saturday"
        assert d0_agenda.total_hours == 3.5
        assert d0_agenda.tasks_involved == ("T01", "T02")
        assert not d0_agenda.is_rest_day
        assert "3.5h" in str(d0_agenda)

        d2_agenda = agendas[1]
        assert d2_agenda.date == D2
        assert d2_agenda.total_hours == 2.0
        assert d2_agenda.tasks_involved == ("T01",)

    def test_stream_daily_agendas_with_rest_days(
        self,
        multi_session_result: ScheduleResult,
    ) -> None:
        """stream_daily_agendas with include_empty_days=True yields rest days."""
        agendas = list(stream_daily_agendas(multi_session_result, include_empty_days=True))
        assert len(agendas) == 3  # D0, D1, D2

        rest_agenda = agendas[1]
        assert rest_agenda.date == D1
        assert rest_agenda.is_rest_day
        assert rest_agenda.total_hours == 0.0
        assert rest_agenda.tasks_involved == ()
        assert "Rest Day" in str(rest_agenda)

    def test_schedule_result_stream_agendas_method(
        self,
        multi_session_result: ScheduleResult,
    ) -> None:
        """ScheduleResult.stream_agendas() delegates cleanly to generator."""
        agendas = list(multi_session_result.stream_agendas(include_empty_days=True))
        assert len(agendas) == 3

    def test_stream_task_progress(
        self,
        multi_session_result: ScheduleResult,
        sample_subject_algorithms: Subject,
        sample_subject_ml: Subject,
    ) -> None:
        """stream_task_progress yields incremental completion ratios per session."""
        tasks = [
            StudyTask(
                task_id="T01",
                title="Algorithms Lab 1",
                subject=sample_subject_algorithms,
                estimated_hours=4.0,
                deadline=D2,
                priority=Priority.HIGH,
                difficulty=Difficulty.HARD,
            ),
            StudyTask(
                task_id="T02",
                title="ML Reading",
                subject=sample_subject_ml,
                estimated_hours=1.5,
                deadline=D1,
                priority=Priority.MEDIUM,
                difficulty=Difficulty.INTERMEDIATE,
            ),
        ]

        snapshots = list(stream_task_progress(multi_session_result, tasks))
        assert len(snapshots) == 3

        # Session 1: T01 (2h / 4h = 50.0%)
        snap1 = snapshots[0]
        assert isinstance(snap1, TaskProgressSnapshot)
        assert snap1.task_id == "T01"
        assert snap1.hours_completed_so_far == 2.0
        assert snap1.total_required_hours == 4.0
        assert snap1.progress_percentage == 50.0
        assert not snap1.is_task_complete
        assert "50.0%" in str(snap1)

        # Session 2: T02 (1.5h / 1.5h = 100.0%)
        snap2 = snapshots[1]
        assert snap2.task_id == "T02"
        assert snap2.hours_completed_so_far == 1.5
        assert snap2.progress_percentage == 100.0
        assert snap2.is_task_complete
        assert "COMPLETE" in str(snap2)

        # Session 3: T01 (4.0h / 4.0h = 100.0%)
        snap3 = snapshots[2]
        assert snap3.task_id == "T01"
        assert snap3.hours_completed_so_far == 4.0
        assert snap3.progress_percentage == 100.0
        assert snap3.is_task_complete

    def test_schedule_result_stream_progress_method(
        self,
        multi_session_result: ScheduleResult,
    ) -> None:
        """ScheduleResult.stream_progress() delegates directly."""
        snapshots = list(multi_session_result.stream_progress(multi_session_result.completed_tasks))
        assert len(snapshots) == 3


# ==============================================================================
# 3. Context Managers Tests
# ==============================================================================


class TestBenchmarkTimer:
    """Test suite for BenchmarkTimer context manager."""

    def test_normal_execution_measures_time(self) -> None:
        """BenchmarkTimer records elapsed execution time in seconds and milliseconds."""
        with BenchmarkTimer("Test Operation") as timer:
            total = sum(i * i for i in range(10_000))
            assert total > 0

        assert not timer.is_running
        assert not timer.had_exception
        assert timer.elapsed_seconds >= 0.0
        assert timer.elapsed_ms >= 0.0
        assert "Test Operation" in str(timer)
        assert "ms" in str(timer)

    def test_exception_handling_captures_duration(self) -> None:
        """BenchmarkTimer captures elapsed duration even when an exception occurs."""
        timer = BenchmarkTimer("Failing Operation")
        with pytest.raises(ZeroDivisionError):
            with timer:
                _ = 1 / 0

        assert not timer.is_running
        assert timer.had_exception
        assert timer.elapsed_seconds >= 0.0
        assert "Failed" in str(timer)


class TestProfileSandbox:
    """Test suite for ProfileSandbox context manager."""

    def test_profile_sandbox_normal_lifecycle(
        self,
        sample_student_profile: StudentProfile,
    ) -> None:
        """ProfileSandbox constructs trial profile, supports evaluation, and cleans up cleanly."""
        original_monday_hours = sample_student_profile.get_daily_hours("monday")
        sandbox = ProfileSandbox(
            sample_student_profile,
            availability_overrides={"monday": 1.0},
            max_daily_hours=6.0,
            max_continuous_hours=2.0,
        )

        assert not sandbox.is_active

        with sandbox as active_sb:
            assert active_sb.is_active
            trial = active_sb.trial_profile

            # Overrides applied on trial profile
            assert trial.get_daily_hours("monday") == 1.0
            assert trial.max_daily_hours == 6.0
            assert trial.max_continuous_hours == 2.0

            # Original profile remains completely untouched
            assert sample_student_profile.get_daily_hours("monday") == original_monday_hours
            assert sample_student_profile.max_daily_hours == 8.0

            active_sb.record_result("trial_eval_1")
            assert active_sb.evaluation_results == ("trial_eval_1",)

        # Post-exit verification
        assert not sandbox.is_active
        assert sandbox.is_cleaned_up
        assert not sandbox.had_error
        assert sandbox.error is None

    def test_sandbox_evaluate_with_scheduler(
        self,
        sample_student_profile: StudentProfile,
        sample_task: StudyTask,
    ) -> None:
        """sandbox.evaluate() successfully schedules with trial constraints."""
        scheduler = GreedyEDFScheduler()
        with ProfileSandbox(
            sample_student_profile,
            max_daily_hours=4.0,
            max_continuous_hours=2.0,
        ) as sandbox:
            res = sandbox.evaluate(
                scheduler=scheduler,
                tasks=[sample_task],
                start_date=D0,
                horizon_days=7,
            )
            assert res.total_scheduled_hours > 0
            assert len(sandbox.evaluation_results) == 1

    def test_sandbox_guaranteed_cleanup_on_exception(
        self,
        sample_student_profile: StudentProfile,
    ) -> None:
        """ProfileSandbox records error and marks cleaned_up=True even when an error occurs."""
        sandbox = ProfileSandbox(sample_student_profile)

        with pytest.raises(RuntimeError, match="Simulated algorithm failure"):
            with sandbox:
                raise RuntimeError("Simulated algorithm failure")

        assert not sandbox.is_active
        assert sandbox.is_cleaned_up
        assert sandbox.had_error
        assert isinstance(sandbox.error, RuntimeError)

    def test_sandbox_inactive_access_raises_runtime_error(
        self,
        sample_student_profile: StudentProfile,
    ) -> None:
        """Accessing trial profile or methods outside context raises RuntimeError."""
        sandbox = ProfileSandbox(sample_student_profile)

        with pytest.raises(RuntimeError, match="only available after context entry"):
            _ = sandbox.trial_profile

        with pytest.raises(RuntimeError, match="Cannot record results to an inactive sandbox"):
            sandbox.record_result("metric")

        with pytest.raises(RuntimeError, match="only be run inside an active sandbox"):
            sandbox.evaluate(
                GreedyEDFScheduler(),
                [],
                D0,
                horizon_days=7,
            )

    def test_sandbox_reentry_raises_runtime_error(
        self,
        sample_student_profile: StudentProfile,
    ) -> None:
        """Re-entering an already active sandbox raises RuntimeError."""
        sandbox = ProfileSandbox(sample_student_profile)
        with sandbox:
            with pytest.raises(RuntimeError, match="already active"):
                sandbox.__enter__()

    def test_sandbox_invalid_override_fails_on_enter(
        self,
        sample_student_profile: StudentProfile,
    ) -> None:
        """Invalid overrides (e.g., max_continuous > max_daily) raise InvalidProfileError."""
        sandbox = ProfileSandbox(
            sample_student_profile,
            max_daily_hours=2.0,
            max_continuous_hours=5.0,  # Invalid: continuous cannot exceed daily
        )
        with pytest.raises(InvalidProfileError):
            with sandbox:
                pass

    def test_temporary_profile_override_context_manager(
        self,
        sample_student_profile: StudentProfile,
    ) -> None:
        """temporary_profile_override yields trial StudentProfile and reverts cleanly."""
        with temporary_profile_override(
            sample_student_profile,
            max_daily_hours=3.0,
        ) as trial:
            assert trial.max_daily_hours == 3.0
            assert sample_student_profile.max_daily_hours == 8.0

        # Verify safe behavior under exception
        with pytest.raises(ValueError):
            with temporary_profile_override(sample_student_profile, max_daily_hours=3.0):
                raise ValueError("Boom")
