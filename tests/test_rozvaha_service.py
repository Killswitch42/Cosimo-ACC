import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_generate_rozvaha_returns_structure(client):
    """Rozvaha returns the correct dict structure with aktiva/pasiva sections."""
    from app.database import async_session_factory
    from app.services.rozvaha_service import generate_rozvaha
    from app.services.ledger_service import get_default_company_id
    from app.models.fiscal_period import FiscalPeriod
    from sqlalchemy import select

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        period_result = await session.execute(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id == company_id,
                FiscalPeriod.is_current == True,
            )
        )
        period = period_result.scalar_one_or_none()
        if not period:
            pytest.skip("No current fiscal period.")

        data = await generate_rozvaha(session, company_id, period.id)

    assert "aktiva" in data
    assert "pasiva" in data
    assert "aktiva_celkem" in data
    assert "pasiva_celkem" in data
    assert "is_balanced" in data
    assert isinstance(data["aktiva_celkem"], Decimal)
    assert isinstance(data["pasiva_celkem"], Decimal)


@pytest.mark.asyncio
async def test_generate_rozvaha_all_keys_present(client):
    """All statutory rozvaha line codes are present in the output."""
    from app.database import async_session_factory
    from app.services.rozvaha_service import generate_rozvaha, AKTIVA_LINE_MAP, PASIVA_LINE_MAP
    from app.services.ledger_service import get_default_company_id
    from app.models.fiscal_period import FiscalPeriod
    from sqlalchemy import select

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        period_result = await session.execute(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id == company_id,
                FiscalPeriod.is_current == True,
            )
        )
        period = period_result.scalar_one_or_none()
        if not period:
            pytest.skip("No current fiscal period.")

        data = await generate_rozvaha(session, company_id, period.id)

    for line in AKTIVA_LINE_MAP:
        assert line in data["aktiva"], f"Missing aktiva line: {line}"
    for line in PASIVA_LINE_MAP:
        assert line in data["pasiva"], f"Missing pasiva line: {line}"


@pytest.mark.asyncio
async def test_generate_rozvaha_returns_decimal_totals(client):
    """Rozvaha totals are Decimal values regardless of period content."""
    from app.database import async_session_factory
    from app.services.rozvaha_service import generate_rozvaha
    from app.services.ledger_service import get_default_company_id
    from app.models.fiscal_period import FiscalPeriod
    from sqlalchemy import select

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        period_result = await session.execute(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id == company_id,
                FiscalPeriod.is_current == True,
            )
        )
        period = period_result.scalar_one_or_none()
        if not period:
            pytest.skip("No current fiscal period.")

        data = await generate_rozvaha(session, company_id, period.id)

    # Totals are Decimals; balance check is a bool — that's all we can assert
    # mid-year without a year-end close (P&L accounts don't map to the balance sheet).
    assert isinstance(data["aktiva_celkem"], Decimal)
    assert isinstance(data["pasiva_celkem"], Decimal)
    assert isinstance(data["is_balanced"], bool)
    assert isinstance(data["difference"], Decimal)


def _duplicate_accounts(line_map):
    """Return accounts that appear in more than one line of a single side."""
    from collections import Counter

    counts = Counter(acct for accounts in line_map.values() for acct in accounts)
    return {acct: n for acct, n in counts.items() if n > 1}


@pytest.mark.asyncio
async def test_dual_nature_accounts_routed_by_balance_sign(client):
    """341/342 are receivables (aktiva) in a net-debit position and payables
    (pasiva) in a net-credit position. They must land on exactly one side per
    their balance sign — never summed into both."""
    from datetime import date
    from app.database import async_session_factory
    from app.services.rozvaha_service import generate_rozvaha
    from app.services.ledger_service import get_default_company_id
    from app.models.account_balance import AccountBalance
    from app.models.fiscal_period import FiscalPeriod
    from sqlalchemy import select, delete

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)

        # A throwaway period isolated from every other test's postings.
        label = "rozvaha-p0b-test"
        period = (
            await session.execute(
                select(FiscalPeriod).where(
                    FiscalPeriod.company_id == company_id,
                    FiscalPeriod.label == label,
                )
            )
        ).scalar_one_or_none()
        if not period:
            period = FiscalPeriod(
                company_id=company_id, label=label, period_type="annual",
                date_start=date(2099, 1, 1), date_end=date(2099, 12, 31),
                status="open", is_current=False,
            )
            session.add(period)
            await session.flush()

        # Clean slate on re-run (account_balances is not immutable).
        await session.execute(
            delete(AccountBalance).where(AccountBalance.fiscal_period_id == period.id)
        )
        # closing_balance_czk is credit-normal for these accounts:
        #   341 net DEBIT  -> stored negative -> receivable (aktiva C.II)
        #   342 net CREDIT -> stored positive -> payable    (pasiva B.III)
        session.add_all([
            AccountBalance(
                company_id=company_id, fiscal_period_id=period.id,
                account_number="341", closing_balance_czk=Decimal("-5000.00"),
                entry_count=1,
            ),
            AccountBalance(
                company_id=company_id, fiscal_period_id=period.id,
                account_number="342", closing_balance_czk=Decimal("3000.00"),
                entry_count=1,
            ),
        ])
        await session.commit()

        data = await generate_rozvaha(session, company_id, period.id)

        # 341 receivable -> aktiva C.II only; 342 payable -> pasiva B.III only.
        assert data["aktiva"]["C.II"] == Decimal("5000.00")
        assert data["pasiva"]["B.III"] == Decimal("3000.00")
        # The receivable is NOT also sitting in pasiva (and vice versa).
        assert data["aktiva"]["C.II"] == data["aktiva_celkem"]
        assert data["pasiva"]["B.III"] == data["pasiva_celkem"]

        # Cleanup so the throwaway period leaves no residue.
        await session.execute(
            delete(AccountBalance).where(AccountBalance.fiscal_period_id == period.id)
        )
        await session.commit()


def test_no_account_double_counted_within_a_side():
    """Regression: an account mapped into two lines of the same side is summed
    twice into that side's total (e.g. 383/384/389 were once in both B.III and C),
    inflating aktiva/pasiva and silently breaking the balance check."""
    from app.services.rozvaha_service import AKTIVA_LINE_MAP, PASIVA_LINE_MAP

    aktiva_dupes = _duplicate_accounts(AKTIVA_LINE_MAP)
    pasiva_dupes = _duplicate_accounts(PASIVA_LINE_MAP)
    assert not aktiva_dupes, f"Accounts double-counted in AKTIVA: {aktiva_dupes}"
    assert not pasiva_dupes, f"Accounts double-counted in PASIVA: {pasiva_dupes}"
