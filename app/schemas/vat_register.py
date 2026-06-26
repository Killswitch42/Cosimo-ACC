from datetime import date
from decimal import Decimal
import uuid

from pydantic import BaseModel


class VatRegisterEntryResponse(BaseModel):
    id: uuid.UUID
    vat_period: str
    direction: str
    invoice_number: str
    invoice_date: date
    duzp: date
    counterparty_name: str
    counterparty_dic: str | None
    vat_rate: Decimal
    tax_base_czk: Decimal
    tax_amount_czk: Decimal
    kh_section: str
    kh_detail_required: bool

    model_config = {"from_attributes": True}
