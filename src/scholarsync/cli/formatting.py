"""Terminal formatting utilities for ScholarSync CLI.

Renders clean, human-readable terminal tables, agenda timelines, and metrics
summaries using pure Python standard library string utilities without external dependencies.
"""

from collections.abc import Sequence

from scholarsync.algorithms.metrics import ScheduleMetrics
from scholarsync.models.schedule import ScheduleResult
from scholarsync.pipelines.generators import DailyAgenda


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    alignments: Sequence[str] | None = None,
) -> str:
    """Render a text table with aligned columns and clean separator borders.

    Args:
        headers: Column header strings.
        rows: Rows of string values matching header count.
        alignments: List of 'left' or 'right' alignments (defaults to 'left').

    Returns:
        Formatted multi-line table string.
    """
    col_count = len(headers)
    if alignments is None:
        alignments = ["left"] * col_count

    # Compute maximum width per column
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx in range(min(col_count, len(row))):
            col_widths[idx] = max(col_widths[idx], len(str(row[idx])))

    # Format helpers
    def pad(text: str, width: int, align: str) -> str:
        return text.rjust(width) if align == "right" else text.ljust(width)

    # Build border line
    sep_line = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    # Build header row
    header_cells = [pad(h, col_widths[i], alignments[i]) for i, h in enumerate(headers)]
    header_str = "| " + " | ".join(header_cells) + " |"

    # Build data rows
    data_lines = []
    for row in rows:
        cells = []
        for i in range(col_count):
            val = str(row[i]) if i < len(row) else ""
            cells.append(pad(val, col_widths[i], alignments[i]))
        data_lines.append("| " + " | ".join(cells) + " |")

    parts = [sep_line, header_str, sep_line]
    parts.extend(data_lines)
    parts.append(sep_line)
    return "\n".join(parts)


def format_agenda_view(
    result: ScheduleResult,
    include_empty_days: bool = False,
) -> str:
    """Format daily schedule overview into a chronological readable timeline."""
    lines: list[str] = [
        f"Schedule Planning Horizon: {result.start_date} to {result.end_date} "
        f"({result.strategy_name})",
        "=" * 80,
    ]

    agendas: list[DailyAgenda] = list(result.stream_agendas(include_empty_days=include_empty_days))
    if not agendas:
        lines.append("No active study sessions scheduled in this time horizon.")
        return "\n".join(lines)

    for agenda in agendas:
        if agenda.is_rest_day:
            lines.append(f"\n[{agenda.date} {agenda.weekday}] Rest Day (0.0h)")
            continue

        lines.append(
            f"\n[{agenda.date} {agenda.weekday}] Total: {agenda.total_hours:.1f}h "
            f"({len(agenda.sessions)} session{'s' if len(agenda.sessions) > 1 else ''})"
        )
        for s in agenda.sessions:
            time_range = s.slot.format_time_range()
            final_tag = " [COMPLETED]" if s.is_completed_here else ""
            lines.append(
                f"   * {time_range:>13} | [{s.subject_code}] {s.task_title} "
                f"({s.hours:.1f}h){final_tag}"
            )

    return "\n".join(lines)


def format_metrics_summary(metrics: ScheduleMetrics) -> str:
    """Render a quantitative metrics evaluation table."""
    headers = ["Academic Performance Metric", "Value"]
    rows = [
        ["Total Tasks Considered", str(metrics.total_tasks)],
        ["Fully Completed Tasks", f"{metrics.completed_tasks} / {metrics.total_tasks}"],
        ["Task Completion Rate", f"{metrics.completion_rate * 100.0:.1f}%"],
        ["On-Time Completed Tasks", f"{metrics.on_time_tasks} / {metrics.total_tasks}"],
        ["On-Time Completion Rate", f"{metrics.on_time_rate * 100.0:.1f}%"],
        ["Total Scheduled Study Hours", f"{metrics.total_scheduled_hours:.2f} hrs"],
        ["Total Student Available Hours", f"{metrics.total_available_hours:.2f} hrs"],
        ["Capacity Utilization", f"{metrics.capacity_utilization * 100.0:.1f}%"],
        ["Workload Balance (Daily Mean)", f"{metrics.mean_daily_hours:.2f} hrs/day"],
        ["Workload Balance (Daily StdDev)", f"+/- {metrics.std_daily_hours:.2f} hrs/day"],
        ["High-Difficulty Study Hours (Diff >= 4)", f"{metrics.high_difficulty_hours:.2f} hrs"],
        ["Cognitive Load Index", f"{metrics.cognitive_load_index:.2f}"],
    ]
    alignments = ["left", "right"]
    return render_table(headers, rows, alignments)


def format_comparison_table(
    benchmarks: Sequence[tuple[str, ScheduleMetrics, float]],
) -> str:
    """Render a comparative table contrasting multiple scheduling algorithms side-by-side."""
    headers = [
        "Scheduling Algorithm",
        "Hours",
        "Completed",
        "On-Time",
        "Capacity %",
        "Daily Mean",
        "Daily StdDev",
        "Cognitive Index",
        "Latency",
    ]
    rows = []
    for strat_name, m, latency_ms in benchmarks:
        rows.append(
            [
                strat_name,
                f"{m.total_scheduled_hours:.1f}h",
                f"{m.completed_tasks}/{m.total_tasks} ({m.completion_rate * 100.0:.0f}%)",
                f"{m.on_time_rate * 100.0:.0f}%",
                f"{m.capacity_utilization * 100.0:.1f}%",
                f"{m.mean_daily_hours:.2f}h",
                f"{m.std_daily_hours:.2f}h",
                f"{m.cognitive_load_index:.1f}",
                f"{latency_ms:.2f} ms",
            ]
        )

    alignments = ["left", "right", "right", "right", "right", "right", "right", "right", "right"]
    return render_table(headers, rows, alignments)
