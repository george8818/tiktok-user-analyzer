"""
Application configuration using pydantic-settings.
Loads from environment variables and .env file.
"""

from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperSettings(BaseSettings):
    """Configuration for the TikTok scraper module."""

    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium"
    headless: bool = True
    timeout: int = Field(default=30, alias="SCRAPER_TIMEOUT")
    max_retries: int = Field(default=3, alias="SCRAPER_MAX_RETRIES")
    request_delay: float = Field(default=2.0, alias="SCRAPER_REQUEST_DELAY")

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


class LLMSettings(BaseSettings):
    """Configuration for LLM/AI model usage."""

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    model: str = Field(default="claude-sonnet-4-20250514", alias="LLM_MODEL")
    vision_model: str = Field(default="claude-sonnet-4-20250514", alias="VISION_MODEL")
    max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")
    temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "ANTHROPIC_API_KEY is required. "
                "Set it in your .env file or environment variables."
            )
        return v


class StorageSettings(BaseSettings):
    """Configuration for data storage."""

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/tiktok_analyzer.db",
        alias="DATABASE_URL",
    )
    media_dir: Path = Field(default=Path("./data/media"), alias="MEDIA_DIR")
    reports_dir: Path = Field(default=Path("./data/reports"), alias="REPORTS_DIR")

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        # Ensure SQLite directory exists
        if "sqlite" in self.database_url:
            db_path = self.database_url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


class APISettings(BaseSettings):
    """Configuration for the FastAPI server."""

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class AgentSettings(BaseSettings):
    """Configuration for the conversational agent."""

    max_conversation_turns: int = Field(default=20, alias="MAX_CONVERSATION_TURNS")
    frames_per_video: int = Field(default=5, alias="FRAMES_PER_VIDEO")
    max_videos_per_user: int = Field(default=2, alias="MAX_VIDEOS_PER_USER")

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


class LoggingSettings(BaseSettings):
    """Configuration for logging."""

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    format: Literal["json", "console"] = Field(default="json", alias="LOG_FORMAT")

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


class Settings(BaseSettings):
    """Root application settings aggregating all sub-configurations."""

    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    api: APISettings = Field(default_factory=APISettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def initialize(self) -> "Settings":
        """Run initialization tasks (create dirs, etc.)."""
        self.storage.ensure_dirs()
        return self


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings().initialize()
