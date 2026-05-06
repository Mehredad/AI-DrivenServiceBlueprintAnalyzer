"""Agent endpoint tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_types_mock():
    """Return a mock that stands in for google.genai.types."""
    types = MagicMock()
    types.Part = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    types.Content = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    types.GenerateContentConfig = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    types.Blob = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    return types


def _make_client_mock(text: str = "Test agent response."):
    usage = MagicMock()
    usage.total_token_count = 15

    response = MagicMock()
    response.text = text
    response.usage_metadata = usage

    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_chat_accepts_role_field(client, auth_headers, board):
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_client_mock("Here is your developer-focused review.")):
        r = await client.post(
            "/api/agent/chat",
            json={
                "board_id": board["id"],
                "message":  "Review this board.",
                "history":  [],
                "role":     "developer",
            },
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert "response" in data
    assert data["response"] == "Here is your developer-focused review."
    assert "token_count" in data
    assert "message_id" in data


@pytest.mark.asyncio
async def test_chat_without_role_still_works(client, auth_headers, board):
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_client_mock("Generic board review.")):
        r = await client.post(
            "/api/agent/chat",
            json={
                "board_id": board["id"],
                "message":  "What's on this board?",
                "history":  [],
            },
            headers=auth_headers,
        )

    assert r.status_code == 200
    assert r.json()["response"] == "Generic board review."
