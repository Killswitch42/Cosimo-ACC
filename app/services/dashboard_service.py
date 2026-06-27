"""
Dashboard aggregation service — pulls together everything the main
dashboard view needs in as few queries as possible.
"""
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRecord
from app.models.invoice import Invoice
from app.services.deadline_service import build_deadline_calendar


async def get_dashboard_summary(
    session: AsyncSession,
    company_id: uuid.UUID,
    has_tax_advisor: bool = False,
) -> dict:
    """Single call that returns everything the dashboard template needs."""

    # Open alerts by severity
    alert_counts_result = await session.execute(
        select(AlertRecord.severity, func.count(AlertRecord.id))
        .where(AlertRecord.company_id == company_id, AlertRecord.status == "open")
        .group_by(AlertRecord.severity)
    )
    alert_counts = {row[0]: row[1] for row in alert_counts_result.all()}

    # Recent open alerts (top 10, BLOCKER first)
    recent_alerts_result = await session.execute(
        select(AlertRecord)
        .where(AlertRecord.company_id == company_id, AlertRecord.status == "open")
        .order_by(AlertRecord.severity.desc(), AlertRecord.created_at.desc())
        .limit(10)
    )
    recent_alerts = list(recent_alerts_result.scalars().all())

    # Upcoming deadlines (next 30 days), with days_until computed
    today = date.today()
    deadlines = []
    for d in build_deadline_calendar(today, has_tax_advisor):
        days_until = (d["deadline_date"] - today).days
        if days_until <= 30:
            deadlines.append({**d, "days_until": days_until})

    # Unpaid issued invoice total
    unpaid_issued_result = await session.execute(
        select(func.coalesce(func.sum(Invoice.total_gross_czk), 0))
        .where(
            Invoice.company_id == company_id,
            Invoice.direction == "ISSUED",
            Invoice.status == "posted",
            Invoice.payment_date.is_(None),
        )
    )
    unpaid_issued_total = unpaid_issued_result.scalar()

    # Unpaid received invoice total
    unpaid_received_result = await session.execute(
        select(func.coalesce(func.sum(Invoice.total_gross_czk), 0))
        .where(
            Invoice.company_id == company_id,
            Invoice.direction == "RECEIVED",
            Invoice.status == "posted",
            Invoice.payment_date.is_(None),
        )
    )
    unpaid_received_total = unpaid_received_result.scalar()

    return {
        "alert_counts": alert_counts,
        "recent_alerts": recent_alerts,
        "deadlines": deadlines,
        "unpaid_issued_total": unpaid_issued_total,
        "unpaid_received_total": unpaid_received_total,
    }
