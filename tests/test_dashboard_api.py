import pytest


@pytest.mark.asyncio
async def test_authenticated_alerts_partial(client):
    login_resp = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "changeme123"},
        follow_redirects=False,
    )
    token = login_resp.cookies.get("access_token")
    client.cookies.set("access_token", token)

    response = await client.get("/dashboard/alerts-partial")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_alerts_partial_requires_auth(client):
    response = await client.get("/dashboard/alerts-partial", follow_redirects=False)
    assert response.status_code in (401, 303, 307)
