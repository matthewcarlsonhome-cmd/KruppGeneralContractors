"""Tests for kruppai.skills.base — BaseSkill abstract class."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kruppai.core.api_client import AnthropicClient, ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager, ProjectContext
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.base import BaseSkill, SkillResult


class ConcreteSkill(BaseSkill):
    """Minimal concrete implementation for testing."""

    skill_name = "test_skill"
    display_name = "Test Skill"
    description = "A test skill"
    phase = 1
    default_model = "sonnet"
    output_formats = ["docx"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_order: list[str] = []

    def validate_input(self, **kwargs) -> dict:
        self.call_order.append("validate")
        if "fail_validation" in kwargs:
            raise ValueError("Validation failed")
        return dict(kwargs)

    def build_prompt(self, validated, context):
        self.call_order.append("prompt")
        return [{"role": "user", "content": "test prompt"}]

    def format_output(self, response, context, validated):
        self.call_order.append("format")
        # Create a dummy output file
        output_path = self.settings.output_dir / "test_output.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("test output content")
        return output_path


@pytest.fixture
def skill_deps(test_db: Settings, mock_api_client: AnthropicClient):
    """Skill dependencies for testing."""
    settings = test_db
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    formatter = OutputFormatter(settings)
    context_manager = ContextManager(settings)
    knowledge_base = KnowledgeBase(settings)

    return {
        "settings": settings,
        "api_client": mock_api_client,
        "formatter": formatter,
        "context_manager": context_manager,
        "knowledge_base": knowledge_base,
    }


class TestBaseSkill:
    def test_execute_lifecycle_order(self, skill_deps: dict) -> None:
        """validate -> prompt -> api -> format -> persist order."""
        skill = ConcreteSkill(**skill_deps)
        result = skill.execute(notes="test notes")
        assert skill.call_order == ["validate", "prompt", "format"]
        # API call was made (mocked)
        skill_deps["api_client"].call.assert_called_once()

    def test_execute_returns_skill_result(self, skill_deps: dict) -> None:
        """Result has all fields populated."""
        skill = ConcreteSkill(**skill_deps)
        result = skill.execute(notes="test")
        assert isinstance(result, SkillResult)
        assert result.skill_name == "test_skill"
        assert result.output_path.exists()
        assert result.cost_cents >= 0
        assert result.input_tokens >= 0
        assert result.model is not None

    def test_execute_logs_to_generated_documents(
        self, skill_deps: dict
    ) -> None:
        """DB has record after execution."""
        skill = ConcreteSkill(**skill_deps)
        skill.execute(notes="test")

        from kruppai.core.database import get_db

        with get_db(skill_deps["settings"]) as conn:
            cursor = conn.execute(
                "SELECT * FROM generated_documents WHERE skill_name = 'test_skill'"
            )
            rows = cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["skill_name"] == "test_skill"

    def test_execute_without_project(self, skill_deps: dict) -> None:
        """Skills that don't require project_id still work."""
        skill = ConcreteSkill(**skill_deps)
        result = skill.execute(topic="fall protection")
        assert result.project_code is None
        assert result.output_path.exists()

    def test_validation_error_stops_execution(
        self, skill_deps: dict
    ) -> None:
        """Bad input raises before API is called."""
        skill = ConcreteSkill(**skill_deps)
        with pytest.raises(ValueError, match="Validation failed"):
            skill.execute(fail_validation=True)
        # API should not have been called
        skill_deps["api_client"].call.assert_not_called()
        assert skill.call_order == ["validate"]
