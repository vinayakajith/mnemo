"""Typed config loaded from environment / .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aws_region: str = Field(default="us-east-1")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    bedrock_model_id: str = Field(default="us.anthropic.claude-opus-4-7-20250514:0")
    log_level: str = Field(default="INFO")
    system_prompt_path: str = Field(default="prompts/samantha_v1.txt")
    transcripts_dir: str = Field(default="transcripts")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
