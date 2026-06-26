"""
FxRate — daily CNB (Czech National Bank) exchange rates.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FxRate(Base, TimestampMixin):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("rate_date", "currency_code", name="uq_fx_rate_date_currency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    currency_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    rate_czk: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    unit_rate_czk: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(10), default="CNB", nullable=False)
