from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        # El backend de producción no necesita SUPABASE_SERVICE_ROLE_KEY (solo la usan
        # los scripts de backend/exel/, que leen el .env directamente por su cuenta) —
        # ignorar variables extra evita que Settings() explote si el .env trae claves
        # que esta app no declara.
        extra="ignore",
    )

    supabase_url: str
    supabase_anon_key: str
    frontend_origin: str = "http://localhost:3000"
    allow_local_network_origins: bool = True
    gemini_api_key: str


settings = Settings()