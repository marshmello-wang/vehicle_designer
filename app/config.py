import os
from dataclasses import dataclass


@dataclass
class Settings:
    # Runtime
    app_name: str = "vehicle-designer-api"
    env: str = os.getenv("ENV", "dev")
    log_level: str = os.getenv("LOG_LEVEL", "info")

    # Supabase
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_service_role_key: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    # Ark API
    ark_base_url: str | None = os.getenv("ARK_BASE_URL")
    ark_api_key: str | None = os.getenv("ARK_API_KEY")


settings = Settings()
