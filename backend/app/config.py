from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QuackQuant API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QUACKQUANT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

