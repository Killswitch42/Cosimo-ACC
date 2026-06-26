import pytest


@pytest.mark.asyncio
async def test_list_alerts_endpoint_returns_list(client):
    response = await client.get("/api/v1/alerts/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_resolve_alert_endpoint(client):
    # Create a simple alert directly in the database to resolve it.
    from app.database import async_session_factory
    from app.models.alert import AlertRecord
    from app.services.ledger_service import get_default_company_id
    import uuid

    async with async_session_factory() as session:
        async with session.begin():
            company_id = await get_default_company_id(session)
            alert = AlertRecord(
                id=uuid.uuid4(),
                company_id=company_id,
                severity="WARNING",
                category="COMPLIANCE",
                rule_code="TEST_RESOLVE_ALERT",
                title="Test resolve alert",
                detail="This is a test alert.",
                status="open",
                ai_generated=False,
            )
            session.add(alert)
            await session.flush()
            alert_id = alert.id

    response = await client.post(f"/api/v1/alerts/{alert_id}/resolve?resolved_by=test&resolution_note=done")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["alert_id"] == str(alert_id)
