import pytest


@pytest.mark.asyncio
async def test_vat_register_created_on_invoice_post(client):
    payload = {
        "direction": "ISSUED",
        "invoice_number": "VAT-TEST-001",
        "invoice_date": "2024-05-10",
        "duzp": "2024-05-08",
        "counterparty_name": "Test zákazník s.r.o.",
        "counterparty_dic": "CZ11223344",
        "lines": [
            {"description": "Služba A", "quantity": "1", "unit_price_net": "5000", "vat_rate": "21"},
            {"description": "Služba B", "quantity": "1", "unit_price_net": "2000", "vat_rate": "12"},
        ],
    }
    post_resp = await client.post("/api/v1/invoices/", json=payload)
    assert post_resp.status_code == 200

    totals_resp = await client.get("/api/v1/vat-register/period-totals?vat_period=2024-05")
    assert totals_resp.status_code == 200
    totals = totals_resp.json()["totals"]
    assert "issued_21" in totals
    assert "issued_12" in totals


@pytest.mark.asyncio
async def test_kh_detail_endpoint(client):
    payload = {
        "direction": "ISSUED",
        "invoice_number": "VAT-DETAIL-001",
        "invoice_date": "2024-05-10",
        "duzp": "2024-05-08",
        "counterparty_name": "Detail zákazník s.r.o.",
        "counterparty_dic": "CZ11223345",
        "lines": [
            {"description": "Velká služba", "quantity": "1", "unit_price_net": "50000", "vat_rate": "21"}
        ],
    }
    post_resp = await client.post("/api/v1/invoices/", json=payload)
    assert post_resp.status_code == 200

    response = await client.get(
        "/api/v1/vat-register/kh-detail?vat_period=2024-05&kh_section=A1"
    )
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "count" in data
