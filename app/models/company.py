"""
Company master record for Medici Analytica s.r.o.
The system is designed for a single company but the companies table
allows future multi-entity support (e.g. subsidiaries).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ico: Mapped[str | None] = mapped_column(String(8), unique=True, nullable=True)
    dic: Mapped[str | None] = mapped_column(String(12), unique=True, nullable=True)
    registered_office: Mapped[str | None] = mapped_column(String(500), nullable=True)
    legal_form: Mapped[str] = mapped_column(String(50), default="s.r.o.", nullable=False)
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_vat_payer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    vat_filing_period: Mapped[str] = mapped_column(
        String(10), default="monthly", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    fiscal_periods: Mapped[list["FiscalPeriod"]] = relationship(back_populates="company")
