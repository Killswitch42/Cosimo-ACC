"""
Invoice register — issued and received invoices.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    invoice_type: Mapped[str] = mapped_column(
        String(15), nullable=False, default="STANDARD"
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    internal_reference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    duzp: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    counterparty_name: Mapped[str] = mapped_column(String(255), nullable=False)
    counterparty_ico: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    counterparty_dic: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    counterparty_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counterparty_country: Mapped[str] = mapped_column(String(2), nullable=False, default="CZ")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CZK")
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, default=Decimal("1.000000")
    )
    total_net_foreign: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    total_vat_foreign: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    total_gross_foreign: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    total_net_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    total_vat_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    total_gross_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    counterparty_is_vat_payer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_reverse_charge: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_eu_supply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ares_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ares_validation_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft", index=True)
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credits_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    vat_entries: Mapped[list["VatRegisterEntry"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class InvoiceLine(Base, TimestampMixin):
    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("1.0000")
    )
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_price_net: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("21.00")
    )
    line_net_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    line_vat_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    line_gross_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    account_number: Mapped[str | None] = mapped_column(
        String(10), ForeignKey("ledger_accounts.account_number"), nullable=True
    )
    cost_centre: Mapped[str | None] = mapped_column(String(50), nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")
