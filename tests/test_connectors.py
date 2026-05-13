"""Connector endpoint tests — PRD-18."""
import pytest
import uuid


def _step_id():
    return str(uuid.uuid4())


@pytest.fixture
def two_steps():
    """Return two distinct step UUIDs to use as board state steps."""
    return _step_id(), _step_id()


async def _board_with_steps(client, auth_headers, step_ids):
    """Create a board and patch it to have the given step IDs in state."""
    r = await client.post("/api/boards", json={"title": "Connector Test"}, headers=auth_headers)
    board = r.json()
    steps = [{"id": sid, "name": f"Step {i}"} for i, sid in enumerate(step_ids)]
    await client.patch(
        f"/api/boards/{board['id']}",
        json={"state": {"steps": steps, "swimlanes": []}},
        headers=auth_headers,
    )
    return board


# ── AC-3: step-to-step connector ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_step_to_step_connector(client, auth_headers, two_steps):
    s1, s2 = two_steps
    board = await _board_with_steps(client, auth_headers, [s1, s2])
    bid = board["id"]

    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_step_id": s1, "target_step_id": s2, "connector_type": "sequence"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["tier"] == "step"
    assert c["connector_type"] == "sequence"
    assert c["source_step_id"] == s1
    assert c["target_step_id"] == s2


# ── AC-4: element-to-element connector ───────────────────────────────────────

@pytest.mark.asyncio
async def test_create_element_to_element_connector(client, auth_headers, board):
    bid = board["id"]

    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "El1"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "El2"}, headers=auth_headers)).json()

    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "data_flow"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["tier"] == "element"
    assert c["connector_type"] == "data_flow"


# ── AC-5: mixed tier ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_mixed_tier_connector(client, auth_headers, two_steps):
    s1, _ = two_steps
    board = await _board_with_steps(client, auth_headers, [s1])
    bid = board["id"]

    el = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "backstage_action", "name": "El"}, headers=auth_headers)).json()

    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_step_id": s1, "target_element_id": el["id"],
              "connector_type": "trigger"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["tier"] == "mixed"


# ── AC-6: both source fields set → 400 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_both_source_fields(client, auth_headers, two_steps):
    s1, s2 = two_steps
    board = await _board_with_steps(client, auth_headers, [s1, s2])
    bid = board["id"]
    el = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "El"}, headers=auth_headers)).json()

    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_step_id": s1, "source_element_id": el["id"],
              "target_step_id": s2, "connector_type": "sequence"},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


# ── AC-7: step not on board → 400 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_unknown_step_id(client, auth_headers, board):
    bid = board["id"]
    ghost = _step_id()
    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_step_id": ghost, "target_step_id": _step_id(),
              "connector_type": "sequence"},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


# ── AC-8: element from another board → 400 ───────────────────────────────────

@pytest.mark.asyncio
async def test_reject_element_from_other_board(client, auth_headers, board):
    bid = board["id"]

    other_board = (await client.post("/api/boards", json={"title": "Other"},
                                      headers=auth_headers)).json()
    other_el = (await client.post(f"/api/boards/{other_board['id']}/elements",
        json={"type": "system", "name": "Alien"}, headers=auth_headers)).json()

    el = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "Local"}, headers=auth_headers)).json()

    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_element_id": el["id"], "target_element_id": other_el["id"],
              "connector_type": "data_flow"},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


# ── AC-9: self-loop → 400 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_self_loop_step(client, auth_headers, two_steps):
    s1, s2 = two_steps
    board = await _board_with_steps(client, auth_headers, [s1, s2])
    bid = board["id"]

    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_step_id": s1, "target_step_id": s1, "connector_type": "sequence"},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_reject_self_loop_element(client, auth_headers, board):
    bid = board["id"]
    el = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "El"}, headers=auth_headers)).json()

    r = await client.post(
        f"/api/boards/{bid}/connectors",
        json={"source_element_id": el["id"], "target_element_id": el["id"],
              "connector_type": "feedback"},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


# ── AC-10: duplicate type between same pair is allowed ───────────────────────

@pytest.mark.asyncio
async def test_allow_multiple_types_same_pair(client, auth_headers, board):
    bid = board["id"]
    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "A"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "B"}, headers=auth_headers)).json()

    r1 = await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "sequence"}, headers=auth_headers)
    r2 = await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "failure"}, headers=auth_headers)

    assert r1.status_code == 201
    assert r2.status_code == 201


# ── AC-11: PATCH updates type/label; extra fields (endpoints) rejected ────────

@pytest.mark.asyncio
async def test_patch_connector_type_and_label(client, auth_headers, board):
    bid = board["id"]
    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "A"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "B"}, headers=auth_headers)).json()

    c = (await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "sequence"}, headers=auth_headers)).json()

    r = await client.patch(
        f"/api/boards/{bid}/connectors/{c['id']}",
        json={"connector_type": "data_flow", "label": "payload"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["connector_type"] == "data_flow"
    assert r.json()["label"] == "payload"


@pytest.mark.asyncio
async def test_patch_rejects_endpoint_fields(client, auth_headers, board):
    bid = board["id"]
    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "A"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "B"}, headers=auth_headers)).json()

    c = (await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "sequence"}, headers=auth_headers)).json()

    # source_element_id is not in ConnectorUpdate schema → extra fields ignored by Pydantic strict=False,
    # but the field shouldn't change on the connector
    r = await client.patch(
        f"/api/boards/{bid}/connectors/{c['id']}",
        json={"source_element_id": el2["id"], "connector_type": "trigger"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    # endpoint was NOT changed
    assert r.json()["source_element_id"] == el1["id"]


# ── AC-12: element delete cascades connectors ─────────────────────────────────

@pytest.mark.asyncio
async def test_element_delete_cascades_connectors(client, auth_headers, board):
    bid = board["id"]
    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "A"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "B"}, headers=auth_headers)).json()

    c = (await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "data_flow"}, headers=auth_headers)).json()

    await client.delete(f"/api/boards/{bid}/elements/{el1['id']}", headers=auth_headers)

    r = await client.get(f"/api/boards/{bid}/connectors/{c['id']}", headers=auth_headers)
    assert r.status_code == 404


# ── AC-13: step delete cascades connectors ────────────────────────────────────

@pytest.mark.asyncio
async def test_step_delete_cascades_connectors(client, auth_headers, two_steps):
    s1, s2 = two_steps
    board = await _board_with_steps(client, auth_headers, [s1, s2])
    bid = board["id"]

    c = (await client.post(f"/api/boards/{bid}/connectors",
        json={"source_step_id": s1, "target_step_id": s2, "connector_type": "sequence"},
        headers=auth_headers)).json()

    # Remove s1 from steps (simulate step delete)
    await client.patch(
        f"/api/boards/{bid}",
        json={"state": {"steps": [{"id": s2, "name": "Step 1"}]}},
        headers=auth_headers,
    )

    r = await client.get(f"/api/boards/{bid}/connectors/{c['id']}", headers=auth_headers)
    assert r.status_code == 404


# ── AC-14: filter by tier and type ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_by_tier_and_type(client, auth_headers, two_steps):
    s1, s2 = two_steps
    board = await _board_with_steps(client, auth_headers, [s1, s2])
    bid = board["id"]

    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "El1"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "El2"}, headers=auth_headers)).json()

    # step-sequence
    await client.post(f"/api/boards/{bid}/connectors",
        json={"source_step_id": s1, "target_step_id": s2, "connector_type": "sequence"},
        headers=auth_headers)
    # element-data_flow
    await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "data_flow"}, headers=auth_headers)

    r = await client.get(f"/api/boards/{bid}/connectors?tier=step&type=sequence", headers=auth_headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["tier"] == "step"
    assert rows[0]["connector_type"] == "sequence"


# ── AC-15: unauthorised access → 403 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_connector_access_control(client, board):
    other_token = (await client.post("/api/auth/register", json={
        "email": "other@example.com", "password": "Secure123",
        "full_name": "Other", "role": "designer",
    })).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    bid = board["id"]

    r = await client.get(f"/api/boards/{bid}/connectors", headers=other_headers)
    assert r.status_code == 403


# ── AC-17: provenance actor ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provenance_actor(client, auth_headers, board):
    bid = board["id"]
    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "A"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "system", "name": "B"}, headers=auth_headers)).json()

    # default actor = user
    c1 = (await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "sequence"}, headers=auth_headers)).json()
    assert c1["created_by_actor"] == "user"

    # explicit agent actor
    el3 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "backstage_action", "name": "C"}, headers=auth_headers)).json()
    c2 = (await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el3["id"],
              "connector_type": "trigger", "actor": "agent"}, headers=auth_headers)).json()
    assert c2["created_by_actor"] == "agent"


# ── Full CRUD lifecycle ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connector_lifecycle(client, auth_headers, board):
    bid = board["id"]
    el1 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "touchpoint", "name": "Login"}, headers=auth_headers)).json()
    el2 = (await client.post(f"/api/boards/{bid}/elements",
        json={"type": "backstage_action", "name": "Auth"}, headers=auth_headers)).json()

    # Create
    r = await client.post(f"/api/boards/{bid}/connectors",
        json={"source_element_id": el1["id"], "target_element_id": el2["id"],
              "connector_type": "sequence", "label": "submit"},
        headers=auth_headers)
    assert r.status_code == 201
    cid = r.json()["id"]

    # Get one
    r = await client.get(f"/api/boards/{bid}/connectors/{cid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["label"] == "submit"

    # List
    r = await client.get(f"/api/boards/{bid}/connectors", headers=auth_headers)
    assert any(c["id"] == cid for c in r.json())

    # Update
    r = await client.patch(f"/api/boards/{bid}/connectors/{cid}",
        json={"connector_type": "dependency", "notes": "blocking call"},
        headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["connector_type"] == "dependency"

    # Delete
    r = await client.delete(f"/api/boards/{bid}/connectors/{cid}", headers=auth_headers)
    assert r.status_code == 204

    r = await client.get(f"/api/boards/{bid}/connectors/{cid}", headers=auth_headers)
    assert r.status_code == 404
