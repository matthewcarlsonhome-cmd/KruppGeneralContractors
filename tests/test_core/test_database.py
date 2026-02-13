"""Tests for kruppai.core.database."""

import sqlite3

import pytest

from kruppai.core.config import Settings
from kruppai.core.database import get_db, get_next_number, init_db


class TestDatabase:
    def test_init_creates_all_tables(self, test_db: Settings) -> None:
        """After init, every table from schema exists."""
        expected_tables = {
            "company", "team_members", "projects", "project_team",
            "subcontractors", "project_subcontractors",
            "daily_reports", "rfis", "meetings", "action_items",
            "safety_talks", "punch_lists", "punch_items",
            "estimate_reviews", "bid_comparisons", "change_orders",
            "schedule_snapshots", "submittals", "contract_reviews",
            "proposals", "budget_forecasts", "closeout_packages",
            "lessons_learned", "case_studies", "incident_reports",
            "cost_history", "api_usage", "generated_documents",
            "settings",
        }
        with get_db(test_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            actual_tables = {row["name"] for row in cursor.fetchall()}

        assert expected_tables.issubset(actual_tables), (
            f"Missing tables: {expected_tables - actual_tables}"
        )

    def test_foreign_keys_enforced(self, test_db: Settings) -> None:
        """Inserting a record with bad FK raises IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            with get_db(test_db) as conn:
                conn.execute(
                    "INSERT INTO daily_reports (project_id, report_date, raw_notes) "
                    "VALUES (99999, '2026-02-13', 'test')"
                )

    def test_get_next_number(self, seeded_db: Settings) -> None:
        """Returns 1 for first, 2 for second, handles multiple projects."""
        with get_db(seeded_db) as conn:
            # First RFI on project 1
            num1 = get_next_number(conn, "rfis", 1, "rfi_number")
            assert num1 == 1

            # Insert an RFI
            conn.execute(
                "INSERT INTO rfis (project_id, rfi_number, subject, question) "
                "VALUES (1, 1, 'Test RFI', 'Test question')"
            )

            # Second should be 2
            num2 = get_next_number(conn, "rfis", 1, "rfi_number")
            assert num2 == 2

    def test_context_manager_commits(self, test_db: Settings) -> None:
        """Successful block commits data."""
        with get_db(test_db) as conn:
            conn.execute(
                "INSERT INTO company (name) VALUES (?)",
                ("Test Company",),
            )

        # Verify it persisted
        with get_db(test_db) as conn:
            cursor = conn.execute("SELECT name FROM company")
            row = cursor.fetchone()
            assert row["name"] == "Test Company"

    def test_context_manager_rollback(self, test_db: Settings) -> None:
        """Exception block rolls back."""
        try:
            with get_db(test_db) as conn:
                conn.execute(
                    "INSERT INTO company (name) VALUES (?)",
                    ("Should Not Persist",),
                )
                raise ValueError("Simulated error")
        except ValueError:
            pass

        with get_db(test_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM company")
            assert cursor.fetchone()[0] == 0

    def test_idempotent_init(self, tmp_settings: Settings) -> None:
        """Calling init_db twice doesn't error."""
        init_db(tmp_settings)
        init_db(tmp_settings)  # Should not raise

    def test_get_next_number_invalid_table(self, test_db: Settings) -> None:
        """Invalid table name raises ValueError."""
        with get_db(test_db) as conn:
            with pytest.raises(ValueError, match="not in allowed tables"):
                get_next_number(conn, "users", 1, "rfi_number")

    def test_get_next_number_invalid_column(self, test_db: Settings) -> None:
        """Invalid column name raises ValueError."""
        with get_db(test_db) as conn:
            with pytest.raises(ValueError, match="not in allowed columns"):
                get_next_number(conn, "rfis", 1, "bad_column")

    def test_default_settings_inserted(self, test_db: Settings) -> None:
        """Default settings are inserted during init."""
        with get_db(test_db) as conn:
            cursor = conn.execute(
                "SELECT value FROM settings WHERE key = 'default_model'"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["value"] == "claude-sonnet-4-5-20250929"
