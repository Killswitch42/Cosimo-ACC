import pytest
from datetime import date
from decimal import Decimal

from app.services.bank_import_service import (
    BankImportError,
    import_transactions,
    parse_csv,
    parse_mt940,
)

CSV = (
    b"Datum;Castka;VS;Protiucet;Nazev protiuctu;Zprava\n"
    b"2024-03-15;30250,00;2024777;123/0800;Zakaznik s.r.o.;Platba faktury\n"
    b"2024-03-16;-12100,00;99;456/0100;Dodavatel a.s.;Najem\n"
)

MT940 = (
    b":25:CZ1234567890/0800\n"
    b":60F:C240315CZK1000,00\n"
    b":61:2403150315C30250,00NTRFNONREF//\n"
    b":86:PLATBA FAKTURY /VS/2024777\n"
    b":61:2403160316D12100,00NTRFNONREF//\n"
    b":86:NAJEM VS:99\n"
    b":62F:C240316CZK18900,00\n"
)


def test_parse_csv_basic():
    rows = parse_csv(CSV, "111-222/0800")
    assert len(rows) == 2
    assert rows[0]["transaction_date"] == date(2024, 3, 15)
    assert rows[0]["amount_czk"] == Decimal("30250.00")
    assert rows[0]["direction"] == "CREDIT"
    assert rows[0]["variable_symbol"] == "2024777"
    assert rows[1]["direction"] == "DEBIT"
    assert rows[1]["amount_czk"] == Decimal("12100.00")


def test_parse_csv_rejects_headerless():
    with pytest.raises(BankImportError):
        parse_csv(b"foo,bar\n1,2\n", "111")


def test_parse_mt940_basic():
    rows = parse_mt940(MT940)
    assert len(rows) == 2
    assert rows[0]["direction"] == "CREDIT"
    assert rows[0]["amount_czk"] == Decimal("30250.00")
    assert rows[0]["variable_symbol"] == "2024777"
    assert rows[1]["direction"] == "DEBIT"
    assert rows[1]["variable_symbol"] == "99"


@pytest.mark.asyncio
async def test_import_dedupe(client):
    from app.database import async_session_factory
    from app.services.ledger_service import get_default_company_id

    rows = parse_csv(CSV, "111-222/0800")
    async with async_session_factory() as session:
        async with session.begin():
            company_id = await get_default_company_id(session)
            first = await import_transactions(session, company_id, rows, "CSV")
            second = await import_transactions(session, company_id, rows, "CSV")
    assert len(first) == 2
    assert len(second) == 0  # re-import is idempotent


@pytest.mark.asyncio
async def test_import_endpoint_requires_auth(client):
    resp = await client.post(
        "/api/v1/bank/import",
        files={"file": ("s.csv", CSV, "text/csv")},
        data={"format": "csv", "bank_account_number": "111"},
        follow_redirects=False,
    )
    assert resp.status_code in (401, 303, 307)


@pytest.mark.asyncio
async def test_import_endpoint_summary(client):
    login = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "changeme123"},
        follow_redirects=False,
    )
    client.cookies.set("access_token", login.cookies.get("access_token"))

    resp = await client.post(
        "/api/v1/bank/import",
        files={"file": ("s.csv", CSV, "text/csv")},
        data={"format": "csv", "bank_account_number": "111-222/0800"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 2
    # No invoices exist (cleaned per test) → both land as unmatched.
    assert {"auto_matched", "suggested", "unmatched"}.issubset(body.keys())
    assert body["unmatched"] == 2
