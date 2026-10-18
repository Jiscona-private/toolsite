from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    port: int = 3000
    base_path: str = "/wg"
    app_base_url: str = "http://127.0.0.1:8000/wg"
    secret_key: str = "dev-secret-key-change-me"
    database_path: str = "./data/wg.db"
    backup_dir: str = "./data/backups"
    backup_keep_days: int = 14
    ntfy_base_url: str = "https://ntfy.sh"
    tz: str = "Europe/Berlin"
    log_level: str = "info"


settings = Settings()
