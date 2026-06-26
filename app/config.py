from typing import Optional

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    anthropic_api_key: Optional[str] = None
    cnb_api_base_url: str = "https://api.cnb.cz/cnbapi/exrates"
    epartal_base_url: str = "https://adisspr.mfcr.cz"
    filing_output_dir: str = "/tmp/medici-analytica-filings"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value


settings = Settings()
