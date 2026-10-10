from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    bot_token: str = Field(min_length=20)
    telegram_api_id: int
    telegram_api_hash: str = Field(min_length=10)
    telegram_api_base: str = "https://api.telegram.org"
    telegram_local_api: bool = False
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_database: str = "anime_bot"
    log_level: str = "INFO"
    download_dir: Path = Path("./downloads")
    max_download_mb: int = Field(default=1900, ge=1, le=1900)
    download_timeout_seconds: int = Field(default=900, ge=30, le=7200)
    max_concurrent_downloads: int = Field(default=2, ge=1, le=10)
    catalog_source: str = "animealpha"
    authorized_catalog_json: Path = Path("./data/catalog.json")

    @field_validator("catalog_source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        value = value.lower().strip()
        # Added "animealpha" to the allowed sources
        if value not in {"demo", "authorized_json", "animealpha"}:
            raise ValueError("CATALOG_SOURCE must be demo, authorized_json, or animealpha")
        return value

    @field_validator("telegram_api_base")
    @classmethod
    def strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
    
