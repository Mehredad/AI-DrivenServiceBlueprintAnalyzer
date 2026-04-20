"""Auth endpoint tests."""
import pytest


@pytest.mark.asyncio
async def test_register_success(client, user_payload):
    r = await client.post("/api/auth/register", json=user_payload)
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client, user_payload):
    await client.post("/api/auth/register", json=user_payload)
    r = await client.post("/api/auth/register", json=user_payload)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password(client):
    r = await client.post("/api/auth/register", json={
        "email": "x@x.com", "password": "weak",
        "full_name": "X", "role": "designer"
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, user_payload):
    await client.post("/api/auth/register", json=user_payload)
    r = await client.post("/api/auth/login", json={
        "email": user_payload["email"],
        "password": user_payload["password"],
    })
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client, user_payload):
    await client.post("/api/auth/register", json=user_payload)
    r = await client.post("/api/auth/login", json={
        "email": user_payload["email"], "password": "WrongPass9"
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user(client, auth_headers, user_payload):
    r = await client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == user_payload["email"]


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_token_refresh(client, user_payload):
    reg = await client.post("/api/auth/register", json=user_payload)
    refresh = reg.json()["refresh_token"]
    r = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_logout_invalidates_token(client, user_payload):
    reg = await client.post("/api/auth/register", json=user_payload)
    refresh = reg.json()["refresh_token"]
    await client.post("/api/auth/logout", json={"refresh_token": refresh})
    r = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401
