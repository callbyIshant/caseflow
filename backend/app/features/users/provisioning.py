from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password
from app.features.auth.schemas import RegisterRequest
from app.features.auth.service import normalize_email
from app.features.users.models import User


def provision_staff_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: Literal["agent", "admin"],
) -> User:
    request = RegisterRequest(full_name=full_name, email=email, password=password)
    normalized_email = normalize_email(str(request.email))
    if role not in {"agent", "admin"}:
        raise ValueError("The provisioned role must be agent or admin.")
    existing = db.scalar(select(User.id).where(User.email == normalized_email))
    if existing is not None:
        raise ApiError(409, "EMAIL_ALREADY_REGISTERED", "An account with this email already exists.")

    user = User(
        full_name=request.full_name,
        email=normalized_email,
        password_hash=hash_password(request.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "EMAIL_ALREADY_REGISTERED", "An account with this email already exists.") from exc
    return user
