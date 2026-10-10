# ScholarSync: An Intelligent Academic Workload Planning System

**Academic Context:** M.Tech Computer Science & Engineering (*Computational Thinking and Programming*)  
**Status:** Phases 1–7 Complete (Foundation, Schedulers, Audit, Pipelines, CLI, Benchmarks, Final QA & Research Readiness)

---

## 1. Project Overview

Graduate scholars frequently experience cognitive fatigue and deadline clustering across coursework, laboratory milestones, and thesis research. Standard calendar applications (e.g., Google Calendar) are purely passive reminder systems that require manual slot allocation. Conversely, standard project management tools (e.g., Jira, Trello) lack cognitive-aware scheduling that accounts for task difficulty, fatigue thresholds, and student study constraints.

**ScholarSync** addresses this challenge through computational thinking, modeling academic scheduling as a multi-constraint discrete optimization problem:
1. **Decomposition:** Decomposes complex multi-week semester workloads into daily study slot allocations, task utility estimations, and fatigue-constrained interval assignments.
2. **Pattern Recognition:** Maps daily study allocation to the **Bounded 0/1 Knapsack Problem** and deadline sequencing to **Earliest Deadline First (EDF) Interval Scheduling**.
3. **Abstraction:** Decouples scheduling policies (Greedy, DP, Hybrid) from student representations and persistence formats via the Strategy Pattern.
4. **Algorithmic Thinking:** Formulates deterministic dynamic programming recurrences and heuristic priority weightings with verified polynomial complexity bounds.

---

## 2. Core Scheduling Engines

| Strategy | Algorithm Class | Key Characteristics | Computational Complexity |
|---|---|---|---|
| **Greedy EDF-CW** | Priority Heuristic | Earliest Deadline First with Cognitive Weighting and prerequisite topology | $\mathcal{O}(N \log N + N \cdot D)$ |
| **DP 0/1 Knapsack** | Dynamic Programming | Optimal daily knapsack utility allocation using discrete 30-min time quanta | $\mathcal{O}(N \cdot W)$ per day |
| **Rolling-Horizon Hybrid** | Hybrid Optimization | Combines multi-day horizon scoping with daily dynamic programming optimization | $\mathcal{O}(D \cdot N \cdot W \cdot K) \subseteq \mathcal{O}(D \cdot N \cdot W^2)$ |

---

## 3. Installation & Setup

ScholarSync is built with the **Python Standard Library** for core execution, requiring Python 3.10 or newer. Developer tooling includes `pytest`, `pytest-cov`, `ruff`, and `mypy`.

### Clone & Install in Editable Mode:
```powershell
git clone <repo-url>
cd D:\SCHOLAR_SYNC

# Install dependencies and console script entry point
python -m pip install -e .
```

---

## 4. CLI Usage & Commands

After installation, the application provides the `scholarsync` command (as well as direct execution via `python -m scholarsync`).

### 1. Help & Available Commands
```powershell
scholarsync --help
# or via python module:
python -m scholarsync --help
```

### 2. Deterministic Demo (`demo`)
Runs an out-of-the-box demonstration on realistic M.Tech coursework (Algorithms, Machine Learning, Operating Systems, Research Seminar) without requiring external files:
```powershell
# Run default demo (Hybrid strategy, 14-day horizon)
scholarsync demo

# Run demo with Greedy strategy
scholarsync demo --strategy greedy

# Run demo and export schedule directly to CSV
scholarsync demo --strategy hybrid --export demo_schedule.csv
```

### 3. Generate Schedule Plan (`plan`)
Generates an optimized study schedule using custom or sample academic tasks and student profiles:
```powershell
# Plan with default sample data
scholarsync plan --strategy hybrid --horizon 14

# Plan with custom JSON tasks and profile files
scholarsync plan --tasks my_tasks.json --profile my_profile.json --strategy dp --export my_plan.json

# Include zero-hour rest days in schedule timeline
scholarsync plan --include-rest-days
```

### 4. Side-by-Side Algorithm Comparison (`compare`)
Benchmarks all three strategies on the identical workload and displays a formatted comparative table with execution latencies captured via `BenchmarkTimer`:
```powershell
scholarsync compare --horizon 14
```
**Example Comparison Output:**
```
+----------------------------------+-------+------------+---------+------------+------------+--------------+-----------------+---------+
| Scheduling Algorithm             | Hours |  Completed | On-Time | Capacity % | Daily Mean | Daily StdDev | Cognitive Index | Latency |
+----------------------------------+-------+------------+---------+------------+------------+--------------+-----------------+---------+
| Greedy EDF-CW                    | 25.0h | 7/7 (100%) |    100% |      42.4% |      4.17h |        1.11h |            95.0 | 0.73 ms |
| Dynamic Programming 0/1 Knapsack | 25.0h | 7/7 (100%) |    100% |      42.4% |      4.17h |        0.85h |            95.0 | 0.89 ms |
| Rolling-Horizon Hybrid Strategy  | 25.0h | 7/7 (100%) |    100% |      42.4% |      4.17h |        1.11h |            95.0 | 1.09 ms |
+----------------------------------+-------+------------+---------+------------+------------+--------------+-----------------+---------+
```

### 5. Schedule Export (`export`)
Exports study plans directly to RFC 4180 CSV or structured JSON:
```powershell
# Export to CSV (auto-inferred from extension)
scholarsync export --output semester_schedule.csv

# Export to JSON
scholarsync export --output semester_schedule.json
```

### 6. Reproducible Algorithmic Benchmarking (`benchmark`)
Executes empirical evaluations across standardized small, medium, and large synthetic workloads with isolated timing trials, statistical aggregation, and mathematical constraint audits:
```powershell
# Run full benchmark suite across all workloads (10 repetitions)
scholarsync benchmark --size all --repetitions 10

# Benchmark a specific scenario and export machine-readable results
scholarsync benchmark --size medium --repetitions 5 --export-json bench.json --export-csv bench.csv
```

---

## 5. File Formats & Persistence

### Task JSON Format (`tasks.json`):
```json
[
  {
    "task_id": "T01",
    "title": "Algorithm Complexity Analysis",
    "subject": {
      "code": "CS601",
      "name": "Advanced Data Structures & Algorithms",
      "credits": 4,
      "description": "Core M.Tech module"
    },
    "estimated_hours": 3.0,
    "deadline": "2026-10-14",
    "priority": 4,
    "difficulty": 3,
    "completed": false,
    "prerequisites": [],
    "created_at": "2026-10-10"
  }
]
```

### Student Profile JSON Format (`profile.json`):
```json
{
  "student_id": "STU_MTECH_2026",
  "name": "Aarav Sharma",
  "daily_availability": {
    "monday": 4.0,
    "tuesday": 4.0,
    "wednesday": 3.5,
    "thursday": 4.0,
    "friday": 3.0,
    "saturday": 6.0,
    "sunday": 5.0
  },
  "max_daily_hours": 8.0,
  "max_continuous_hours": 3.5,
  "break_duration_minutes": 20
}
```

---

## 6. Pythonic Constructs & Architecture

- **`ScheduleTimelineIterator`:** Custom iterator implementing `__iter__`, `__next__`, `__len__`, `__reversed__`, `peek()`, and `reset()`. Supports filtering by `target_date`, `date_range`, `task_id`, `subject_code`, and `min_duration_hours`.
- **Streaming Generators:** `stream_daily_agendas()` yields memory-efficient `DailyAgenda` summaries across the horizon; `stream_task_progress()` streams real-time completion ratios per session.
- **Context Managers:**
  - `ProfileSandbox`: Non-mutating "what-if" capacity simulation with automated constraint clamping and guaranteed cleanup/restoration.
  - `BenchmarkTimer`: High-resolution algorithm execution timing (`perf_counter`) that records durations even on exception.
  - `temporary_profile_override`: Convenient `@contextmanager` yielding temporary trial profiles.

---

## 7. End-to-End Demonstration Sequence

Follow this complete step-by-step verification workflow from any terminal:

```powershell
# Step 1: Run deterministic CLI demo
scholarsync demo

# Step 2: Compare Greedy, DP, and Hybrid schedulers on identical workload
scholarsync compare --horizon 14

# Step 3: Generate and export schedule to CSV
scholarsync plan --strategy hybrid --horizon 14 --export exports/schedule.csv

# Step 4: Run reproducible benchmarks across all workload sizes
scholarsync benchmark --size all --repetitions 10 --export-json benchmarks_output.json --export-csv benchmarks_output.csv
```

---

## 8. Research Documentation & Benchmark Artifacts

The system includes formal academic documentation and reproducible experiment artifacts:
- **[`RESEARCH_EVALUATION.md`](file:///D:/SCHOLAR_SYNC/RESEARCH_EVALUATION.md):** Complete technical report with formal problem formulations, complexity proofs, empirical analysis, threats to validity, and comparative evaluation.
- **[`benchmark_report.md`](file:///D:/SCHOLAR_SYNC/benchmark_report.md):** Markdown benchmark results table and strategy trade-off summary.
- **[`benchmarks_output.json`](file:///D:/SCHOLAR_SYNC/benchmarks_output.json):** Machine-readable JSON trial latencies, variance, capacity utilizations, and validation notes.
- **[`benchmarks_output.csv`](file:///D:/SCHOLAR_SYNC/benchmarks_output.csv):** Standard RFC 4180 CSV export for external statistical software.

---

## 9. Testing & Quality Assurance

ScholarSync enforces strict quality gates:

```powershell
# 1. Run all unit and integration tests with line coverage:
python -m pytest -v --cov=scholarsync --cov-report=term-missing

# 2. Run Ruff linter:
python -m ruff check .

# 3. Verify formatting:
python -m ruff format --check .

# 4. Run strict static type analysis:
python -m mypy
```

**Quality Status:**
- **243 Unit & Integration Tests Passing** (100% pass rate)
- **96% Test Coverage** across codebase
- **0 Warnings / 0 Errors** on Ruff and Strict Mypy

---

## 10. Known Limitations & Future Scope

- **Single Student Scope:** Designed for individual graduate scholar workload optimization; multi-student team scheduling is outside current scope.
- **Fixed Daily Start Hour:** Assumes standard daily study start times (default 09:00 AM) with mandatory break offsets rather than arbitrary calendar slot fragmentation.
- **Discrete Time Quantum:** 30-minute ($\Delta t = 0.5$h) slot quanta.
- **Web Interface:** Web visualization dashboard (Streamlit or FastAPI) is planned as future scope following CLI verification and concurrency benchmarking.
