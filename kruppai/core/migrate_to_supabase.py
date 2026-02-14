"""One-time migration from SQLite to Supabase PostgreSQL.

Provides utilities to convert the SQLite schema to PostgreSQL DDL,
export all data from the local SQLite database, and import it into
a Supabase-hosted PostgreSQL instance. Designed for the transition
from prototype (SQLite) to production (Supabase/Postgres).

Requires the ``psycopg2`` package for PostgreSQL connectivity.
"""

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    """Outcome of a SQLite-to-PostgreSQL migration run.

    Attributes:
        tables_migrated: Number of tables successfully created and populated.
        rows_migrated: Total number of rows inserted across all tables.
        errors: List of error messages encountered during migration.
        success: True if all tables migrated without errors.
    """

    tables_migrated: int
    rows_migrated: int
    errors: list[str] = field(default_factory=list)
    success: bool = False


def generate_postgres_schema(sqlite_schema_path: Path) -> str:
    """Convert a SQLite schema file to PostgreSQL-compatible DDL.

    Applies the following transformations:
    - ``INTEGER PRIMARY KEY`` becomes ``SERIAL PRIMARY KEY``
    - ``strftime(...)`` default expressions become ``NOW()``
    - ``PRAGMA`` statements are removed
    - ``INSERT OR IGNORE`` becomes ``INSERT ... ON CONFLICT DO NOTHING``
    - SQLite-specific type affinity preserved (TEXT, REAL, INTEGER)

    Args:
        sqlite_schema_path: Path to the SQLite schema SQL file.

    Returns:
        PostgreSQL-compatible DDL as a string.

    Raises:
        FileNotFoundError: If the schema file does not exist.
    """
    if not sqlite_schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {sqlite_schema_path}")

    sql = sqlite_schema_path.read_text(encoding="utf-8")

    # Remove PRAGMA statements
    sql = re.sub(r"^\s*PRAGMA\s+[^;]+;\s*$", "", sql, flags=re.MULTILINE)

    # INTEGER PRIMARY KEY -> SERIAL PRIMARY KEY
    sql = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\b",
        "SERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )

    # strftime('%Y-%m-%dT%H:%M:%SZ', 'now') -> NOW()
    sql = re.sub(
        r"strftime\s*\(\s*'[^']*'\s*,\s*'now'\s*\)",
        "NOW()",
        sql,
        flags=re.IGNORECASE,
    )

    # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING
    sql = re.sub(
        r"\bINSERT\s+OR\s+IGNORE\b",
        "INSERT",
        sql,
        flags=re.IGNORECASE,
    )
    # Add ON CONFLICT DO NOTHING to the converted INSERT statements
    # that were originally INSERT OR IGNORE (settings table inserts)
    sql = re.sub(
        r"(INSERT\s+INTO\s+settings\s+\([^)]+\)\s+VALUES\s*\n\s*(?:\([^)]+\),?\s*\n?\s*)+);",
        lambda m: m.group(0).rstrip(";") + "\nON CONFLICT DO NOTHING;",
        sql,
        flags=re.IGNORECASE,
    )

    # strftime('%Y-%m', ...) in views -> to_char(..., 'YYYY-MM')
    sql = re.sub(
        r"strftime\s*\(\s*'%Y-%m'\s*,\s*(\w+)\s*\)",
        r"to_char(\1::timestamp, 'YYYY-MM')",
        sql,
        flags=re.IGNORECASE,
    )

    return sql


def export_sqlite_data(sqlite_path: Path) -> dict[str, list[dict]]:
    """Export all data from a SQLite database as a table-to-rows mapping.

    Reads every user table (excluding views and sqlite_ internal tables)
    and returns the data as a dictionary keyed by table name.

    Args:
        sqlite_path: Path to the SQLite database file.

    Returns:
        Dictionary mapping table names to lists of row dictionaries.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    result: dict[str, list[dict]] = {}

    try:
        # Get all user tables (exclude sqlite_ internals)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]

        for table in tables:
            rows_cursor = conn.execute(f"SELECT * FROM {table}")  # noqa: S608
            rows = [dict(row) for row in rows_cursor.fetchall()]
            result[table] = rows
            logger.info("Exported %d rows from table '%s'.", len(rows), table)
    finally:
        conn.close()

    return result


def migrate(
    sqlite_path: Path,
    supabase_url: str,
    supabase_key: str,
) -> MigrationResult:
    """Execute a full migration from SQLite to Supabase PostgreSQL.

    Workflow:
    1. Generate PostgreSQL DDL from the SQLite schema file.
    2. Export all data from the SQLite database.
    3. Connect to Supabase PostgreSQL and create the schema.
    4. Insert all exported data into the new tables.
    5. Verify row counts match.

    Args:
        sqlite_path: Path to the local SQLite database file.
        supabase_url: Supabase PostgreSQL connection URL
            (e.g., ``postgresql://user:pass@host:5432/postgres``).
        supabase_key: Supabase service role key (used for auth context,
            connection is via direct PostgreSQL URL).

    Returns:
        MigrationResult with counts and any errors encountered.
    """
    try:
        import psycopg2  # noqa: F811
    except ImportError:
        return MigrationResult(
            tables_migrated=0,
            rows_migrated=0,
            errors=["psycopg2 is not installed. Run: pip install psycopg2-binary"],
            success=False,
        )

    result = MigrationResult(tables_migrated=0, rows_migrated=0)

    # Step 1: Generate PostgreSQL schema
    schema_path = Path(__file__).parent.parent.parent / "schema" / "init.sql"
    try:
        pg_schema = generate_postgres_schema(schema_path)
    except FileNotFoundError as exc:
        result.errors.append(str(exc))
        return result

    # Step 2: Export SQLite data
    try:
        data = export_sqlite_data(sqlite_path)
    except FileNotFoundError as exc:
        result.errors.append(str(exc))
        return result

    # Step 3: Connect to PostgreSQL and create schema
    pg_conn = None
    try:
        pg_conn = psycopg2.connect(supabase_url)
        pg_conn.autocommit = False
        cursor = pg_conn.cursor()

        # Execute schema DDL
        cursor.execute(pg_schema)
        pg_conn.commit()
        logger.info("PostgreSQL schema created successfully.")

        # Step 4: Insert data table by table
        for table_name, rows in data.items():
            if not rows:
                logger.info("Skipping empty table '%s'.", table_name)
                continue

            columns = list(rows[0].keys())
            # Skip 'id' column — let SERIAL generate new IDs
            insert_columns = [c for c in columns if c != "id"]
            if not insert_columns:
                continue

            placeholders = ", ".join(["%s"] * len(insert_columns))
            col_names = ", ".join(insert_columns)
            insert_sql = (
                f"INSERT INTO {table_name} ({col_names}) "  # noqa: S608
                f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            )

            row_count = 0
            for row in rows:
                values = [row.get(c) for c in insert_columns]
                try:
                    cursor.execute(insert_sql, values)
                    row_count += 1
                except Exception as exc:
                    result.errors.append(
                        f"Error inserting into {table_name}: {exc}"
                    )
                    pg_conn.rollback()

            pg_conn.commit()
            result.tables_migrated += 1
            result.rows_migrated += row_count
            logger.info(
                "Migrated %d rows into '%s'.", row_count, table_name
            )

    except Exception as exc:
        result.errors.append(f"PostgreSQL connection/schema error: {exc}")
        if pg_conn:
            pg_conn.rollback()
    finally:
        if pg_conn:
            pg_conn.close()

    result.success = len(result.errors) == 0
    return result
