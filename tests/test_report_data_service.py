import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_build_dph_priznani_data_empty_period(client):
    """Returns zeros for a period with no invoices posted."""
    from app.database import async_session_factory
    from app.services.report_data_service import build_dph_priznani_data
    from app.services.ledger_service import get_default_company_id

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        data = await build_dph_priznani_data(session, company_id, "2024-03")

    assert data["vat_period"] == "2024-03"
    assert data["row_01_base"] == Decimal("0.00")
    assert data["row_01_tax"]  == Decimal("0.00")
    assert data["row_65_net_vat"] == Decimal("0.00")
    assert not data["is_excess_deduction"]


@pytest.mark.asyncio
async def test_build_dph_data_after_invoice(client):
    """After posting an invoice, DPH data reflects the tax amounts."""
    issued_payload = {
        "direction": "ISSUED",
        "invoice_number": "RPT-TEST-001",
        "invoice_date": "2024-03-15",
        "duzp": "2024-03-10",
        "counterparty_name": "Zákazník s.r.o.",
        "counterparty_dic": "CZ11223344",
        "lines": [
            {
                "description": "Konzultace",
                "quantity": "1",
                "unit_price_net": "10000.00",
                "vat_rate": "21.00",
                "account_number": "602",
            }
        ],
    }
    resp = await client.post("/api/v1/invoices/", json=issued_payload)
    assert resp.status_code == 200

    from app.database import async_session_factory
    from app.services.report_data_service import build_dph_priznani_data
    from app.services.ledger_service import get_default_company_id

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        data = await build_dph_priznani_data(session, company_id, "2024-03")

    assert data["row_01_base"] == Decimal("10000.00")
    assert data["row_01_tax"]  == Decimal("2100.00")


@pytest.mark.asyncio
async def test_build_kh_data_empty_period(client):
    """Returns empty sections for period with no invoices."""
    from app.database import async_session_factory
    from app.services.report_data_service import build_kh_data
    from app.services.ledger_service import get_default_company_id

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        data = await build_kh_data(session, company_id, "2024-03")

    assert data["section_a1_detail"] == []
    assert data["section_b2_detail"] == []


@pytest.mark.asyncio
async def test_get_period_by_label_not_found(client):
    """Missing period raises ReportDataError."""
    from app.database import async_session_factory
    from app.services.report_data_service import get_period_by_label, ReportDataError
    from app.services.ledger_service import get_default_company_id

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        with pytest.raises(ReportDataError):
            await get_period_by_label(session, company_id, "1900")
