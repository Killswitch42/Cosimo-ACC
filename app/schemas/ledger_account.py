from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class LedgerAccountRead(BaseModel):
    id: UUID
    account_number: str
    name_cz: str
    name_en: str | None = None
    account_class: int
    balance_type: str
    account_type: str
    parent_account_number: str | None = None
    is_synthetic: bool
    is_analytical: bool
    allows_posting: bool
    is_vat_account: bool
    vat_rate: Decimal | None = None
    report_line_rozvaha: str | None = None
    report_line_vzz: str | None = None
    is_active: bool
    notes: str | None = None

    model_config = {"from_attributes": True}
