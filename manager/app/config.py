from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Raspberry Pi Datacenter Manager"
    app_env: str = "production"
    secret_key: str
    jwt_expire_minutes: int = 720
    database_url: str = "sqlite:////data/rpdm.db"
    cors_origins: str = ""
    admin_user: str = "admin"
    admin_password: str = ""
    enrollment_token: str = ""
    offline_after_seconds: int = 25
    degraded_cpu_percent: float = 90.0
    degraded_mem_percent: float = 92.0
    degraded_temp_c: float = 80.0
    metric_history_limit: int = 360

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return []
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def data_dir(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.replace("sqlite:///", "", 1))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return db_path.parent
        return Path("/data")


@lru_cache
def get_settings() -> Settings:
    return Settings()
