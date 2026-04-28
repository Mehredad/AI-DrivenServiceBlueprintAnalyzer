"""Agent endpoint tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_anthropic_response(text: str = "Test agent response."):
    content_block = MagicMock()
    content_block.text = text
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


def _mock_client(text: str):
    mock = MagicMock()
    mock.messages.create = AsyncMock(return_value=_mock_anthropic_response(text))
    return mock


@pytest.mark.asyncio
async def test_chat_accepts_role_field(client, auth_headers, board):
    with patch(
        "app.services.agent_service._get_client",
        return_value=_mock_client("Here is your developer-focused review."),
    ):
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
    with patch(
        "app.services.agent_service._get_client",
        return_value=_mock_client("Generic board review."),
    ):
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
