from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_trial_balance_returns_data(client):
    await client.post(
        "/api/v1/journal-entries/",
        json={
            "entry_date": "2024-05-01",
            "description": "Trial balance seed entry",
            "lines": [
                {"account_number": "112", "side": "DEBIT", "amount_foreign": 100.00},
                {"account_number": "221", "side": "CREDIT", "amount_foreign": 100.00},
            ],
        },
    )
    response = await client.get("/api/v1/account-balances/trial-balance")
    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert "total_debits" in data
    assert "total_credits" in data


@pytest.mark.asyncio
async def test_trial_balance_debits_equal_credits(client):
    response = await client.get("/api/v1/account-balances/trial-balance")
    data = response.json()
    assert Decimal(data["total_debits"]) == Decimal(data["total_credits"])
