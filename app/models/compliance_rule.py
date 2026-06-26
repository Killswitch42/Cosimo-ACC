"""
ComplianceRule — registry of Czech statutory rules enforced by the watchdog.
"""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ComplianceRule(Base, TimestampMixin):
    __tablename__ = "compliance_rules"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name_cz: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(15), nullable=False)
    default_severity: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
