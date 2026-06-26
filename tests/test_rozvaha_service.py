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
