from datetime import date
from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_czk_rate_is_one():
    from app.database import async_session_factory
    from app.services.cnb_fx_service import get_cnb_rate

    async with async_session_factory() as session:
        rate = await get_cnb_rate(session, "CZK", date.today())
        assert rate == Decimal("1.000000")


@pytest.mark.asyncio
async def test_eur_rate_is_reasonable():
    from app.database import async_session_factory
    from app.services.cnb_fx_service import get_cnb_rate

    async with async_session_factory() as session:
        rate = await get_cnb_rate(session, "EUR", date(2024, 6, 3))
        assert Decimal("20") < rate < Decimal("35"), f"Unexpected EUR rate: {rate}"


@pytest.mark.asyncio
async def test_invalid_currency_raises():
    from app.database import async_session_factory
    from app.services.cnb_fx_service import FxRateError, get_cnb_rate

    async with async_session_factory() as session:
        with pytest.raises(FxRateError):
            await get_cnb_rate(session, "XYZ", date(2024, 6, 3))
