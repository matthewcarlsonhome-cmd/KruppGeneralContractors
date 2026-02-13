"""Abstract base class for all KruppAI skills.

Every skill implements three methods:
1. validate_input() — Parse and validate user input
2. build_prompt() — Assemble the Claude API messages array
3. format_output() — Transform Claude's response into a document

The base class provides execute() which orchestrates the full lifecycle:
validate -> load context -> build prompt -> call API -> format -> persist -> return
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from kruppai.core.api_client import AnthropicClient, ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager, ProjectContext
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter


@dataclass
class SkillResult:
    """Result from executing a skill."""

    output_path: Path
    cost_cents: int
    input_tokens: int
    output_tokens: int
    model: str
    duration_ms: int
    skill_name: str
    project_code: str | None = None


class BaseSkill(ABC):
    """Abstract base class that every KruppAI skill must inherit."""

    skill_name: str
    display_name: str
    description: str
    phase: int
    default_model: str  # "sonnet" or "opus"
    output_formats: list[str]  # ["docx"], ["docx", "xlsx"], etc.

    def __init__(
        self,
        settings: Settings,
        api_client: AnthropicClient,
        formatter: OutputFormatter,
        context_manager: ContextManager,
        knowledge_base: KnowledgeBase,
    ) -> None:
        self.settings = settings
        self.api_client = api_client
        self.formatter = formatter
        self.context_manager = context_manager
        self.knowledge_base = knowledge_base

    @abstractmethod
    def validate_input(self, **kwargs: object) -> dict:
        """Validate and normalize user input.

        Returns:
            Dict of validated input fields. Must include 'project_id'
            if the skill requires project context.

        Raises:
            ValueError: If input is invalid.
        """

    @abstractmethod
    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages array.

        Args:
            validated: Output from validate_input().
            context: Project context (None if skill doesn't require a project).

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """

    @abstractmethod
    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Transform Claude's response into a branded document.

        Args:
            response: Raw text response from Claude.
            context: Project context for document headers.
            validated: Original validated input.

        Returns:
            Path to the generated output file.
        """

    def execute(self, **kwargs: object) -> SkillResult:
        """Full skill lifecycle — do not override.

        Steps: validate -> load context -> build prompt -> call API
               -> format -> persist -> return
        """
        # 1. Validate input
        validated = self.validate_input(**kwargs)

        # 2. Load context (if project_id provided)
        context: ProjectContext | None = None
        project_id = validated.get("project_id")
        if project_id is not None:
            context = self.context_manager.load(project_id)

        # 3. Build prompt
        messages = self.build_prompt(validated, context)

        # 4. Call API
        system_context = self.knowledge_base.get_system_context()
        response: ApiResponse = self.api_client.call(
            messages=messages,
            skill_name=self.skill_name,
            project_id=project_id,
            system=system_context if system_context else None,
        )

        # 5. Format output
        output_path = self.format_output(response.content, context, validated)

        # 6. Persist to generated_documents
        self._persist(validated, response, output_path, context)

        # 7. Return result
        return SkillResult(
            output_path=output_path,
            cost_cents=response.cost_cents,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            model=response.model,
            duration_ms=response.duration_ms,
            skill_name=self.skill_name,
            project_code=(
                context.project["project_code"] if context else None
            ),
        )

    def _persist(
        self,
        validated: dict,
        response: ApiResponse,
        output_path: Path,
        context: ProjectContext | None,
    ) -> None:
        """Log the generated document to the database."""
        project_id = validated.get("project_id")
        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO generated_documents "
                "(project_id, skill_name, document_type, file_name, "
                "file_path, file_size_bytes, input_summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    self.skill_name,
                    output_path.suffix.lstrip("."),
                    output_path.name,
                    str(output_path),
                    output_path.stat().st_size if output_path.exists() else 0,
                    str(validated)[:500],
                ),
            )
