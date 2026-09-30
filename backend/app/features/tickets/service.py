from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from sqlalchemy import String, func, literal, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.errors import ApiError
from app.features.tickets.models import Ticket, TicketEvent, TicketMessage
from app.features.tickets.schemas import (
    DashboardSummary,
    MessageCreateRequest,
    Pagination,
    PublicTimelineItem,
    TicketCounts,
    TicketCreateRequest,
    TicketDetail,
    TicketPage,
    TicketStatus,
    TicketSummary,
    TicketTimeline,
)
from app.features.users.models import User

_PUBLIC_EVENT_SUMMARIES = {
    "ticket_created": "Request submitted",
    "status_changed": "Request status updated",
    "ticket_reopened": "Request reopened",
}


def _customer_query(user: User) -> Select[Ticket]:
    return select(Ticket).where(Ticket.customer_id == user.id)


def create_customer_ticket(db: Session, user: User, payload: TicketCreateRequest) -> TicketDetail:
    ticket = Ticket(
        customer_id=user.id,
        subject=payload.subject,
        description=payload.description,
        category=payload.category,
        priority="medium",
        status="open",
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=user.id,
            event_type="ticket_created",
            visibility="public",
            new_value={"reference": ticket.reference},
        )
    )
    db.commit()
    db.refresh(ticket)
    return TicketDetail.model_validate(ticket)


def list_customer_tickets(
    db: Session,
    user: User,
    *,
    page: int,
    page_size: int,
    status: TicketStatus | None,
    category: str | None,
    query: str | None,
) -> TicketPage:
    statement = _customer_query(user)
    if status is not None:
        statement = statement.where(Ticket.status == status)
    if category is not None:
        statement = statement.where(Ticket.category == category)
    normalized_query = query.strip() if query else None
    if normalized_query:
        escaped = normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
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
    tickets = db.scalars(
        statement.order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TicketPage(
        items=[TicketSummary.model_validate(ticket) for ticket in tickets],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=ceil(total_items / page_size) if total_items else 0,
        ),
    )


def customer_ticket_or_404(db: Session, user: User, ticket_id: UUID) -> Ticket:
    ticket = db.scalar(_customer_query(user).where(Ticket.id == ticket_id))
    if ticket is None:
        raise ApiError(404, "TICKET_NOT_FOUND", "The requested ticket was not found.")
    return ticket


def get_customer_ticket(db: Session, user: User, ticket_id: UUID) -> TicketDetail:
    ticket = customer_ticket_or_404(db, user, ticket_id)
    return TicketDetail.model_validate(ticket)


def create_customer_reply(
    db: Session,
    user: User,
    ticket_id: UUID,
    payload: MessageCreateRequest,
) -> PublicTimelineItem:
    if payload.visibility == "internal":
        raise ApiError(403, "FORBIDDEN", "Customer replies must be public.")
    ticket = db.scalar(
        _customer_query(user).where(Ticket.id == ticket_id).with_for_update()
    )
    if ticket is None:
        raise ApiError(404, "TICKET_NOT_FOUND", "The requested ticket was not found.")
    if ticket.status in {"resolved", "closed"}:
        raise ApiError(
            409,
            "TICKET_NOT_WRITABLE",
            "This request is not accepting replies in its current state.",
        )

    message = TicketMessage(
        ticket_id=ticket.id,
        author_id=user.id,
        body=payload.body,
        visibility="public",
    )
    db.add(message)
    ticket.updated_at = datetime.now(UTC)
    ticket.version += 1
    db.flush()
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_id=user.id,
            event_type="public_message_added",
            visibility="public",
            new_value={"message_id": str(message.id)},
        )
    )
    if ticket.status == "waiting_customer":
        ticket.status = "in_progress"
        db.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=user.id,
                event_type="status_changed",
                visibility="public",
                old_value={"status": "waiting_customer"},
                new_value={"status": "in_progress"},
            )
        )
    db.commit()
    db.refresh(message)
    return PublicTimelineItem(
        kind="message",
        id=message.id,
        created_at=message.created_at,
        actor_name=user.full_name,
        body=message.body,
    )


def get_customer_timeline(db: Session, user: User, ticket_id: UUID) -> TicketTimeline:
    ticket = customer_ticket_or_404(db, user, ticket_id)
    message_rows = db.execute(
        select(TicketMessage, User.full_name)
        .join(User, TicketMessage.author_id == User.id)
        .where(TicketMessage.ticket_id == ticket.id, TicketMessage.visibility == "public")
    ).all()
    event_rows = db.execute(
        select(TicketEvent, User.full_name)
        .outerjoin(User, TicketEvent.actor_id == User.id)
        .where(
            TicketEvent.ticket_id == ticket.id,
            TicketEvent.visibility == "public",
            TicketEvent.event_type != "public_message_added",
        )
    ).all()

    items = [
        PublicTimelineItem(
            kind="message",
            id=message.id,
            created_at=message.created_at,
            actor_name=author_name,
            body=message.body,
        )
        for message, author_name in message_rows
    ]
    items.extend(
        PublicTimelineItem(
            kind="event",
            id=event.id,
            created_at=event.created_at,
            actor_name=actor_name or "CaseFlow",
            summary=_PUBLIC_EVENT_SUMMARIES.get(event.event_type, "Request updated"),
        )
        for event, actor_name in event_rows
    )
    items.sort(key=lambda item: (item.created_at, str(item.id)))
    return TicketTimeline(ticket_id=ticket.id, items=items)


def get_customer_dashboard(db: Session, user: User) -> DashboardSummary:
    rows = db.execute(
        select(Ticket.status, func.count(Ticket.id))
        .where(Ticket.customer_id == user.id)
        .group_by(Ticket.status)
    ).all()
    counts: dict[str, int] = {status: int(count) for status, count in rows}
    recent = db.scalars(
        _customer_query(user).order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(5)
    ).all()
    return DashboardSummary(
        ticket_counts=TicketCounts(
            **{status: counts.get(status, 0) for status in TicketCounts.model_fields}
        ),
        recent_tickets=[TicketSummary.model_validate(ticket) for ticket in recent],
        total_tickets=sum(counts.values()),
    )
