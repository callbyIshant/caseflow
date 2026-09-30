from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import ApiError
from app.core.rate_limit import (
    client_ip,
    identity_key,
    release_rate_limit_event,
    reserve_rate_limit_event,
)
from app.core.security import derive_csrf_token, hash_session_token
from app.features.auth.models import UserSession
from app.features.auth.schemas import (
    AuthenticatedResponse,
    LoginRequest,
    RegisterRequest,
    SessionResponse,
    UserPublic,
)
from app.features.auth.service import load_session, login_customer, register_customer
from app.features.users.deps import CurrentUser
from app.features.users.models import User

router = APIRouter(prefix="/api/v1", tags=["authentication"])
Database = Annotated[Session, Depends(get_db)]


def _set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    settings = get_settings()
    remaining_seconds = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=remaining_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/auth/register", response_model=AuthenticatedResponse, status_code=201)
def register(
    payload: RegisterRequest, response: Response, db: Database, request: Request
) -> AuthenticatedResponse:
    ip = client_ip(request)
    key = f"register:ip:{ip}"
    reserve_rate_limit_event(key, 3, 60 * 60)
    created = register_customer(db, payload)
    _set_session_cookie(response, created.token, created.expires_at)
    return AuthenticatedResponse(
        user=UserPublic.model_validate(created.user), csrf_token=created.csrf_token
    )


@router.post("/auth/login", response_model=AuthenticatedResponse)
def login(
    payload: LoginRequest, response: Response, db: Database, request: Request
) -> AuthenticatedResponse:
    ip = client_ip(request)
    ip_key = f"login:ip:{ip}"
    identity = f"login:identity:{identity_key(str(payload.email))}"
    ip_token = reserve_rate_limit_event(ip_key, 20, 15 * 60)
    try:
        identity_token = reserve_rate_limit_event(identity, 5, 15 * 60)
    except ApiError:
        release_rate_limit_event(ip_key, ip_token)
        raise
    try:
        created = login_customer(db, payload)
    except ApiError as exc:
        if exc.code == "INVALID_CREDENTIALS":
            raise
        release_rate_limit_event(ip_key, ip_token)
        release_rate_limit_event(identity, identity_token)
        raise
    except Exception:
        release_rate_limit_event(ip_key, ip_token)
        release_rate_limit_event(identity, identity_token)
        raise
    release_rate_limit_event(ip_key, ip_token)
    release_rate_limit_event(identity, identity_token)
    _set_session_cookie(response, created.token, created.expires_at)
    return AuthenticatedResponse(
        user=UserPublic.model_validate(created.user), csrf_token=created.csrf_token
    )


@router.get("/auth/session", response_model=SessionResponse, response_model_exclude_none=True)
def get_session(request: Request, db: Database) -> SessionResponse:
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    authenticated = load_session(db, token)
    if authenticated is None or token is None:
        return SessionResponse(authenticated=False)
    user, session = authenticated
    csrf_token = derive_csrf_token(
        settings.csrf_secret.get_secret_value(), token, session.csrf_nonce
    )
    return SessionResponse(
        authenticated=True,
        user=UserPublic.model_validate(user),
        csrf_token=csrf_token,
    )


@router.post("/auth/logout", status_code=204, response_model=None)
def logout(request: Request, response: Response, db: Database, user: CurrentUser) -> Response:
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if token is None:
        raise ApiError(401, "AUTH_REQUIRED", "Sign in to continue.")
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_session_token(token)))
    db.commit()
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.status_code = 204
    return response


@router.get("/users/me", response_model=UserPublic)
def current_user(user: CurrentUser) -> User:
    return user
