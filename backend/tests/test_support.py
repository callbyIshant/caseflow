from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.features.tickets.models import Ticket, TicketEvent
from app.features.users.models import User
from app.features.users.provisioning import provision_staff_user
from app.main import app
from tests.test_auth import PASSWORD, register, remove_test_user

ORIGIN = get_settings().allowed_origin


def _create_ticket(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Support workflow example",
            "description": "A synthetic customer request for testing support actions and visibility.",
            "category": "technical",
        },
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201
    return response.json()


def _provision_staff(email: str, role: str = "agent", *, active: bool = True) -> None:
    with SessionLocal() as db:
        staff = provision_staff_user(
            db,
            full_name=f"Test {role.title()}",
            email=email,
            password=PASSWORD,
            role=role,
        )
        if not active:
            staff.is_active = False
            db.commit()


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def test_support_queue_claim_authorization_priority_and_private_timeline() -> None:
    customer_email = f"support-customer-{uuid4().hex}@example.com"
    agent_email = f"support-agent-{uuid4().hex}@example.com"
    other_agent_email = f"support-other-{uuid4().hex}@example.com"
    try:
        _provision_staff(agent_email)
        _provision_staff(other_agent_email)
        with TestClient(app) as customer, TestClient(app) as agent, TestClient(app) as other:
            registered = register(customer, customer_email)
            assert registered.status_code == 201
            customer.headers["X-CSRF-Token"] = registered.json()["csrf_token"]
            ticket = _create_ticket(customer)
            ticket_id = ticket["id"]
            _login(agent, agent_email)
            _login(other, other_agent_email)

            queue = agent.get("/api/v1/tickets?status=open&priority=medium&assigned_to=unassigned")
            assert queue.status_code == 200
            assert queue.json()["pagination"]["total_items"] == 1
            row = queue.json()["items"][0]
            assert row["customer_id"]
            assert row["customer_name"] == "Jordan Example"
            assert row["assignee_id"] is None

            claimed = agent.post(
                f"/api/v1/tickets/{ticket_id}/claim", headers={"Origin": ORIGIN}
            )
            assert claimed.status_code == 200
            assert claimed.json()["assignee_name"] == "Test Agent"
            assert claimed.json()["status"] == "open"  # Claiming does not start work.

            competing_claim = other.post(
                f"/api/v1/tickets/{ticket_id}/claim", headers={"Origin": ORIGIN}
            )
            assert competing_claim.status_code == 409
            assert competing_claim.json()["error"]["code"] == "TICKET_ALREADY_ASSIGNED"

            forbidden_note = other.post(
                f"/api/v1/tickets/{ticket_id}/messages",
                json={"body": "PRIVATE_AGENT_SENTINEL", "visibility": "internal"},
                headers={"Origin": ORIGIN},
            )
            assert forbidden_note.status_code == 403

            priority = agent.patch(
                f"/api/v1/tickets/{ticket_id}/priority",
                json={"priority": "high"},
                headers={"Origin": ORIGIN},
            )
            assert priority.status_code == 200
            same_priority = agent.patch(
                f"/api/v1/tickets/{ticket_id}/priority",
                json={"priority": "high"},
                headers={"Origin": ORIGIN},
            )
            assert same_priority.status_code == 200
            with SessionLocal() as db:
                assert db.scalar(
                    select(func.count()).select_from(TicketEvent).where(
                        TicketEvent.ticket_id == ticket_id,
                        TicketEvent.event_type == "priority_changed",
                    )
                ) == 1

            note = agent.post(
                f"/api/v1/tickets/{ticket_id}/messages",
                json={"body": "PRIVATE_AGENT_SENTINEL", "visibility": "internal"},
                headers={"Origin": ORIGIN},
            )
            assert note.status_code == 201
            assert note.json()["visibility"] == "internal"
            assert note.json()["body"] == "PRIVATE_AGENT_SENTINEL"
            customer_timeline = customer.get(f"/api/v1/tickets/{ticket_id}/timeline")
            assert "PRIVATE_AGENT_SENTINEL" not in customer_timeline.text
            support_timeline = agent.get(f"/api/v1/tickets/{ticket_id}/timeline")
            assert "PRIVATE_AGENT_SENTINEL" in support_timeline.text
            assert any(
                item["visibility"] == "internal"
                for item in support_timeline.json()["items"]
                if item["kind"] == "message"
            )
    finally:
        remove_test_user(customer_email)
        remove_test_user(agent_email)
        remove_test_user(other_agent_email)


def test_claim_is_serialized_between_two_agents() -> None:
    customer_email = f"race-customer-{uuid4().hex}@example.com"
    first_email = f"race-agent-a-{uuid4().hex}@example.com"
    second_email = f"race-agent-b-{uuid4().hex}@example.com"
    try:
        _provision_staff(first_email)
        _provision_staff(second_email)
        with TestClient(app) as customer:
            registered = register(customer, customer_email)
            customer.headers["X-CSRF-Token"] = registered.json()["csrf_token"]
            ticket_id = _create_ticket(customer)["id"]

        gate = Barrier(2)

        def attempt_claim(email: str) -> tuple[int, str | None]:
            with TestClient(app) as client:
                _login(client, email)
                gate.wait(timeout=10)
                response = client.post(
                    f"/api/v1/tickets/{ticket_id}/claim", headers={"Origin": ORIGIN}
                )
                error_code = response.json().get("error", {}).get("code")
                return response.status_code, error_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt_claim, (first_email, second_email)))
        assert sorted(status for status, _ in results) == [200, 409]
        assert next(code for status, code in results if status == 409) == "TICKET_ALREADY_ASSIGNED"
        with SessionLocal() as db:
            ticket = db.get(Ticket, ticket_id)
            assert ticket is not None
            assert ticket.assignee_id in {
                db.scalar(select(User.id).where(User.email == first_email)),
                db.scalar(select(User.id).where(User.email == second_email)),
            }
    finally:
        remove_test_user(customer_email)
        remove_test_user(first_email)
        remove_test_user(second_email)


def test_status_resolution_customer_auto_resume_and_reopen_lifecycle() -> None:
    customer_email = f"lifecycle-customer-{uuid4().hex}@example.com"
    agent_email = f"lifecycle-agent-{uuid4().hex}@example.com"
    try:
        _provision_staff(agent_email)
        with TestClient(app) as customer, TestClient(app) as agent:
            registered = register(customer, customer_email)
            customer.headers["X-CSRF-Token"] = registered.json()["csrf_token"]
            ticket_id = _create_ticket(customer)["id"]
            _login(agent, agent_email)
            assert agent.post(
                f"/api/v1/tickets/{ticket_id}/claim", headers={"Origin": ORIGIN}
            ).status_code == 200

            invalid = agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={"status": "resolved", "resolution_message": "Completed the request."},
                headers={"Origin": ORIGIN},
            )
            assert invalid.status_code == 409
            assert invalid.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
            assert agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={"status": "in_progress"},
                headers={"Origin": ORIGIN},
            ).status_code == 200
            assert agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={"status": "waiting_customer"},
                headers={"Origin": ORIGIN},
            ).status_code == 200

            reply = customer.post(
                f"/api/v1/tickets/{ticket_id}/messages",
                json={"body": "I have added the fictional details you requested."},
                headers={"Origin": ORIGIN},
            )
            assert reply.status_code == 201
            detail = customer.get(f"/api/v1/tickets/{ticket_id}").json()
            assert detail["status"] == "in_progress"
            timeline = customer.get(f"/api/v1/tickets/{ticket_id}/timeline").json()
            assert any(
                item["summary"] == "Request status updated"
                for item in timeline["items"]
                if item["kind"] == "event"
            )

            missing_summary = agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={"status": "resolved"},
                headers={"Origin": ORIGIN},
            )
            assert missing_summary.status_code == 422
            resolved = agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={
                    "status": "resolved",
                    "resolution_message": "The synthetic request has been resolved successfully.",
                },
                headers={"Origin": ORIGIN},
            )
            assert resolved.status_code == 200
            assert resolved.json()["resolved_at"] is not None
            public_timeline = customer.get(f"/api/v1/tickets/{ticket_id}/timeline")
            assert "The synthetic request has been resolved successfully." in public_timeline.text

            generic_reply = customer.post(
                f"/api/v1/tickets/{ticket_id}/messages",
                json={"body": "A generic reply is not valid after resolution."},
                headers={"Origin": ORIGIN},
            )
            assert generic_reply.status_code == 409
            reopened = customer.post(
                f"/api/v1/tickets/{ticket_id}/reopen",
                json={"reason": "The same synthetic issue appeared once more."},
                headers={"Origin": ORIGIN},
            )
            assert reopened.status_code == 200
            assert reopened.json()["status"] == "open"
            assert reopened.json()["resolved_at"] is None

            assert agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={"status": "in_progress"},
                headers={"Origin": ORIGIN},
            ).status_code == 200
            assert agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={
                    "status": "resolved",
                    "resolution_message": "The reopened synthetic request is resolved again.",
                },
                headers={"Origin": ORIGIN},
            ).status_code == 200
            closed = agent.patch(
                f"/api/v1/tickets/{ticket_id}/status",
                json={"status": "closed"},
                headers={"Origin": ORIGIN},
            )
            assert closed.status_code == 200
            assert closed.json()["closed_at"] is not None
            after_close = agent.post(
                f"/api/v1/tickets/{ticket_id}/messages",
                json={"body": "This message is not allowed because the request is closed."},
                headers={"Origin": ORIGIN},
            )
            assert after_close.status_code == 409
    finally:
        remove_test_user(customer_email)
        remove_test_user(agent_email)


def test_admin_assignment_requires_active_support_and_reopen_window_expires() -> None:
    customer_email = f"admin-customer-{uuid4().hex}@example.com"
    admin_email = f"admin-{uuid4().hex}@example.com"
    agent_email = f"assign-agent-{uuid4().hex}@example.com"
    inactive_email = f"inactive-agent-{uuid4().hex}@example.com"
    try:
        _provision_staff(admin_email, role="admin")
        _provision_staff(agent_email)
        _provision_staff(inactive_email, active=False)
        with TestClient(app) as customer, TestClient(app) as admin, TestClient(app) as agent:
            registered = register(customer, customer_email)
            customer.headers["X-CSRF-Token"] = registered.json()["csrf_token"]
            ticket_id = _create_ticket(customer)["id"]
            _login(admin, admin_email)
            _login(agent, agent_email)

            assigned = admin.put(
                f"/api/v1/tickets/{ticket_id}/assignee",
                json={"assignee_id": str(select_staff_id(agent_email))},
                headers={"Origin": ORIGIN},
            )
            assert assigned.status_code == 200
            assert assigned.json()["assignee_id"] == str(select_staff_id(agent_email))
            roster = admin.get("/api/v1/support/agents")
            assert roster.status_code == 200
            roster_ids = {member["id"] for member in roster.json()}
            assert str(select_staff_id(agent_email)) in roster_ids
            assert str(select_staff_id(inactive_email)) not in roster_ids
            inactive = admin.put(
                f"/api/v1/tickets/{ticket_id}/assignee",
                json={"assignee_id": str(select_staff_id(inactive_email))},
                headers={"Origin": ORIGIN},
            )
            assert inactive.status_code == 422
            non_admin = agent.put(
                f"/api/v1/tickets/{ticket_id}/assignee",
                json={"assignee_id": None},
                headers={"Origin": ORIGIN},
            )
            assert non_admin.status_code == 403
            unassigned = admin.put(
                f"/api/v1/tickets/{ticket_id}/assignee",
                json={"assignee_id": None},
                headers={"Origin": ORIGIN},
            )
            assert unassigned.status_code == 200
            assert unassigned.json()["assignee_id"] is None

            with SessionLocal() as db:
                ticket = db.get(Ticket, ticket_id)
                assert ticket is not None
                ticket.assignee_id = select_staff_id(agent_email)
                ticket.status = "resolved"
                ticket.resolved_at = datetime.now(UTC) - timedelta(days=8)
                db.commit()
            expired = customer.post(
                f"/api/v1/tickets/{ticket_id}/reopen",
                json={"reason": "This is an overdue synthetic reopening request."},
                headers={"Origin": ORIGIN},
            )
            assert expired.status_code == 409
            assert expired.json()["error"]["code"] == "REOPEN_WINDOW_EXPIRED"
            assert customer.get(f"/api/v1/tickets/{ticket_id}").json()["status"] == "resolved"
    finally:
        remove_test_user(customer_email)
        remove_test_user(admin_email)
        remove_test_user(agent_email)
        remove_test_user(inactive_email)


def test_status_and_event_roll_back_together_when_event_insert_fails() -> None:
    customer_email = f"atomic-customer-{uuid4().hex}@example.com"
    agent_email = f"atomic-agent-{uuid4().hex}@example.com"
    try:
        _provision_staff(agent_email)
        with TestClient(app) as customer:
            registered = register(customer, customer_email)
            customer.headers["X-CSRF-Token"] = registered.json()["csrf_token"]
            ticket_id = _create_ticket(customer)["id"]

        def fail_status_event(mapper, connection, target) -> None:
            if target.event_type == "status_changed":
                raise RuntimeError("controlled test event failure")

        with TestClient(app, raise_server_exceptions=False) as agent:
            _login(agent, agent_email)
            assert agent.post(
                f"/api/v1/tickets/{ticket_id}/claim", headers={"Origin": ORIGIN}
            ).status_code == 200
            event.listen(TicketEvent, "before_insert", fail_status_event)
            try:
                failed = agent.patch(
                    f"/api/v1/tickets/{ticket_id}/status",
                    json={"status": "in_progress"},
                    headers={"Origin": ORIGIN},
                )
            finally:
                event.remove(TicketEvent, "before_insert", fail_status_event)
        assert failed.status_code == 500
        with SessionLocal() as db:
            ticket = db.get(Ticket, ticket_id)
            assert ticket is not None
            assert ticket.status == "open"
            assert db.scalar(
                select(func.count()).select_from(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "status_changed",
                )
            ) == 0
    finally:
        remove_test_user(customer_email)
        remove_test_user(agent_email)


def select_staff_id(email: str):
    with SessionLocal() as db:
        result = db.scalar(select(User.id).where(User.email == email))
        assert result is not None
        return result
