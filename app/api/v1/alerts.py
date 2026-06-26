import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.alert import AlertRecord
from app.schemas.alert import AlertResponse
from app.services.ledger_service import get_default_company_id

router = APIRouter(prefix="/alerts", tags=["alerts"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    severity: str | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    company_id = await get_default_company_id(session)
    query = select(AlertRecord).where(AlertRecord.company_id == company_id)
    if severity:
        query = query.where(AlertRecord.severity == severity)
    if category:
        query = query.where(AlertRecord.category == category)
    if status:
        query = query.where(AlertRecord.status == status)
    result = await session.execute(query.order_by(AlertRecord.severity, AlertRecord.created_at.desc()))
    return list(result.scalars().all())


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: uuid.UUID,
    resolved_by: str | None = None,
    resolution_note: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    company_id = await get_default_company_id(session)
    result = await session.execute(
        select(AlertRecord).where(AlertRecord.id == alert_id, AlertRecord.company_id == company_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    alert.status = "resolved"
    alert.resolved_by = resolved_by
    alert.resolution_note = resolution_note
    alert.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return {"status": "resolved", "alert_id": str(alert_id)}
