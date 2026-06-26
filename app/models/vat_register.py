"""
VAT register — transaction-level DPH data.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class VatRegisterEntry(Base, TimestampMixin):
    __tablename__ = "vat_register"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True
    )
    vat_period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    duzp: Mapped[date] = mapped_column(Date, nullable=False)
    counterparty_name: Mapped[str] = mapped_column(String(255), nullable=False)
    counterparty_dic: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    counterparty_country: Mapped[str] = mapped_column(String(2), nullable=False, default="CZ")
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_base_czk: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount_czk: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    kh_section: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    kh_detail_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_reverse_charge: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_eu_supply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    eu_supply_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zdph_paragraph: Mapped[str | None] = mapped_column(String(10), nullable=True)
    kh_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kh_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priznani_submitted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    priznani_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="vat_entries")
