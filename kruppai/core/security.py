"""Security utilities for input validation and sanitization.

Provides defense-in-depth measures for user-supplied text and file paths:
- Input text sanitization to mitigate prompt injection
- File path validation to prevent path traversal attacks
- File size enforcement to guard against resource exhaustion
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS: set[str] = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".xls",
    ".csv",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
}

MAX_INPUT_LENGTH: int = 50_000

# Patterns commonly associated with prompt injection attempts.
# These are stripped from user input before it reaches the AI model.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*instruction\s*>", re.IGNORECASE),
    re.compile(r"<\s*/\s*instruction\s*>", re.IGNORECASE),
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+(?:a\s+)?(?:different|new)\b", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*\n", re.IGNORECASE),
    re.compile(r"\bassistant\s*:\s*\n", re.IGNORECASE),
    re.compile(r"\bhuman\s*:\s*\n", re.IGNORECASE),
]


def sanitize_input(text: str) -> str:
    """Remove potential prompt injection patterns and enforce length limits.

    Strips recognized injection patterns from the input text and truncates
    to MAX_INPUT_LENGTH characters. This is a best-effort defense layer;
    it does not guarantee complete protection against adversarial inputs.

    Args:
        text: Raw user-supplied text (field notes, descriptions, etc.).

    Returns:
        Sanitized text with injection patterns removed and length capped.

    Raises:
        ValueError: If the input is empty after stripping whitespace.
    """
    if not text or not text.strip():
        raise ValueError("Input text must not be empty.")

    # Truncate to maximum allowed length
    if len(text) > MAX_INPUT_LENGTH:
        logger.warning(
            "Input truncated from %d to %d characters.",
            len(text),
            MAX_INPUT_LENGTH,
        )
        text = text[:MAX_INPUT_LENGTH]

    # Strip null bytes
    text = text.replace("\x00", "")

    # Remove recognized injection patterns
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("", text)

    # Collapse excessive whitespace left by removals
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def validate_file_path(
    path: Path,
    allowed_extensions: list[str] | None = None,
) -> Path:
    """Validate a file path for safety and allowed types.

    Resolves the path to an absolute location, checks for path traversal
    indicators, and verifies the file extension against an allowlist.

    Args:
        path: Path to validate (may be relative or absolute).
        allowed_extensions: List of permitted extensions (e.g., [".pdf", ".docx"]).
            Defaults to ALLOWED_EXTENSIONS if not provided.

    Returns:
        Resolved absolute Path to the validated file.

    Raises:
        ValueError: If the path contains traversal sequences or has a
            disallowed extension.
        FileNotFoundError: If the resolved path does not exist.
    """
    extensions = set(allowed_extensions) if allowed_extensions else ALLOWED_EXTENSIONS

    # Detect path traversal attempts in the raw string
    raw = str(path)
    if ".." in raw:
        raise ValueError(
            f"Path traversal detected in '{raw}'. Paths must not contain '..' segments."
        )

    # Resolve to absolute path
    resolved = path.resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    # Check extension
    suffix = resolved.suffix.lower()
    if suffix not in extensions:
        raise ValueError(
            f"File type '{suffix}' is not allowed. "
            f"Permitted types: {sorted(extensions)}"
        )

    return resolved


def check_file_size(path: Path, max_size_mb: float = 50.0) -> None:
    """Verify that a file does not exceed the maximum allowed size.

    Args:
        path: Path to the file to check.
        max_size_mb: Maximum allowed file size in megabytes.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file exceeds the size limit.
    """
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    size_bytes = resolved.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    if size_mb > max_size_mb:
        raise ValueError(
            f"File '{resolved.name}' is {size_mb:.1f} MB, "
            f"which exceeds the {max_size_mb:.1f} MB limit."
        )
