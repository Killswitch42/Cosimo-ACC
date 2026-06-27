import pytest


@pytest.mark.asyncio
async def test_login_page_loads(client):
    response = await client.get("/auth/login")
    assert response.status_code == 200
    assert "Přihlášení" in response.text


@pytest.mark.asyncio
async def test_login_with_seeded_admin(client):
    response = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "changeme123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password(client):
    response = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client):
    response = await client.get("/", follow_redirects=False)
    assert response.status_code in (401, 303, 307)


@pytest.mark.asyncio
async def test_dashboard_loads_when_authenticated(client):
    login_resp = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "changeme123"},
        follow_redirects=False,
    )
    token = login_resp.cookies.get("access_token")
    client.cookies.set("access_token", token)
    response = await client.get("/")
    assert response.status_code == 200
    assert "Přehled" in response.text
