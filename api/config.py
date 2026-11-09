from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    telegram_webapp_url: str = ""
    telegram_webhook_secret: str = ""

    database_url: str = "sqlite:///./dev.db"
    # Optional separate URL for Alembic only. On Supabase, DATABASE_URL is the transaction
    # pooler (port 6543) and this is the session pooler or direct URL (port 5432), because
    # migrations need session features the transaction pooler does not provide.
    database_url_direct: str = ""

    admin_telegram_ids: str = ""
    social_admin_telegram_ids: str = ""
    welfare_admin_telegram_ids: str = ""
    secret_key: str = "dev-secret-key"
    environment: str = "development"

    # Random string appended to the public .ics subscription feed URL so it can't be
    # trivially guessed. Leave blank to serve the feed without a token (fine for local dev).
    calendar_feed_token: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""
    resend_cc_email: str = "rh.social.i@u.nus.edu"
    welfare_resend_cc_email: str = "rh.social.e@u.nus.edu"
    app_timezone: str = "Asia/Kuala_Lumpur"
    collection_reminder_hour: int = 8
    grading_enabled: bool = False
    grading_remind_admins: bool = True
    ai_reviewer_enabled: bool = False
    ai_reviewer_model: str = "gemini-2.5-flash"
    ai_reviewer_max_chars: int = 60000
    ai_reviewer_timeout_seconds: int = 90
    gemini_api_key: str = ""
    # disabled | live
    google_drive_mode: str = "disabled"
    google_service_account_file: str = ""
    google_service_account_json: str = ""
    google_drive_parent_folder_id: str = ""
    google_drive_social_parent_folder_id: str = ""
    google_drive_welfare_parent_folder_id: str = ""

    # JSON object keyed by committee name. This is intentionally configuration-
    # driven for the first Google Forms test, so adding a form does not require
    # a database migration. Example:
    # {"Sports":{"url":"https://docs.google.com/forms/d/e/.../viewform",
    # "fields":{"request_id":"entry.123"},"sections":["Request","Budget"]}}
    google_form_configs: str = "{}"

    # Telegram id to send finished event/initiative announcements to — in practice
    # a separate relay bot that posts into the announcement channel, not our own
    # bot. 0 means announcing is disabled.
    announcement_telegram_id: int = 0

    # Bearer token the scheduler (Supabase pg_cron) must send to /api/cron/*. Blank
    # disables those endpoints.
    cron_secret: str = ""
    # Where scheduled jobs run: "auto" runs the in-process loops except on Vercel, where
    # there is no long-lived process; "inprocess" / "external" force one or the other.
    scheduler_mode: str = "auto"
    # Vercel sets VERCEL=1 in every deployment.
    vercel: bool = False

    # Where posters and return photos live: "database" (bytea columns, the original
    # behaviour) or "supabase" (a private Supabase Storage bucket). Rows already in the
    # database keep working in either mode; scripts/move_files_to_storage.py moves them.
    storage_mode: str = "database"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "uploads"

    @property
    def migration_database_url(self) -> str:
        return self.database_url_direct or self.database_url

    @property
    def run_inprocess_scheduler(self) -> bool:
        if self.scheduler_mode == "inprocess":
            return True
        if self.scheduler_mode == "external":
            return False
        return not self.vercel

    @property
    def uses_supabase_storage(self) -> bool:
        return self.storage_mode == "supabase"

    def production_problems(self) -> list[str]:
        """Settings that are unsafe or missing for a production deploy (empty when fine)."""
        if self.environment != "production":
            return []
        problems = []
        if not self.secret_key or self.secret_key == "dev-secret-key":
            problems.append("SECRET_KEY is unset or the development default")
        if not self.telegram_bot_token:
            problems.append("TELEGRAM_BOT_TOKEN is unset")
        if not self.telegram_webhook_secret:
            problems.append("TELEGRAM_WEBHOOK_SECRET is unset")
        # CALENDAR_FEED_TOKEN is deliberately optional: production has always served the
        # feed without one, and setting it would break every existing subscription URL.
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL points at SQLite")
        if not self.run_inprocess_scheduler and not self.cron_secret:
            problems.append("CRON_SECRET is unset but scheduled jobs run externally")
        if self.uses_supabase_storage and not (self.supabase_url and self.supabase_service_role_key):
            problems.append("STORAGE_MODE=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        if self.storage_mode not in ("database", "supabase"):
            problems.append(f"STORAGE_MODE must be database or supabase, not {self.storage_mode!r}")
        if self.scheduler_mode not in ("auto", "inprocess", "external"):
            problems.append(f"SCHEDULER_MODE must be auto, inprocess or external, not {self.scheduler_mode!r}")
        return problems

    @property
    def admin_telegram_id_set(self) -> set[int]:
        return {
            int(raw.strip())
            for raw in self.admin_telegram_ids.split(",")
            if raw.strip()
        }

    @staticmethod
    def _parse_telegram_ids(raw_ids: str) -> set[int]:
        return {int(raw.strip()) for raw in raw_ids.split(",") if raw.strip()}

    @property
    def social_admin_telegram_id_set(self) -> set[int]:
        # Keep the existing ADMIN_TELEGRAM_IDS setting as the Social fallback.
        raw = self.social_admin_telegram_ids or self.admin_telegram_ids
        return self._parse_telegram_ids(raw)

    @property
    def welfare_admin_telegram_id_set(self) -> set[int]:
        return self._parse_telegram_ids(self.welfare_admin_telegram_ids)

    @property
    def all_admin_telegram_id_set(self) -> set[int]:
        return self.admin_telegram_id_set | self.social_admin_telegram_id_set | self.welfare_admin_telegram_id_set


@lru_cache
def get_settings() -> Settings:
    return Settings()
