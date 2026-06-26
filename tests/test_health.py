import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_confirms_accounts_loaded(client):
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["ledger_accounts_loaded"] > 200
    assert data["phase"] == "01"
