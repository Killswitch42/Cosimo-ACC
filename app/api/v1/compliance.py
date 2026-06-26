from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.services.deadline_service import build_deadline_calendar, run_deadline_scan
from app.services.watchdog_service import scan_vat_period
from app.services.ledger_service import get_default_company_id

router = APIRouter(prefix="/compliance", tags=["compliance"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.get("/deadlines")
async def get_deadlines(
    has_tax_advisor: bool = Query(False),
):
    deadlines = build_deadline_calendar(date.today(), has_tax_advisor=has_tax_advisor)
    for item in deadlines:
        item["days_until"] = (item["deadline_date"] - date.today()).days
    return {"deadlines": deadlines}


@router.post("/scan")
async def trigger_compliance_scan(
    vat_period: str = Query(..., description="Format: YYYY-MM"),
    session: AsyncSession = Depends(get_session),
):
    company_id = await get_default_company_id(session)
    deadline_alerts = await run_deadline_scan(session, company_id)
    period_alerts = await scan_vat_period(session, company_id, vat_period)
    return {
        "vat_period": vat_period,
        "deadline_alerts_created": len(deadline_alerts),
        "period_alerts_created": len(period_alerts),
        "total_alerts": len(deadline_alerts) + len(period_alerts),
    }
