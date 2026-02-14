"""Tests for kruppai.cli.main — Click CLI entry point."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from kruppai.cli.main import cli
from kruppai.core.config import Settings
from kruppai.core.database import init_db


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_settings(tmp_path: Path) -> Settings:
    """Settings for CLI tests."""
    settings = Settings(
        db_path=tmp_path / "cli_test.db",
        output_dir=tmp_path / "output",
        _env_file=None,
    )
    return settings


class TestCLI:
    def test_cli_help(self, runner: CliRunner) -> None:
        """kruppai --help exits 0, shows command list."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Construction AI Toolkit" in result.output
        assert "init" in result.output
        assert "project" in result.output
        assert "status" in result.output

    def test_version(self, runner: CliRunner) -> None:
        """kruppai --version shows version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_init_command(
        self, runner: CliRunner, cli_settings: Settings
    ) -> None:
        """kruppai init creates database and directories."""
        with patch("kruppai.cli.main._get_settings", return_value=cli_settings):
            result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "ready" in result.output.lower()
        assert cli_settings.db_path.exists()

    def test_project_list_empty(
        self, runner: CliRunner, cli_settings: Settings
    ) -> None:
        """Shows 'No projects found' message."""
        init_db(cli_settings)
        with patch("kruppai.cli.main._get_settings", return_value=cli_settings):
            result = runner.invoke(cli, ["project", "list"])
        assert result.exit_code == 0
        assert "no projects" in result.output.lower()

    def test_project_add(
        self, runner: CliRunner, cli_settings: Settings
    ) -> None:
        """Interactive add creates project in DB."""
        init_db(cli_settings)
        with patch("kruppai.cli.main._get_settings", return_value=cli_settings):
            result = runner.invoke(
                cli,
                [
                    "project", "add",
                    "--code", "KRUPP-2026-001",
                    "--name", "Test Project",
                    "--client", "Test Client",
                    "--type", "commercial",
                ],
            )
        assert result.exit_code == 0
        assert "created" in result.output.lower()

    def test_project_add_then_list(
        self, runner: CliRunner, cli_settings: Settings
    ) -> None:
        """Added project appears in list."""
        init_db(cli_settings)
        with patch("kruppai.cli.main._get_settings", return_value=cli_settings):
            runner.invoke(
                cli,
                [
                    "project", "add",
                    "--code", "KRUPP-2026-001",
                    "--name", "Test Project",
                    "--client", "Test Client",
                    "--type", "commercial",
                ],
            )
            result = runner.invoke(cli, ["project", "list"])
        assert "KRUPP-2026-001" in result.output
        assert "Test Project" in result.output

    def test_status_shows_usage(
        self, runner: CliRunner, cli_settings: Settings
    ) -> None:
        """Displays API cost summary."""
        init_db(cli_settings)
        with patch("kruppai.cli.main._get_settings", return_value=cli_settings):
            result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "cost" in result.output.lower() or "usage" in result.output.lower()

    def test_project_help(self, runner: CliRunner) -> None:
        """project --help shows subcommands."""
        result = runner.invoke(cli, ["project", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "add" in result.output


class TestPhase1CLIHelp:
    """All 6 Phase 1 skill commands show help text."""

    def test_daily_report_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["daily-report", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--notes" in result.output
        assert "--date" in result.output

    def test_daily_report_missing_args(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["daily-report"])
        assert result.exit_code != 0
        assert "missing" in result.output.lower() or "required" in result.output.lower()

    def test_rfi_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["rfi", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--issue" in result.output
        assert "--priority" in result.output

    def test_rfi_missing_args(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["rfi"])
        assert result.exit_code != 0

    def test_minutes_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["minutes", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--type" in result.output
        assert "--notes" in result.output

    def test_minutes_missing_args(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["minutes"])
        assert result.exit_code != 0

    def test_client_update_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["client-update", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--notes" in result.output
        assert "--period" in result.output

    def test_client_update_missing_args(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["client-update"])
        assert result.exit_code != 0

    def test_safety_talk_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["safety-talk", "--help"])
        assert result.exit_code == 0
        assert "--topic" in result.output
        assert "--project" in result.output
        assert "--season" in result.output

    def test_safety_talk_missing_args(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["safety-talk"])
        assert result.exit_code != 0

    def test_punch_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["punch-list", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--notes" in result.output
        assert "--area" in result.output

    def test_punch_list_missing_args(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["punch-list"])
        assert result.exit_code != 0

    def test_all_commands_in_help(self, runner: CliRunner) -> None:
        """All 6 skill commands appear in main help."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "daily-report" in result.output
        assert "rfi" in result.output
        assert "minutes" in result.output
        assert "client-update" in result.output
        assert "safety-talk" in result.output
        assert "punch-list" in result.output
