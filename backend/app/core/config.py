from functools import lru_cache
import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[BASE_DIR / ".env", BASE_DIR.parent / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Nifty 50 Live Option Chain Dashboard"
    environment: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # Security & CORS
    secret_key: str = Field(..., alias="SECRET_KEY")
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list, alias="CORS_ORIGINS")

    # Databases
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # FYERS API
    fyers_client_id: str = Field("", alias="FYERS_CLIENT_ID")
    fyers_secret_key: str = Field("", alias="FYERS_SECRET_KEY")
    fyers_redirect_uri: str = Field("", alias="FYERS_REDIRECT_URI")
    fyers_access_token: str = Field("", alias="FYERS_ACCESS_TOKEN")
    fyers_symbol: str = Field("NSE:NIFTY50-INDEX", alias="FYERS_SYMBOL")
    fyers_strikecount: int = Field(12, alias="FYERS_STRIKECOUNT")

    # Option chain behaviour
    option_chain_provider: str = Field("fyers", alias="OPTION_CHAIN_PROVIDER")
    option_chain_cache_ttl_seconds: int = Field(10, alias="OPTION_CHAIN_CACHE_TTL_SECONDS")
    option_chain_last_good_ttl_seconds: int = Field(
        60 * 60 * 24,
        alias="OPTION_CHAIN_LAST_GOOD_TTL_SECONDS",
    )
    option_chain_refresh_seconds: int = Field(15, alias="OPTION_CHAIN_REFRESH_SECONDS")

    # Google OAuth
    google_client_id: str = Field("", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field("", alias="GOOGLE_CLIENT_SECRET")
    google_oauth_redirect_url: str = Field("", alias="GOOGLE_OAUTH_REDIRECT_URL")
    auth_token_lifetime_seconds: int = 60 * 60 * 12

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @property
    def oauth_csrf_cookie_secure(self) -> bool:
        return self.environment.lower() != "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
