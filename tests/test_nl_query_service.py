import json
import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_ask_question_executes_tool_and_returns_answer(client):
    """Mock Grok's tool-use response and verify the flow completes."""
    from app.database import async_session_factory
    from app.services.nl_query_service import ask_question

    # Build mock tool call (first response)
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "get_open_alerts_summary"
    mock_tool_call.function.arguments = "{}"

    mock_msg_with_tools = MagicMock()
    mock_msg_with_tools.content = None
    mock_msg_with_tools.tool_calls = [mock_tool_call]

    first_choice = MagicMock()
    first_choice.finish_reason = "tool_calls"
    first_choice.message = mock_msg_with_tools

    first_response = MagicMock()
    first_response.choices = [first_choice]

    # Build mock text response (second response)
    mock_text_msg = MagicMock()
    mock_text_msg.content = "Aktuálně máte 0 otevřených upozornění."
    mock_text_msg.tool_calls = None

    second_choice = MagicMock()
    second_choice.finish_reason = "stop"
    second_choice.message = mock_text_msg

    second_response = MagicMock()
    second_response.choices = [second_choice]

    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.side_effect = [
        first_response, second_response
    ]

    company_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    async with async_session_factory() as session:
        with patch("app.services.nl_query_service.openai.OpenAI", return_value=mock_client_instance):
            answer = await ask_question(session, company_id, "Kolik mám otevřených upozornění?")

    assert "upozornění" in answer.lower() or "alert" in answer.lower()


@pytest.mark.asyncio
async def test_ask_without_api_key_raises(client):
    from app.config import settings
    from app.database import async_session_factory
    from app.services.nl_query_service import NLQueryError, ask_question

    original_key = settings.xai_api_key
    settings.xai_api_key = None
    try:
        company_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        async with async_session_factory() as session:
            with pytest.raises(NLQueryError):
                await ask_question(session, company_id, "test question")
    finally:
        settings.xai_api_key = original_key
