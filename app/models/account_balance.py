"""
AccountBalance — pre-computed per-account per-period balances.
"""

from decimal import Decimal
import uuid

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AccountBalance(Base, TimestampMixin):
    __tablename__ = "account_balances"
    __table_args__ = (
        UniqueConstraint(
            "fiscal_period_id", "account_number", name="uq_balance_period_account"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fiscal_periods.id"), nullable=False, index=True
    )
    account_number: Mapped[str] = mapped_column(
        String(10), ForeignKey("ledger_accounts.account_number"), nullable=False, index=True
    )
    opening_balance_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    period_debit_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    period_credit_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    closing_balance_czk: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    entry_count: Mapped[int] = mapped_column(nullable=False, default=0)
