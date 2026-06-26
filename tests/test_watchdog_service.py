import pytest
from unittest.mock import patch
from decimal import Decimal

RECEIVED_INVALID_DIC_PAYLOAD = {
    "direction": "RECEIVED",
    "invoice_number": "FAK-2024-0100",
    "invoice_date": "2024-03-20",
    "duzp": "2024-03-18",
    "due_date": "2024-04-20",
    "counterparty_name": "Dodavatel a.s.",
    "counterparty_ico": "98765432",
    "counterparty_dic": "ABC123",
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
async def test_received_invoice_without_dic_creates_blocker_alert(client):
    payload = {**RECEIVED_INVALID_DIC_PAYLOAD, "counterparty_dic": None}
    response = await client.post("/api/v1/invoices/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "posted"
    alert_resp = await client.get("/api/v1/alerts/?severity=BLOCKER&category=COMPLIANCE")
    assert alert_resp.status_code == 200
    alerts = alert_resp.json()
    assert any(alert["rule_code"] == "MISSING_DIC_10000" for alert in alerts)


@pytest.mark.asyncio
async def test_invalid_dic_format_creates_warning(client):
    response = await client.post("/api/v1/invoices/", json=RECEIVED_INVALID_DIC_PAYLOAD)
    assert response.status_code == 200
    alert_resp = await client.get("/api/v1/alerts/?severity=WARNING&category=COMPLIANCE")
    assert alert_resp.status_code == 200
    alerts = alert_resp.json()
    assert any(alert["rule_code"] == "INVALID_DIC_FORMAT" for alert in alerts)
