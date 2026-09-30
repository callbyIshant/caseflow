from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.features.tickets.models import Ticket, TicketEvent, TicketMessage
from app.features.users.models import User
from app.main import app
from tests.test_auth import PASSWORD, register, remove_test_user

ORIGIN = get_settings().allowed_origin


def create_payload(**extra: object) -> dict[str, object]:
    return {
        "subject": "Cannot access my profile",
        "description": "The fictional support profile stops loading after I sign in to the demo.",
        "category": "account",
        **extra,
    }


def register_customer(client: TestClient, email: str) -> None:
    response = register(client, email)
    assert response.status_code == 201
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def submit_ticket(client: TestClient, **extra: object):
    return client.post(
        "/api/v1/tickets",
        json=create_payload(**extra),
        headers={"Origin": ORIGIN},
    )


def test_customer_ticket_create_list_detail_and_dashboard_are_persistent() -> None:
    email = f"ticket-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        register_customer(client, email)
        created = submit_ticket(client)
        assert created.status_code == 201
        detail = created.json()
        assert detail["reference"].startswith("CF-")
        assert len(detail["reference"]) >= 9
        assert detail["status"] == "open"
        assert detail["priority"] == "medium"
        assert detail["category"] == "account"
        assert "customer_id" not in detail
        assert "assignee_id" not in detail
        ticket_id = detail["id"]

        listing = client.get("/api/v1/tickets?page=1&page_size=10")
        assert listing.status_code == 200
        assert listing.json()["pagination"] == {
            "page": 1,
            "page_size": 10,
            "total_items": 1,
            "total_pages": 1,
        }
        assert listing.json()["items"][0]["id"] == ticket_id

        persisted = client.get(f"/api/v1/tickets/{ticket_id}")
        assert persisted.status_code == 200
        assert persisted.json()["description"] == detail["description"]

        dashboard = client.get("/api/v1/tickets/summary")
        assert dashboard.status_code == 200
        assert dashboard.json()["ticket_counts"]["open"] == 1
        assert dashboard.json()["total_tickets"] == 1
        assert dashboard.json()["recent_tickets"][0]["reference"] == detail["reference"]

    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            assert user is not None
            ticket = db.scalar(select(Ticket).where(Ticket.customer_id == user.id))
            assert ticket is not None
            assert ticket.reference.startswith("CF-")
            events = db.scalars(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket.id,
                    TicketEvent.event_type == "ticket_created",
                )
            ).all()
            assert len(events) == 1
            assert events[0].visibility == "public"
            assert events[0].new_value == {"reference": ticket.reference}
    finally:
        remove_test_user(email)


def test_ticket_fields_are_validated_and_mass_assignment_is_rejected() -> None:
    email = f"validation-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        register_customer(client, email)
        invalid = [
            {"subject": "Short", "description": "Too brief.", "category": "account"},
            {**create_payload(), "category": "finance"},
            {**create_payload(), "priority": "high"},
            {**create_payload(), "assignee_id": str(uuid4())},
            {**create_payload(), "customer_id": str(uuid4())},
            {**create_payload(), "role": "admin"},
        ]
        for payload in invalid:
            response = client.post(
                "/api/v1/tickets", json=payload, headers={"Origin": ORIGIN}
            )
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    remove_test_user(email)


def test_customer_scope_is_applied_before_filtering_pagination_and_detail_lookup() -> None:
    first_email = f"ticket-a-{uuid4().hex}@example.com"
    second_email = f"ticket-b-{uuid4().hex}@example.com"
    try:
        with TestClient(app) as first, TestClient(app) as second:
            register_customer(first, first_email)
            register_customer(second, second_email)
            first_ticket = submit_ticket(first)
            second_ticket = submit_ticket(second, subject="Billing history needs a refresh")
            assert first_ticket.status_code == second_ticket.status_code == 201

            response = first.get("/api/v1/tickets?page=1&page_size=1")
            assert response.status_code == 200
            assert response.json()["pagination"]["total_items"] == 1
            assert response.json()["items"][0]["id"] == first_ticket.json()["id"]
            assert second_ticket.json()["id"] not in str(response.json())

            private_detail = first.get(f"/api/v1/tickets/{second_ticket.json()['id']}")
            private_timeline = first.get(
                f"/api/v1/tickets/{second_ticket.json()['id']}/timeline"
            )
            assert private_detail.status_code == private_timeline.status_code == 404
            assert private_detail.json()["error"]["code"] == "TICKET_NOT_FOUND"

            filtered = first.get("/api/v1/tickets?status=resolved&page=1&page_size=10")
            assert filtered.json()["pagination"]["total_items"] == 0
    finally:
        remove_test_user(first_email)
        remove_test_user(second_email)


def test_customer_reply_and_timeline_exclude_internal_records() -> None:
    email = f"timeline-{uuid4().hex}@example.com"
    try:
        with TestClient(app) as client:
            register_customer(client, email)
            ticket_response = submit_ticket(client)
            ticket_id = ticket_response.json()["id"]
            reply = client.post(
                f"/api/v1/tickets/{ticket_id}/messages",
                json={"body": "I can share another fictional detail about the issue."},
                headers={"Origin": ORIGIN},
            )
            assert reply.status_code == 201
            assert reply.json()["kind"] == "message"
            assert reply.json()["visibility"] == "public"

            forbidden_note = client.post(
                f"/api/v1/tickets/{ticket_id}/messages",
                json={"body": "This would be an internal note.", "visibility": "internal"},
                headers={"Origin": ORIGIN},
            )
            assert forbidden_note.status_code == 403
            assert forbidden_note.json()["error"]["code"] == "FORBIDDEN"

            with SessionLocal() as db:
                ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id))
                assert ticket is not None
                db.add(
                    TicketMessage(
                        ticket_id=ticket.id,
                        author_id=ticket.customer_id,
                        body="PRIVATE_INTERNAL_NOTE_SENTINEL",
                        visibility="internal",
                    )
                )
                db.add(
                    TicketEvent(
                        ticket_id=ticket.id,
                        actor_id=ticket.customer_id,
                        event_type="internal_note_added",
                        visibility="internal",
                        new_value={"note": "PRIVATE_EVENT_SENTINEL"},
                    )
                )
                db.commit()

            timeline_response = client.get(f"/api/v1/tickets/{ticket_id}/timeline")
            timeline_text = timeline_response.text
            assert timeline_response.status_code == 200
            assert "PRIVATE_INTERNAL_NOTE_SENTINEL" not in timeline_text
            assert "PRIVATE_EVENT_SENTINEL" not in timeline_text
            items = timeline_response.json()["items"]
            assert [item["kind"] for item in items] == ["event", "message"]
            assert all(item["visibility"] == "public" for item in items)
            assert all("old_value" not in item and "new_value" not in item for item in items)
            assert items[0]["summary"] == "Request submitted"
            assert items[1]["body"] == "I can share another fictional detail about the issue."

            detail_response = client.get(f"/api/v1/tickets/{ticket_id}")
            assert "PRIVATE_INTERNAL_NOTE_SENTINEL" not in detail_response.text
    finally:
        remove_test_user(email)


def test_ticket_search_filters_and_invalid_pagination() -> None:
    email = f"filters-{uuid4().hex}@example.com"
    try:
        with TestClient(app) as client:
            register_customer(client, email)
            created = submit_ticket(client)
            reference = created.json()["reference"]
            by_reference = client.get(f"/api/v1/tickets?q={reference}&category=account")
            assert by_reference.status_code == 200
            assert by_reference.json()["pagination"]["total_items"] == 1
            assert by_reference.json()["items"][0]["reference"] == reference

            too_small = client.get("/api/v1/tickets?page=0")
            too_large = client.get("/api/v1/tickets?page_size=51")
            assert too_small.status_code == too_large.status_code == 422
    finally:
        remove_test_user(email)


def test_support_role_uses_the_shared_ticket_queue() -> None:
    email = f"agent-{uuid4().hex}@example.com"
    try:
        with SessionLocal() as db:
            from app.features.users.provisioning import provision_staff_user

            provision_staff_user(
                db,
                full_name="Queue Agent",
                email=email,
                password=PASSWORD,
                role="agent",
            )
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
            assert login.status_code == 200
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            response = client.get("/api/v1/tickets")
            assert response.status_code == 200
            assert response.json()["pagination"]["page"] == 1
    finally:
        remove_test_user(email)
