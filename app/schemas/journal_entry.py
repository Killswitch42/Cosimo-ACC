from datetime import date
from decimal import Decimal
from typing import Optional
import uuid

from pydantic import BaseModel, field_validator, model_validator


class JournalEntryLineCreate(BaseModel):
    account_number: str
    side: str
    amount_foreign: Decimal
    description: Optional[str] = None
    cost_centre: Optional[str] = None
    vat_rate: Optional[Decimal] = None
    line_order: int = 0

    @field_validator("side")
    @classmethod
    def side_must_be_valid(cls, value):
        if value not in ("DEBIT", "CREDIT"):
            raise ValueError("side must be DEBIT or CREDIT")
        return value

    @field_validator("amount_foreign")
    @classmethod
    def amount_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("amount must be positive")
        return value


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str
    currency: str = "CZK"
    entry_type: str = "STANDARD"
    source_type: Optional[str] = None
    source_id: Optional[uuid.UUID] = None
    lines: list[JournalEntryLineCreate]

    @field_validator("lines")
    @classmethod
    def must_have_at_least_two_lines(cls, value):
        if len(value) < 2:
            raise ValueError("A journal entry must have at least 2 lines")
        return value

    @model_validator(mode="after")
    def debits_must_equal_credits(self):
        debits = sum(line.amount_foreign for line in self.lines if line.side == "DEBIT")
        credits = sum(line.amount_foreign for line in self.lines if line.side == "CREDIT")
        if abs(debits - credits) > Decimal("0.01"):
            raise ValueError(
                f"Journal entry does not balance: debits={debits}, credits={credits}"
            )
        return self


class JournalEntryLineResponse(BaseModel):
    account_number: str
    side: str
    amount_foreign: Decimal
    amount_czk: Decimal
    description: str | None = None
    cost_centre: str | None = None
    vat_rate: Decimal | None = None
    line_order: int

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    entry_number: str
    entry_date: date
    entry_type: str
    status: str
    description: str
    currency: str
    exchange_rate: Decimal
    lines: list[JournalEntryLineResponse]

    model_config = {"from_attributes": True}


class ReversalRequest(BaseModel):
    reversal_date: date
    reason: str
    correction_lines: Optional[list[JournalEntryLineCreate]] = None
