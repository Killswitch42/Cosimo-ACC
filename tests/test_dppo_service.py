from decimal import Decimal

import pytest

from app.services.dppo_service import dppo_rate
from app.services.pdf_report_service import render_dppo_pdf


def test_dppo_rate_by_year():
    assert dppo_rate(2024) == Decimal("21")
    assert dppo_rate(2025) == Decimal("21")
    assert dppo_rate(2023) == Decimal("19")


def test_render_dppo_pdf_returns_pdf_bytes():
    data = {
        "year": 2024,
        "profit_before_tax": Decimal("15000.00"),
        "adjustments": [
            {"account": "513", "label": "Reprezentace", "amount": Decimal("10000.00")}
        ],
        "total_adjustments": Decimal("10000.00"),
        "tax_base": Decimal("25000.00"),
        "rounded_tax_base": Decimal("25000"),
        "rate": Decimal("21"),
        "tax": Decimal("5250"),
        "net_profit_after_tax": Decimal("9750.00"),
        "is_simplified": True,
    }
    pdf = render_dppo_pdf("Medici Analytica s.r.o.", "12345678", "2024", data)
    assert isinstance(pdf, bytes)
    assert pdf[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_compute_dppo_relationships(client, monkeypatch):
    """The DPPO figures are internally consistent, whatever the period holds."""
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)

    from app.database import async_session_factory
    from app.services.ledger_service import get_default_company_id
    from app.services.dppo_service import compute_dppo
    from app.models.fiscal_period import FiscalPeriod
    from sqlalchemy import select

    async with async_session_factory() as session:
        company_id = await get_default_company_id(session)
        period = await session.scalar(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id == company_id,
                FiscalPeriod.is_current == True,
            )
        )
        if not period:
            pytest.skip("No current fiscal period.")
        data = await compute_dppo(session, company_id, period.id, 2024)

    assert data["rate"] == Decimal("21")
    assert data["is_simplified"] is True
    # Base = accounting profit + non-deductible add-backs.
    assert data["tax_base"] == data["profit_before_tax"] + data["total_adjustments"]
    # Rounded base is a whole-thousands figure, tax follows the rate.
    assert data["rounded_tax_base"] % 1000 == 0
    if data["tax_base"] > 0:
        expected = (data["rounded_tax_base"] * Decimal("21") / 100)
        # tax is rounded up to whole crowns
        assert data["tax"] >= expected
        assert data["tax"] - expected < 1
    else:
        assert data["tax"] == 0
    assert data["net_profit_after_tax"] == data["profit_before_tax"] - data["tax"]


@pytest.mark.asyncio
async def test_compute_dppo_adds_back_representation(client, monkeypatch):
    """A representation expense (§25 account 513) is added back to the base."""
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)

    from datetime import date
    from app.database import async_session_factory
    from app.services.ledger_service import get_default_company_id
    from app.services.invoice_service import post_invoice
    from app.services.dppo_service import compute_dppo
    from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate
    from app.models.fiscal_period import FiscalPeriod
    from sqlalchemy import select

    async with async_session_factory() as session:
        async with session.begin():
            company_id = await get_default_company_id(session)
            period = await session.scalar(
                select(FiscalPeriod).where(
                    FiscalPeriod.company_id == company_id,
                    FiscalPeriod.is_current == True,
                )
            )
            if not period:
                pytest.skip("No current fiscal period.")

            before = await compute_dppo(session, company_id, period.id, 2024)

            # Post a received invoice booked to 513 (representation, non-deductible).
            await post_invoice(
                session,
                company_id,
                InvoiceCreate(
                    direction="RECEIVED",
                    invoice_number="REP-2024-001",
                    invoice_date=date(2024, 3, 20),
                    duzp=date(2024, 3, 18),
                    counterparty_name="Restaurace s.r.o.",
                    counterparty_ico="98765432",
                    lines=[
                        InvoiceLineCreate(
                            description="Reprezentace — oběd s klientem",
                            unit_price_net=Decimal("10000.00"),
                            vat_rate=Decimal("21.00"),
                            account_number="513",
                        )
                    ],
                ),
            )

            after = await compute_dppo(session, company_id, period.id, 2024)

    # The 513 expense lowers accounting profit but is fully added back, so the
    # tax base is unchanged by a non-deductible cost.
    accounts = {a["account"] for a in after["adjustments"]}
    assert "513" in accounts
    assert after["total_adjustments"] - before["total_adjustments"] == Decimal("10000.00")
    assert after["tax_base"] == before["tax_base"]
