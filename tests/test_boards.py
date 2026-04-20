"""Board, capability, insight, and governance endpoint tests."""
import pytest


@pytest.mark.asyncio
async def test_create_board(client, auth_headers):
    r = await client.post(
        "/api/boards",
        json={"title": "ED Triage", "domain": "healthcare"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "ED Triage"
    assert data["domain"] == "healthcare"
    assert data["phase"] == "understand"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_list_boards(client, auth_headers):
    for i in range(3):
        await client.post("/api/boards", json={"title": f"Board {i}"}, headers=auth_headers)
    r = await client.get("/api/boards", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


@pytest.mark.asyncio
async def test_get_board(client, auth_headers, board):
    r = await client.get(f"/api/boards/{board['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == board["id"]


@pytest.mark.asyncio
async def test_patch_board_title_and_phase(client, auth_headers, board):
    r = await client.patch(
        f"/api/boards/{board['id']}",
        json={"title": "Updated Title", "phase": "harvest"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Updated Title"
    assert r.json()["phase"] == "harvest"
    assert r.json()["version"] == 2


@pytest.mark.asyncio
async def test_patch_board_state_merge(client, auth_headers, board):
    r = await client.patch(
        f"/api/boards/{board['id']}",
        json={"state": {"steps": ["arrival", "triage"], "custom_key": "value"}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    state = r.json()["state"]
    assert state["steps"] == ["arrival", "triage"]
    assert state["custom_key"] == "value"


@pytest.mark.asyncio
async def test_board_not_found(client, auth_headers):
    r = await client.get(
        "/api/boards/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_board_access_denied(client, user_payload, board):
    # Register a second user
    other = await client.post("/api/auth/register", json={
        "email": "other@example.com", "password": "OtherPass1",
        "full_name": "Other", "role": "designer"
    })
    other_token = other.json()["access_token"]
    r = await client.get(
        f"/api/boards/{board['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_archive_board(client, auth_headers, board):
    r = await client.delete(f"/api/boards/{board['id']}", headers=auth_headers)
    assert r.status_code == 204
    r2 = await client.get(f"/api/boards/{board['id']}", headers=auth_headers)
    assert r2.status_code == 404


# ── Capabilities ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capability_lifecycle(client, auth_headers, board):
    bid = board["id"]
    cap = {
        "cap_id": "CAP-001", "name": "Risk scoring",
        "type": "classification", "risk_level": "high",
        "frontstage": True, "status": "draft",
    }
    # Create
    r = await client.post(f"/api/boards/{bid}/capabilities", json=cap, headers=auth_headers)
    assert r.status_code == 201
    cap_id = r.json()["id"]
    assert r.json()["cap_id"] == "CAP-001"

    # List
    r = await client.get(f"/api/boards/{bid}/capabilities", headers=auth_headers)
    assert len(r.json()) == 1

    # Update
    r = await client.patch(
        f"/api/boards/{bid}/capabilities/{cap_id}",
        json={**cap, "status": "live", "owner": "Dr. Test"},
        headers=auth_headers,
    )
    assert r.json()["status"] == "live"
    assert r.json()["owner"] == "Dr. Test"

    # Delete
    r = await client.delete(f"/api/boards/{bid}/capabilities/{cap_id}", headers=auth_headers)
    assert r.status_code == 204

    r = await client.get(f"/api/boards/{bid}/capabilities", headers=auth_headers)
    assert len(r.json()) == 0


@pytest.mark.asyncio
async def test_duplicate_cap_id_rejected(client, auth_headers, board):
    bid = board["id"]
    cap = {"cap_id": "CAP-001", "name": "A", "status": "draft"}
    await client.post(f"/api/boards/{bid}/capabilities", json=cap, headers=auth_headers)
    r = await client.post(f"/api/boards/{bid}/capabilities", json=cap, headers=auth_headers)
    assert r.status_code == 400


# ── Governance ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_governance_decision(client, auth_headers, board):
    bid = board["id"]
    r = await client.post(
        f"/api/boards/{bid}/governance",
        json={"decision_type": "approve", "title": "Approved CAP-001", "rationale": "Passed review."},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["decision_type"] == "approve"

    r = await client.get(f"/api/boards/{bid}/governance", headers=auth_headers)
    assert len(r.json()) == 1


# ── Health ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code in (200, 503)
    assert r.json()["version"] == "1.0.0"
