from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.rate_limit import rate_limiter
from app.core.security import hash_session_token, verify_password
from app.features.auth.models import UserSession
from app.features.tickets.models import Ticket, TicketEvent, TicketMessage
from app.features.users.models import User
from app.features.users.provisioning import provision_staff_user
from app.main import app

ORIGIN = get_settings().allowed_origin
PASSWORD = "a patient example passphrase"


def remove_test_user(email: str) -> None:
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == email))
        if user_id is not None:
            ticket_ids = select(Ticket.id).where(Ticket.customer_id == user_id)
            db.execute(
                delete(TicketEvent).where(
                    (TicketEvent.actor_id == user_id) | TicketEvent.ticket_id.in_(ticket_ids)
                )
            )
            db.execute(
                delete(TicketMessage).where(
                    (TicketMessage.author_id == user_id) | TicketMessage.ticket_id.in_(ticket_ids)
                )
            )
            db.execute(delete(Ticket).where(Ticket.customer_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
            db.commit()


@pytest.fixture
def user_client() -> Iterator[tuple[TestClient, str]]:
    email = f"caseflow-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        yield client, email
    remove_test_user(email)


def register(client: TestClient, email: str, **extra: object):
    payload: dict[str, object] = {
        "full_name": "Jordan Example",
        "email": email,
        "password": PASSWORD,
        **extra,
    }
    return client.post(
        "/api/v1/auth/register", json=payload, headers={"Origin": ORIGIN}
    )


def test_registration_creates_customer_and_hashed_opaque_session(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    response = register(client, f"  {email.upper()}  ")

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "customer"
    assert body["user"]["full_name"] == "Jordan Example"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]
    assert len(body["csrf_token"]) == 64

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=604799" in cookie or "Max-Age=604800" in cookie
    token = client.cookies.get(get_settings().cookie_name)
    assert token is not None
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.role == "customer"
        assert user.password_hash != PASSWORD
        assert verify_password(PASSWORD, user.password_hash)
        session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
        assert session is not None
        assert session.token_hash == hash_session_token(token)
        assert token not in session.token_hash
        assert len(session.csrf_nonce) == 32


def test_role_escalation_and_unexpected_registration_fields_are_rejected(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    response = register(client, email, role="admin", is_active=True)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_staff_roles_can_only_be_created_by_the_secure_provisioner(
    user_client: tuple[TestClient, str],
) -> None:
    _, email = user_client
    with SessionLocal() as db:
        agent = provision_staff_user(
            db,
            full_name="Alex Support",
            email=email,
            password=PASSWORD,
            role="agent",
        )
        assert agent.role == "agent"
        assert verify_password(PASSWORD, agent.password_hash)


def test_registration_refuses_control_characters_in_name(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Jordan\tExample", "email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 422


def test_duplicate_email_uses_case_insensitive_normalization(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    assert register(client, email).status_code == 201
    duplicate = register(client, email.upper())

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_login_errors_are_generic_and_success_renews_session(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    assert register(client, email).status_code == 201
    client.cookies.clear()
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "a different wrong passphrase"},
        headers={"Origin": ORIGIN},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["code"] == wrong.json()["error"]["code"]
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]

    success = client.post(
        "/api/v1/auth/login",
        json={"email": email.upper(), "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert success.status_code == 200
    assert success.json()["user"]["email"] == email


def test_session_bootstrap_csrf_protection_and_logout_revocation(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    signed_up = register(client, email)
    csrf = signed_up.json()["csrf_token"]

    bootstrap = client.get("/api/v1/auth/session")
    assert bootstrap.status_code == 200
    assert bootstrap.headers["cache-control"] == "no-store"
    assert bootstrap.json()["authenticated"] is True
    assert bootstrap.json()["csrf_token"] == csrf
    assert client.get("/api/v1/users/me").json()["role"] == "customer"

    missing_csrf = client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN})
    invalid_csrf = client.post(
        "/api/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong"}
    )
    assert missing_csrf.status_code == invalid_csrf.status_code == 403
    assert invalid_csrf.json()["error"]["code"] == "CSRF_INVALID"

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
    )
    assert logout.status_code == 204
    assert "Max-Age=0" in logout.headers["set-cookie"]
    assert client.get("/api/v1/auth/session").json() == {"authenticated": False}
    assert client.get("/api/v1/users/me").status_code == 401


def test_sessions_for_disabled_users_are_revoked(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    assert register(client, email).status_code == 201
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.is_active = False
        db.commit()

    assert client.get("/api/v1/auth/session").json() == {"authenticated": False}


def test_same_origin_is_required_for_credential_creation(
    user_client: tuple[TestClient, str],
) -> None:
    client, email = user_client
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Jordan Example", "email": email, "password": PASSWORD},
        headers={"Origin": "https://unexpected.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_INVALID"


def test_five_failed_login_attempts_are_rate_limited() -> None:
    settings = get_settings()
    settings.rate_limit_enabled = True
    rate_limiter.clear_all()
    email = f"rate-limit-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        for _ in range(5):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
            assert response.status_code == 401
        blocked = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert blocked.headers["retry-after"].isdigit()
    assert blocked.headers["x-request-id"] == blocked.json()["error"]["request_id"]
