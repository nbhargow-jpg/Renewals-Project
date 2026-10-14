"""
Application configuration — all settings come from environment variables or .env.
Never hard-code secrets or model names here.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = f"sqlite:///{ROOT_DIR / 'renewals.db'}"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Ensure standard postgres:// or postgresql:// URLs use an available psycopg dialect."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql+psycopg2://"):
            try:
                import psycopg2  # noqa: F401
            except ImportError:
                # Fall back to psycopg (v3) if psycopg2 binary is not installed in the environment
                url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        return url

    # AI provider (stub by default; swap to "gemini" or "openai" via .env)
    AI_PROVIDER: str = "demo"          # "demo" | "gemini" | "openai" | "custom"
    AI_BASE_URL: str = ""              # e.g. https://generativelanguage.googleapis.com
    AI_MODEL_NAME: str = ""            # e.g. gemini-1.5-flash  (never hard-coded)
    AI_API_KEY: str = ""

    # AI / LLM provider
    DEMO_MODE: bool = True
    LLM_BASE_URL: str = ""             # e.g. https://api.openai.com/v1
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT: int = 30
    LLM_MAX_TOOL_CALLS: int = 6
    LLM_SEND_MODE: str = "aggregates"  # "aggregates" | "full"

    # Paths
    DATA_DIR: Path = ROOT_DIR / "data"
    ASSETS_DIR: Path = ROOT_DIR / "assets"

    # App
    APP_TITLE: str = "Mobileum Horizon"
    APP_VERSION: str = "1.0.0"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    FISCAL_YEAR_START_MONTH: int = 1

    # Security & Admin Auth (Addendum D)
    ENVIRONMENT: str = "development"
    ADMIN_PASSWORD: str = ""
    ADMIN_SECRET_KEY: str = ""
    COOKIE_SECURE: Optional[bool] = None
    ADMIN_TOKEN_EXPIRE_HOURS: int = 8

    @property
    def is_cookie_secure(self) -> bool:
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_admin_configured(self) -> bool:
        disallowed_keys = {
            "",
            "supersecret_renewals_admin_signing_key_change_in_prod",
            "change_this_to_a_long_random_secret_in_production",
        }
        return bool(self.ADMIN_PASSWORD and self.ADMIN_PASSWORD.strip()) and bool(
            self.ADMIN_SECRET_KEY and self.ADMIN_SECRET_KEY.strip() and self.ADMIN_SECRET_KEY.strip() not in disallowed_keys
        )


settings = Settings()
