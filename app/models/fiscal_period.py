"""
Fiscal periods (ucetni obdobi).
Czech law (§ 3 zakon 563/1991 Sb.) defines the accounting period.
A period must be explicitly OPENED before posting and CLOSED before
the next period begins. Closed periods are immutable; corrections
require a new opravny zapis entry in the corrected period.
"""

from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FiscalPeriod(Base, TimestampMixin):
    __tablename__ = "fiscal_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(10), default="annual", nullable=False
    )
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="draft", nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="fiscal_periods")
