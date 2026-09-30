from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import String, func, literal, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql import Select

from app.core.errors import ApiError
from app.features.tickets.models import Ticket, TicketEvent, TicketMessage
from app.features.tickets.schemas import (
    MessageCreateRequest,
    Pagination,
    SupportTicketDetail,
    SupportTicketPage,
    SupportTicketSummary,
    SupportTicketTimeline,
    SupportTimelineItem,
    SupportUserSummary,
    TicketAssigneeUpdateRequest,
    TicketCategory,
    TicketDetail,
    TicketPriority,
    TicketPriorityUpdateRequest,
    TicketReopenRequest,
    TicketStatus,
    TicketStatusUpdateRequest,
)
from app.features.users.models import User

_EVENT_SUMMARIES = {
    "ticket_created": "Request submitted",
    "ticket_claimed": "Request claimed by support",
    "ticket_assigned": "Request assignment changed",
    "priority_changed": "Request priority changed",
    "status_changed": "Request status updated",
    "ticket_reopened": "Request reopened",
}
_MESSAGE_EVENTS = {"public_message_added", "internal_note_added"}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress"},
    "in_progress": {"waiting_customer", "resolved"},
    "waiting_customer": {"in_progress", "resolved"},
    "resolved": {"closed"},
    "closed": set(),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def _staff_ticket_query() -> Select[Ticket]:
    return select(Ticket)


def _staff_ticket_or_404(db: Session, ticket_id: UUID, *, lock: bool = False) -> Ticket:
    statement = select(Ticket).where(Ticket.id == ticket_id)
    if lock:
        statement = statement.with_for_update()
    ticket = db.scalar(statement)
    if ticket is None:
        raise ApiError(404, "TICKET_NOT_FOUND", "The requested ticket was not found.")
    return ticket


def _ensure_write_access(ticket: Ticket, actor: User) -> None:
    if actor.role == "admin":
        return
    if ticket.assignee_id != actor.id:
        raise ApiError(403, "FORBIDDEN", "You do not have permission to update this request.")


def _support_detail(db: Session, ticket_id: UUID) -> SupportTicketDetail:
    customer = aliased(User)
    assignee = aliased(User)
    row = db.execute(
        select(Ticket, customer.full_name, assignee.full_name)
        .join(customer, Ticket.customer_id == customer.id)
        .outerjoin(assignee, Ticket.assignee_id == assignee.id)
        .where(Ticket.id == ticket_id)
    ).one()
    ticket, customer_name, assignee_name = row
    return SupportTicketDetail(
        id=ticket.id,
        reference=ticket.reference,
        subject=ticket.subject,
        category=cast(TicketCategory, ticket.category),
        priority=cast(TicketPriority, ticket.priority),
        status=cast(TicketStatus, ticket.status),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        customer_id=ticket.customer_id,
        customer_name=customer_name,
        assignee_id=ticket.assignee_id,
        assignee_name=assignee_name,
        description=ticket.description,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        version=ticket.version,
    )


def list_support_tickets(
    db: Session,
    actor: User,
    *,
    page: int,
    page_size: int,
    status: TicketStatus | None,
    category: str | None,
    priority: TicketPriority | None,
    assigned_to: str | None,
    query: str | None,
) -> SupportTicketPage:
    statement = _staff_ticket_query()
    if status is not None:
        statement = statement.where(Ticket.status == status)
    if category is not None:
        statement = statement.where(Ticket.category == category)
    if priority is not None:
        statement = statement.where(Ticket.priority == priority)
    if assigned_to == "me":
        statement = statement.where(Ticket.assignee_id == actor.id)
    elif assigned_to == "unassigned":
        statement = statement.where(Ticket.assignee_id.is_(None))
    if query:
        escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        reference = func.concat(
            literal("CF-"), func.lpad(sql_cast(Ticket.ticket_number, String), 6, "0")
        )
        statement = statement.where(
            or_(
                Ticket.subject.ilike(pattern, escape="\\"),
                reference.ilike(pattern, escape="\\"),
            )
        )

    total_items = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    page_tickets = db.scalars(
        statement.order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    ticket_ids = [ticket.id for ticket in page_tickets]
    if not page_tickets:
        return SupportTicketPage(
            items=[],
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=ceil(total_items / page_size) if total_items else 0,
            ),
        )
    customer = aliased(User)
    assignee = aliased(User)
    rows = db.execute(
        select(Ticket, customer.full_name, assignee.full_name)
        .join(customer, Ticket.customer_id == customer.id)
        .outerjoin(assignee, Ticket.assignee_id == assignee.id)
        .where(Ticket.id.in_(ticket_ids))
    ).all()
    summary_by_id = {
        ticket.id: SupportTicketSummary(
            id=ticket.id,
            reference=ticket.reference,
            subject=ticket.subject,
            category=cast(TicketCategory, ticket.category),
            priority=cast(TicketPriority, ticket.priority),
            status=cast(TicketStatus, ticket.status),
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            customer_id=ticket.customer_id,
            customer_name=customer_name,
            assignee_id=ticket.assignee_id,
            assignee_name=assignee_name,
        )
        for ticket, customer_name, assignee_name in rows
    }
    return SupportTicketPage(
        items=[summary_by_id[ticket_id] for ticket_id in ticket_ids],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=ceil(total_items / page_size) if total_items else 0,
        ),
    )


def list_active_support_users(db: Session) -> list[SupportUserSummary]:
    users = db.scalars(
        select(User)
        .where(User.is_active.is_(True), User.role.in_(("agent", "admin")))
        .order_by(User.full_name, User.id)
    ).all()
    return [
        SupportUserSummary(
            id=user.id,
            full_name=user.full_name,
            role=cast(Literal["agent", "admin"], user.role),
        )
        for user in users
    ]


def get_support_ticket(db: Session, ticket_id: UUID) -> SupportTicketDetail:
    _staff_ticket_or_404(db, ticket_id)
    return _support_detail(db, ticket_id)


def get_support_timeline(db: Session, ticket_id: UUID) -> SupportTicketTimeline:
    ticket = _staff_ticket_or_404(db, ticket_id)
    message_rows = db.execute(
        select(TicketMessage, User.full_name)
        .join(User, TicketMessage.author_id == User.id)
        .where(TicketMessage.ticket_id == ticket.id)
    ).all()
    event_rows = db.execute(
        select(TicketEvent, User.full_name)
        .outerjoin(User, TicketEvent.actor_id == User.id)
        .where(TicketEvent.ticket_id == ticket.id, TicketEvent.event_type.not_in(_MESSAGE_EVENTS))
    ).all()
    items = [
        SupportTimelineItem(
            kind="message",
            id=message.id,
            created_at=message.created_at,
            actor_name=author_name,
            visibility=cast(Literal["public", "internal"], message.visibility),
            body=message.body,
        )
        for message, author_name in message_rows
    ]
    items.extend(
        SupportTimelineItem(
            kind="event",
            id=event.id,
            created_at=event.created_at,
            actor_name=actor_name or "CaseFlow",
            visibility=cast(Literal["public", "internal"], event.visibility),
            summary=_EVENT_SUMMARIES.get(event.event_type, "Request updated"),
            event_type=event.event_type,
            old_value=event.old_value,
            new_value=event.new_value,
        )
        for event, actor_name in event_rows
    )
    items.sort(key=lambda item: (item.created_at, str(item.id)))
    return SupportTicketTimeline(ticket_id=ticket.id, items=items)


def claim_ticket(db: Session, actor: User, ticket_id: UUID) -> SupportTicketDetail:
    ticket = _staff_ticket_or_404(db, ticket_id, lock=True)
    if ticket.assignee_id is not None:
        raise _conflict("TICKET_ALREADY_ASSIGNED", "This request has already been claimed.")
    if ticket.status != "open":
        raise _conflict("TICKET_NOT_CLAIMABLE", "Only open requests can be claimed.")
    now = _now()
    ticket.assignee_id = actor.id
    ticket.updated_at = now
    ticket.version += 1
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=actor.id,
            event_type="ticket_claimed",
            visibility="internal",
            new_value={"assignee_id": str(actor.id)},
        )
    )
    db.commit()
    return _support_detail(db, ticket.id)


def assign_ticket(
    db: Session,
    actor: User,
    ticket_id: UUID,
    payload: TicketAssigneeUpdateRequest,
) -> SupportTicketDetail:
    ticket = _staff_ticket_or_404(db, ticket_id, lock=True)
    if ticket.status in {"resolved", "closed"}:
        raise _conflict("TICKET_NOT_WRITABLE", "Resolved and closed requests are read-only.")
    assignee: User | None = None
    if payload.assignee_id is not None:
        assignee = db.scalar(
            select(User).where(
                User.id == payload.assignee_id,
                User.role.in_(("agent", "admin")),
                User.is_active.is_(True),
            )
        )
        if assignee is None:
            raise ApiError(422, "INVALID_ASSIGNEE", "Choose an active support team member.")
    if payload.assignee_id is None and ticket.status != "open":
        raise _conflict("TICKET_MUST_BE_OPEN", "Only open requests can be unassigned.")
    old_assignee_id = ticket.assignee_id
    new_assignee_id = assignee.id if assignee else None
    if old_assignee_id == new_assignee_id:
        db.rollback()
        return _support_detail(db, ticket.id)
    now = _now()
    ticket.assignee_id = new_assignee_id
    ticket.updated_at = now
    ticket.version += 1
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=actor.id,
            event_type="ticket_assigned",
            visibility="internal",
            old_value={"assignee_id": str(old_assignee_id) if old_assignee_id else None},
            new_value={"assignee_id": str(new_assignee_id) if new_assignee_id else None},
        )
    )
    db.commit()
    return _support_detail(db, ticket.id)


def update_ticket_priority(
    db: Session,
    actor: User,
    ticket_id: UUID,
    payload: TicketPriorityUpdateRequest,
) -> SupportTicketDetail:
    ticket = _staff_ticket_or_404(db, ticket_id, lock=True)
    _ensure_write_access(ticket, actor)
    if ticket.status in {"resolved", "closed"}:
        raise _conflict("TICKET_NOT_WRITABLE", "Resolved and closed requests are read-only.")
    if ticket.priority == payload.priority:
        db.rollback()
        return _support_detail(db, ticket.id)
    old_priority = ticket.priority
    ticket.priority = payload.priority
    ticket.updated_at = _now()
    ticket.version += 1
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=actor.id,
            event_type="priority_changed",
            visibility="internal",
            old_value={"priority": old_priority},
            new_value={"priority": payload.priority},
        )
    )
    db.commit()
    return _support_detail(db, ticket.id)


def update_ticket_status(
    db: Session,
    actor: User,
    ticket_id: UUID,
    payload: TicketStatusUpdateRequest,
) -> SupportTicketDetail:
    ticket = _staff_ticket_or_404(db, ticket_id, lock=True)
    _ensure_write_access(ticket, actor)
    if payload.status not in _ALLOWED_TRANSITIONS[ticket.status]:
        raise _conflict(
            "INVALID_STATUS_TRANSITION",
            f"A request cannot move from {ticket.status.replace('_', ' ')} to {payload.status.replace('_', ' ')}.",
        )
    if payload.status in {"in_progress", "waiting_customer", "resolved"}:
        assignee = db.scalar(
            select(User).where(
                User.id == ticket.assignee_id,
                User.role.in_(("agent", "admin")),
                User.is_active.is_(True),
            )
        )
        if assignee is None:
            raise _conflict("TICKET_REQUIRES_ASSIGNEE", "Assign this request before moving it forward.")
    if payload.status == "resolved" and payload.resolution_message is None:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Provide a 10–1000 character public resolution summary.",
        )

    old_status = ticket.status
    now = _now()
    ticket.status = payload.status
    ticket.updated_at = now
    ticket.version += 1
    if payload.status == "resolved":
        ticket.resolved_at = now
    if payload.status == "closed":
        ticket.closed_at = now
    if payload.status == "in_progress":
        ticket.resolved_at = None
        ticket.closed_at = None
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=actor.id,
            event_type="status_changed",
            visibility="public",
            old_value={"status": old_status},
            new_value={"status": payload.status},
        )
    )
    if payload.status == "resolved":
        assert payload.resolution_message is not None
        message = TicketMessage(
            ticket_id=ticket.id,
            author_id=actor.id,
            body=payload.resolution_message,
            visibility="public",
        )
        db.add(message)
        db.flush()
        db.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=actor.id,
                event_type="public_message_added",
                visibility="public",
                new_value={"message_id": str(message.id)},
            )
        )
    db.commit()
    return _support_detail(db, ticket.id)


def add_support_message(
    db: Session,
    actor: User,
    ticket_id: UUID,
    payload: MessageCreateRequest,
) -> SupportTimelineItem:
    ticket = _staff_ticket_or_404(db, ticket_id, lock=True)
    _ensure_write_access(ticket, actor)
    if ticket.status in {"resolved", "closed"}:
        raise _conflict("TICKET_NOT_WRITABLE", "This request does not accept messages in its current state.")
    now = _now()
    message = TicketMessage(
        ticket_id=ticket.id,
        author_id=actor.id,
        body=payload.body,
        visibility=payload.visibility,
    )
    db.add(message)
    ticket.updated_at = now
    ticket.version += 1
    db.flush()
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=actor.id,
            event_type="public_message_added" if payload.visibility == "public" else "internal_note_added",
            visibility=payload.visibility,
            new_value={"message_id": str(message.id)},
        )
    )
    if ticket.status == "waiting_customer" and payload.visibility == "public":
        ticket.status = "in_progress"
        db.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=actor.id,
                event_type="status_changed",
                visibility="public",
                old_value={"status": "waiting_customer"},
                new_value={"status": "in_progress"},
            )
        )
    db.commit()
    db.refresh(message)
    return SupportTimelineItem(
        kind="message",
        id=message.id,
        created_at=message.created_at,
        actor_name=actor.full_name,
        visibility=cast(Literal["public", "internal"], message.visibility),
        body=message.body,
    )


def reopen_ticket(
    db: Session,
    actor: User,
    ticket_id: UUID,
    payload: TicketReopenRequest,
) -> SupportTicketDetail | TicketDetail:
    if actor.role == "customer":
        ticket = db.scalar(
            select(Ticket)
            .where(Ticket.id == ticket_id, Ticket.customer_id == actor.id)
            .with_for_update()
        )
        if ticket is None:
            raise ApiError(404, "TICKET_NOT_FOUND", "The requested ticket was not found.")
    else:
        ticket = _staff_ticket_or_404(db, ticket_id, lock=True)
    if ticket.status != "resolved" or ticket.resolved_at is None:
        raise _conflict("INVALID_STATUS_TRANSITION", "Only resolved requests can be reopened.")
    if actor.role == "agent":
        _ensure_write_access(ticket, actor)
    if _now() - ticket.resolved_at > timedelta(days=7):
        raise _conflict("REOPEN_WINDOW_EXPIRED", "This request can no longer be reopened.")
    now = _now()
    message = TicketMessage(
        ticket_id=ticket.id,
        author_id=actor.id,
        body=payload.reason,
        visibility="public",
    )
    db.add(message)
    ticket.status = "open"
    ticket.resolved_at = None
    ticket.closed_at = None
    ticket.updated_at = now
    ticket.version += 1
    db.flush()
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=actor.id,
            event_type="ticket_reopened",
            visibility="public",
            old_value={"status": "resolved"},
            new_value={"status": "open", "message_id": str(message.id)},
        )
    )
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=actor.id,
            event_type="public_message_added",
            visibility="public",
            new_value={"message_id": str(message.id)},
        )
    )
    db.commit()
    if actor.role == "customer":
        db.refresh(ticket)
        return TicketDetail.model_validate(ticket)
    return _support_detail(db, ticket.id)
