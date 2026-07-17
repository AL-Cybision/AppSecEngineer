from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "ExpenseGuard"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str | None = None
    database_host: str | None = None
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "expenseguard"
    database_user: str = "expenseguard"
    database_password: str | None = None

    session_absolute_minutes: int = Field(default=480, ge=5, le=1440)
    session_idle_minutes: int = Field(default=30, ge=5, le=480)
    reset_token_minutes: int = Field(default=30, ge=5, le=120)

    storage_endpoint_url: str | None = None
    storage_region: str = "us-east-1"
    storage_bucket: str = "expenseguard-receipts"
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_request_encryption: bool = True
    storage_presign_seconds: int = Field(default=60, ge=15, le=300)

    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_from: str = "security@example.test"
    public_reset_url: str = "http://localhost:8000/docs"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1"]

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def parse_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
