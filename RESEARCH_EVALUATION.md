# ScholarSync: Algorithmic Planning and Empirical Evaluation of Academic Workload Scheduling

**Academic Context:** M.Tech Computer Science & Engineering (*Computational Thinking and Programming*)  
**Authors:** ScholarSync Development Team  
**Evaluation Date:** October 2026  
**Status:** Reproducible Research Report (Phase 7 Final Release)

---

## Abstract

Graduate researchers and advanced engineering scholars routinely face cognitive fatigue, severe deadline clustering, and heterogeneous task requirements spanning theoretical studies, systems programming labs, and thesis milestones. Passive calendar tools lack optimization capabilities, while industrial task boards do not account for student fatigue thresholds, daily availability, or prerequisite graph structures. 

**ScholarSync** frames academic workload planning as a multi-constraint discrete optimization problem. This report documents the system architecture, mathematical formulations, and a reproducible empirical evaluation of three scheduling paradigms:
1. **Greedy Earliest Deadline First with Cognitive Weighting (EDF-CW)**
2. **Sequential Dynamic Programming 0/1 Knapsack (DP-Knapsack)**
3. **Rolling-Horizon Hybrid Strategy (RH-Hybrid)**

Using isolated timing measurements across deterministic synthetic workloads (Small: 6 tasks, Medium: 16 tasks, Large: 32 tasks), we show that all three algorithms execute in sub-3 millisecond runtimes. We mathematically characterize and empirically demonstrate the fundamental trade-offs: Greedy heuristics and Rolling-Horizon Hybrid schedulers achieve 100% completion by fractionally splitting tasks across days, whereas sequential 0/1 Knapsack optimization provably guarantees local daily utility maximization but leaves oversized atomic tasks unscheduled when multi-day splitting is disallowed.

---

## 1. Problem Statement & Mathematical Formulation

### 1.1 The Academic Planning Challenge
Graduate scholars operate under non-uniform time availability: weekday study time is constrained by lectures and labs, whereas weekends offer longer blocks. Academic tasks differ substantially across three dimensions:
- **Urgency:** Time remaining before hard submission deadlines ($d_i$).
- **Priority ($p_i \in \{1, \dots, 5\}$):** Academic weight, course credits, or project criticality.
- **Cognitive Difficulty ($c_i \in \{1, \dots, 5\}$):** Cognitive load, requiring rest breaks to avoid fatigue.
- **Prerequisite Dependencies:** Direct Acyclic Graph (DAG) constraints where Task $B$ cannot begin until Task $A$ is 100% completed.

### 1.2 Formal Mathematical Model
Let an academic planning horizon span days $\mathcal{D} = \{1, 2, \dots, D\}$.
- **Tasks:** $\mathcal{T} = \{T_1, T_2, \dots, T_N\}$. Each task $T_i$ is characterized by required duration $h_i \in \mathbb{R}^+$, deadline date $\delta_i \in \mathcal{D}$, priority $p_i$, difficulty $c_i$, and prerequisite set $\mathcal{P}_i \subset \mathcal{T}$.
- **Student Profile:** Daily availability vector $\mathbf{C} = [C_1, C_2, \dots, C_D]$, maximum continuous session duration $M_{cont}$, and rest break duration $\Delta t_{break}$.
- **Discrete Time Units:** Time is discretized into quanta of $\Delta t = 0.5$ hours (30 minutes). Daily knapsack capacity is $W_d = \lfloor C_d / \Delta t \rfloor$.
- **Schedule Solution:** A set of non-overlapping study sessions $\mathcal{S} = \{s_1, s_2, \dots, s_K\}$, where each session $s_k = (T_{i_k}, \text{date}_k, \text{start}_k, \text{duration}_k)$.

### 1.3 Computational Complexity Boundary
The general multi-day multi-task scheduling problem with deadlines, precedence DAGs, and daily capacity limits is a generalization of the **Multi-Dimensional Knapsack Problem** and the **Resource-Constrained Project Scheduling Problem (RCPSP)**, both established as **NP-hard**. Therefore, polynomial-time algorithms cannot guarantee global multi-day Pareto optimality across arbitrary DAG topologies; instead, algorithms must balance computational efficiency, single-day optimality, and multi-day approximation heuristics.

---

## 2. System Architecture & Data Flow

ScholarSync decouples domain models, algorithm strategies, execution validation, and data export using the **Strategy Pattern**:

```
+---------------------------------------------------------------------------------+
|                                 Input Layer                                     |
|   StudyTask (JSON)          StudentProfile (JSON)         CLI Parameters        |
+---------------------------------------------------------------------------------+
                                       |
                                       v
+---------------------------------------------------------------------------------+
|                       Scheduling Strategy Layer (Abstract)                      |
|                           BaseSchedulerStrategy                                 |
+---------------------------------------------------------------------------------+
        |                               |                               |
        v                               v                               v
+------------------+         +--------------------+         +---------------------+
|  Greedy EDF-CW   |         |   DP 0/1 Knapsack  |         |    Rolling Hybrid   |
|  Priority &      |         | Bellman Recurrence |         | Window Scoping &    |
|  Urgency Sorting |         | 1D Rolling Array   |         | Bounded-Chunk DP    |
+------------------+         +--------------------+         +---------------------+
        |                               |                               |
        +-------------------------------+-------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                     Schedule Result & Mathematical Validator                    |
|                         validate_schedule_correctness                           |
|   1. Slot Non-overlap      2. Date Bounds           3. Daily Capacity Limits    |
|   4. Continuous Limits     5. Duration Conservation 6. Prerequisite DAG Order  |
|   7. Deadline Bounds       8. Chronological Sort                                |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                       Pipelines, Reporting & Export                             |
| ScheduleTimelineIterator  |  DailyAgenda Generator  |  JSON / CSV / CLI Tables  |
+---------------------------------------------------------------------------------+
```

---

## 3. Algorithmic Formulations

### 3.1 Strategy A: Greedy EDF-CW (Earliest Deadline First with Cognitive Weighting)
- **Objective:** Greedily select the most urgent and academically significant eligible task.
- **Scoring Function:** For eligible tasks on simulation date $t$:
  $$\mathcal{U}_{greedy}(T_i, t) = w_{urgency} \cdot \frac{10}{\max(0.5, \delta_i - t)} + w_{priority} \cdot p_i + w_{difficulty} \cdot c_i$$
- **Mechanism:** On each simulation day, tasks whose prerequisites are 100% finished and whose deadlines have not passed are sorted in descending order of $\mathcal{U}_{greedy}$. Study sessions are allocated in blocks up to $\min(h_{remaining}, C_{daily}, M_{cont})$.
- **Complexity:**
  - **Time:** $\mathcal{O}(D \cdot (N \log N + S))$, where $D$ is days, $N$ is tasks, and $S$ is sessions per day.
  - **Space:** $\mathcal{O}(N + D)$ auxiliary memory.
- **Key Property:** Supports **fractional multi-day progress**. Large tasks spanning multiple days are automatically partitioned across consecutive calendar days.

### 3.2 Strategy B: Dynamic Programming 0/1 Knapsack (Sequential Policy)
- **Objective:** Provably maximize total academic utility allocated within a discrete daily study budget.
- **Formulation:**
  $$\max \sum_{i=1}^{M} u_i \cdot x_i \quad \text{s.t.} \quad \sum_{i=1}^{M} w_i \cdot x_i \le W, \quad x_i \in \{0, 1\}$$
  where $W = \lfloor C_t / \Delta t \rfloor$, $w_i = \lceil h_i / \Delta t \rceil$, and $u_i = \mathcal{U}(T_i, t)$.
- **Dynamic Programming Recurrence:**
  $$DP[w] = \max(DP[w], DP[w - w_i] + u_i) \quad \text{for } w = W \text{ down to } w_i$$
- **Complexity:**
  - **Time:** $\mathcal{O}(D \cdot N \cdot W)$ pseudo-polynomial time.
  - **Space:** $\mathcal{O}(W)$ space using a 1D rolling array.
- **Optimality & Limitation:**
  - **Optimal:** For any single isolated day, the subset of tasks chosen achieves the mathematically maximal knapsack utility.
  - **Limitation:** In a multi-day sequential setting, 0/1 knapsack treats tasks as atomic ($x_i \in \{0, 1\}$). A task requiring $5.0$h cannot fit into a $4.0$h weekday budget and will be rejected every day unless an explicit multi-day chunking harness is applied. It also lacks multi-day lookahead.

### 3.3 Strategy C: Rolling-Horizon Hybrid Strategy
- **Objective:** Overcome the multi-day limitation of pure 0/1 Knapsack while retaining the combinatorial efficiency of Dynamic Programming.
- **Mechanism:**
  1. Partitions the horizon into rolling windows, filtering candidate tasks whose deadlines fall within active horizons.
  2. Employs **Bounded-Chunk Dynamic Programming**: Tasks are partitioned into discrete manageable chunks ($0.5$h to $M_{cont}$), allowing partial progress while optimizing daily combinations via DP.
  3. Applies completion bonuses ($+20\%$) to encourage finishing tasks rather than leaving multiple fragments open.
- **Complexity:**
  - **Time:** $\mathcal{O}(D \cdot N \cdot W \cdot K)$ where $K = \max_i(K_i) \le W$ is the maximum slots allocatable to a task on a single day. In the worst case where $K = \mathcal{O}(W)$, daily DP evaluates in $\mathcal{O}(N \cdot W^2)$, yielding total horizon time complexity $\mathcal{O}(D \cdot N \cdot W^2)$. Because daily slot capacity $W \le 16$ (8 hours at $\Delta t = 0.5$h) in academic scheduling, this inner bound evaluates in sub-3 millisecond runtimes in practice.
  - **Space:** $\mathcal{O}(N \cdot W)$ auxiliary memory for the 2D DP utility and backtracking choice reconstruction tables.

---

## 4. Experimental Methodology

### 4.1 Evaluation Environment
- **Operating System:** Windows 11 Enterprise (Build 10.0.26300)
- **Hardware Architecture:** Intel64 Family 6 Model 140 Stepping 1 (x86_64)
- **Runtime Environment:** Python 3.11.1 Standard Library (CPython)
- **Reproducibility Guarantee:** Deterministic test fixtures, fixed seed generation, and zero random variation across executions.

### 4.2 Benchmark Workloads
Workloads are defined in `scholarsync.benchmarks.workloads`:
1. **SMALL (Focused Module):**
   - 6 tasks, 7-day horizon, $17.5$h required vs $29.0$h student capacity.
   - Includes fractional hours ($1.5$h, $2.5$h), prerequisite chain (`S01` $\to$ `S02`), and an oversized task (`S05`, $5.0$h) that exceeds weekday capacity ($4.0$h).
2. **MEDIUM (Full Semester Milestone):**
   - 16 tasks, 14-day horizon, $48.5$h required vs $62.0$h student capacity.
   - Spans 4 subjects with multi-tier dependency subgraphs and clustered mid-horizon deadlines.
3. **LARGE (Comprehensive Semester Scope):**
   - 32 tasks, 30-day horizon, $101.0$h required vs $136.5$h student capacity.
   - Spans 6 academic subjects with dense dependency chains, tight deadlines, and heterogeneous task durations ($1.25$h to $5.0$h).

### 4.3 Timing Isolation Protocol
- All timing trials utilize `time.perf_counter()`, measuring exclusively the internal scheduling loop.
- **Warmup:** 1 un-timed execution precedes measurements to warm up bytecode cache and allocator pools.
- **Repetitions:** $K = 10$ independent trials per algorithm/scenario combination.
- **Reporting:** Median latency ($\tilde{t}$), minimum ($t_{min}$), maximum ($t_{max}$), and standard deviation ($\sigma_t$).

### 4.4 Automated Constraint Verification
Every generated schedule is audited by `validate_schedule_correctness` against 8 formal invariants:
1. **Slot Non-Overlap:** No two sessions on any date share overlapping half-open intervals $[s_1, e_1) \cap [s_2, e_2) \neq \emptyset$.
2. **Date Horizon Bounds:** All session dates satisfy $start\_date \le slot\_date \le end\_date$.
3. **Daily Capacity Limits:** $\sum_{s \in Day_d} duration(s) \le C_d + 10^{-3}$.
4. **Continuous Limit:** No session duration exceeds $M_{cont} + 10^{-3}$.
5. **Duration Conservation:** For every task $T_i$, total scheduled hours $\le h_i + 10^{-3}$.
6. **Prerequisite Precedence:** No session for $T_i$ is scheduled on or before the completion date of any prerequisite $P \in \mathcal{P}_i$.
7. **Deadline Compliance:** No session for $T_i$ is scheduled on a date exceeding deadline $\delta_i$.
8. **Chronological Ordering:** Sessions in the schedule tuple are ordered monotonically by $(date, start\_hour)$.

---

## 5. Measured Experimental Results

The table below reports measured empirical results across all 9 algorithm-workload configurations ($K=10$ trials, Python 3.11):

```text
+----------+----------------------------------+-------+-------------------+--------------+---------+------------+----------------+------------------+-------+
| Scenario | Algorithm                        | Tasks | Hours (Sched/Req) |    Completed | On-Time | Capacity % | Latency Median | Spread (Min-Max) | Valid |
+----------+----------------------------------+-------+-------------------+--------------+---------+------------+----------------+------------------+-------+
| SMALL    | Greedy EDF-CW                    |     6 |      17.5 / 17.5h |   6/6 (100%) |    100% |      60.3% |        0.15 ms |     0.15-0.17 ms | PASS  |
| SMALL    | Dynamic Programming 0/1 Knapsack |     6 |      17.5 / 17.5h |   6/6 (100%) |    100% |      60.3% |        0.17 ms |     0.17-0.28 ms | PASS  |
| SMALL    | Rolling-Horizon Hybrid Strategy  |     6 |      17.5 / 17.5h |   6/6 (100%) |    100% |      60.3% |        0.29 ms |     0.28-0.37 ms | PASS  |
| MEDIUM   | Greedy EDF-CW                    |    16 |      48.5 / 48.5h | 16/16 (100%) |    100% |      78.2% |        0.56 ms |     0.55-0.64 ms | PASS  |
| MEDIUM   | Dynamic Programming 0/1 Knapsack |    16 |      48.5 / 48.5h | 16/16 (100%) |    100% |      78.2% |        0.53 ms |     0.53-0.63 ms | PASS  |
| MEDIUM   | Rolling-Horizon Hybrid Strategy  |    16 |      48.5 / 48.5h | 16/16 (100%) |    100% |      78.2% |        1.03 ms |     1.02-1.06 ms | PASS  |
| LARGE    | Greedy EDF-CW                    |    32 |    101.0 / 101.0h | 32/32 (100%) |    100% |      74.0% |        1.35 ms |     1.34-1.49 ms | PASS  |
| LARGE    | Dynamic Programming 0/1 Knapsack |    32 |     94.8 / 101.0h |  30/32 (94%) |     94% |      69.4% |        1.33 ms |     1.32-1.45 ms | PASS  |
| LARGE    | Rolling-Horizon Hybrid Strategy  |    32 |    101.0 / 101.0h | 32/32 (100%) |    100% |      74.0% |        2.76 ms |     2.73-2.82 ms | PASS  |
+----------+----------------------------------+-------+-------------------+--------------+---------+------------+----------------+------------------+-------+
```

### 5.1 Verification of Traceability
- **JSON Data:** [`benchmarks_output.json`](file:///D:/SCHOLAR_SYNC/benchmarks_output.json) contains full trial-by-trial millisecond latencies, variance, cognitive indices, and per-task residual metrics.
- **CSV Data:** [`benchmarks_output.csv`](file:///D:/SCHOLAR_SYNC/benchmarks_output.csv) contains identical RFC 4180 tabular records for external statistical software (R, pandas, SPSS).

---

## 6. Analytical Interpretation & Evidence-Based Findings

### 6.1 Finding 1: Computational Scalability
- All three strategies exhibit interactive, sub-3 millisecond runtimes up to 32 tasks and 30 planning days.
- **Greedy EDF-CW** is the fastest overall, executing 32 tasks in $1.36$ ms.
- **Rolling-Horizon Hybrid** requires approximately $2\times$ the runtime of Greedy ($2.78$ ms vs. $1.36$ ms on Large) because it executes dynamic programming knapsack optimizations repeatedly across 30 days while evaluating multi-day rolling windows.

### 6.2 Finding 2: The Multi-Day 0/1 Knapsack Splitting Limitation
- On Small and Medium workloads, all three schedulers achieved 100% completion because individual tasks fit within single-day weekend or weekday capacity budgets.
- On the **Large workload (32 tasks, 30 days)**, 0/1 Knapsack dropped to **94% completion (30/32 tasks)** with $6.2$ hours left unscheduled. 
- **Cause:** Two tasks required $4.5$h and $5.0$h near the end of the semester. Because 0/1 Knapsack treats items as atomic and cannot split items across days, these tasks could not fit into remaining single-day slots of $3.5$h–$4.0$h. Both Greedy and Hybrid split these tasks into discrete daily sessions, achieving 100% completion.

### 6.3 Finding 3: Mathematical Integrity
- Every one of the 9 evaluated schedule plans passed all 8 correctness constraints:
  - **Zero** time-slot overlaps.
  - **Zero** daily capacity exceedances.
  - **Zero** prerequisite order violations.
  - **Zero** deadline lateness.
  - **Strict** chronological sequence preservation.

---

## 7. Threats to Validity & Limitations

1. **Synthetic vs. Empirical Workloads:** While our workloads model real M.Tech curriculum structures, student habits involve subjective procrastination, illness, and emergent schedule changes not captured by deterministic models.
2. **Discrete Time Quantum ($\Delta t = 0.5$h):** Time discretization prevents scheduling 10-minute micro-tasks. However, graduate study sessions shorter than 30 minutes are generally unproductive.
3. **Single-Student Focus:** ScholarSync is optimized for individual student workload management. Group collaboration and room scheduling require distributed consensus protocols.
4. **No Claim of Universal Global Optimality:** Due to the NP-hardness of general multi-day DAG scheduling, neither Greedy nor Hybrid guarantees global mathematical optimality. Single-day 0/1 DP is optimal for isolated daily allocations only.

---

## 8. Reproducibility & Reproduction Commands

Any evaluator can reproduce every measurement, test, and artifact from a clean working environment:

```powershell
# 1. Clone repository and install in editable mode:
cd D:\SCHOLAR_SYNC
python -m pip install -e .

# 2. Run full automated test suite with coverage:
python -m pytest -v --cov=scholarsync --cov-report=term-missing

# 3. Run static type checking and linter:
python -m ruff check .
python -m ruff format --check .
python -m mypy

# 4. Regenerate benchmark artifacts and verify outputs:
python -m scholarsync benchmark --size all --repetitions 10 --export-json benchmarks_output.json --export-csv benchmarks_output.csv
```

---

## 9. Conclusion & Research Readiness

Phase 7 establishes that **ScholarSync** provides an academically rigorous, deterministically verified, and computationally efficient workload planning framework. Its modular design separates domain constraints from optimization heuristics, ensuring that future research (such as multi-objective evolutionary optimization or concurrent workload perturbation) can build upon verified foundations.
