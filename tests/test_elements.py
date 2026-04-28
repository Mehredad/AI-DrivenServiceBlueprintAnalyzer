"""Element endpoint tests — PRD-03."""
import pytest


@pytest.mark.asyncio
async def test_element_lifecycle(client, auth_headers, board):
    bid = board["id"]

    # Create a touchpoint element
    r = await client.post(
        f"/api/boards/{bid}/elements",
        json={
            "type": "touchpoint",
            "name": "Patient intake form",
            "notes": "Web form on portal",
            "status": "draft",
            "meta": {"channel": "web"},
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    el = r.json()
    assert el["type"] == "touchpoint"
    assert el["name"] == "Patient intake form"
    assert el["meta"]["channel"] == "web"
    el_id = el["id"]

    # List
    r = await client.get(f"/api/boards/{bid}/elements", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Get one
    r = await client.get(f"/api/boards/{bid}/elements/{el_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == el_id

    # Patch
    r = await client.patch(
        f"/api/boards/{bid}/elements/{el_id}",
        json={"status": "live", "owner": "UX team"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "live"
    assert r.json()["owner"] == "UX team"

    # Delete
    r = await client.delete(f"/api/boards/{bid}/elements/{el_id}", headers=auth_headers)
    assert r.status_code == 204

    r = await client.get(f"/api/boards/{bid}/elements", headers=auth_headers)
    assert len(r.json()) == 0


@pytest.mark.asyncio
async def test_element_type_validation(client, auth_headers, board):
    r = await client.post(
        f"/api/boards/{board['id']}/elements",
        json={"type": "invalid_type", "name": "Test"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_element_name_required(client, auth_headers, board):
    r = await client.post(
        f"/api/boards/{board['id']}/elements",
        json={"type": "system"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_ai_capability_element(client, auth_headers, board):
    bid = board["id"]
    r = await client.post(
        f"/api/boards/{bid}/elements",
        json={
            "type": "ai_capability",
            "name": "Risk scoring model",
            "status": "draft",
            "meta": {
                "cap_id": "CAP-001",
                "ai_type": "classification",
                "risk_level": "high",
                "xai_strategy": "SHAP explanations",
                "autonomy": "advisory",
                "frontstage": True,
            },
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    el = r.json()
    assert el["type"] == "ai_capability"
    assert el["meta"]["cap_id"] == "CAP-001"
    assert el["meta"]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_element_not_found(client, auth_headers, board):
    r = await client.get(
        f"/api/boards/{board['id']}/elements/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_all_element_types(client, auth_headers, board):
    bid = board["id"]
    types = [
        "customer_action", "physical_evidence", "frontstage_action", "backstage_action",
        "support_process", "moment_of_truth",
        "touchpoint", "system", "data_flow", "handoff", "risk",
        "opportunity", "pain_point", "research_evidence", "ai_capability", "governance_checkpoint",
    ]
    for t in types:
        r = await client.post(
            f"/api/boards/{bid}/elements",
            json={"type": t, "name": f"Test {t}"},
            headers=auth_headers,
        )
        assert r.status_code == 201, f"Failed for type {t}: {r.text}"

    r = await client.get(f"/api/boards/{bid}/elements", headers=auth_headers)
    assert len(r.json()) == len(types)
