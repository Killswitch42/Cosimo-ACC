from uuid import UUID

from pydantic import BaseModel


class CompanyRead(BaseModel):
    id: UUID
    name: str
    ico: str | None = None
    dic: str | None = None
    registered_office: str | None = None
    legal_form: str
    fiscal_year_start_month: int
    is_vat_payer: bool
    vat_filing_period: str
    is_active: bool

    model_config = {"from_attributes": True}
