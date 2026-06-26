"""
Chart of accounts — Czech uctova osnova.

Based on: Vyhlaska c. 500/2002 Sb., pro podnikatele.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LedgerAccount(Base, TimestampMixin):
    __tablename__ = "ledger_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_number: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
    )
    name_cz: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_class: Mapped[int] = mapped_column(nullable=False)
    balance_type: Mapped[str] = mapped_column(String(8), nullable=False)
    account_type: Mapped[str] = mapped_column(String(15), nullable=False)
    parent_account_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_analytical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allows_posting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_vat_account: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    report_line_rozvaha: Mapped[str | None] = mapped_column(String(10), nullable=True)
    report_line_vzz: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
