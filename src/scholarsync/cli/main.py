"""Command-line interface entry point for ScholarSync.

Provides argument parsing, sub-command dispatch, and formatted error reporting.
"""

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from scholarsync.cli.commands import (
    handle_benchmark,
    handle_compare,
    handle_demo,
    handle_export,
    handle_plan,
)
from scholarsync.core.exceptions import ScholarSyncError


def build_parser() -> argparse.ArgumentParser:
    """Build and configure the top-level CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="scholarsync",
        description="ScholarSync: An Intelligent Academic Workload Planning System",
        epilog=(
            "Examples:\n"
            "  scholarsync demo\n"
            "  scholarsync demo --strategy greedy\n"
            "  scholarsync plan --strategy hybrid --horizon 14\n"
            "  scholarsync compare\n"
            "  scholarsync export --output my_schedule.csv\n"
            "  scholarsync benchmark --size all --repetitions 5\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        title="Available Commands",
        description="Run 'scholarsync <command> --help' for command-specific options.",
    )

    # 1. demo command
    demo_p = subparsers.add_parser(
        "demo",
        help="Run a deterministic demonstration on sample M.Tech coursework",
        description="Executes a self-contained schedule generation demo using sample M.Tech data.",
    )
    demo_p.add_argument(
        "--strategy",
        choices=["greedy", "dp", "hybrid"],
        default="hybrid",
        help="Scheduling algorithm to execute (default: hybrid)",
    )
    demo_p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Calendar start date (YYYY-MM-DD, defaults to today)",
    )
    demo_p.add_argument(
        "--horizon",
        type=int,
        default=14,
        help="Planning horizon in days (default: 14)",
    )
    demo_p.add_argument(
        "--include-rest-days",
        action="store_true",
        help="Include zero-hour rest days in timeline output",
    )
    demo_p.add_argument(
        "--export",
        type=str,
        default=None,
        help="Export schedule to destination filepath (.json or .csv)",
    )
    demo_p.add_argument(
        "--format",
        choices=["json", "csv"],
        default=None,
        help="Explicitly override export format",
    )

    # 2. plan command
    plan_p = subparsers.add_parser(
        "plan",
        help="Generate a study schedule for custom or sample academic tasks",
        description="Generates an optimized schedule using the selected strategy.",
    )
    plan_p.add_argument(
        "--strategy",
        choices=["greedy", "dp", "hybrid"],
        default="hybrid",
        help="Scheduling algorithm to execute (default: hybrid)",
    )
    plan_p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Calendar start date (YYYY-MM-DD, defaults to today)",
    )
    plan_p.add_argument(
        "--horizon",
        type=int,
        default=14,
        help="Planning horizon in days (default: 14)",
    )
    plan_p.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Path to tasks JSON file (defaults to sample M.Tech tasks if omitted)",
    )
    plan_p.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Path to student profile JSON file (defaults to sample profile if omitted)",
    )
    plan_p.add_argument(
        "--include-rest-days",
        action="store_true",
        help="Include zero-hour rest days in timeline output",
    )
    plan_p.add_argument(
        "--export",
        type=str,
        default=None,
        help="Export schedule to destination filepath (.json or .csv)",
    )
    plan_p.add_argument(
        "--format",
        choices=["json", "csv"],
        default=None,
        help="Explicitly override export format",
    )

    # 3. compare command
    compare_p = subparsers.add_parser(
        "compare",
        help="Compare Greedy, DP, and Hybrid strategies on identical workload",
        description=(
            "Benchmarks all 3 scheduling algorithms side-by-side with latency and utility metrics."
        ),
    )
    compare_p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Calendar start date (YYYY-MM-DD, defaults to today)",
    )
    compare_p.add_argument(
        "--horizon",
        type=int,
        default=14,
        help="Planning horizon in days (default: 14)",
    )
    compare_p.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Path to tasks JSON file (defaults to sample M.Tech tasks if omitted)",
    )
    compare_p.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Path to student profile JSON file (defaults to sample profile if omitted)",
    )

    # 4. export command
    export_p = subparsers.add_parser(
        "export",
        help="Export a schedule plan directly to CSV or JSON",
        description="Generates and exports an academic study schedule to disk.",
    )
    export_p.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Target destination file path (e.g. schedule.csv or plan.json)",
    )
    export_p.add_argument(
        "--format",
        choices=["json", "csv"],
        default=None,
        help="Explicit export format (inferred from file extension if omitted)",
    )
    export_p.add_argument(
        "--strategy",
        choices=["greedy", "dp", "hybrid"],
        default="hybrid",
        help="Scheduling algorithm to use (default: hybrid)",
    )
    export_p.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Calendar start date (YYYY-MM-DD, defaults to today)",
    )
    export_p.add_argument(
        "--horizon",
        type=int,
        default=14,
        help="Planning horizon in days (default: 14)",
    )
    export_p.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Path to tasks JSON file (defaults to sample tasks if omitted)",
    )
    export_p.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Path to student profile JSON file (defaults to sample profile if omitted)",
    )

    # 5. benchmark command
    benchmark_p = subparsers.add_parser(
        "benchmark",
        help="Run reproducible benchmarks across workload sizes and algorithms",
        description=(
            "Executes empirical evaluation of Greedy, DP, and Hybrid schedulers across "
            "standardized workloads with repeated timing trials."
        ),
    )
    benchmark_p.add_argument(
        "--size",
        choices=["small", "medium", "large", "all"],
        default="all",
        help="Benchmark workload scenario to evaluate (default: all)",
    )
    benchmark_p.add_argument(
        "--repetitions",
        type=int,
        default=5,
        help="Number of timed execution trials per algorithm (default: 5)",
    )
    benchmark_p.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="Export empirical benchmark results to JSON file",
    )
    benchmark_p.add_argument(
        "--export-csv",
        type=str,
        default=None,
        help="Export empirical benchmark results to CSV file",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    """Primary CLI entry point. Parses arguments and executes the appropriate command.

    Args:
        argv: Command-line arguments sequence (defaults to sys.argv[1:]).
        out: Text output stream for normal results (defaults to sys.stdout).
        err: Text error stream for diagnostic messages (defaults to sys.stderr).

    Returns:
        Integer exit code (0 for success, non-zero for failures).
    """
    parser = build_parser()
    if argv and len(argv) == 1 and argv[0] in ("-h", "--help"):
        parser.print_help(out)
        return 0

    try:
        args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    if not args.command:
        parser.print_help(out)
        return 0

    try:
        if args.command == "demo":
            return handle_demo(args, out=out)
        elif args.command == "plan":
            return handle_plan(args, out=out)
        elif args.command == "compare":
            return handle_compare(args, out=out)
        elif args.command == "export":
            return handle_export(args, out=out)
        elif args.command == "benchmark":
            return handle_benchmark(args, out=out)
        else:
            err.write(f"Error: Unknown command '{args.command}'.\n")
            parser.print_help(err)
            return 2
    except ScholarSyncError as exc:
        err.write(f"\n[ScholarSync Error] {exc}\n")
        return 1
    except (ValueError, FileNotFoundError, PermissionError) as exc:
        err.write(f"\n[System Error] {exc}\n")
        return 1
    except Exception as exc:
        err.write(f"\n[Unexpected Error] {type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
