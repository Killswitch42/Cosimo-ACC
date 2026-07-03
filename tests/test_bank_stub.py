"""Phase 06 left /api/v1/bank/import as a 501 stub; Phase 07 implemented it.
The functional coverage now lives in test_bank_import.py / test_bank_matching.py.
Only the auth guard is checked here."""
import pytest


@pytest.mark.asyncio
async def test_bank_import_requires_auth(client):
    response = await client.post("/api/v1/bank/import", follow_redirects=False)
    assert response.status_code in (401, 303, 307)
