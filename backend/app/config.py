from typing import Literal

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_key: str
    frontend_origin: str = "http://localhost:3000"
    app_environment: Literal["development", "test", "production"] = "development"
    allow_local_network_origins: bool = False
    gemini_api_key: str
    supabase_timeout_seconds: float = Field(default=10, gt=0, le=120)
    gemini_timeout_seconds: float = Field(default=45, gt=0, le=180)
    request_timeout_seconds: float = Field(default=60, gt=0, le=300)
    external_retry_attempts: int = Field(default=2, ge=1, le=4)
    external_retry_backoff_seconds: float = Field(default=0.2, ge=0, le=5)
