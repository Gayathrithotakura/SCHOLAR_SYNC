"""Integration tests comparing Greedy, 0/1 DP, and Hybrid schedulers on a shared workload.

Verifies:
1. All three strategies execute successfully on a realistic M.Tech semester workload.
2. Invariant consistency across all three strategies:
   - No overlapping time slots (has_overlapping_slots is False)
   - Clock boundaries (all slots between 00:00 and 24:00)
   - No task over-allocation (allocated hours <= task.estimated_hours)
   - Accurate fractional duration handling (0.25h and 0.75h)
   - Strict prerequisite precedence
   - Hard deadline enforcement (no sessions after deadline)
   - Remaining task hours tracking and unfinished task reporting
   - Deterministic repeatability
3. Consistent evaluation metrics across all three strategies.
"""

from datetime import date, timedelta

import pytest

from scholarsync.algorithms.dynamic_programming import DPKnapsackScheduler
from scholarsync.algorithms.greedy import GreedyEDFScheduler
from scholarsync.algorithms.hybrid import RollingHorizonHybridScheduler
from scholarsync.algorithms.metrics import evaluate_schedule
from scholarsync.core.types import Difficulty, Priority
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask


@pytest.fixture
def audit_start_date() -> date:
    """Audit evaluation start date (Monday)."""
    return date(2026, 10, 12)


@pytest.fixture
def audit_student() -> StudentProfile:
    """M.Tech student profile with 4.0h weekdays and 6.0h weekends."""
    return StudentProfile(
        student_id="STU_AUDIT",
        name="Aakash Narang",
        daily_availability={
            "monday": 4.0,
            "tuesday": 4.0,
            "wednesday": 4.0,
            "thursday": 4.0,
            "friday": 4.0,
            "saturday": 6.0,
            "sunday": 6.0,
        },
        max_daily_hours=8.0,
        max_continuous_hours=2.0,
        break_duration_minutes=15,
    )


@pytest.fixture
def shared_mtech_workload(
    sample_subject_algorithms: Subject,
    sample_subject_ml: Subject,
    audit_start_date: date,
) -> list[StudyTask]:
    """Shared realistic workload with fractional hours and prerequisites."""
    subject_os = Subject(
        code="CS603",
        name="Advanced Operating Systems",
        credits=4,
        description="Kernel design and scheduling",
    )

    return [
        # Task 1: Fractional short task (0.75h = 45 min)
        StudyTask(
            task_id="TASK_01",
            title="Algorithm Proof Reading",
            subject=sample_subject_algorithms,
            estimated_hours=0.75,
            deadline=audit_start_date + timedelta(days=2),
            priority=Priority.HIGH,
            difficulty=Difficulty.MODERATE,
        ),
        # Task 2: Medium task (2.5h)
        StudyTask(
            task_id="TASK_02",
            title="Dynamic Programming Lab",
            subject=sample_subject_algorithms,
            estimated_hours=2.5,
            deadline=audit_start_date + timedelta(days=3),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.VERY_HARD,
        ),
        # Task 3: Fractional 0.25h task (15 min)
        StudyTask(
            task_id="TASK_03",
            title="OS Quiz Submission",
            subject=subject_os,
            estimated_hours=0.25,
            deadline=audit_start_date + timedelta(days=1),
            priority=Priority.HIGH,
            difficulty=Difficulty.EASY,
        ),
        # Task 4: Prerequisite task (2.0h)
        StudyTask(
            task_id="TASK_04",
            title="ML Model Training Pipeline",
            subject=sample_subject_ml,
            estimated_hours=2.0,
            deadline=audit_start_date + timedelta(days=4),
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
        ),
        # Task 5: Dependent task requiring TASK_04 (3.0h)
        StudyTask(
            task_id="TASK_05",
            title="ML Thesis Experiments",
            subject=sample_subject_ml,
            estimated_hours=3.0,
            deadline=audit_start_date + timedelta(days=5),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.VERY_HARD,
            prerequisites=("TASK_04",),
        ),
    ]


class TestSchedulerComparativeAudit:
    """Comparative correctness audit across Greedy, 0/1 DP, and Hybrid."""

    @pytest.mark.parametrize(
        "strategy_cls",
        [
            GreedyEDFScheduler,
            DPKnapsackScheduler,
            RollingHorizonHybridScheduler,
        ],
    )
    def test_shared_workload_execution_and_invariants(
        self,
        strategy_cls: type,
        shared_mtech_workload: list[StudyTask],
        audit_student: StudentProfile,
        audit_start_date: date,
    ) -> None:
        """Verify all invariants hold across all three scheduling algorithms."""
        scheduler = strategy_cls()
        result = scheduler.schedule(
            tasks=shared_mtech_workload,
            student=audit_student,
            start_date=audit_start_date,
            horizon_days=7,
        )

        # 1. No overlapping time slots
        assert result.has_overlapping_slots() is False, (
            f"{scheduler.name} produced overlapping time slots!"
        )

        # 2. Daily capacity limits respected
        curr_d = audit_start_date
        while curr_d <= audit_start_date + timedelta(days=6):
            day_hours = result.daily_allocated_hours(curr_d)
            weekday_name = curr_d.strftime("%A").lower()
            allowed_hours = audit_student.get_daily_hours(weekday_name)
            assert day_hours <= allowed_hours + 0.01, (
                f"{scheduler.name} exceeded daily capacity on {curr_d}: "
                f"{day_hours}h > {allowed_hours}h"
            )
            curr_d += timedelta(days=1)

        # 3. No midnight overflow (00:00 to 24:00)
        for session in result.sessions:
            assert session.slot.start_hour >= 0.0
            assert session.slot.end_hour <= 24.0

        # 4. No task over-allocation (allocated <= estimated)
        for task in shared_mtech_workload:
            task_sessions = result.get_task_sessions(task.task_id)
            allocated_h = sum(s.hours for s in task_sessions)
            assert round(allocated_h, 2) <= task.estimated_hours, (
                f"{scheduler.name} over-allocated task {task.task_id}: "
                f"{allocated_h}h > {task.estimated_hours}h"
            )

        # 5. Accurate fractional task handling (0.25h and 0.75h)
        for task in shared_mtech_workload:
            if task in result.completed_tasks:
                task_sessions = result.get_task_sessions(task.task_id)
                allocated_h = sum(s.hours for s in task_sessions)
                assert round(allocated_h, 2) == task.estimated_hours
                assert result.get_remaining_hours(task.task_id) == 0.0

        # 6. Strict prerequisite precedence (TASK_05 only after TASK_04 finishes)
        t4_sessions = result.get_task_sessions("TASK_04")
        t5_sessions = result.get_task_sessions("TASK_05")
        if t5_sessions:
            assert len(t4_sessions) > 0
            t4_finish = result.task_completion_dates.get("TASK_04")
            assert t4_finish is not None
            for s5 in t5_sessions:
                assert s5.slot.slot_date >= t4_finish

        # 7. Strict deadline enforcement (no sessions after deadline)
        for session in result.sessions:
            task = next(t for t in shared_mtech_workload if t.task_id == session.task_id)
            assert session.slot.slot_date <= task.deadline, (
                f"{scheduler.name} scheduled session for {task.task_id} past deadline: "
                f"{session.slot.slot_date} > {task.deadline}"
            )

        # 8. Remaining hours consistency
        for task in shared_mtech_workload:
            rem = result.get_remaining_hours(task.task_id)
            task_sessions = result.get_task_sessions(task.task_id)
            allocated_h = sum(s.hours for s in task_sessions)
            expected_rem = round(task.estimated_hours - allocated_h, 2)
            assert round(rem, 2) == expected_rem

        # 9. Deterministic repeatability
        run2 = scheduler.schedule(
            tasks=shared_mtech_workload,
            student=audit_student,
            start_date=audit_start_date,
            horizon_days=7,
        )
        assert len(result.sessions) == len(run2.sessions)
        for s1, s2 in zip(result.sessions, run2.sessions, strict=True):
            assert s1.task_id == s2.task_id
            assert s1.slot.slot_date == s2.slot.slot_date
            assert s1.slot.start_hour == s2.slot.start_hour
            assert s1.hours == s2.hours

        # 10. Consistent Metrics Calculation
        metrics = evaluate_schedule(result, audit_student)
        assert metrics.total_tasks == len(shared_mtech_workload)
        assert 0.0 <= metrics.completion_rate <= 1.0
        assert 0.0 <= metrics.capacity_utilization <= 1.0
        assert metrics.total_scheduled_hours == result.total_scheduled_hours

    def test_comparative_completion_trade_offs(
        self,
        shared_mtech_workload: list[StudyTask],
        audit_student: StudentProfile,
        audit_start_date: date,
    ) -> None:
        """Compare quantitative outputs between the three algorithms."""
        greedy = GreedyEDFScheduler()
        dp = DPKnapsackScheduler()
        hybrid = RollingHorizonHybridScheduler()

        res_greedy = greedy.schedule(shared_mtech_workload, audit_student, audit_start_date, 7)
        res_dp = dp.schedule(shared_mtech_workload, audit_student, audit_start_date, 7)
        res_hybrid = hybrid.schedule(shared_mtech_workload, audit_student, audit_start_date, 7)

        # All three must produce valid schedules
        assert res_greedy.total_scheduled_hours > 0.0
        assert res_dp.total_scheduled_hours > 0.0
        assert res_hybrid.total_scheduled_hours > 0.0

        # Hybrid and Greedy complete all feasible tasks
        assert len(res_hybrid.completed_tasks) == len(shared_mtech_workload)
        assert len(res_greedy.completed_tasks) == len(shared_mtech_workload)

        # Compare metrics
        m_greedy = evaluate_schedule(res_greedy, audit_student)
        m_dp = evaluate_schedule(res_dp, audit_student)
        m_hybrid = evaluate_schedule(res_hybrid, audit_student)

        assert m_greedy.total_tasks == 5
        assert m_dp.total_tasks == 5
        assert m_hybrid.total_tasks == 5
