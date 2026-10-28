from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "SnapLink"
    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "sqlite+aiosqlite:///./snaplink.db"
    redis_url: str | None = None
    public_base_url: str | None = None
    admin_api_key: str | None = None
    auto_create_tables: bool = True
    cors_origins: list[str] = Field(default_factory=list)

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 10

    create_limit: int = 10
    create_window_seconds: int = 3600
    stats_limit: int = 60
    stats_window_seconds: int = 60
    redirect_limit: int = 300
    redirect_window_seconds: int = 60
    report_limit: int = 5
    report_window_seconds: int = 3600

    max_url_length: int = 4096
    short_code_length: int = 8
    log_level: str = "INFO"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        # Providers often supply a driver-neutral PostgreSQL URL. The async app
        # requires SQLAlchemy's asyncpg dialect.
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("sqlite://"):
            return value.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return value

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.rstrip("/")
        try:
            parsed = urlsplit(value)
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("PUBLIC_BASE_URL is malformed") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PUBLIC_BASE_URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("PUBLIC_BASE_URL must not contain credentials, query, or fragment")
        if parsed.path not in {"", "/"}:
            raise ValueError("PUBLIC_BASE_URL must not contain a path")
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.environment == "production":
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires a PostgreSQL DATABASE_URL")
            if not self.redis_url:
                raise ValueError("Production requires REDIS_URL for shared rate limits")
            if not self.public_base_url or not self.public_base_url.startswith("https://"):
                raise ValueError("Production requires an HTTPS PUBLIC_BASE_URL")
            if not self.admin_api_key or len(self.admin_api_key) < 32:
                raise ValueError("Production requires an ADMIN_API_KEY of at least 32 characters")
            if self.auto_create_tables:
                raise ValueError("AUTO_CREATE_TABLES must be false in production; run migrations")
        if self.short_code_length < 7 or self.short_code_length > 16:
            raise ValueError("SHORT_CODE_LENGTH must be between 7 and 16")
        for name in (
            "create_limit", "create_window_seconds", "stats_limit",
            "stats_window_seconds", "redirect_limit", "redirect_window_seconds",
            "report_limit", "report_window_seconds",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        return self
