"""Monitoring, health checks, and cost tracking utilities.

Provides system health verification and API cost monitoring for KruppAI.
Health checks validate database connectivity, API key presence, output
directory writability, and available disk space. Cost tracking aggregates
API usage from the database for budget enforcement.
"""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import date

from kruppai.core.config import Settings
from kruppai.core.database import get_db

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class HealthStatus:
    """Result of a full system health check.

    Attributes:
        database: True if the database is reachable and has the expected schema.
        api_key_configured: True if an Anthropic API key is present in settings.
        output_directory: True if the output directory exists and is writable.
        disk_space_mb: Available disk space in megabytes on the output volume.
        version: Current KruppAI version string.
    """

    database: bool
    api_key_configured: bool
    output_directory: bool
    disk_space_mb: float
    version: str


@dataclass
class CostSummary:
    """Aggregated API cost data for budget monitoring.

    Attributes:
        today_cents: Total API cost today in cents.
        month_cents: Total API cost this calendar month in cents.
        daily_limit_cents: Configured daily cost cap in cents.
        monthly_limit_cents: Configured monthly cost cap in cents.
        by_skill: Mapping of skill name to total cost in cents for the current month.
    """

    today_cents: int
    month_cents: int
    daily_limit_cents: int
    monthly_limit_cents: int
    by_skill: dict[str, int] = field(default_factory=dict)


def check_health(settings: Settings) -> HealthStatus:
    """Run health checks against all system components.

    Tests database connectivity, API key configuration, output directory
    access, and available disk space.

    Args:
        settings: Application settings instance.

    Returns:
        HealthStatus with the result of each check.
    """
    db_ok = _check_database(settings)
    api_ok = _check_api_key(settings)
    output_ok = _check_output_dir(settings)
    disk_mb = _check_disk_space(settings)

    return HealthStatus(
        database=db_ok,
        api_key_configured=api_ok,
        output_directory=output_ok,
        disk_space_mb=disk_mb,
        version=_VERSION,
    )


def get_cost_summary(settings: Settings) -> CostSummary:
    """Get current API cost summary from the database.

    Queries the api_usage table for today's and this month's totals,
    broken down by skill.

    Args:
        settings: Application settings instance.

    Returns:
        CostSummary with aggregated cost data.
    """
    today_str = date.today().isoformat()
    month_prefix = today_str[:7]  # "YYYY-MM"

    today_cents = 0
    month_cents = 0
    by_skill: dict[str, int] = {}

    try:
        with get_db(settings) as conn:
            # Today's total cost
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
                "WHERE created_at >= ? AND success = 1",
                (today_str + "T00:00:00Z",),
            ).fetchone()
            today_cents = row[0] if row else 0

            # Monthly total cost
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
                "WHERE created_at >= ? AND success = 1",
                (month_prefix + "-01T00:00:00Z",),
            ).fetchone()
            month_cents = row[0] if row else 0

            # Cost by skill this month
            rows = conn.execute(
                "SELECT skill_name, COALESCE(SUM(cost_cents), 0) FROM api_usage "
                "WHERE created_at >= ? AND success = 1 "
                "GROUP BY skill_name ORDER BY SUM(cost_cents) DESC",
                (month_prefix + "-01T00:00:00Z",),
            ).fetchall()
            by_skill = {r[0]: r[1] for r in rows}
    except Exception as exc:
        logger.error("Failed to query cost summary: %s", exc)

    return CostSummary(
        today_cents=today_cents,
        month_cents=month_cents,
        daily_limit_cents=settings.daily_cost_limit_cents,
        monthly_limit_cents=settings.monthly_cost_limit_cents,
        by_skill=by_skill,
    )


def _check_database(settings: Settings) -> bool:
    """Verify the database is accessible and has the api_usage table.

    Args:
        settings: Application settings instance.

    Returns:
        True if a basic query succeeds, False otherwise.
    """
    try:
        with get_db(settings) as conn:
            conn.execute("SELECT COUNT(*) FROM api_usage")
        return True
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return False


def _check_api_key(settings: Settings) -> bool:
    """Check whether an Anthropic API key is configured.

    Args:
        settings: Application settings instance.

    Returns:
        True if the key is present and has a plausible format.
    """
    key = settings.anthropic_api_key
    return bool(key and key.startswith("sk-ant-"))


def _check_output_dir(settings: Settings) -> bool:
    """Verify the output directory exists and is writable.

    Args:
        settings: Application settings instance.

    Returns:
        True if the directory is accessible for writing.
    """
    try:
        output_dir = settings.output_dir
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
        # Test writability by checking directory permissions
        return output_dir.is_dir() and output_dir.stat().st_mode & 0o200 != 0
    except OSError as exc:
        logger.warning("Output directory check failed: %s", exc)
        return False


def _check_disk_space(settings: Settings) -> float:
    """Return available disk space in MB on the output directory volume.

    Args:
        settings: Application settings instance.

    Returns:
        Available disk space in megabytes, or 0.0 on error.
    """
    try:
        output_dir = settings.output_dir
        if not output_dir.exists():
            output_dir = output_dir.parent
        usage = shutil.disk_usage(str(output_dir))
        return usage.free / (1024 * 1024)
    except OSError as exc:
        logger.warning("Disk space check failed: %s", exc)
        return 0.0
