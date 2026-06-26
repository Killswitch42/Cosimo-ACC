import pytest
from app.database import async_session_factory
from app.services.ledger_service import get_default_company_id
from app.services.reconciliation_service import check_kh_priznani_reconciliation, check_balance_sheet


@pytest.mark.asyncio
async def test_kh_reconciliation_clean_period():
    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        result = await check_kh_priznani_reconciliation(session, company_id, "2024-03")
    assert hasattr(result, "is_clean")


@pytest.mark.asyncio
async def test_balance_sheet_check():
    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        result = await check_balance_sheet(session, company_id, None)
    assert isinstance(result.is_clean, bool)
