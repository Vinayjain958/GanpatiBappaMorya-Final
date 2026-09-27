from __future__ import annotations

from tests.conftest import auth_header, register_provider, register_traveler


def test_register_traveler_succeeds(client) -> None:
    body = register_traveler(client, "trav1@example.com")
    assert body["user"]["role"] == "traveler"
    assert body["traveler"] is not None
    assert body["provider"] is None
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_register_provider_succeeds(client) -> None:
    body = register_provider(client, "biz1@example.com", "Fort Walking Tours")
    assert body["user"]["role"] == "provider"
    assert body["provider"]["business_name"] == "Fort Walking Tours"
    assert body["provider"]["verification_status"] == "unverified"
    assert body["traveler"] is None


def test_register_admin_is_rejected(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "password": "supersecret123",
            "role": "admin",
            "display_name": "Admin",
        },
    )
    assert response.status_code == 422


def test_register_provider_without_business_name_rejected(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "nobiz@example.com",
            "password": "supersecret123",
            "role": "provider",
            "display_name": "No Biz",
        },
    )
    assert response.status_code == 422


def test_duplicate_email_rejected(client) -> None:
    register_traveler(client, "dup@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "password": "supersecret123",
            "role": "traveler",
            "display_name": "Dup",
        },
    )
    assert response.status_code == 409


def test_email_is_normalized_to_lowercase(client) -> None:
    register_traveler(client, "MixedCase@Example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "mixedcase@example.com", "password": "supersecret123"},
    )
    assert response.status_code == 200


def test_password_hash_never_returned(client) -> None:
    body = register_traveler(client, "hashcheck@example.com")
    assert "password_hash" not in body["user"]
    assert "password" not in body["user"]


def test_login_success(client) -> None:
    register_traveler(client, "login1@example.com")
    response = client.post(
        "/api/v1/auth/login", json={"email": "login1@example.com", "password": "supersecret123"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_rejected(client) -> None:
    register_traveler(client, "login2@example.com")
    response = client.post(
        "/api/v1/auth/login", json={"email": "login2@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password."


def test_login_unknown_email_rejected_generically(client) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "doesnotexist@example.com", "password": "whatever123"}
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password."


def test_me_returns_current_user(client) -> None:
    body = register_traveler(client, "me1@example.com")
    response = client.get("/api/v1/auth/me", headers=auth_header(body))
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "me1@example.com"


def test_me_without_token_rejected(client) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_garbage_token_rejected(client) -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_logout_works(client) -> None:
    register_traveler(client, "logout1@example.com")
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204


def test_refresh_issues_new_access_token(client) -> None:
    register_traveler(client, "refresh1@example.com")
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_rotates_and_old_token_is_rejected(client) -> None:
    register_traveler(client, "rotate1@example.com")
    old_cookies = dict(client.cookies)

    first_refresh = client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200

    # Simulate reusing the pre-rotation cookie (e.g. a stolen token) with a
    # separate client that never saw the rotation.
    from fastapi.testclient import TestClient

    stale_client = TestClient(client.app)
    stale_client.cookies.update(old_cookies)
    reuse_response = stale_client.post("/api/v1/auth/refresh")
    assert reuse_response.status_code == 401


def test_refresh_without_cookie_rejected(client) -> None:
    from fastapi.testclient import TestClient

    fresh_client = TestClient(client.app)
    response = fresh_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_cookie_is_httponly(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "cookiecheck@example.com",
            "password": "supersecret123",
            "role": "traveler",
            "display_name": "Cookie Check",
        },
    )
    set_cookie = response.headers.get("set-cookie", "")
    assert "refresh" in set_cookie.lower()
    assert "httponly" in set_cookie.lower()


def test_logout_revokes_session_so_refresh_then_fails(client) -> None:
    register_traveler(client, "logoutrevoke@example.com")
    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401
