from typing import Optional

from pydantic import PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: Optional[PostgresDsn] = None
    REDIS_URL: Optional[RedisDsn] = None

    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_envs(self) -> "Settings":
        # Production requirements: Fail fast
        if self.APP_ENV == "production":
            missing = []
            if not self.DATABASE_URL:
                missing.append("DATABASE_URL")
            if not self.REDIS_URL:
                missing.append("REDIS_URL")

            if missing:
                msg = f"Missing required environment variables in production: {', '.join(missing)}"
                raise ValueError(msg)

        # Development defaults: Convenience
        else:
            if not self.DATABASE_URL:
                self.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/reponis"  # type: ignore
            if not self.REDIS_URL:
                self.REDIS_URL = "redis://localhost:6379/0"  # type: ignore

        return self


settings = Settings()
