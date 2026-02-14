"""Application configuration loaded from environment variables and .env file.

Settings hierarchy (highest priority first):
1. Environment variables
2. .env file
3. Default values
"""

import os
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """KruppAI application settings."""

    model_config = SettingsConfigDict(
        env_prefix="KRUPPAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API key — reads KRUPPAI_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-5-20250929"
    opus_model: str = "claude-opus-4-6"

    @model_validator(mode="before")
    @classmethod
    def resolve_api_key(cls, values: dict) -> dict:
        """Read ANTHROPIC_API_KEY from env if prefixed version is empty."""
        key = values.get("anthropic_api_key") or ""
        if not key:
            key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            # Also try reading directly from .env file as fallback
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY=") and not line.startswith("#"):
                        key = line.split("=", 1)[1].strip().strip("'\"")
                        break
        if key:
            values["anthropic_api_key"] = key
        return values

    # Paths
    db_path: Path = Path.home() / ".kruppai" / "kruppai.db"
    output_dir: Path = Path.home() / "KruppAI-Output"
    knowledge_dir: Path = Path("knowledge")

    # Limits
    daily_cost_limit_cents: int = 5000
    monthly_cost_limit_cents: int = 30000
    max_input_tokens: int = 150000
    cost_warning_cents: int = 50

    # Features
    weather_enabled: bool = True
    log_level: str = "INFO"

    @field_validator("db_path", "output_dir", mode="before")
    @classmethod
    def expand_home(cls, v: str | Path) -> Path:
        """Expand ~ in paths."""
        return Path(v).expanduser()

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
