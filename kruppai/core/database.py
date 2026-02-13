"""Database connection manager for SQLite (prototype) and future PostgreSQL.

Key behaviors:
- Auto-creates database file and runs schema on first access
- Foreign keys always enforced
- All connections use context manager pattern
- get_next_number() provides auto-incrementing per project per entity type
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from kruppai.core.config import Settings

# Path to schema file relative to this module
_SCHEMA_PATH = Path(__file__).parent.parent.parent / "schema" / "init.sql"


class ProjectNotFoundError(Exception):
    """Raised when a project lookup fails."""


def init_db(settings: Settings) -> None:
    """Create the database and run the schema if needed."""
    settings.ensure_directories()
    conn = sqlite3.connect(str(settings.db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db(settings: Settings) -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection with foreign keys enforced.

    Commits on successful exit, rolls back on exception.
    """
    conn = sqlite3.connect(
        str(settings.db_path),
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_next_number(
    conn: sqlite3.Connection,
    table: str,
    project_id: int,
    number_column: str,
) -> int:
    """Return the next auto-incrementing number for a project.

    Args:
        conn: Active database connection.
        table: Table name (e.g., 'rfis', 'change_orders').
        number_column: Column holding the sequence number (e.g., 'rfi_number').
        project_id: Project to scope the sequence.

    Returns:
        Next sequential number (1-based).
    """
    # Use parameterized column/table via string formatting for identifiers only,
    # but project_id is parameterized to prevent injection.
    allowed_tables = {
        "rfis",
        "change_orders",
        "daily_reports",
        "meetings",
        "incident_reports",
    }
    if table not in allowed_tables:
        raise ValueError(f"Table '{table}' not in allowed tables: {allowed_tables}")

    allowed_columns = {
        "rfi_number",
        "co_number",
        "report_number",
        "meeting_number",
        "incident_number",
    }
    if number_column not in allowed_columns:
        raise ValueError(
            f"Column '{number_column}' not in allowed columns: {allowed_columns}"
        )

    query = (
        f"SELECT COALESCE(MAX({number_column}), 0) + 1 "
        f"FROM {table} WHERE project_id = ?"
    )
    cursor = conn.execute(query, (project_id,))
    row = cursor.fetchone()
    return row[0]
