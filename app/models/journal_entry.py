"""
Journal entries — the immutable ledger of all financial transactions.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fiscal_periods.id"), nullable=False, index=True
    )
    entry_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    posting_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(
        String(15), nullable=False, default="STANDARD"
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    reverses_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CZK")
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, default=Decimal("1.000000")
    )
    posted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_classification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    lines: Mapped[list["JournalEntryLine"]] = relationship(
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class JournalEntryLine(Base, TimestampMixin):
    __tablename__ = "journal_entry_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=False, index=True
    )
    account_number: Mapped[str] = mapped_column(
        String(10), ForeignKey("ledger_accounts.account_number"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(6), nullable=False)
    amount_foreign: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount_czk: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost_centre: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    line_order: Mapped[int] = mapped_column(nullable=False, default=0)

    journal_entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    ledger_account: Mapped["LedgerAccount"] = relationship(
        "LedgerAccount",
        foreign_keys=[account_number],
        primaryjoin="JournalEntryLine.account_number == LedgerAccount.account_number",
    )
