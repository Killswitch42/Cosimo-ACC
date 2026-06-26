import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_generate_vzz_returns_structure(client):
    """VZZ returns the correct dict structure."""
    from app.database import async_session_factory
    from app.services.vzz_service import generate_vzz
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

        data = await generate_vzz(session, company_id, period.id)

    assert "lines" in data
    assert "profit_before_tax" in data
    assert "net_profit_loss" in data
    assert isinstance(data["profit_before_tax"], Decimal)


@pytest.mark.asyncio
async def test_generate_vzz_all_line_codes_present(client):
    """All statutory VZZ line codes are returned."""
    from app.database import async_session_factory
    from app.services.vzz_service import generate_vzz, VZZ_LINE_MAP
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

        data = await generate_vzz(session, company_id, period.id)

    for line in VZZ_LINE_MAP:
        assert line in data["lines"], f"Missing VZZ line: {line}"


@pytest.mark.asyncio
async def test_generate_vzz_net_profit_derived_correctly(client):
    """net_profit_loss = profit_before_tax - income taxes (regardless of absolute values)."""
    from app.database import async_session_factory
    from app.services.vzz_service import generate_vzz
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

        data = await generate_vzz(session, company_id, period.id)

    # Verify the arithmetic relationship holds regardless of period content.
    expected_net = (
        data["profit_before_tax"]
        - data["income_tax_current"]
        - data["income_tax_deferred"]
    )
    assert data["net_profit_loss"] == expected_net
