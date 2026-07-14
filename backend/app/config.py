from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    frontend_origin: str = "http://localhost:3000"
    gemini_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()
