"""Anthropic API client with retry logic, cost tracking, and usage limits.

Pricing (as of Feb 2026):
- claude-sonnet-4-5-20250929: $3/M input, $15/M output
- claude-opus-4-6: $15/M input, $75/M output
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from kruppai.core.config import Settings

# Model pricing in cents per million tokens
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-5-20250929": {"input": 300, "output": 1500},
    "claude-opus-4-6": {"input": 1500, "output": 7500},
}

# Skills that require the Opus model
OPUS_SKILLS: set[str] = {"contract_checker", "proposal_generator", "estimate_reviewer"}


class CostLimitExceeded(Exception):
    """Raised when daily or monthly API cost limit is exceeded."""


@dataclass
class ApiResponse:
    """Result from a Claude API call."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_cents: int
    duration_ms: int


def calculate_cost_cents(
    model: str, input_tokens: int, output_tokens: int
) -> int:
    """Calculate cost in cents for a given model and token counts."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        # Default to Sonnet pricing for unknown models
        pricing = MODEL_PRICING["claude-sonnet-4-5-20250929"]
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost)


def get_model_for_skill(skill_name: str, settings: Settings) -> str:
    """Return the appropriate model for a given skill."""
    if skill_name in OPUS_SKILLS:
        return settings.opus_model
    return settings.default_model


def _check_cost_limits(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    """Raise CostLimitExceeded if daily or monthly limits are exceeded."""
    today = date.today().isoformat()
    month = today[:7]  # "YYYY-MM"

    cursor = conn.execute(
        "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
        "WHERE created_at >= ? AND success = 1",
        (today,),
    )
    daily_total = cursor.fetchone()[0]
    if daily_total >= settings.daily_cost_limit_cents:
        raise CostLimitExceeded(
            f"Daily API cost limit reached: "
            f"${daily_total / 100:.2f} / ${settings.daily_cost_limit_cents / 100:.2f}"
        )

    cursor = conn.execute(
        "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
        "WHERE created_at >= ? AND success = 1",
        (month + "-01",),
    )
    monthly_total = cursor.fetchone()[0]
    if monthly_total >= settings.monthly_cost_limit_cents:
        raise CostLimitExceeded(
            f"Monthly API cost limit reached: "
            f"${monthly_total / 100:.2f} / "
            f"${settings.monthly_cost_limit_cents / 100:.2f}"
        )


def _log_usage(
    conn: sqlite3.Connection,
    skill_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_cents: int,
    duration_ms: int,
    success: bool,
    error_message: str | None,
    project_id: int | None,
) -> int:
    """Log API usage to database. Returns the api_usage row id."""
    cursor = conn.execute(
        "INSERT INTO api_usage "
        "(skill_name, model, input_tokens, output_tokens, total_tokens, "
        "cost_cents, duration_ms, success, error_message, project_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            skill_name,
            model,
            input_tokens,
            output_tokens,
            input_tokens + output_tokens,
            cost_cents,
            duration_ms,
            1 if success else 0,
            error_message,
            project_id,
        ),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def parse_claude_json(text: str) -> dict | list:
    """Parse JSON from Claude's response, handling common quirks.

    Handles:
    - ```json ... ``` code fences
    - Trailing commas
    - Leading/trailing whitespace
    """
    cleaned = text.strip()
    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return json.loads(cleaned)


class AnthropicClient:
    """Wrapper around the Anthropic Python SDK."""

    def __init__(
        self,
        settings: Settings,
        db_conn_factory: Callable | None = None,
    ) -> None:
        self.settings = settings
        self._db_conn_factory = db_conn_factory
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key
            )
        return self._client

    def call(
        self,
        messages: list[dict],
        skill_name: str,
        project_id: int | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        system: str | None = None,
    ) -> ApiResponse:
        """Call the Claude API with retry logic and cost tracking.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            skill_name: Skill making the call (for logging and model routing).
            project_id: Optional project ID for usage tracking.
            model: Override model selection (otherwise auto-routed by skill).
            max_tokens: Maximum output tokens.
            system: Optional system prompt.

        Returns:
            ApiResponse with content, tokens, cost, and duration.

        Raises:
            CostLimitExceeded: If daily/monthly limits are exceeded.
        """
        if model is None:
            model = get_model_for_skill(skill_name, self.settings)

        # Check cost limits if we have DB access
        if self._db_conn_factory:
            with self._db_conn_factory() as conn:
                _check_cost_limits(conn, self.settings)

        client = self._get_client()
        max_retries = 3
        backoff_seconds = [2, 4, 8]

        last_error: Exception | None = None
        start_ms = int(time.time() * 1000)

        for attempt in range(max_retries):
            try:
                kwargs: dict = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                }
                if system:
                    kwargs["system"] = system

                response = client.messages.create(**kwargs)

                duration_ms = int(time.time() * 1000) - start_ms
                content = response.content[0].text if response.content else ""
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cost_cents = calculate_cost_cents(model, input_tokens, output_tokens)

                # Log success
                if self._db_conn_factory:
                    with self._db_conn_factory() as conn:
                        _log_usage(
                            conn,
                            skill_name,
                            model,
                            input_tokens,
                            output_tokens,
                            cost_cents,
                            duration_ms,
                            success=True,
                            error_message=None,
                            project_id=project_id,
                        )

                return ApiResponse(
                    content=content,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_cents=cost_cents,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                last_error = e
                error_code = getattr(
                    getattr(e, "response", None), "status_code", None
                )
                if error_code in (429, 500, 503) and attempt < max_retries - 1:
                    time.sleep(backoff_seconds[attempt])
                    continue
                # Non-retryable error or final attempt
                break

        # Log failure
        duration_ms = int(time.time() * 1000) - start_ms
        if self._db_conn_factory:
            with self._db_conn_factory() as conn:
                _log_usage(
                    conn,
                    skill_name,
                    model,
                    0,
                    0,
                    0,
                    duration_ms,
                    success=False,
                    error_message=str(last_error),
                    project_id=project_id,
                )

        raise last_error  # type: ignore[misc]
