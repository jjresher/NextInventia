from typing import Literal

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_key: str
    frontend_origin: str = "http://localhost:3000"
    app_environment: Literal["development", "test", "production"] = "development"
    allow_local_network_origins: bool = False
    gemini_api_key: str
