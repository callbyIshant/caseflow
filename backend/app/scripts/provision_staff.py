import os

from pydantic import ValidationError

from app.core.db import SessionLocal
from app.core.errors import ApiError
from app.features.users.provisioning import provision_staff_user


def main() -> None:
    full_name = os.environ.get("CASEFLOW_STAFF_NAME")
    email = os.environ.get("CASEFLOW_STAFF_EMAIL")
    password = os.environ.get("CASEFLOW_STAFF_PASSWORD")
    role_value = os.environ.get("CASEFLOW_STAFF_ROLE")
    if not full_name or not email or not password or not role_value:
        raise SystemExit(
            "Set CASEFLOW_STAFF_NAME, CASEFLOW_STAFF_EMAIL, CASEFLOW_STAFF_PASSWORD, and CASEFLOW_STAFF_ROLE."
        )
    if role_value not in {"agent", "admin"}:
        raise SystemExit("CASEFLOW_STAFF_ROLE must be agent or admin.")
    role = role_value  # validated literal below

    try:
        with SessionLocal() as db:
            provision_staff_user(
                db,
                full_name=full_name,
                email=email,
                password=password,
                role=role,  # type: ignore[arg-type]
            )
    except ApiError as exc:
        raise SystemExit(exc.message) from exc
    except ValidationError as exc:
        raise SystemExit("Staff account fields failed validation.") from exc
    print("Staff account provisioned successfully.")


if __name__ == "__main__":
    main()
