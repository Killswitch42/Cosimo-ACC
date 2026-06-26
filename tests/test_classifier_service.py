import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal

from app.services.ai_client import AIClientError

CLASSIFY_PAYLOAD = {
    "description": "Nakup kancelářského materiálu",
    "counterparty": "Dodavatel s.r.o.",
    "amount_czk": "12500.00",
    "direction": "RECEIVED",
}


@pytest.mark.asyncio
async def test_classify_transaction_returns_suggestion(client):
    with patch("app.services.classifier_service.call_claude", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = (
            '{"debit_account": "518", "credit_account": "321", "vat_rate": 21.0, "cost_centre": null, "reasoning": "Standard input DPH.", "confidence": 0.92}',
            120,
        )
        response = await client.post("/api/v1/ai/classify", json=CLASSIFY_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["suggested_debit_account"] == "518"
        assert data["suggested_credit_account"] == "321"
        assert data["confidence_score"] == "0.92"


@pytest.mark.asyncio
async def test_classify_handles_ai_unavailable(client):
    with patch("app.services.classifier_service.call_claude", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = AIClientError("API unavailable")
        response = await client.post("/api/v1/ai/classify", json=CLASSIFY_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["classification_id"] is not None
