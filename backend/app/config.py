from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    frontend_origin: str = "http://localhost:3000"
    allow_local_network_origins: bool = True
    gemini_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()
