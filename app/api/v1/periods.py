import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.services.ledger_service import LedgerError, get_default_company_id
from app.services.period_service import close_period, lock_period, open_period

router = APIRouter(prefix="/periods", tags=["periods"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.post("/{period_id}/open")
async def open_fiscal_period(
    period_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
        period = await open_period(session, company_id, period_id)
        return {"period_label": period.label, "status": period.status}
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{period_id}/close")
async def close_fiscal_period(
    period_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
        period = await close_period(session, company_id, period_id)
        return {"period_label": period.label, "status": period.status}
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{period_id}/lock")
async def lock_fiscal_period(
    period_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
        period = await lock_period(session, company_id, period_id)
        return {"period_label": period.label, "status": period.status}
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
