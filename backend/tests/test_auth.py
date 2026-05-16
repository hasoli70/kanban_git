from fastapi.testclient import TestClient

from app.main import app


def _fresh_client() -> TestClient:
    return TestClient(app)


def test_login_success_sets_session_cookie() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 204
    assert "pm_session" in client.cookies


def test_login_failure_returns_401() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "wrong"}
    )
    assert response.status_code == 401
    assert "pm_session" not in client.cookies


def test_me_unauthenticated_returns_401() -> None:
    client = _fresh_client()
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_authenticated_returns_user() -> None:
    client = _fresh_client()
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"user": "user"}


def test_logout_clears_session() -> None:
    client = _fresh_client()
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    assert client.get("/api/auth/me").status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_cookie_flags() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "pm_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
