"""Cross-account data isolation regression tests (PRD-13)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_types_mock():
    types = MagicMock()
    types.Part = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    types.Content = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    types.GenerateContentConfig = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    types.Blob = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    return types


def _make_client_mock(text: str = "Agent response."):
    usage = MagicMock()
    usage.total_token_count = 10

    response = MagicMock()
    response.text = text
    response.usage_metadata = usage

    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=response)
    return client


# ── Fixtures for two separate users ──────────────────────────────────────────

@pytest.fixture
def user_a_payload():
    return {"email": "alice@example.com", "password": "Secure123", "full_name": "Alice", "role": "pm"}


@pytest.fixture
def user_b_payload():
    return {"email": "bob@example.com", "password": "Secure456", "full_name": "Bob", "role": "developer"}


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_chat_history(client, user_a_payload, user_b_payload):
    """GET /api/agent/boards/{id}/history must return 403 for non-members."""
    # Register and authenticate User A
    resp_a = await client.post("/api/auth/register", json=user_a_payload)
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register and authenticate User B
    resp_b = await client.post("/api/auth/register", json=user_b_payload)
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # A creates a board and sends a message
    board_resp = await client.post(
        "/api/boards",
        json={"title": "Alice's Private Board", "domain": "healthcare"},
        headers=headers_a,
    )
    board_id = board_resp.json()["id"]

    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client", return_value=_make_client_mock("private")):
        await client.post(
            "/api/agent/chat",
            json={"board_id": board_id, "message": "secret message from Alice", "history": []},
            headers=headers_a,
        )

    # B tries to read A's board history — must be 403
    r = await client.get(f"/api/agent/boards/{board_id}/history", headers=headers_b)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


@pytest.mark.asyncio
async def test_user_cannot_post_chat_to_another_users_board(client, user_a_payload, user_b_payload):
    """POST /api/agent/chat with another user's board_id must return 403."""
    resp_a = await client.post("/api/auth/register", json=user_a_payload)
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp_b = await client.post("/api/auth/register", json=user_b_payload)
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    board_resp = await client.post(
        "/api/boards",
        json={"title": "Alice's Board", "domain": "finance"},
        headers=headers_a,
    )
    board_id = board_resp.json()["id"]

    # B tries to send a message to A's board — must be 403
    r = await client.post(
        "/api/agent/chat",
        json={"board_id": board_id, "message": "intruder message", "history": []},
        headers=headers_b,
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_chat_history(client, user_a_payload, user_b_payload):
    """DELETE /api/agent/boards/{id}/history must return 403 for non-members."""
    resp_a = await client.post("/api/auth/register", json=user_a_payload)
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp_b = await client.post("/api/auth/register", json=user_b_payload)
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    board_resp = await client.post(
        "/api/boards",
        json={"title": "Alice's Board", "domain": "other"},
        headers=headers_a,
    )
    board_id = board_resp.json()["id"]

    r = await client.delete(f"/api/agent/boards/{board_id}/history", headers=headers_b)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_read_chat_history(client, user_a_payload):
    """No auth token → 401 or 403, never data."""
    resp_a = await client.post("/api/auth/register", json=user_a_payload)
    headers_a = {"Authorization": f"Bearer {resp_a.json()['access_token']}"}

    board_resp = await client.post(
        "/api/boards",
        json={"title": "Alice's Board", "domain": "education"},
        headers=headers_a,
    )
    board_id = board_resp.json()["id"]

    r = await client.get(f"/api/agent/boards/{board_id}/history")
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


@pytest.mark.asyncio
async def test_chat_history_is_scoped_to_board(client, user_a_payload):
    """Messages posted to board A do not appear in board B, even for the same user."""
    resp_a = await client.post("/api/auth/register", json=user_a_payload)
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    board_x = (await client.post("/api/boards", json={"title": "Board X", "domain": "healthcare"}, headers=headers_a)).json()
    board_y = (await client.post("/api/boards", json={"title": "Board Y", "domain": "healthcare"}, headers=headers_a)).json()

    with patch("app.services.agent_service.types", _make_types_mock()), \
         patch("app.services.agent_service._get_client", return_value=_make_client_mock("reply")):
        await client.post(
            "/api/agent/chat",
            json={"board_id": board_x["id"], "message": "message on board X", "history": []},
            headers=headers_a,
        )

    # Board Y must have no messages
    r = await client.get(f"/api/agent/boards/{board_y['id']}/history", headers=headers_a)
    assert r.status_code == 200
    assert r.json() == [], f"Board Y should have no messages but got: {r.json()}"
