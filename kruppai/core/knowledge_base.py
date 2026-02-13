"""Loads company knowledge files for prompt enrichment.

Knowledge files are markdown documents in the knowledge/ directory.
They are injected into system prompts so Claude generates documents
that sound like Krupp, not like generic AI output.
"""

from pathlib import Path

from kruppai.core.config import Settings


class KnowledgeBase:
    """Loads and manages company knowledge base files."""

    def __init__(self, settings: Settings) -> None:
        self.knowledge_dir = settings.knowledge_dir

    def load_all(self) -> dict[str, str]:
        """Load all markdown files from the knowledge directory.

        Returns:
            Dict mapping filename (without extension) to file content.
            Empty dict if directory doesn't exist.
        """
        if not self.knowledge_dir.exists():
            return {}

        result: dict[str, str] = {}
        for md_file in sorted(self.knowledge_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                result[md_file.stem] = content
            except Exception:
                continue
        return result

    def load_file(self, name: str) -> str | None:
        """Load a specific knowledge file by name (without .md extension).

        Args:
            name: File stem, e.g., "company_profile" for company_profile.md

        Returns:
            File content as string, or None if not found.
        """
        file_path = self.knowledge_dir / f"{name}.md"
        if not file_path.exists():
            return None
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception:
            return None

    def get_system_context(self) -> str:
        """Assemble all knowledge files into a single system context string.

        Returns:
            Combined content with section headers, or empty string if no files.
        """
        files = self.load_all()
        if not files:
            return ""

        parts: list[str] = []
        for name, content in files.items():
            display_name = name.replace("_", " ").title()
            parts.append(f"=== {display_name} ===\n{content}")

        return "\n\n".join(parts)
