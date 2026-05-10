"""Agent endpoint tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_types_mock():
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


def _make_error_client(exc: Exception):
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=exc)
    return client


def _make_client_error(code: int, status: str = ""):
    from google.genai import errors as genai_errors
    err = genai_errors.ClientError.__new__(genai_errors.ClientError)
    err.code = code
    err.status = status
    err.message = f"HTTP {code}"
    err.args = (f"{code} {status}",)
    return err


def _make_server_error(code: int = 503):
    from google.genai import errors as genai_errors
    err = genai_errors.ServerError.__new__(genai_errors.ServerError)
    err.code = code
    err.status = "UNAVAILABLE"
    err.message = f"HTTP {code}"
    err.args = (f"{code} UNAVAILABLE",)
    return err


# -- Existing happy-path tests -------------------------------------------------

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
                "message":  "What is on this board?",
                "history":  [],
            },
            headers=auth_headers,
        )

    assert r.status_code == 200
    assert r.json()["response"] == "Generic board review."


# -- Error classification tests -----------------------------------------------

@pytest.mark.asyncio
async def test_chat_quota_exhausted_returns_error_card(client, auth_headers, board):
    exc = _make_client_error(429, "RESOURCE_EXHAUSTED")
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        r = await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "hello", "history": []},
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["error"]["code"] == "quota_exhausted"
    assert data["error"]["retry_advice"] == "wait_24h"
    assert "daily limit" in data["error"]["user_message"]
    assert "request_id" in data["error"]
    assert data.get("response") is None


@pytest.mark.asyncio
async def test_chat_rate_limited_returns_error_card(client, auth_headers, board):
    exc = _make_client_error(429, "RATE_LIMIT_EXCEEDED")
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        r = await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "hello", "history": []},
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["error"]["code"] == "rate_limited"
    assert data["error"]["retry_advice"] == "wait_1m"


@pytest.mark.asyncio
async def test_chat_service_unavailable_returns_error_card(client, auth_headers, board):
    exc = _make_server_error(503)
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        r = await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "hello", "history": []},
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["error"]["code"] == "service_unavailable"
    assert data["error"]["retry_advice"] == "retry_now"


@pytest.mark.asyncio
async def test_chat_invalid_request_returns_error_card(client, auth_headers, board):
    exc = _make_client_error(400, "BAD_REQUEST")
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        r = await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "hello", "history": []},
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["error"]["code"] == "invalid_request"
    assert data["error"]["retry_advice"] == "edit_request"


@pytest.mark.asyncio
async def test_chat_auth_failure_returns_error_card(client, auth_headers, board):
    exc = _make_client_error(401, "UNAUTHENTICATED")
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        r = await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "hello", "history": []},
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["error"]["code"] == "auth_failure"
    assert data["error"]["retry_advice"] == "contact_admin"


@pytest.mark.asyncio
async def test_chat_unknown_exception_falls_to_unknown_code(client, auth_headers, board):
    exc = RuntimeError("Unexpected failure without status code")
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        r = await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "hello", "history": []},
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["error"]["code"] == "unknown"
    assert data["error"]["retry_advice"] == "retry_now"


# -- request_id shape test -----------------------------------------------------

@pytest.mark.asyncio
async def test_error_response_has_uuid_request_id(client, auth_headers, board):
    exc = _make_server_error(500)
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        r = await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "hello", "history": []},
            headers=auth_headers,
        )

    data = r.json()
    assert "request_id" in data["error"]
    assert len(data["error"]["request_id"]) == 36  # UUID format


# -- User message persistence on error (FR-7) ----------------------------------

@pytest.mark.asyncio
async def test_user_message_persisted_on_error(client, auth_headers, board):
    """User message must be in DB even when the LLM call fails."""
    from sqlalchemy import select
    from app.models import ChatMessage
    from app.database import AsyncSessionLocal

    exc = _make_server_error(503)
    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client",
               return_value=_make_error_client(exc)):
        await client.post(
            "/api/agent/chat",
            json={"board_id": board["id"], "message": "persist me on error", "history": []},
            headers=auth_headers,
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChatMessage).where(
                ChatMessage.board_id == board["id"],
                ChatMessage.role == "user",
            )
        )
        msgs = result.scalars().all()

    assert any(m.content == "persist me on error" for m in msgs), \
        "User message should be persisted even when the LLM fails"


# -- Health endpoint -----------------------------------------------------------

@pytest.mark.asyncio
async def test_health_agent_ok_initially(client):
    import app.services.agent_service as svc
    svc._consecutive_failures = 0
    svc._last_error_code = None

    r = await client.get("/health/agent")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["last_error"] is None
    assert "checked_at" in data


@pytest.mark.asyncio
async def test_health_agent_degraded_after_some_failures(client):
    import app.services.agent_service as svc
    svc._consecutive_failures = 3
    svc._last_error_code = "service_unavailable"

    r = await client.get("/health/agent")
    data = r.json()
    assert data["status"] == "degraded"
    assert data["last_error"] == "service_unavailable"

    svc._consecutive_failures = 0
    svc._last_error_code = None


@pytest.mark.asyncio
async def test_health_agent_down_after_five_failures(client):
    import app.services.agent_service as svc
    svc._consecutive_failures = 5
    svc._last_error_code = "quota_exhausted"

    r = await client.get("/health/agent")
    data = r.json()
    assert data["status"] == "down"

    svc._consecutive_failures = 0
    svc._last_error_code = None