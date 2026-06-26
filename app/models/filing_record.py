"""
FilingRecord — tracks every generated statutory report.
"""
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import uuid


class FilingRecord(Base, TimestampMixin):
    __tablename__ = "filing_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    # DPH_PRIZNANI | KONTROLNI_HLASENI | SOUHRNNE_HLASENI | ROZVAHA | VZZ
    filing_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # "2024-03" for monthly, "2024-Q1" for quarterly, "2024" for annual
    period_label: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # draft → reconciled → generated → submitted → amended
    status: Mapped[str] = mapped_column(
        String(15), nullable=False, default="draft", index=True
    )

    reconciliation_passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reconciliation_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    amends_filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filing_records.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
