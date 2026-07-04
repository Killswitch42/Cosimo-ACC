from typing import Optional

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRET = "change-this-to-a-random-64-char-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = "Medici Analytica Accounting"
    app_env: str = "development"
    app_secret_key: str
    debug: bool = False

    database_url: PostgresDsn
    database_pool_size: int = 10
    database_max_overflow: int = 20

    company_name: str = "Medici Analytica s.r.o."
    company_ico: Optional[str] = None
    company_dic: Optional[str] = None
    company_registered_office: Optional[str] = None
    fiscal_year_start_month: int = 1

    xai_api_key: Optional[str] = None
    cnb_api_base_url: str = "https://api.cnb.cz/cnbapi/exrates"
    epartal_base_url: str = "https://adisspr.mfcr.cz"
    filing_output_dir: str = "/tmp/medici-analytica-filings"
    document_storage_dir: str = "/tmp/medici-analytica-documents"

    # Session cookie security. Keep secure=False for plain-HTTP LAN/Tailscale
    # access; set COOKIE_SECURE=true once the app is served over HTTPS.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # Google Drive backup (off until configured). Share a Drive folder with the
    # service account's email, then set the folder id + key path below.
    gdrive_backup_enabled: bool = False
    gdrive_service_account_file: Optional[str] = None
    gdrive_backup_folder_id: Optional[str] = None
    backup_keep_count: int = 14
    # DB dump: uses host `pg_dump` if present, else `docker exec <container>`.
    pg_container_name: Optional[str] = None

    # Initial admin account (used only by the seed). Override in .env and
    # change the password after first login.
    admin_email: str = "admin@medicianalytica.cz"
    admin_password: str = "changeme123"

    @property
    def secret_key_is_weak(self) -> bool:
        return (
            not self.app_secret_key
            or self.app_secret_key == _PLACEHOLDER_SECRET
            or len(self.app_secret_key) < 32
        )

    @property
    def admin_password_is_default(self) -> bool:
        return self.admin_password == "changeme123"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value


settings = Settings()
