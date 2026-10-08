"""Application configuration management using pydantic-settings."""

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class CorsSettings(BaseModel):
    """CORS configuration."""

    origins: list[str] = ["*"]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Environment
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str

    # Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_settings(self) -> CorsSettings:
        """Parse CORS origins from JSON string or list."""
        raw = self.CORS_ORIGINS
        if isinstance(raw, str):
            # Parse JSON string like '["*"]' or '["http://localhost:8080"]'
            import json

            try:
                parsed = json.loads(raw)
                return CorsSettings(origins=parsed if isinstance(parsed, list) else [raw])
            except json.JSONDecodeError:
                return CorsSettings(origins=[o.strip() for o in raw.split(",")])
        return CorsSettings(origins=raw if isinstance(raw, list) else [raw])


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
