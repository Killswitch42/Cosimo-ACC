import pytest


@pytest.mark.asyncio
async def test_bank_import_stub_returns_501(client):
    login_resp = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "changeme123"},
        follow_redirects=False,
    )
    token = login_resp.cookies.get("access_token")
    client.cookies.set("access_token", token)

    response = await client.post("/api/v1/bank/import")
    assert response.status_code == 501
    assert "Phase 07" in response.json()["detail"]


@pytest.mark.asyncio
async def test_bank_import_requires_auth(client):
    response = await client.post("/api/v1/bank/import", follow_redirects=False)
    assert response.status_code in (401, 303, 307)
