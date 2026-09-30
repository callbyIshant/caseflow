from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import (
    create_csrf_nonce,
    create_session_token,
    derive_csrf_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.features.auth.models import UserSession
from app.features.auth.schemas import LoginRequest, RegisterRequest
from app.features.users.models import User


class CreatedSession(NamedTuple):
    user: User
    token: str
    csrf_token: str
    expires_at: datetime


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def _new_session(db: Session, user: User) -> CreatedSession:
    settings = get_settings()
    token = create_session_token()
    nonce = create_csrf_nonce()
    expires_at = datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            csrf_nonce=nonce,
            expires_at=expires_at,
        )
    )
    db.flush()
    csrf_token = derive_csrf_token(
        settings.csrf_secret.get_secret_value(), token, nonce
    )
    return CreatedSession(user, token, csrf_token, expires_at)


def register_customer(db: Session, request: RegisterRequest) -> CreatedSession:
    user = User(
        full_name=request.full_name,
        email=normalize_email(str(request.email)),
        password_hash=hash_password(request.password),
        role="customer",
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            409,
            "EMAIL_ALREADY_REGISTERED",
            "An account with this email address already exists.",
        ) from exc
    created = _new_session(db, user)
    db.commit()
    return created


def login_customer(db: Session, request: LoginRequest) -> CreatedSession:
    user = db.scalar(select(User).where(User.email == normalize_email(str(request.email))))
    password_valid = verify_password(
        request.password, user.password_hash if user is not None else None
    )
    if not password_valid or user is None or not user.is_active:
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    created = _new_session(db, user)
    db.commit()
    return created


def load_session(db: Session, token: str | None) -> tuple[User, UserSession] | None:
    if not token:
        return None
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_session_token(token))
    )
    if session is None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC) or not session.user.is_active:
        db.delete(session)
        db.commit()
        return None
    return session.user, session
