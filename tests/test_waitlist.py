"""
PRD-24 Waitlist endpoint tests.
Covers public capture, duplicate handling, validation, admin CRUD, and CSV export.
"""
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Public: POST /api/waitlist
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_waitlist_email_only(client):
    r = await client.post("/api/waitlist", json={"email": "test@example.com"})
    assert r.status_code == 200
    assert r.json()["already_member"] is False


@pytest.mark.asyncio
async def test_waitlist_full_payload(client):
    payload = {
        "email": "full@example.com",
        "full_name": "Jane Doe",
        "job_title": "Head of Design",
        "industry": "Healthcare",
        "company": "Acme Corp",
        "use_case": "Map patient journeys",
        "marketing_consent": True,
        "source": "landing_hero_cta",
        "referrer": "https://google.com",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "launch",
    }
    r = await client.post("/api/waitlist", json=payload)
    assert r.status_code == 200
    assert r.json()["already_member"] is False


@pytest.mark.asyncio
async def test_waitlist_invalid_email(client):
    r = await client.post("/api/waitlist", json={"email": "not-an-email"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_waitlist_missing_email(client):
    r = await client.post("/api/waitlist", json={"full_name": "Jane"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_waitlist_duplicate_same_case(client):
    await client.post("/api/waitlist", json={"email": "dup@example.com"})
    r = await client.post("/api/waitlist", json={"email": "dup@example.com"})
    assert r.status_code == 200
    assert r.json()["already_member"] is True


@pytest.mark.asyncio
async def test_waitlist_duplicate_different_case(client):
    """Same email in different case must not create a second row."""
    await client.post("/api/waitlist", json={"email": "DUP@example.com"})
    r = await client.post("/api/waitlist", json={"email": "dup@example.com"})
    assert r.status_code == 200
    assert r.json()["already_member"] is True


@pytest.mark.asyncio
async def test_waitlist_duplicate_enriches_fields(client, admin_headers):
    """Second submission with more data fills in blank fields on the existing row."""
    await client.post("/api/waitlist", json={"email": "enrich@example.com"})
    await client.post("/api/waitlist", json={
        "email": "enrich@example.com",
        "full_name": "Enriched Name",
        "company": "NewCo",
    })
    r = await client.get("/api/admin/waitlist", headers=admin_headers)
    rows = [row for row in r.json() if row["email"].lower() == "enrich@example.com"]
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Enriched Name"
    assert rows[0]["company"] == "NewCo"


@pytest.mark.asyncio
async def test_waitlist_use_case_too_long(client):
    r = await client.post("/api/waitlist", json={
        "email": "long@example.com",
        "use_case": "x" * 2001,
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_waitlist_full_name_too_long(client):
    r = await client.post("/api/waitlist", json={
        "email": "long2@example.com",
        "full_name": "A" * 201,
    })
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Admin: GET /api/admin/waitlist
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_list_requires_auth(client):
    r = await client.get("/api/admin/waitlist")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_requires_admin_role(client, auth_headers):
    r = await client.get("/api/admin/waitlist", headers=auth_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_returns_rows(client, admin_headers):
    await client.post("/api/waitlist", json={"email": "list1@example.com", "full_name": "Alice"})
    await client.post("/api/waitlist", json={"email": "list2@example.com", "full_name": "Bob"})
    r = await client.get("/api/admin/waitlist", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


@pytest.mark.asyncio
async def test_admin_list_filter_by_status(client, admin_headers):
    await client.post("/api/waitlist", json={"email": "s1@example.com"})
    r = await client.get("/api/admin/waitlist?status=new", headers=admin_headers)
    assert r.status_code == 200
    for row in r.json():
        assert row["status"] == "new"


@pytest.mark.asyncio
async def test_admin_list_filter_by_search(client, admin_headers):
    await client.post("/api/waitlist", json={"email": "findme@example.com", "full_name": "UniqueSearchName"})
    r = await client.get("/api/admin/waitlist?q=UniqueSearchName", headers=admin_headers)
    assert r.status_code == 200
    assert any("UniqueSearchName" in (row.get("full_name") or "") for row in r.json())


@pytest.mark.asyncio
async def test_admin_list_pagination(client, admin_headers):
    for i in range(5):
        await client.post("/api/waitlist", json={"email": f"page{i}@example.com"})
    r = await client.get("/api/admin/waitlist?limit=3&offset=0", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) <= 3


# ─────────────────────────────────────────────────────────────────────────────
# Admin: GET /api/admin/waitlist/export
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_export_csv(client, admin_headers):
    await client.post("/api/waitlist", json={
        "email": "export@example.com",
        "full_name": "Export User",
        "job_title": "PM",
    })
    r = await client.get("/api/admin/waitlist/export", headers=admin_headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.text
    assert "export@example.com" in body
    assert "Export User" in body


@pytest.mark.asyncio
async def test_admin_export_requires_admin(client, auth_headers):
    r = await client.get("/api/admin/waitlist/export", headers=auth_headers)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Admin: PATCH status
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_patch_status(client, admin_headers):
    await client.post("/api/waitlist", json={"email": "patch@example.com"})
    rows = (await client.get("/api/admin/waitlist", headers=admin_headers)).json()
    signup_id = next(r["id"] for r in rows if r["email"] == "patch@example.com")

    r = await client.patch(
        f"/api/admin/waitlist/{signup_id}/status",
        json={"status": "invited"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "invited"


@pytest.mark.asyncio
async def test_admin_patch_invalid_status(client, admin_headers):
    await client.post("/api/waitlist", json={"email": "badstatus@example.com"})
    rows = (await client.get("/api/admin/waitlist", headers=admin_headers)).json()
    signup_id = rows[0]["id"]

    r = await client.patch(
        f"/api/admin/waitlist/{signup_id}/status",
        json={"status": "invalid_status"},
        headers=admin_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_admin_patch_nonexistent(client, admin_headers):
    r = await client.patch(
        "/api/admin/waitlist/nonexistent-id/status",
        json={"status": "invited"},
        headers=admin_headers,
    )
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Admin: DELETE (GDPR right-to-erasure)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_delete(client, admin_headers):
    await client.post("/api/waitlist", json={"email": "delete@example.com"})
    rows = (await client.get("/api/admin/waitlist", headers=admin_headers)).json()
    signup_id = next(r["id"] for r in rows if r["email"] == "delete@example.com")

    r = await client.delete(f"/api/admin/waitlist/{signup_id}", headers=admin_headers)
    assert r.status_code == 204

    rows_after = (await client.get("/api/admin/waitlist", headers=admin_headers)).json()
    assert all(row["id"] != signup_id for row in rows_after)


@pytest.mark.asyncio
async def test_admin_delete_nonexistent(client, admin_headers):
    r = await client.delete("/api/admin/waitlist/nonexistent-id", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_delete_requires_admin(client, auth_headers):
    r = await client.delete("/api/admin/waitlist/some-id", headers=auth_headers)
    assert r.status_code == 403
