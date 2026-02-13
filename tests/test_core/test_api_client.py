"""Tests for kruppai.core.api_client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from kruppai.core.api_client import (
    OPUS_SKILLS,
    AnthropicClient,
    ApiResponse,
    CostLimitExceeded,
    _check_cost_limits,
    _log_usage,
    calculate_cost_cents,
    get_model_for_skill,
    parse_claude_json,
)
from kruppai.core.config import Settings
from kruppai.core.database import get_db


class TestCostCalculation:
    def test_cost_calculation_sonnet(self) -> None:
        """1000 input + 500 output tokens on Sonnet -> correct cents."""
        cost = calculate_cost_cents(
            "claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
        )
        # (1000/1M * 300) + (500/1M * 1500) = 0.3 + 0.75 = 1.05 -> 1 cent
        assert cost == 1

    def test_cost_calculation_opus(self) -> None:
        """Same tokens on Opus -> higher cost (5x input, 5x output)."""
        cost = calculate_cost_cents(
            "claude-opus-4-6",
            input_tokens=1000,
            output_tokens=500,
        )
        # (1000/1M * 1500) + (500/1M * 7500) = 1.5 + 3.75 = 5.25 -> 5 cents
        assert cost == 5

    def test_cost_calculation_large_volume(self) -> None:
        """Large token counts produce reasonable costs."""
        cost = calculate_cost_cents(
            "claude-sonnet-4-5-20250929",
            input_tokens=100_000,
            output_tokens=4_000,
        )
        # (100000/1M * 300) + (4000/1M * 1500) = 30 + 6 = 36 cents
        assert cost == 36

    def test_unknown_model_uses_sonnet_pricing(self) -> None:
        """Unknown model falls back to Sonnet pricing."""
        cost = calculate_cost_cents(
            "claude-unknown-model",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        assert cost == 300  # $3/M input = 300 cents


class TestModelRouting:
    def test_daily_report_uses_sonnet(self) -> None:
        settings = Settings(_env_file=None)
        assert get_model_for_skill("daily_report", settings) == settings.default_model

    def test_contract_checker_uses_opus(self) -> None:
        settings = Settings(_env_file=None)
        assert get_model_for_skill("contract_checker", settings) == settings.opus_model

    def test_proposal_generator_uses_opus(self) -> None:
        settings = Settings(_env_file=None)
        assert get_model_for_skill("proposal_generator", settings) == settings.opus_model

    def test_estimate_reviewer_uses_opus(self) -> None:
        settings = Settings(_env_file=None)
        assert get_model_for_skill("estimate_reviewer", settings) == settings.opus_model

    def test_safety_talk_uses_sonnet(self) -> None:
        settings = Settings(_env_file=None)
        assert get_model_for_skill("safety_talk", settings) == settings.default_model


class TestCostLimits:
    def test_daily_cost_limit(self, seeded_db: Settings) -> None:
        """After exceeding limit, _check_cost_limits raises."""
        with get_db(seeded_db) as conn:
            # Insert usage that exceeds daily limit
            conn.execute(
                "INSERT INTO api_usage "
                "(skill_name, model, input_tokens, output_tokens, total_tokens, "
                "cost_cents, duration_ms, success) "
                "VALUES ('test', 'model', 1000, 500, 1500, ?, 100, 1)",
                (seeded_db.daily_cost_limit_cents + 1,),
            )
            conn.commit()

            with pytest.raises(CostLimitExceeded, match="Daily"):
                _check_cost_limits(conn, seeded_db)


class TestUsageLogging:
    def test_usage_logged_to_db(self, test_db: Settings) -> None:
        """After logging, api_usage table has a record."""
        with get_db(test_db) as conn:
            row_id = _log_usage(
                conn, "daily_report", "claude-sonnet-4-5-20250929",
                1000, 500, 2, 3500, True, None, None,
            )
            assert row_id is not None

            cursor = conn.execute(
                "SELECT * FROM api_usage WHERE id = ?", (row_id,)
            )
            row = cursor.fetchone()
            assert row["skill_name"] == "daily_report"
            assert row["input_tokens"] == 1000
            assert row["cost_cents"] == 2
            assert row["success"] == 1


class TestApiResponseDataclass:
    def test_all_fields_populated(self) -> None:
        resp = ApiResponse(
            content="test response",
            model="claude-sonnet-4-5-20250929",
            input_tokens=100,
            output_tokens=50,
            cost_cents=1,
            duration_ms=500,
        )
        assert resp.content == "test response"
        assert resp.model == "claude-sonnet-4-5-20250929"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.cost_cents == 1
        assert resp.duration_ms == 500


class TestParseClaudeJson:
    def test_parse_plain_json(self) -> None:
        result = parse_claude_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_with_code_fence(self) -> None:
        text = '```json\n{"key": "value"}\n```'
        result = parse_claude_json(text)
        assert result == {"key": "value"}

    def test_parse_with_trailing_comma(self) -> None:
        text = '{"key": "value", "list": [1, 2, 3,],}'
        result = parse_claude_json(text)
        assert result == {"key": "value", "list": [1, 2, 3]}

    def test_parse_json_array(self) -> None:
        result = parse_claude_json('[{"a": 1}, {"b": 2}]')
        assert len(result) == 2

    def test_parse_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            parse_claude_json("not json at all")
