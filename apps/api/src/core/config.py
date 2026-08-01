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

    SECRET_KEY: Optional[str] = None
    FERNET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    FRONTEND_URL: str = "http://localhost:3000"

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
            if not self.SECRET_KEY:
                missing.append("SECRET_KEY")
            if not self.FERNET_KEY:
                missing.append("FERNET_KEY")

            if missing:
                msg = f"Missing required environment variables in production: {', '.join(missing)}"
                raise ValueError(msg)

        # Development defaults: Convenience
        else:
            if not self.DATABASE_URL:
                self.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/reponis"  # type: ignore
            if not self.REDIS_URL:
                self.REDIS_URL = "redis://localhost:6379/0"  # type: ignore
            if not self.SECRET_KEY:
                self.SECRET_KEY = "dev_secret_key"
            if not self.FERNET_KEY:
                # A valid Fernet key for dev: 32 url-safe base64-encoded bytes
                self.FERNET_KEY = "ZGV2X2Zlcm5ldF9rZXlfZm9yX2xvY2FsX2RldmVsb3A="

        return self


settings = Settings()
