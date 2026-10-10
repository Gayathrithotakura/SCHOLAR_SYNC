"""Deterministic, reproducible benchmark workloads for algorithm evaluation.

Generates structured test scenarios of small, medium, and large sizes with:
- Varied task counts and fractional durations (0.25h, 0.5h, 0.75h, etc.)
- Multi-tier prerequisite chains (linear, branching, converging)
- Tasks exceeding single-day study limits (stressing atomic vs split schedulers)
- Tight, clustered, and relaxed deadlines
- Realistic student availability constraints and overload stress testing
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from scholarsync.core.types import DayOfWeek, Difficulty, Priority
from scholarsync.models.student import StudentProfile
from scholarsync.models.subject import Subject
from scholarsync.models.task import StudyTask

BENCHMARK_BASE_DATE: Final[date] = date(2026, 10, 12)  # Monday


@dataclass(frozen=True)
class BenchmarkScenario:
    """Encapsulates a fully reproducible benchmark workload configuration.

    Attributes:
        scenario_id: Short unique identifier (e.g., 'SMALL', 'MEDIUM', 'LARGE').
        name: Descriptive scenario name.
        description: Description of the academic workload characteristics.
        student: Configured StudentProfile with availability and burnout limits.
        tasks: Immutable tuple of StudyTasks to schedule.
        start_date: Calendar start date for planning.
        horizon_days: Planning horizon in days.
    """

    scenario_id: str
    name: str
    description: str
    student: StudentProfile
    tasks: tuple[StudyTask, ...]
    start_date: date
    horizon_days: int

    @property
    def total_task_hours(self) -> float:
        """Sum of all estimated study hours across tasks."""
        return round(sum(t.estimated_hours for t in self.tasks), 2)

    @property
    def total_student_capacity(self) -> float:
        """Sum of student available study hours across the planning horizon."""
        total = 0.0
        curr = self.start_date
        end_d = self.start_date + timedelta(days=self.horizon_days - 1)
        while curr <= end_d:
            total += self.student.get_daily_hours(curr.strftime("%A").lower())
            curr += timedelta(days=1)
        return round(total, 2)


def get_standard_subjects() -> dict[str, Subject]:
    """Return standard academic subjects for benchmark workloads."""
    return {
        "CS601": Subject(code="CS601", name="Advanced Algorithms", credits=4),
        "AI702": Subject(code="AI702", name="Machine Learning Systems", credits=4),
        "CS603": Subject(code="CS603", name="Advanced Operating Systems", credits=3),
        "CS604": Subject(code="CS604", name="Distributed Computing", credits=3),
        "CS699": Subject(code="CS699", name="M.Tech Thesis Research", credits=4),
        "MA601": Subject(code="MA601", name="Mathematical Foundations of CS", credits=3),
    }


def create_small_workload(anchor: date = BENCHMARK_BASE_DATE) -> BenchmarkScenario:
    """Create Small benchmark workload (6 tasks, 7-day horizon).

    Key Characteristics:
    - 6 tasks totaling 17.5 hours over a 7-day horizon (29.0 hours available capacity).
    - Fractional durations: 1.5h, 2.5h.
    - One task (T05, 5.0h) exceeds single-day weekday capacity (4.0h), testing multi-day
      splitting vs 0/1 rejection.
    - Prerequisite chain: T01 -> T02.
    - Clustered deadlines on days 3, 5, 6, 7.
    """
    subjects = get_standard_subjects()
    student = StudentProfile(
        student_id="STU_BENCH_SMALL",
        name="Small Workload Scholar",
        daily_availability={
            DayOfWeek.MONDAY.value: 4.0,
            DayOfWeek.TUESDAY.value: 4.0,
            DayOfWeek.WEDNESDAY.value: 4.0,
            DayOfWeek.THURSDAY.value: 4.0,
            DayOfWeek.FRIDAY.value: 3.0,
            DayOfWeek.SATURDAY.value: 5.0,
            DayOfWeek.SUNDAY.value: 5.0,
        },
        max_daily_hours=6.0,
        max_continuous_hours=3.0,
        break_duration_minutes=15,
    )

    tasks = (
        StudyTask(
            task_id="S01",
            title="Algorithm Asymptotic Analysis",
            subject=subjects["CS601"],
            estimated_hours=2.5,
            deadline=anchor + timedelta(days=2),
            priority=Priority.HIGH,
            difficulty=Difficulty.INTERMEDIATE,
            created_at=anchor,
        ),
        StudyTask(
            task_id="S02",
            title="Divide-and-Conquer Recurrences",
            subject=subjects["CS601"],
            estimated_hours=3.0,
            deadline=anchor + timedelta(days=4),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.HARD,
            prerequisites=("S01",),
            created_at=anchor,
        ),
        StudyTask(
            task_id="S03",
            title="Gradient Descent Math Foundations",
            subject=subjects["AI702"],
            estimated_hours=1.5,
            deadline=anchor + timedelta(days=3),
            priority=Priority.HIGH,
            difficulty=Difficulty.MODERATE,
            created_at=anchor,
        ),
        StudyTask(
            task_id="S04",
            title="Process Threading & Concurrency Lab",
            subject=subjects["CS603"],
            estimated_hours=2.5,
            deadline=anchor + timedelta(days=5),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.HARD,
            created_at=anchor,
        ),
        StudyTask(
            task_id="S05",
            title="Comprehensive OS Kernel Assignment",
            subject=subjects["CS603"],
            estimated_hours=5.0,  # Exceeds 4h weekday capacity!
            deadline=anchor + timedelta(days=6),
            priority=Priority.HIGH,
            difficulty=Difficulty.VERY_HARD,
            created_at=anchor,
        ),
        StudyTask(
            task_id="S06",
            title="Weekly Thesis Reading Review",
            subject=subjects["CS699"],
            estimated_hours=3.0,
            deadline=anchor + timedelta(days=6),
            priority=Priority.LOW,
            difficulty=Difficulty.EASY,
            created_at=anchor,
        ),
    )

    return BenchmarkScenario(
        scenario_id="SMALL",
        name="Small Workload (Focused Module)",
        description=(
            "6 tasks across 7 days with fractional hours and a 5.0h task exceeding daily capacity."
        ),
        student=student,
        tasks=tasks,
        start_date=anchor,
        horizon_days=7,
    )


def create_medium_workload(anchor: date = BENCHMARK_BASE_DATE) -> BenchmarkScenario:
    """Create Medium benchmark workload (16 tasks, 14-day horizon).

    Key Characteristics:
    - 16 tasks totaling 46.5 hours over a 14-day horizon (62.0 hours capacity).
    - Multi-tier prerequisite DAGs:
      M01 -> M02 -> M03 (Algorithms pipeline)
      M06 -> M07 (ML pipeline)
      M09 -> M10 -> M11 (Systems pipeline)
    - Fractional durations: 0.75h, 1.25h, 2.5h, 3.5h, 4.5h, 6.0h.
    - Varied urgency, cognitive tax, and clustered deadlines.
    """
    subjects = get_standard_subjects()
    student = StudentProfile(
        student_id="STU_BENCH_MEDIUM",
        name="Medium Workload Scholar",
        daily_availability={
            DayOfWeek.MONDAY.value: 4.0,
            DayOfWeek.TUESDAY.value: 4.5,
            DayOfWeek.WEDNESDAY.value: 3.5,
            DayOfWeek.THURSDAY.value: 4.0,
            DayOfWeek.FRIDAY.value: 4.0,
            DayOfWeek.SATURDAY.value: 6.0,
            DayOfWeek.SUNDAY.value: 5.0,
        },
        max_daily_hours=7.0,
        max_continuous_hours=3.0,
        break_duration_minutes=20,
    )

    tasks = (
        # Pipeline 1: Algorithms
        StudyTask(
            task_id="M01",
            title="Graph Representation & BFS/DFS",
            subject=subjects["CS601"],
            estimated_hours=2.5,
            deadline=anchor + timedelta(days=3),
            priority=Priority.HIGH,
            difficulty=Difficulty.INTERMEDIATE,
            created_at=anchor,
        ),
        StudyTask(
            task_id="M02",
            title="Shortest Paths Dijkstra & Bellman-Ford",
            subject=subjects["CS601"],
            estimated_hours=3.5,
            deadline=anchor + timedelta(days=6),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.HARD,
            prerequisites=("M01",),
            created_at=anchor,
        ),
        StudyTask(
            task_id="M03",
            title="Network Flow & Bipartite Matching",
            subject=subjects["CS601"],
            estimated_hours=4.5,
            deadline=anchor + timedelta(days=10),
            priority=Priority.HIGH,
            difficulty=Difficulty.VERY_HARD,
            prerequisites=("M02",),
            created_at=anchor,
        ),
        StudyTask(
            task_id="M04",
            title="Linear Programming Formulations",
            subject=subjects["MA601"],
            estimated_hours=2.0,
            deadline=anchor + timedelta(days=5),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.INTERMEDIATE,
            created_at=anchor,
        ),
        StudyTask(
            task_id="M05",
            title="Simplex Algorithm Problem Set",
            subject=subjects["MA601"],
            estimated_hours=3.0,
            deadline=anchor + timedelta(days=9),
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
            prerequisites=("M04",),
            created_at=anchor,
        ),
        # Pipeline 2: Machine Learning
        StudyTask(
            task_id="M06",
            title="Supervised Learning Foundations",
            subject=subjects["AI702"],
            estimated_hours=2.0,
            deadline=anchor + timedelta(days=4),
            priority=Priority.HIGH,
            difficulty=Difficulty.MODERATE,
            created_at=anchor,
        ),
        StudyTask(
            task_id="M07",
            title="Convolutional Neural Networks Implementation",
            subject=subjects["AI702"],
            estimated_hours=4.5,
            deadline=anchor + timedelta(days=8),
            priority=Priority.CRITICAL,
            difficulty=Difficulty.VERY_HARD,
            prerequisites=("M06",),
            created_at=anchor,
        ),
        StudyTask(
            task_id="M08",
            title="Transformer Self-Attention Paper Study",
            subject=subjects["AI702"],
            estimated_hours=3.0,
            deadline=anchor + timedelta(days=12),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.HARD,
            created_at=anchor,
        ),
        # Pipeline 3: Operating Systems & Distributed Systems
        StudyTask(
            task_id="M09",
            title="Virtual Memory & TLB Simulator",
            subject=subjects["CS603"],
            estimated_hours=3.5,
            deadline=anchor + timedelta(days=5),
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
            created_at=anchor,
        ),
        StudyTask(
            task_id="M10",
            title="File System Inode Design",
            subject=subjects["CS603"],
            estimated_hours=3.0,
            deadline=anchor + timedelta(days=9),
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
            prerequisites=("M09",),
            created_at=anchor,
        ),
        StudyTask(
            task_id="M11",
            title="Crash Consistency & Journaling Lab",
            subject=subjects["CS603"],
            estimated_hours=4.0,
            deadline=anchor + timedelta(days=13),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.VERY_HARD,
            prerequisites=("M10",),
            created_at=anchor,
        ),
        StudyTask(
            task_id="M12",
            title="RPC & Socket Programming Benchmark",
            subject=subjects["CS604"],
            estimated_hours=2.5,
            deadline=anchor + timedelta(days=7),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.INTERMEDIATE,
            created_at=anchor,
        ),
        StudyTask(
            task_id="M13",
            title="Consensus Protocols (Raft/Paxos) Proofs",
            subject=subjects["CS604"],
            estimated_hours=3.5,
            deadline=anchor + timedelta(days=11),
            priority=Priority.HIGH,
            difficulty=Difficulty.HARD,
            prerequisites=("M12",),
            created_at=anchor,
        ),
        # Research & Quick Reviews (Fractional items)
        StudyTask(
            task_id="M14",
            title="Weekly Thesis Advisor Progress Report",
            subject=subjects["CS699"],
            estimated_hours=1.25,
            deadline=anchor + timedelta(days=6),
            priority=Priority.HIGH,
            difficulty=Difficulty.MODERATE,
            created_at=anchor,
        ),
        StudyTask(
            task_id="M15",
            title="Latex Chapter Outline Drafting",
            subject=subjects["CS699"],
            estimated_hours=0.75,
            deadline=anchor + timedelta(days=12),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.EASY,
            created_at=anchor,
        ),
        StudyTask(
            task_id="M16",
            title="Comprehensive Literature Review Synthesis",
            subject=subjects["CS699"],
            estimated_hours=5.0,  # Long task
            deadline=anchor + timedelta(days=13),
            priority=Priority.MEDIUM,
            difficulty=Difficulty.HARD,
            created_at=anchor,
        ),
    )

    return BenchmarkScenario(
        scenario_id="MEDIUM",
        name="Medium Workload (Full Semester Milestone)",
        description=(
            "16 tasks across 14 days with multi-branch dependency DAGs and varied fractional "
            "study hours."
        ),
        student=student,
        tasks=tasks,
        start_date=anchor,
        horizon_days=14,
    )


def create_large_workload(anchor: date = BENCHMARK_BASE_DATE) -> BenchmarkScenario:
    """Create Large benchmark workload (32 tasks, 30-day horizon).

    Key Characteristics:
    - 32 tasks totaling 104.5 hours over a 30-day horizon (136.0 hours capacity).
    - Heavy cognitive load, 6 subjects, 6 distinct prerequisite subgraphs.
    - Tests scalability, boundary handling, and capacity stress under high task counts.
    """
    subjects = get_standard_subjects()
    student = StudentProfile(
        student_id="STU_BENCH_LARGE",
        name="Large Workload Graduate Scholar",
        daily_availability={
            DayOfWeek.MONDAY.value: 4.0,
            DayOfWeek.TUESDAY.value: 4.5,
            DayOfWeek.WEDNESDAY.value: 4.0,
            DayOfWeek.THURSDAY.value: 4.5,
            DayOfWeek.FRIDAY.value: 3.5,
            DayOfWeek.SATURDAY.value: 6.0,
            DayOfWeek.SUNDAY.value: 5.5,
        },
        max_daily_hours=8.0,
        max_continuous_hours=3.5,
        break_duration_minutes=20,
    )

    # Deterministic generation across the 30-day horizon
    task_list: list[StudyTask] = []
    subj_keys = ("CS601", "AI702", "CS603", "CS604", "CS699", "MA601")

    # Build 32 tasks with diverse configurations
    durations = (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 1.25, 2.75, 3.25, 4.25)
    for i in range(1, 33):
        t_id = f"L{i:02d}"
        subj = subjects[subj_keys[(i - 1) % len(subj_keys)]]
        dur = durations[(i - 1) % len(durations)]
        # Distribute deadlines across days 3 to 29
        deadline_day = min(29, 3 + (i * 26) // 32)
        prereqs: tuple[str, ...] = ()

        # Add chain dependencies for select groups
        if i in (2, 3, 5, 6, 8, 9, 12, 13, 16, 17, 20, 21, 25, 26, 30, 31):
            prereqs = (f"L{i - 1:02d}",)

        p_val = Priority(((i * 2) % 5) + 1)
        d_val = Difficulty(((i * 3) % 5) + 1)

        task_list.append(
            StudyTask(
                task_id=t_id,
                title=f"{subj.code} Research Milestone Module {i}",
                subject=subj,
                estimated_hours=dur,
                deadline=anchor + timedelta(days=deadline_day),
                priority=p_val,
                difficulty=d_val,
                prerequisites=prereqs,
                created_at=anchor,
            )
        )

    return BenchmarkScenario(
        scenario_id="LARGE",
        name="Large Workload (Comprehensive Semester Scope)",
        description=(
            "32 tasks across 30 days spanning 6 subjects with dense dependencies and "
            "varied capacities."
        ),
        student=student,
        tasks=tuple(task_list),
        start_date=anchor,
        horizon_days=30,
    )


def generate_benchmark_suite() -> Sequence[BenchmarkScenario]:
    """Return the complete suite of deterministic benchmark workloads."""
    return (
        create_small_workload(),
        create_medium_workload(),
        create_large_workload(),
    )


def get_benchmark_workload(size: str) -> BenchmarkScenario:
    """Retrieve benchmark scenario by size key ('small', 'medium', 'large').

    Raises:
        ValueError: If size key is not recognized.
    """
    key = size.upper().strip()
    if key == "SMALL":
        return create_small_workload()
    elif key == "MEDIUM":
        return create_medium_workload()
    elif key == "LARGE":
        return create_large_workload()
    else:
        raise ValueError(
            f"Unknown benchmark workload size '{size}'. Choose from: SMALL, MEDIUM, LARGE."
        )
