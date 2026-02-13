"""Tests for kruppai.core.knowledge_base."""

from pathlib import Path

import pytest

from kruppai.core.config import Settings
from kruppai.core.knowledge_base import KnowledgeBase


class TestKnowledgeBase:
    def test_load_all_files(self, knowledge_dir: Path) -> None:
        """Returns dict with all .md files from knowledge dir."""
        settings = Settings(knowledge_dir=knowledge_dir, _env_file=None)
        kb = KnowledgeBase(settings)
        files = kb.load_all()

        assert "company_profile" in files
        assert "writing_standards" in files
        assert "safety_standards" in files
        assert "Krupp GC" in files["company_profile"]

    def test_missing_directory(self, tmp_path: Path) -> None:
        """Returns empty dict, doesn't crash."""
        settings = Settings(
            knowledge_dir=tmp_path / "nonexistent",
            _env_file=None,
        )
        kb = KnowledgeBase(settings)
        files = kb.load_all()
        assert files == {}

    def test_system_context_assembly(self, knowledge_dir: Path) -> None:
        """Combines files into single formatted string."""
        settings = Settings(knowledge_dir=knowledge_dir, _env_file=None)
        kb = KnowledgeBase(settings)
        context = kb.get_system_context()

        assert "Company Profile" in context
        assert "Writing Standards" in context
        assert "Safety Standards" in context
        assert "Krupp GC" in context

    def test_load_specific_file(self, knowledge_dir: Path) -> None:
        """Returns content of named file, None if missing."""
        settings = Settings(knowledge_dir=knowledge_dir, _env_file=None)
        kb = KnowledgeBase(settings)

        content = kb.load_file("company_profile")
        assert content is not None
        assert "Krupp GC" in content

        missing = kb.load_file("nonexistent_file")
        assert missing is None

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty dict."""
        empty_dir = tmp_path / "empty_knowledge"
        empty_dir.mkdir()
        settings = Settings(knowledge_dir=empty_dir, _env_file=None)
        kb = KnowledgeBase(settings)
        assert kb.load_all() == {}
        assert kb.get_system_context() == ""
