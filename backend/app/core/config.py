from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "migration", "production"] = Field(
        default="development", validation_alias="ENV"
    )
    app_name: str = Field(default="CaseFlow", validation_alias="APP_NAME")
    public_app_url: str = Field(default="http://localhost:5173", validation_alias="PUBLIC_APP_URL")
    allowed_origin: str = Field(default="http://localhost:5173", validation_alias="ALLOWED_ORIGIN")
    development_allowed_origin: str | None = Field(
        default=None, validation_alias="DEV_ALLOWED_ORIGIN"
    )
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://caseflow:caseflow@localhost:5432/caseflow"),
        validation_alias="DATABASE_URL",
    )
    database_url_direct: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL_DIRECT")
    csrf_secret: SecretStr = Field(
        default=SecretStr("local-development-only-secret-change-before-sharing"),
        validation_alias="CSRF_SECRET",
    )
    session_ttl_hours: int = Field(default=168, ge=1, le=168, validation_alias="SESSION_TTL_HOURS")
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    cookie_name: str = Field(default="caseflow_dev_session", validation_alias="COOKIE_NAME")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    allow_demo_seed: bool = Field(default=False, validation_alias="ALLOW_DEMO_SEED")
    max_request_bytes: int = Field(default=32_768, ge=1_024, le=32_768, validation_alias="MAX_REQUEST_BYTES")
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    trust_render_edge_ip: bool = Field(default=False, validation_alias="TRUST_RENDER_EDGE_IP")

    @property
    def trusted_origins(self) -> frozenset[str]:
        trusted = {self.allowed_origin}
        if self.environment != "production" and self.development_allowed_origin:
            trusted.add(self.development_allowed_origin)
        return frozenset(trusted)

    @model_validator(mode="after")
    def validate_deployment_configuration(self) -> "Settings":
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg scheme.")

        if self.environment == "production":
            if not self.rate_limit_enabled:
                raise ValueError("RATE_LIMIT_ENABLED must remain on in production.")
            public_origin = urlsplit(self.public_app_url)
            allowed_origin = urlsplit(self.allowed_origin)
            if (
                public_origin.scheme != "https"
                or not public_origin.netloc
                or public_origin.path
                or public_origin.query
                or public_origin.fragment
                or public_origin.username
                or public_origin.password
            ):
                raise ValueError("PUBLIC_APP_URL must be a valid HTTPS origin in production.")
            if self.allowed_origin.rstrip("/") != self.public_app_url.rstrip("/"):
                raise ValueError("ALLOWED_ORIGIN must match PUBLIC_APP_URL in production.")
            if (
                allowed_origin.scheme != "https"
                or not allowed_origin.netloc
                or allowed_origin.path
                or allowed_origin.query
                or allowed_origin.fragment
                or allowed_origin.username
                or allowed_origin.password
            ):
                raise ValueError("ALLOWED_ORIGIN must be a valid HTTPS origin in production.")
            if not self.cookie_secure or self.cookie_name != "__Host-caseflow_session":
                raise ValueError("Production requires the secure __Host-caseflow_session cookie.")
            if (
                len(self.csrf_secret.get_secret_value()) < 32
                or self.csrf_secret.get_secret_value()
                == "local-development-only-secret-change-before-sharing"
            ):
                raise ValueError("CSRF_SECRET must contain at least 32 characters in production.")
            if "sslmode=require" not in database_url and "sslmode=verify-full" not in database_url:
                raise ValueError("Production DATABASE_URL must require PostgreSQL TLS.")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
