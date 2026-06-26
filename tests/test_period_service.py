from datetime import date
import uuid

import pytest


@pytest.mark.asyncio
async def test_close_period_with_no_drafts():
    from app.database import async_session_factory
    from app.models.fiscal_period import FiscalPeriod
    from app.services.ledger_service import get_default_company_id
    from app.services.period_service import close_period

    async with async_session_factory() as session:
        async with session.begin():
            company_id = await get_default_company_id(session)
            period = FiscalPeriod(
                id=uuid.uuid4(),
                company_id=company_id,
                label=f"TEST-{uuid.uuid4().hex[:8]}",
                period_type="annual",
                date_start=date(2030, 1, 1),
                date_end=date(2030, 12, 31),
                status="open",
                is_current=False,
            )
            session.add(period)
            await session.flush()
            closed = await close_period(session, company_id, period.id)
            assert closed.status == "closed"


@pytest.mark.asyncio
async def test_cannot_post_to_closed_period(client):
    payload = {
        "entry_date": "2020-01-01",
        "description": "Closed period post attempt",
        "lines": [
            {"account_number": "112", "side": "DEBIT", "amount_foreign": 10.00},
            {"account_number": "221", "side": "CREDIT", "amount_foreign": 10.00},
        ],
    }
    response = await client.post("/api/v1/journal-entries/", json=payload)
    assert response.status_code == 422
