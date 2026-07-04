import pytest

VALID = {
    "direction": "RECEIVED",
    "invoice_number": "UITEST-OK",
    "invoice_date": "2024-03-15",
    "duzp": "",
    "due_date": "",
    "variable_symbol": "",
    "counterparty_name": "Dodavatel s.r.o.",
    "counterparty_ico": "",
    "counterparty_dic": "",
    "currency": "CZK",
    "line_description": "Kancelářské služby",
    "unit_price_net": "1000",
    "vat_rate": "21.00",
    "account_number": "518",
}


async def _login(client):
    r = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "changeme123"},
        follow_redirects=False,
    )
    client.cookies.set("access_token", r.cookies.get("access_token"))


@pytest.mark.asyncio
async def test_create_bad_ico_shows_error_not_500(client, monkeypatch):
    """A 10-digit IČO must yield a friendly error (200), never a 500."""
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)
    await _login(client)

    bad = {**VALID, "invoice_number": "UITEST-BADICO", "counterparty_ico": "2701515161"}
    r = await client.post("/invoices/create", data=bad)
    assert r.status_code == 200
    assert "IČO" in r.text  # error banner rendered, form still works


@pytest.mark.asyncio
async def test_create_bad_account_shows_error_not_500(client, monkeypatch):
    """An unknown ledger account must yield a friendly error, not a 500."""
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)
    await _login(client)

    bad = {**VALID, "invoice_number": "UITEST-BADACC", "account_number": "2701515161"}
    r = await client.post("/invoices/create", data=bad)
    assert r.status_code == 200
    assert "⚠" in r.text or "není" in r.text.lower() or "not found" in r.text.lower()


@pytest.mark.asyncio
async def test_create_valid_invoice_posts(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "xai_api_key", None)
    await _login(client)

    r = await client.post("/invoices/create", data=VALID)
    assert r.status_code == 200
    assert "UITEST-OK" in r.text
    assert "zaúčtována" in r.text
