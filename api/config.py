from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    telegram_webapp_url: str = ""
    telegram_webhook_secret: str = ""

    database_url: str = "sqlite:///./dev.db"

    admin_telegram_ids: str = ""
    secret_key: str = "dev-secret-key"
    environment: str = "development"

    # Random string appended to the public .ics subscription feed URL so it can't be
    # trivially guessed. Leave blank to serve the feed without a token (fine for local dev).
    calendar_feed_token: str = ""

    @property
    def admin_telegram_id_set(self) -> set[int]:
        return {
            int(raw.strip())
            for raw in self.admin_telegram_ids.split(",")
            if raw.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
