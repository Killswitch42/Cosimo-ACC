import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select


def _issued_invoice_data(number: str = "2024/777"):
    from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate

    return InvoiceCreate(
        direction="ISSUED",
        invoice_number=number,
        invoice_date=date(2024, 3, 15),
        duzp=date(2024, 3, 10),
        due_date=date(2024, 4, 15),
        counterparty_name="Zákazník s.r.o.",
        counterparty_dic="CZ12345678",
        lines=[
            InvoiceLineCreate(
                description="Konzultační služby",
                unit_price_net=Decimal("25000.00"),
                vat_rate=Decimal("21.00"),
                account_number="602",
            )
        ],
    )


def _make_tx(company_id, *, amount, vs, direction="CREDIT"):
    from app.models.bank_transaction import BankTransaction

    return BankTransaction(
        id=uuid.uuid4(),
        company_id=company_id,
        bank_account_number="111-222/0800",
        transaction_date=date(2024, 3, 20),
        amount_czk=amount,
        direction=direction,
        variable_symbol=vs,
        is_reconciled=False,
        match_status="UNMATCHED",
        import_source="TEST",
    )


@pytest.mark.asyncio
async def test_auto_match_exact_vs_posts_payment(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)

    from app.database import async_session_factory
    from app.services.ledger_service import get_default_company_id
    from app.services.invoice_service import post_invoice
    from app.services.bank_matching_service import run_auto_match
    from app.models.journal_entry import JournalEntry

    async with async_session_factory() as session:
        async with session.begin():
            company_id = await get_default_company_id(session)
            invoice = await post_invoice(session, company_id, _issued_invoice_data())
            assert invoice.variable_symbol == "2024777"

            tx = _make_tx(company_id, amount=invoice.total_gross_czk, vs=invoice.variable_symbol)
            session.add(tx)
            await session.flush()

            summary = await run_auto_match(session, company_id)
            assert summary["auto_matched"] == 1

            assert tx.is_reconciled is True
            assert tx.match_status == "MATCHED"
            assert tx.matched_invoice_id == invoice.id
            assert tx.matched_journal_entry_id is not None
            assert invoice.payment_date == date(2024, 3, 20)

            entry = await session.get(JournalEntry, tx.matched_journal_entry_id)
            assert entry.source_type == "BANK_PAYMENT"
            assert entry.source_id == tx.id


@pytest.mark.asyncio
async def test_amount_mismatch_is_suggested_not_reconciled(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)

    from app.database import async_session_factory
    from app.services.ledger_service import get_default_company_id
    from app.services.invoice_service import post_invoice
    from app.services.bank_matching_service import run_auto_match
    from app.models.alert import AlertRecord

    async with async_session_factory() as session:
        async with session.begin():
            company_id = await get_default_company_id(session)
            invoice = await post_invoice(session, company_id, _issued_invoice_data("2024/778"))

            # Same VS, different amount → a suggestion, never an auto-post.
            tx = _make_tx(company_id, amount=Decimal("30000.00"), vs=invoice.variable_symbol)
            session.add(tx)
            await session.flush()

            summary = await run_auto_match(session, company_id)
            assert summary["suggested"] == 1
            assert tx.is_reconciled is False
            assert tx.match_status == "SUGGESTED"
            assert invoice.payment_date is None

            alert = await session.scalar(
                select(AlertRecord).where(
                    AlertRecord.source_id == tx.id,
                    AlertRecord.rule_code == "BANK_TX_SUGGESTED",
                )
            )
            assert alert is not None


@pytest.mark.asyncio
async def test_manual_reconcile_then_unmatch(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)

    from app.database import async_session_factory
    from app.services.ledger_service import get_default_company_id
    from app.services.invoice_service import post_invoice
    from app.services.bank_matching_service import reconcile, unmatch

    async with async_session_factory() as session:
        async with session.begin():
            company_id = await get_default_company_id(session)
            invoice = await post_invoice(session, company_id, _issued_invoice_data("2024/779"))

            # No VS on the transaction → wouldn't auto-match, but a human can.
            tx = _make_tx(company_id, amount=invoice.total_gross_czk, vs=None)
            session.add(tx)
            await session.flush()

            await reconcile(session, tx, invoice)
            assert tx.is_reconciled is True
            assert invoice.payment_date == date(2024, 3, 20)
            matched_je = tx.matched_journal_entry_id

            await unmatch(session, tx)
            assert tx.is_reconciled is False
            assert tx.match_status == "UNMATCHED"
            assert tx.matched_invoice_id is None
            assert invoice.payment_date is None
            assert matched_je is not None  # a reversal was posted for it


@pytest.mark.asyncio
async def test_auto_match_endpoint_requires_auth(client):
    resp = await client.post("/api/v1/bank/auto-match", follow_redirects=False)
    assert resp.status_code in (401, 303, 307)
