from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: ClassVar[str] = "Crypto Tax Tool"
    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_api_secret: str = Field(default="", alias="BINANCE_API_SECRET")
    db_path: Path = Field(default=Path("data/crypto_tax_tool.sqlite3"), alias="CRYPTO_TAX_DB_PATH")
    log_dir: Path = Path("logs")

    @property
    def data_dir(self) -> Path:
        return self.db_path.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()
