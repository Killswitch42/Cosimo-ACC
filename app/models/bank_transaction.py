"""
BankTransaction — STUB model for Phase 07.

This phase creates the schema and a placeholder import endpoint so the
integration point exists. Phase 07 implements actual bank API connectivity,
MT940/CSV import, and the matching engine (BankTransaction → Invoice).
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BankTransaction(Base, TimestampMixin):
    __tablename__ = "bank_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    bank_account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_czk: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # DEBIT (money out) or CREDIT (money in) — from the bank's perspective
    direction: Mapped[str] = mapped_column(String(6), nullable=False)

    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    variable_symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Matching status — populated by Phase 07's reconciliation engine
    matched_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True
    )
    matched_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    is_reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # UNMATCHED | SUGGESTED | MATCHED | IGNORED — drives the reconciliation UI.
    match_status: Mapped[str] = mapped_column(
        String(15), nullable=False, default="UNMATCHED"
    )

    # Source: MANUAL_CSV | MT940 | API_<bank_name> — set by Phase 07
    import_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="MANUAL_CSV"
    )
