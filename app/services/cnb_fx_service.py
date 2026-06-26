"""
Czech National Bank exchange rate service.
"""

from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.fx_rate import FxRate


class FxRateError(Exception):
    pass


async def _fetch_from_cnb(rate_date: date) -> list[dict]:
    url = f"{settings.cnb_api_base_url}/daily"
    params = {"date": rate_date.strftime("%Y-%m-%d"), "lang": "EN"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
        return data.get("rates", [])


async def _store_rates(session: AsyncSession, rate_date: date, rates: list[dict]) -> None:
    for rate in rates:
        existing_result = await session.execute(
            select(FxRate).where(
                FxRate.rate_date == rate_date,
                FxRate.currency_code == rate["currencyCode"],
            )
        )
        if existing_result.scalar_one_or_none():
            continue
        quantity = rate.get("amount", 1)
        rate_czk = Decimal(str(rate["rate"]))
        unit_rate = (rate_czk / Decimal(str(quantity))).quantize(Decimal("0.000001"))
        fx = FxRate(
            rate_date=rate_date,
            currency_code=rate["currencyCode"],
            currency_name=rate.get("currency", ""),
            quantity=quantity,
            rate_czk=rate_czk,
            unit_rate_czk=unit_rate,
            source="CNB",
        )
        session.add(fx)
    await session.flush()


async def get_cnb_rate(
    session: AsyncSession,
    currency_code: str,
    for_date: date,
) -> Decimal:
    if currency_code == "CZK":
        return Decimal("1.000000")

    for days_back in range(11):
        check_date = for_date - timedelta(days=days_back)
        result = await session.execute(
            select(FxRate).where(
                FxRate.rate_date == check_date,
                FxRate.currency_code == currency_code,
            )
        )
        cached = result.scalar_one_or_none()
        if cached:
            return cached.unit_rate_czk

        rates = await _fetch_from_cnb(check_date)
        if rates:
            await _store_rates(session, check_date, rates)
            for rate in rates:
                if rate["currencyCode"] == currency_code:
                    quantity = rate.get("amount", 1)
                    rate_czk = Decimal(str(rate["rate"]))
                    return (rate_czk / Decimal(str(quantity))).quantize(
                        Decimal("0.000001")
                    )

    raise FxRateError(
        f"No CNB rate found for {currency_code} within 10 days of {for_date}. "
        f"Check that {currency_code} is a valid currency quoted by CNB."
    )
