import pytest
from sqlalchemy import text


async def _ensure_posted_entry(session):
    result = await session.execute(
        text("SELECT id FROM journal_entries WHERE status = 'posted' LIMIT 1")
    )
    row = result.fetchone()
    if row:
        return row[0]
    pytest.skip("No posted entries to test immutability against.")


@pytest.mark.asyncio
async def test_db_trigger_blocks_update_on_posted_entry(client):
    from app.database import async_session_factory

    await client.post(
        "/api/v1/journal-entries/",
        json={
            "entry_date": "2024-06-01",
            "description": "Immutability update seed",
            "lines": [
                {"account_number": "112", "side": "DEBIT", "amount_foreign": 75.00},
                {"account_number": "221", "side": "CREDIT", "amount_foreign": 75.00},
            ],
        },
    )
    async with async_session_factory() as session:
        entry_id = await _ensure_posted_entry(session)
        with pytest.raises(Exception) as exc_info:
            await session.execute(
                text("UPDATE journal_entries SET description = 'HACKED' WHERE id = :id"),
                {"id": str(entry_id)},
            )
            await session.flush()
        assert "zákon 563" in str(exc_info.value) or "opravný zápis" in str(
            exc_info.value
        ).lower()


@pytest.mark.asyncio
async def test_db_trigger_blocks_delete_on_posted_entry(client):
    from app.database import async_session_factory

    await client.post(
        "/api/v1/journal-entries/",
        json={
            "entry_date": "2024-06-02",
            "description": "Immutability delete seed",
            "lines": [
                {"account_number": "112", "side": "DEBIT", "amount_foreign": 80.00},
                {"account_number": "221", "side": "CREDIT", "amount_foreign": 80.00},
            ],
        },
    )
    async with async_session_factory() as session:
        entry_id = await _ensure_posted_entry(session)
        with pytest.raises(Exception) as exc_info:
            await session.execute(
                text("DELETE FROM journal_entries WHERE id = :id"),
                {"id": str(entry_id)},
            )
            await session.flush()
        assert "retention" in str(exc_info.value).lower() or "zákon 563" in str(
            exc_info.value
        )
