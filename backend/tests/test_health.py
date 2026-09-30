from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_does_not_depend_on_database() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"].startswith("req_")


def test_readiness_checks_postgres() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_unknown_api_path_uses_standard_error_envelope() -> None:
    response = client.get("/api/v1/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_health_response_has_security_headers() -> None:
    response = client.get("/health/live")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_unsafe_api_requests_require_a_trusted_origin() -> None:
    response = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_INVALID"
