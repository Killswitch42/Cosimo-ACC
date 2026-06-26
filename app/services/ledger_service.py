"""
Core ledger service — the single authorised path for posting journal entries.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_balance import AccountBalance
from app.models.fiscal_period import FiscalPeriod
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.ledger_account import LedgerAccount
from app.schemas.journal_entry import (
    JournalEntryCreate,
    JournalEntryLineCreate,
    ReversalRequest,
)
from app.services.cnb_fx_service import get_cnb_rate


class LedgerError(Exception):
    """Raised for accounting rule violations."""


async def get_default_company_id(session: AsyncSession) -> uuid.UUID:
    result = await session.execute(text("SELECT id FROM companies ORDER BY created_at LIMIT 1"))
    company_id = result.scalar_one_or_none()
    if not company_id:
        raise LedgerError("No company record found. Run the Phase 01 seed first.")
    return company_id


async def _get_open_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    entry_date: date,
) -> FiscalPeriod:
    result = await session.execute(
        select(FiscalPeriod).where(
            FiscalPeriod.company_id == company_id,
            FiscalPeriod.date_start <= entry_date,
            FiscalPeriod.date_end >= entry_date,
            FiscalPeriod.status == "open",
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise LedgerError(
            f"No open fiscal period found for date {entry_date}. "
            f"Open a period before posting. (§ 17 zákon 563/1991 Sb.)"
        )
    return period


async def _generate_entry_number(
    session: AsyncSession,
    company_id: uuid.UUID,
    entry_date: date,
) -> str:
    result = await session.execute(text("SELECT nextval('journal_entry_seq')"))
    seq = result.scalar()
    return f"MA-{entry_date.year}-{seq:06d}"


async def _validate_account_allows_posting(
    session: AsyncSession,
    account_number: str,
) -> LedgerAccount:
    result = await session.execute(
        select(LedgerAccount).where(
            LedgerAccount.account_number == account_number,
            LedgerAccount.is_active == True,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise LedgerError(f"Account {account_number} not found or inactive.")
    if not account.allows_posting:
        raise LedgerError(
            f"Account {account_number} ({account.name_cz}) is a synthetic group account "
            f"and does not allow direct posting. Use an analytical sub-account."
        )
    return account


async def _recompute_account_balance(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
    account_number: str,
) -> None:
    result = await session.execute(
        select(
            func.coalesce(
                func.sum(JournalEntryLine.amount_czk).filter(
                    JournalEntryLine.side == "DEBIT"
                ),
                Decimal("0.00"),
            ).label("total_debit"),
            func.coalesce(
                func.sum(JournalEntryLine.amount_czk).filter(
                    JournalEntryLine.side == "CREDIT"
                ),
                Decimal("0.00"),
            ).label("total_credit"),
            func.count(JournalEntryLine.id).label("entry_count"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntry.fiscal_period_id == fiscal_period_id,
            JournalEntry.status == "posted",
            JournalEntryLine.account_number == account_number,
        )
    )
    row = result.one()

    bal_result = await session.execute(
        select(AccountBalance).where(
            AccountBalance.fiscal_period_id == fiscal_period_id,
            AccountBalance.account_number == account_number,
        )
    )
    balance = bal_result.scalar_one_or_none()
    if not balance:
        balance = AccountBalance(
            id=uuid.uuid4(),
            company_id=company_id,
            fiscal_period_id=fiscal_period_id,
            account_number=account_number,
            opening_balance_czk=Decimal("0.00"),
        )
        session.add(balance)

    balance.period_debit_czk = row.total_debit
    balance.period_credit_czk = row.total_credit
    balance.entry_count = row.entry_count

    acct_result = await session.execute(
        select(LedgerAccount).where(LedgerAccount.account_number == account_number)
    )
    account = acct_result.scalar_one()

    if account.balance_type == "DEBIT":
        balance.closing_balance_czk = (
            balance.opening_balance_czk + row.total_debit - row.total_credit
        )
    else:
        balance.closing_balance_czk = (
            balance.opening_balance_czk + row.total_credit - row.total_debit
        )


async def post_journal_entry(
    session: AsyncSession,
    company_id: uuid.UUID,
    data: JournalEntryCreate,
    posted_by: str = "system",
    reverses_entry_id: uuid.UUID | None = None,
) -> JournalEntry:
    period = await _get_open_period(session, company_id, data.entry_date)

    for line in data.lines:
        await _validate_account_allows_posting(session, line.account_number)

    exchange_rate = Decimal("1.000000")
    if data.currency != "CZK":
        exchange_rate = await get_cnb_rate(session, data.currency, data.entry_date)

    total_debit = sum(line.amount_foreign for line in data.lines if line.side == "DEBIT")
    total_credit = sum(line.amount_foreign for line in data.lines if line.side == "CREDIT")
    if abs(total_debit - total_credit) > Decimal("0.01"):
        raise LedgerError(
            f"Entry does not balance: debits={total_debit}, credits={total_credit}"
        )

    entry_number = await _generate_entry_number(session, company_id, data.entry_date)
    now = datetime.now(timezone.utc)
    entry = JournalEntry(
        id=uuid.uuid4(),
        company_id=company_id,
        fiscal_period_id=period.id,
        entry_number=entry_number,
        entry_date=data.entry_date,
        entry_type=data.entry_type,
        status="posted",
        description=data.description,
        source_type=data.source_type,
        source_id=data.source_id,
        reverses_entry_id=reverses_entry_id,
        currency=data.currency,
        exchange_rate=exchange_rate,
        posted_by=posted_by,
        posted_at=now,
    )
    session.add(entry)
    await session.flush()

    affected_accounts = set()
    for index, line_data in enumerate(data.lines):
        amount_czk = (line_data.amount_foreign * exchange_rate).quantize(
            Decimal("0.01")
        )
        line = JournalEntryLine(
            id=uuid.uuid4(),
            journal_entry_id=entry.id,
            account_number=line_data.account_number,
            side=line_data.side,
            amount_foreign=line_data.amount_foreign,
            amount_czk=amount_czk,
            description=line_data.description,
            cost_centre=line_data.cost_centre,
            vat_rate=line_data.vat_rate,
            line_order=index,
        )
        session.add(line)
        affected_accounts.add(line_data.account_number)

    await session.flush()

    for account_number in affected_accounts:
        await _recompute_account_balance(session, company_id, period.id, account_number)

    await session.refresh(entry, attribute_names=["lines"])
    return entry


async def reverse_journal_entry(
    session: AsyncSession,
    original_entry_id: uuid.UUID,
    company_id: uuid.UUID,
    request: ReversalRequest,
    posted_by: str = "system",
) -> tuple[JournalEntry, JournalEntry | None]:
    result = await session.execute(
        select(JournalEntry).where(
            JournalEntry.id == original_entry_id,
            JournalEntry.company_id == company_id,
        )
    )
    original = result.scalar_one_or_none()
    if not original:
        raise LedgerError(f"Journal entry {original_entry_id} not found.")
    if original.status != "posted":
        raise LedgerError(
            f"Only posted entries can be reversed. Entry {original.entry_number} "
            f"has status '{original.status}'."
        )

    reversal_lines = [
        JournalEntryLineCreate(
            account_number=line.account_number,
            side="CREDIT" if line.side == "DEBIT" else "DEBIT",
            amount_foreign=line.amount_foreign,
            description=f"Opravný zápis: {line.description or ''}",
            cost_centre=line.cost_centre,
            vat_rate=line.vat_rate,
        )
        for line in original.lines
    ]
    reversal_data = JournalEntryCreate(
        entry_date=request.reversal_date,
        description=f"Opravný zápis k {original.entry_number}: {request.reason}",
        currency=original.currency,
        entry_type="REVERSAL",
        source_type=original.source_type,
        source_id=original.source_id,
        lines=reversal_lines,
    )

    reversal_entry = await post_journal_entry(
        session,
        company_id,
        reversal_data,
        posted_by,
        reverses_entry_id=original_entry_id,
    )

    await session.execute(
        text(
            "UPDATE journal_entries SET status = 'voided', updated_at = now() "
            "WHERE id = :id AND status = 'posted'"
        ),
        {"id": str(original_entry_id)},
    )
    for account_number in {line.account_number for line in original.lines}:
        await _recompute_account_balance(
            session, company_id, original.fiscal_period_id, account_number
        )

    correction_entry = None
    if request.correction_lines:
        correction_data = JournalEntryCreate(
            entry_date=request.reversal_date,
            description=f"Oprava po stornování {original.entry_number}: {request.reason}",
            currency=original.currency,
            entry_type="CORRECTION",
            lines=request.correction_lines,
        )
        correction_entry = await post_journal_entry(
            session, company_id, correction_data, posted_by
        )

    return reversal_entry, correction_entry


async def get_account_balance(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
    account_number: str,
) -> AccountBalance | None:
    result = await session.execute(
        select(AccountBalance).where(
            AccountBalance.company_id == company_id,
            AccountBalance.fiscal_period_id == fiscal_period_id,
            AccountBalance.account_number == account_number,
        )
    )
    return result.scalar_one_or_none()


async def get_trial_balance(
    session: AsyncSession,
    company_id: uuid.UUID,
    fiscal_period_id: uuid.UUID,
) -> list[AccountBalance]:
    result = await session.execute(
        select(AccountBalance)
        .where(
            AccountBalance.company_id == company_id,
            AccountBalance.fiscal_period_id == fiscal_period_id,
            AccountBalance.entry_count > 0,
        )
        .order_by(AccountBalance.account_number)
    )
    return list(result.scalars().all())
