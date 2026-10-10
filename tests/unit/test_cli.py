"""Unit tests for the ScholarSync command-line interface (CLI).

Tests:
- Top-level help and sub-command help
- demo command across greedy, dp, and hybrid strategies
- plan command with custom files, dates, and export options
- compare command side-by-side benchmarking
- export command for CSV and JSON formats
- Error handling: missing files, invalid dates, unsupported strategies, exit codes
"""

import io
import json
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from scholarsync.cli.main import build_parser, main
from scholarsync.cli.sample_data import get_sample_student_profile, get_sample_tasks
from scholarsync.serialization.json_io import profile_to_json, tasks_to_json

TODAY: Final[date] = date(2026, 10, 10)


class TestCLIParsingAndHelp:
    """Test suite for argument parsing and help output."""

    def test_top_level_help_returns_zero(self) -> None:
        """Invoking CLI without args or with --help displays usage and exits 0."""
        out = io.StringIO()
        err = io.StringIO()

        code_empty = main([], out=out, err=err)
        assert code_empty == 0
        assert "ScholarSync: An Intelligent Academic Workload Planning System" in out.getvalue()
        assert "Available Commands" in out.getvalue()

        out_help = io.StringIO()
        code_help = main(["--help"], out=out_help, err=err)
        assert code_help == 0
        assert "usage: scholarsync" in out_help.getvalue()

    def test_subcommand_help_returns_zero(self) -> None:
        """Subcommand --help displays command specific options and exits 0."""
        for cmd in ("demo", "plan", "compare", "export", "benchmark"):
            with pytest.raises(SystemExit) as exc_info:
                build_parser().parse_args([cmd, "--help"])
            assert exc_info.value.code == 0


class TestCLIDemoCommand:
    """Test suite for scholarsync demo."""

    @pytest.mark.parametrize("strategy", ["greedy", "dp", "hybrid"])
    def test_demo_executes_successfully(self, strategy: str) -> None:
        """Demo runs deterministically with all supported strategies."""
        out = io.StringIO()
        err = io.StringIO()
        code = main(
            ["demo", "--strategy", strategy, "--start-date", "2026-10-10", "--horizon", "7"],
            out=out,
            err=err,
        )
        assert code == 0
        output = out.getvalue()
        assert "Demonstration Mode" in output
        assert "QUANTITATIVE METRICS EVALUATION" in output
        assert "Total Scheduled Study Hours" in output
        assert err.getvalue() == ""

    def test_demo_with_export_creates_file(self, tmp_path: Path) -> None:
        """Demo --export writes formatted schedule to disk."""
        target_file = tmp_path / "demo_schedule.csv"
        out = io.StringIO()
        err = io.StringIO()

        code = main(
            ["demo", "--export", str(target_file), "--start-date", "2026-10-10"],
            out=out,
            err=err,
        )
        assert code == 0
        assert target_file.is_file()
        assert "Successfully exported" in out.getvalue()
        content = target_file.read_text(encoding="utf-8")
        assert "session_id,date,day_of_week" in content


class TestCLIPlanCommand:
    """Test suite for scholarsync plan."""

    def test_plan_with_defaults(self) -> None:
        """Plan command runs cleanly with default sample data."""
        out = io.StringIO()
        err = io.StringIO()
        code = main(["plan", "--strategy", "greedy", "--horizon", "10"], out=out, err=err)
        assert code == 0
        assert "Strategy: Greedy EDF-CW" in out.getvalue()
        assert "SCHEDULE METRICS EVALUATION" in out.getvalue()

    def test_plan_with_custom_files(self, tmp_path: Path) -> None:
        """Plan command ingests custom task and profile JSON files."""
        tasks = get_sample_tasks(TODAY)
        profile = get_sample_student_profile()

        tasks_file = tmp_path / "custom_tasks.json"
        profile_file = tmp_path / "custom_profile.json"
        export_file = tmp_path / "output_plan.json"

        tasks_file.write_text(tasks_to_json(tasks), encoding="utf-8")
        profile_file.write_text(profile_to_json(profile), encoding="utf-8")

        out = io.StringIO()
        err = io.StringIO()
        code = main(
            [
                "plan",
                "--tasks",
                str(tasks_file),
                "--profile",
                str(profile_file),
                "--strategy",
                "hybrid",
                "--start-date",
                "2026-10-10",
                "--export",
                str(export_file),
            ],
            out=out,
            err=err,
        )
        assert code == 0
        assert "custom_tasks.json" in out.getvalue()
        assert export_file.is_file()
        data = json.loads(export_file.read_text(encoding="utf-8"))
        assert data["metadata"]["strategy"] == "Rolling-Horizon Hybrid Strategy"


class TestCLICompareCommand:
    """Test suite for scholarsync compare."""

    def test_compare_runs_all_strategies(self) -> None:
        """Compare command benches all 3 algorithms and prints side-by-side table."""
        out = io.StringIO()
        err = io.StringIO()
        code = main(
            ["compare", "--start-date", "2026-10-10", "--horizon", "14"],
            out=out,
            err=err,
        )
        assert code == 0
        output = out.getvalue()
        assert "Greedy EDF-CW" in output
        assert "Dynamic Programming 0/1 Knapsack" in output
        assert "Rolling-Horizon Hybrid Strategy" in output
        assert "Key Observations:" in output


class TestCLIExportCommand:
    """Test suite for scholarsync export."""

    def test_export_to_csv_and_json(self, tmp_path: Path) -> None:
        """Export command writes valid CSV and JSON outputs."""
        csv_target = tmp_path / "exported.csv"
        json_target = tmp_path / "exported.json"

        out_csv = io.StringIO()
        code_csv = main(["export", "--output", str(csv_target)], out=out_csv, err=io.StringIO())
        assert code_csv == 0
        assert csv_target.is_file()

        out_json = io.StringIO()
        code_json = main(["export", "--output", str(json_target)], out=out_json, err=io.StringIO())
        assert code_json == 0
        assert json_target.is_file()

    def test_export_unsupported_format_fails(self, tmp_path: Path) -> None:
        """Export with unknown file extension and no --format raises error with exit code 1."""
        bad_target = tmp_path / "schedule.xml"
        out = io.StringIO()
        err = io.StringIO()

        code = main(["export", "--output", str(bad_target)], out=out, err=err)
        assert code == 1
        assert "Unsupported export format" in err.getvalue()


class TestCLIErrorHandling:
    """Test suite for CLI error handling and non-zero exit codes."""

    def test_invalid_strategy_fails_cleanly(self) -> None:
        """Invalid strategy option yields non-zero exit code."""
        with pytest.raises(SystemExit) as exc_info:
            build_parser().parse_args(["plan", "--strategy", "quantum_scheduler"])
        assert exc_info.value.code != 0

    def test_invalid_date_format_fails_with_exit_code_1(self) -> None:
        """Invalid date string prints helpful error and exits with 1."""
        out = io.StringIO()
        err = io.StringIO()
        code = main(["plan", "--start-date", "10-10-2026"], out=out, err=err)
        assert code == 1
        assert "Invalid date format" in err.getvalue()

    def test_missing_tasks_file_fails_with_exit_code_1(self) -> None:
        """Non-existent tasks file prints helpful error and exits with 1."""
        out = io.StringIO()
        err = io.StringIO()
        code = main(["plan", "--tasks", "non_existent_tasks.json"], out=out, err=err)
        assert code == 1
        assert "Tasks file not found" in err.getvalue()

    def test_missing_profile_file_fails_with_exit_code_1(self) -> None:
        """Non-existent profile file prints helpful error and exits with 1."""
        out = io.StringIO()
        err = io.StringIO()
        code = main(["plan", "--profile", "non_existent_profile.json"], out=out, err=err)
        assert code == 1
        assert "Profile file not found" in err.getvalue()

    def test_malformed_tasks_json_fails_with_exit_code_1(self, tmp_path: Path) -> None:
        """Malformed tasks JSON file triggers ValidationError and exits with 1."""
        broken = tmp_path / "broken.json"
        broken.write_text("{broken", encoding="utf-8")

        out = io.StringIO()
        err = io.StringIO()
        code = main(["plan", "--tasks", str(broken)], out=out, err=err)
        assert code == 1
        assert "Failed to load tasks" in err.getvalue()


class TestCLIBenchmarkCommand:
    """Test suite for scholarsync benchmark command."""

    def test_benchmark_runs_small_workload(self) -> None:
        """Benchmark runs successfully on small scenario with repetitions=2."""
        out = io.StringIO()
        err = io.StringIO()
        code = main(
            ["benchmark", "--size", "small", "--repetitions", "2"],
            out=out,
            err=err,
        )
        assert code == 0
        output = out.getvalue()
        assert "Reproducible Experimental Benchmark Suite" in output
        assert "SMALL" in output
        assert "Greedy EDF-CW" in output
        assert "Dynamic Programming 0/1 Knapsack" in output
        assert "Rolling-Horizon Hybrid Strategy" in output

    def test_benchmark_export_json_and_csv(self, tmp_path: Path) -> None:
        """Benchmark command exports machine-readable JSON and CSV files."""
        json_file = tmp_path / "bench.json"
        csv_file = tmp_path / "bench.csv"
        out = io.StringIO()
        err = io.StringIO()
        code = main(
            [
                "benchmark",
                "--size",
                "small",
                "--repetitions",
                "2",
                "--export-json",
                str(json_file),
                "--export-csv",
                str(csv_file),
            ],
            out=out,
            err=err,
        )
        assert code == 0
        assert json_file.is_file()
        assert csv_file.is_file()
        assert "Exported JSON results" in out.getvalue()
        assert "Exported CSV results" in out.getvalue()
        assert json_file.stat().st_size > 0
        assert csv_file.stat().st_size > 0
