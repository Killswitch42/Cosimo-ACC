import pytest


@pytest.mark.asyncio
async def test_post_balanced_entry(client):
    payload = {
        "entry_date": "2024-03-15",
        "description": "Test entry — nákup materiálu",
        "currency": "CZK",
        "lines": [
            {"account_number": "112", "side": "DEBIT", "amount_foreign": 1000.00},
            {"account_number": "221", "side": "CREDIT", "amount_foreign": 1000.00},
        ],
    }
    response = await client.post("/api/v1/journal-entries/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["entry_number"].startswith("MA-2024-")
    assert data["status"] == "posted"


@pytest.mark.asyncio
async def test_unbalanced_entry_rejected(client):
    payload = {
        "entry_date": "2024-03-15",
        "description": "Unbalanced — should fail",
        "lines": [
            {"account_number": "112", "side": "DEBIT", "amount_foreign": 1000.00},
            {"account_number": "221", "side": "CREDIT", "amount_foreign": 900.00},
        ],
    }
    response = await client.post("/api/v1/journal-entries/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_single_line_entry_rejected(client):
    payload = {
        "entry_date": "2024-03-15",
        "description": "One line — invalid",
        "lines": [
            {"account_number": "112", "side": "DEBIT", "amount_foreign": 500.00},
        ],
    }
    response = await client.post("/api/v1/journal-entries/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_to_closed_period_rejected(client):
    payload = {
        "entry_date": "2020-01-01",
        "description": "Past period — should fail",
        "lines": [
            {"account_number": "112", "side": "DEBIT", "amount_foreign": 100.00},
            {"account_number": "221", "side": "CREDIT", "amount_foreign": 100.00},
        ],
    }
    response = await client.post("/api/v1/journal-entries/", json=payload)
    assert response.status_code == 422
    assert "open" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reversal_creates_opravny_zapis(client):
    post_resp = await client.post(
        "/api/v1/journal-entries/",
        json={
            "entry_date": "2024-04-01",
            "description": "Entry to be reversed",
            "lines": [
                {"account_number": "518", "side": "DEBIT", "amount_foreign": 500.00},
                {"account_number": "321", "side": "CREDIT", "amount_foreign": 500.00},
            ],
        },
    )
    assert post_resp.status_code == 200
    entry_id = post_resp.json()["id"]

    rev_resp = await client.post(
        f"/api/v1/journal-entries/{entry_id}/reverse",
        json={
            "reversal_date": "2024-04-02",
            "reason": "Chybný dodavatel — test",
        },
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["reversal_entry_number"].startswith("MA-2024-")
