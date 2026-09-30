from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import ApiError
from app.core.security import csrf_token_matches, derive_csrf_token
from app.features.auth.service import load_session
from app.features.users.models import User

Database = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: Database) -> User:
    token = request.cookies.get(get_settings().cookie_name)
    authenticated = load_session(db, token)
    if authenticated is None:
        raise ApiError(401, "AUTH_REQUIRED", "Sign in to continue.")

    user, session = authenticated
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        settings = get_settings()
        expected = derive_csrf_token(
            settings.csrf_secret.get_secret_value(), token or "", session.csrf_nonce
        )
        if not csrf_token_matches(request.headers.get("x-csrf-token"), expected):
            raise ApiError(403, "CSRF_INVALID", "This request could not be verified.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[..., User]:
    def role_guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ApiError(403, "FORBIDDEN", "You do not have permission to do this.")
        return user

    return role_guard
