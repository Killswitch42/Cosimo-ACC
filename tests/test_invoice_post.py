import pytest

ISSUED_PAYLOAD = {
    "direction": "ISSUED",
    "invoice_number": "2024/001",
    "invoice_date": "2024-03-15",
    "duzp": "2024-03-10",
    "due_date": "2024-04-15",
    "counterparty_name": "Zákazník s.r.o.",
    "counterparty_dic": "CZ12345678",
    "currency": "CZK",
    "lines": [
        {
            "description": "Konzultační služby — únor 2024",
            "quantity": "10.0000",
            "unit": "hod",
            "unit_price_net": "2500.00",
            "vat_rate": "21.00",
            "account_number": "602",
        }
    ],
}

RECEIVED_PAYLOAD = {
    "direction": "RECEIVED",
    "invoice_number": "FAK-2024-0099",
    "invoice_date": "2024-03-20",
    "duzp": "2024-03-18",
    "due_date": "2024-04-20",
    "counterparty_name": "Dodavatel a.s.",
    "counterparty_ico": "98765432",
    "counterparty_dic": "CZ98765432",
    "currency": "CZK",
    "lines": [
        {
            "description": "Pronájem kancelářských prostor",
            "quantity": "1.0000",
            "unit_price_net": "15000.00",
            "vat_rate": "21.00",
            "account_number": "518",
        }
    ],
}


@pytest.mark.asyncio
async def test_post_issued_invoice(client):
    response = await client.post("/api/v1/invoices/", json=ISSUED_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "posted"
    assert data["direction"] == "ISSUED"
    assert data["journal_entry_id"] is not None
    assert data["total_net_czk"] == "25000.00"
    assert data["total_vat_czk"] == "5250.00"
    assert data["total_gross_czk"] == "30250.00"


@pytest.mark.asyncio
async def test_post_received_invoice(client):
    response = await client.post("/api/v1/invoices/", json=RECEIVED_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "posted"
    assert data["direction"] == "RECEIVED"
    assert data["journal_entry_id"] is not None


@pytest.mark.asyncio
async def test_invalid_vat_rate_rejected(client):
    payload = {
        **ISSUED_PAYLOAD,
        "lines": [{**ISSUED_PAYLOAD["lines"][0], "vat_rate": "10.00"}],
    }
    response = await client.post("/api/v1/invoices/", json=payload)
    assert response.status_code == 422
    assert "10" in response.text


@pytest.mark.asyncio
async def test_eu_supply_without_dic_rejected(client):
    payload = {
        **ISSUED_PAYLOAD,
        "is_eu_supply": True,
        "counterparty_dic": None,
        "counterparty_country": "DE",
    }
    response = await client.post("/api/v1/invoices/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reverse_charge_on_issued_rejected(client):
    payload = {**ISSUED_PAYLOAD, "is_reverse_charge": True}
    response = await client.post("/api/v1/invoices/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_received_invoice_rejected(client):
    first = await client.post("/api/v1/invoices/", json=RECEIVED_PAYLOAD)
    assert first.status_code == 200
    response2 = await client.post("/api/v1/invoices/", json=RECEIVED_PAYLOAD)
    assert response2.status_code in (422, 409)
