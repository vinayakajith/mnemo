"""Typed config loaded from environment / .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field(default="")
    model_id: str = Field(default="claude-opus-4-7")
    log_level: str = Field(default="INFO")
    system_prompt_path: str = Field(default="prompts/samantha_v1.txt")
    transcripts_dir: str = Field(default="transcripts")
    postgres_dsn: str = Field(default="postgresql://samantha:samantha_dev@localhost:5432/samantha")
    default_user_id: str = Field(default="default")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
