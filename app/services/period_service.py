"""
Fiscal period lifecycle management.
"""

from decimal import Decimal
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_balance import AccountBalance
from app.models.fiscal_period import FiscalPeriod
from app.models.ledger_account import LedgerAccount
from app.services.ledger_service import LedgerError


async def open_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
) -> FiscalPeriod:
    result = await session.execute(
        select(FiscalPeriod).where(
            FiscalPeriod.id == fiscal_period_id,
            FiscalPeriod.company_id == company_id,
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise LedgerError("Fiscal period not found.")
    if period.status != "draft":
        raise LedgerError(
            f"Period '{period.label}' is '{period.status}' — can only open a draft period."
        )
    period.status = "open"
    period.is_current = True
    return period


async def close_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
) -> FiscalPeriod:
    result = await session.execute(
        select(FiscalPeriod).where(
            FiscalPeriod.id == fiscal_period_id,
            FiscalPeriod.company_id == company_id,
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise LedgerError("Fiscal period not found.")
    if period.status != "open":
        raise LedgerError(
            f"Period '{period.label}' is '{period.status}' — can only close an open period."
        )

    from app.models.journal_entry import JournalEntry

    draft_count_result = await session.execute(
        select(func.count()).where(
            JournalEntry.fiscal_period_id == fiscal_period_id,
            JournalEntry.status == "draft",
        )
    )
    draft_count = draft_count_result.scalar()
    if draft_count > 0:
        raise LedgerError(
            f"Cannot close period '{period.label}': {draft_count} draft entries exist. "
            f"Post or delete all drafts before closing."
        )

    period.status = "closed"
    period.is_current = False
    await session.flush()

    next_period_result = await session.execute(
        select(FiscalPeriod)
        .where(
            FiscalPeriod.company_id == company_id,
            FiscalPeriod.date_start > period.date_end,
            FiscalPeriod.status.in_(["draft", "open"]),
        )
        .order_by(FiscalPeriod.date_start)
        .limit(1)
    )
    next_period = next_period_result.scalar_one_or_none()

    if next_period:
        balances_result = await session.execute(
            select(AccountBalance, LedgerAccount)
            .join(
                LedgerAccount,
                AccountBalance.account_number == LedgerAccount.account_number,
            )
            .where(
                AccountBalance.fiscal_period_id == fiscal_period_id,
                LedgerAccount.account_class.in_([0, 1, 2, 3, 4]),
            )
        )
        for balance, account in balances_result.all():
            if balance.closing_balance_czk != Decimal("0.00"):
                new_opening = AccountBalance(
                    id=uuid.uuid4(),
                    company_id=company_id,
                    fiscal_period_id=next_period.id,
                    account_number=balance.account_number,
                    opening_balance_czk=balance.closing_balance_czk,
                    period_debit_czk=Decimal("0.00"),
                    period_credit_czk=Decimal("0.00"),
                    closing_balance_czk=balance.closing_balance_czk,
                    entry_count=0,
                )
                session.add(new_opening)

    return period


async def lock_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
) -> FiscalPeriod:
    result = await session.execute(
        select(FiscalPeriod).where(
            FiscalPeriod.id == fiscal_period_id,
            FiscalPeriod.company_id == company_id,
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise LedgerError("Fiscal period not found.")
    if period.status != "closed":
        raise LedgerError(f"Period '{period.label}' must be closed before locking.")
    period.status = "locked"
    return period
