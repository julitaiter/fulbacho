import os
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fulbacho API"
    environment: str = "development"
    debug: bool = Field(True, validation_alias=AliasChoices("API_DEBUG", "DEBUG"))
    api_v1_prefix: str = "/api/v1"
    secret_key: str = Field(validation_alias=AliasChoices("API_SECRET_KEY", "SECRET_KEY"))
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    database_url: str
    test_database_url: str | None = None
    cors_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    @model_validator(mode="after")
    def production_settings(self):
        if self.environment.lower() == "production":
            if not os.getenv("API_SECRET_KEY") or os.getenv("API_DEBUG", "").lower() != "false":
                raise ValueError("Production requires API_SECRET_KEY and API_DEBUG=false.")
            if self.debug or self.secret_key == os.getenv("DJANGO_SECRET_KEY"):
                raise ValueError("Production requires DEBUG=false and distinct application secrets.")
        return self

    @field_validator("database_url", "test_database_url", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, value):
        if not value:
            return value
        value = str(value)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
