"""
ClassificationLog — immutable record of every AI classification request.
"""

from decimal import Decimal
import uuid

from sqlalchemy import String, Text, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ClassificationLog(Base, TimestampMixin):
    __tablename__ = "classification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    classification_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    input_context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    suggested_debit_account: Mapped[str | None] = mapped_column(String(10), nullable=True)
    suggested_credit_account: Mapped[str | None] = mapped_column(String(10), nullable=True)
    suggested_vat_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    suggested_cost_centre: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    was_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    override_debit_account: Mapped[str | None] = mapped_column(String(10), nullable=True)
    override_credit_account: Mapped[str | None] = mapped_column(String(10), nullable=True)
    model_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="claude-sonnet-4-6"
    )
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
