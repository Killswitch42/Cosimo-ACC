from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.fiscal_period import FiscalPeriod
from app.services.ledger_service import (
    LedgerError,
    get_default_company_id,
    get_trial_balance,
)

router = APIRouter(prefix="/account-balances", tags=["ledger"])


async def get_session():
    async with async_session_factory() as session:
        yield session


@router.get("/trial-balance")
async def trial_balance(
    period_label: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
    except LedgerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if period_label:
        result = await session.execute(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id == company_id,
                FiscalPeriod.label == period_label,
            )
        )
        period = result.scalar_one_or_none()
        if not period:
            raise HTTPException(status_code=404, detail=f"Period '{period_label}' not found.")
    else:
        result = await session.execute(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id == company_id,
                FiscalPeriod.is_current == True,
            )
        )
        period = result.scalar_one_or_none()
        if not period:
            raise HTTPException(status_code=404, detail="No current period found.")

    balances = await get_trial_balance(session, company_id, period.id)
    return {
        "period_label": period.label,
        "period_status": period.status,
        "accounts": [
            {
                "account_number": balance.account_number,
                "opening_balance_czk": str(balance.opening_balance_czk),
                "period_debit_czk": str(balance.period_debit_czk),
                "period_credit_czk": str(balance.period_credit_czk),
                "closing_balance_czk": str(balance.closing_balance_czk),
                "entry_count": balance.entry_count,
            }
            for balance in balances
        ],
        "total_debits": str(sum(balance.period_debit_czk for balance in balances)),
        "total_credits": str(sum(balance.period_credit_czk for balance in balances)),
    }
