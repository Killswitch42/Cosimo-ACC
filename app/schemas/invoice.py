from datetime import date
from decimal import Decimal
from typing import Optional
import uuid

from pydantic import BaseModel, field_validator, model_validator

VALID_VAT_RATES = {Decimal("0"), Decimal("0.00"), Decimal("12"), Decimal("12.00"), Decimal("21"), Decimal("21.00")}


class InvoiceLineCreate(BaseModel):
    description: str
    quantity: Decimal = Decimal("1.0000")
    unit: Optional[str] = None
    unit_price_net: Decimal
    vat_rate: Decimal = Decimal("21.00")
    account_number: Optional[str] = None
    cost_centre: Optional[str] = None

    @field_validator("vat_rate")
    @classmethod
    def vat_rate_must_be_valid(cls, value):
        if value not in VALID_VAT_RATES:
            raise ValueError(
                f"Invalid VAT rate {value}%. Valid Czech DPH rates from 2024: 0%, 12%, 21%."
            )
        return value

    @field_validator("quantity", "unit_price_net")
    @classmethod
    def must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("quantity and unit_price_net must be positive")
        return value


class InvoiceCreate(BaseModel):
    direction: str
    invoice_type: str = "STANDARD"
    invoice_number: str
    internal_reference: Optional[str] = None
    invoice_date: date
    duzp: date
    due_date: Optional[date] = None
    variable_symbol: Optional[str] = None
    counterparty_name: str
    counterparty_ico: Optional[str] = None
    counterparty_dic: Optional[str] = None
    counterparty_address: Optional[str] = None
    counterparty_country: str = "CZ"
    currency: str = "CZK"
    counterparty_is_vat_payer: bool = True
    is_reverse_charge: bool = False
    is_eu_supply: bool = False
    notes: Optional[str] = None
    lines: list[InvoiceLineCreate]

    @field_validator("direction")
    @classmethod
    def direction_must_be_valid(cls, value):
        if value not in ("ISSUED", "RECEIVED"):
            raise ValueError("direction must be ISSUED or RECEIVED")
        return value

    @field_validator("lines")
    @classmethod
    def must_have_at_least_one_line(cls, value):
        if not value:
            raise ValueError("Invoice must have at least one line")
        return value

    @model_validator(mode="after")
    def eu_supply_requires_eu_dic(self):
        if self.is_eu_supply:
            if not self.counterparty_dic:
                raise ValueError("EU zero-rated supplies (§ 64 ZDPH) require the buyer's EU VAT number.")
            if self.counterparty_dic.upper().startswith("CZ"):
                raise ValueError("EU zero-rated supply cannot have a Czech DIČ.")
        return self

    @model_validator(mode="after")
    def reverse_charge_must_be_received(self):
        if self.is_reverse_charge and self.direction != "RECEIVED":
            raise ValueError("Reverse charge (§ 92a) applies to received invoices only.")
        return self


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    direction: str
    invoice_type: str
    invoice_number: str
    invoice_date: date
    duzp: date
    variable_symbol: Optional[str] = None
    counterparty_name: str
    counterparty_dic: Optional[str]
    status: str
    total_net_czk: Decimal
    total_vat_czk: Decimal
    total_gross_czk: Decimal
    journal_entry_id: Optional[uuid.UUID]
    ares_validated: bool
    ares_validation_note: Optional[str]

    model_config = {"from_attributes": True}
