"""
Czech statutory deadline engine.
"""

from calendar import monthrange
from datetime import date, timedelta
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRecord


DEFAULT_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_25th_of_next_month(reference_date: date) -> date:
    year = reference_date.year + (reference_date.month == 12)
    month = 1 if reference_date.month == 12 else reference_date.month + 1
    return date(year, month, 25)


def _days_until(target: date) -> int:
    return (target - date.today()).days


def _severity_for_days(days: int) -> str:
    if days < 0:
        return "BLOCKER"
    if days <= 7:
        return "WARNING"
    return "INFO"


def build_deadline_calendar(reference_date: date, has_tax_advisor: bool = False) -> list[dict]:
    deadlines = []

    deadlines.append(
        {
            "code": "DPH_MONTHLY",
            "title": "DPH přiznání",
            "deadline_date": _get_25th_of_next_month(reference_date),
            "severity": _severity_for_days(_days_until(_get_25th_of_next_month(reference_date))),
        }
    )
    dppo_date = date(reference_date.year, 7, 1) if has_tax_advisor else date(reference_date.year, 4, 1)
    deadlines.append(
        {
            "code": "DPPO_ANNUAL",
            "title": "DPPO podání",
            "deadline_date": dppo_date,
            "severity": _severity_for_days(_days_until(dppo_date)),
        }
    )
    deadlines.append(
        {
            "code": "UCETNI_ZAVERKA",
            "title": "Účetní závěrka",
            "deadline_date": date(reference_date.year, 6, 30),
            "severity": _severity_for_days(_days_until(date(reference_date.year, 6, 30))),
        }
    )

    return sorted(deadlines, key=lambda d: d["deadline_date"])


from sqlalchemy import select

async def run_deadline_scan(
    session: AsyncSession,
    company_id: uuid.UUID,
    has_tax_advisor: bool = False,
) -> list[AlertRecord]:
    alerts_created = []
    deadlines = build_deadline_calendar(date.today(), has_tax_advisor)

    for dl in deadlines:
        days_until = (dl["deadline_date"] - date.today()).days
        if days_until > 14:
            continue

        existing = await session.execute(
            select(AlertRecord).where(
                AlertRecord.company_id == company_id,
                AlertRecord.rule_code == dl["code"],
                AlertRecord.status == "open",
            )
        )
        alert = existing.scalar_one_or_none()

        if alert:
            severity = dl["severity"]
            if severity == "BLOCKER" and alert.severity != "BLOCKER":
                alert.severity = "BLOCKER"
                alert.title = f"⚠️ KRITICKÝ TERMÍN: {alert.title}"
            elif severity == "WARNING" and alert.severity == "INFO":
                alert.severity = "WARNING"
            alerts_created.append(alert)
        else:
            new_alert = AlertRecord(
                id=uuid.uuid4(),
                company_id=company_id,
                severity=dl["severity"],
                category="DEADLINE",
                rule_code=dl["code"],
                title=dl["title"],
                detail=f"Filing deadline is {dl['deadline_date']}. Days until: {days_until}.",
                suggested_action="Ensure all bookkeeping records are complete and file in time.",
                deadline_date=dl["deadline_date"],
                status="open",
                ai_generated=False,
            )
            session.add(new_alert)
            alerts_created.append(new_alert)

    await session.flush()
    return alerts_created

