from fastapi.testclient import TestClient

from app.core.config import get_settings
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


def test_json_mutations_reject_oversized_and_non_json_bodies() -> None:
    too_large = client.post(
        "/api/v1/auth/login",
        content=b"{" + b" " * get_settings().max_request_bytes,
        headers={"Origin": get_settings().allowed_origin, "Content-Type": "application/json"},
    )
    wrong_media_type = client.post(
        "/api/v1/auth/login",
        content="email=a@example.com",
        headers={"Origin": get_settings().allowed_origin, "Content-Type": "application/x-www-form-urlencoded"},
    )

    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert wrong_media_type.status_code == 415
    assert wrong_media_type.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_unknown_spa_route_is_not_served_as_the_landing_page() -> None:
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_asset_and_api_paths_never_use_the_spa_fallback() -> None:
    missing_asset = client.get("/assets/not-a-real-bundle.js")
    api_root = client.get("/api")

    assert missing_asset.status_code == 404
    assert "text/html" not in missing_asset.headers.get("content-type", "")
    assert api_root.status_code == 404
    assert "text/html" not in api_root.headers.get("content-type", "")
