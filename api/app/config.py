from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App
    app_name: str = "Blueprint AI"
    environment: str = "development"
    log_level: str = "INFO"
    port: int = 8000

    # ── Database (Supabase PostgreSQL)
    database_url: str = ""

    # ── Supabase (Realtime)
    supabase_url: str = ""
    supabase_service_key: str = ""

    # ── Auth
    secret_key: str = "dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # ── Anthropic (server-side only — never exposed to frontend)
    anthropic_api_key: str = ""

    # ── CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
