"""Tests for kruppai.core.document_parser."""

import base64
from pathlib import Path

import pytest

from kruppai.core.document_parser import (
    ParsedDocument,
    parse_docx,
    parse_file,
    parse_image,
    parse_text,
    parse_xlsx,
)


class TestParseFile:
    def test_parse_file_dispatch_docx(self, sample_docx: Path) -> None:
        """Correct parser called for .docx files."""
        result = parse_file(sample_docx)
        assert result.file_type == "docx"
        assert result.error is None

    def test_parse_file_dispatch_xlsx(self, sample_xlsx: Path) -> None:
        """Correct parser called for .xlsx files."""
        result = parse_file(sample_xlsx)
        assert result.file_type == "xlsx"
        assert result.error is None

    def test_parse_file_dispatch_image(self, sample_image: Path) -> None:
        """Correct parser called for image files."""
        result = parse_file(sample_image)
        assert result.file_type == "image"
        assert result.error is None

    def test_missing_file(self, tmp_path: Path) -> None:
        """Nonexistent path returns ParsedDocument with error."""
        result = parse_file(tmp_path / "nonexistent.pdf")
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_unsupported_format(self, tmp_path: Path) -> None:
        """Unsupported file type returns error."""
        zip_file = tmp_path / "test.zip"
        zip_file.write_bytes(b"fake zip content")
        result = parse_file(zip_file)
        assert result.error is not None
        assert "unsupported" in result.error.lower()


class TestParseDocx:
    def test_text_extraction(self, sample_docx: Path) -> None:
        """DOCX text is extracted."""
        result = parse_docx(sample_docx)
        assert "Test document content" in result.text
        assert result.error is None

    def test_table_extraction(self, sample_docx: Path) -> None:
        """DOCX table data is extracted."""
        result = parse_docx(sample_docx)
        assert len(result.tables) == 1
        assert result.tables[0][0][0] == "Header A"
        assert result.tables[0][1][2] == "Value 3"


class TestParseXlsx:
    def test_multi_sheet(self, sample_xlsx: Path) -> None:
        """Both sheets extracted from XLSX."""
        result = parse_xlsx(sample_xlsx)
        assert result.error is None
        assert len(result.tables) == 2
        assert "Estimate" in result.text
        assert "Summary" in result.text

    def test_cell_values(self, sample_xlsx: Path) -> None:
        """Cell values correctly extracted."""
        result = parse_xlsx(sample_xlsx)
        # First sheet should have CSI codes
        assert "Concrete" in result.text
        assert "Electrical" in result.text


class TestParseImage:
    def test_base64_encoding(self, sample_image: Path) -> None:
        """Image returns valid base64 string."""
        result = parse_image(sample_image)
        assert result.error is None
        assert len(result.images) == 1
        assert result.images[0]["media_type"] == "image/png"
        # Verify it's valid base64
        decoded = base64.b64decode(result.images[0]["base64"])
        assert len(decoded) > 0


class TestParseText:
    def test_text_passthrough(self, tmp_path: Path) -> None:
        """Plain text passes through."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("Field notes from today's pour.")
        result = parse_text(txt_file)
        assert result.text == "Field notes from today's pour."
        assert result.error is None


class TestTruncation:
    def test_max_chars_truncation(self, tmp_path: Path) -> None:
        """Long document truncated at limit."""
        txt_file = tmp_path / "long.txt"
        txt_file.write_text("A" * 200_000)
        result = parse_file(txt_file, max_chars=1000)
        assert len(result.text) < 200_000
        assert "[TRUNCATED" in result.text
