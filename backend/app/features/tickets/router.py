from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import ApiError
from app.core.rate_limit import consume_rate_limit
from app.features.tickets.schemas import (
    DashboardSummary,
    MessageCreateRequest,
    PublicTimelineItem,
    SupportTicketDetail,
    SupportTicketPage,
    SupportTicketTimeline,
    SupportTimelineItem,
    SupportUserSummary,
    TicketAssigneeUpdateRequest,
    TicketCategory,
    TicketCreateRequest,
    TicketDetail,
    TicketPage,
    TicketPriority,
    TicketPriorityUpdateRequest,
    TicketReopenRequest,
    TicketStatus,
    TicketStatusUpdateRequest,
    TicketTimeline,
)
from app.features.tickets.service import (
    create_customer_reply,
    create_customer_ticket,
    get_customer_dashboard,
    get_customer_ticket,
    get_customer_timeline,
    list_customer_tickets,
)
from app.features.tickets.support_service import (
    add_support_message,
    assign_ticket,
    claim_ticket,
    get_support_ticket,
    get_support_timeline,
    list_active_support_users,
    list_support_tickets,
    reopen_ticket,
    update_ticket_priority,
    update_ticket_status,
)
from app.features.users.deps import CurrentUser
from app.features.users.models import User

router = APIRouter(prefix="/api/v1", tags=["tickets"])
Database = Annotated[Session, Depends(get_db)]


def customer_only(user: CurrentUser) -> User:
    if user.role != "customer":
        raise ApiError(403, "FORBIDDEN", "You do not have permission to do this.")
    return user


Customer = Annotated[User, Depends(customer_only)]


def support_only(user: CurrentUser) -> User:
    if user.role not in {"agent", "admin"}:
        raise ApiError(403, "FORBIDDEN", "You do not have permission to do this.")
    return user


def admin_only(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ApiError(403, "FORBIDDEN", "You do not have permission to do this.")
    return user


Support = Annotated[User, Depends(support_only)]
Admin = Annotated[User, Depends(admin_only)]


@router.get("/support/agents", response_model=list[SupportUserSummary])
def active_support_agents(db: Database, user: Admin) -> list[SupportUserSummary]:
    return list_active_support_users(db)


@router.get("/tickets/summary", response_model=DashboardSummary)
def dashboard_summary(db: Database, user: Customer) -> DashboardSummary:
    return get_customer_dashboard(db, user)


@router.post("/tickets", response_model=TicketDetail, status_code=201)
def create_ticket(payload: TicketCreateRequest, db: Database, user: Customer) -> TicketDetail:
    rate_key = f"ticket:create:user:{user.id}"
    consume_rate_limit(rate_key, 20, 24 * 60 * 60)
    return create_customer_ticket(db, user, payload)


@router.get("/tickets", response_model=SupportTicketPage | TicketPage)
def list_tickets(
    db: Database,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    status: TicketStatus | None = None,
    category: TicketCategory | None = None,
    q: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    priority: TicketPriority | None = None,
    assigned_to: Literal["me", "unassigned"] | None = None,
) -> SupportTicketPage | TicketPage:
    if user.role in {"agent", "admin"}:
        return list_support_tickets(
            db,
            user,
            page=page,
            page_size=page_size,
            status=status,
            category=category,
            priority=priority,
            assigned_to=assigned_to,
            query=q,
        )
    if priority is not None or assigned_to is not None:
        raise ApiError(403, "FORBIDDEN", "These filters are only available to support staff.")
    return list_customer_tickets(
        db,
        user,
        page=page,
        page_size=page_size,
        status=status,
        category=category,
        query=q,
    )


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetail | TicketDetail)
def get_ticket(ticket_id: UUID, db: Database, user: CurrentUser) -> SupportTicketDetail | TicketDetail:
    if user.role == "customer":
        return get_customer_ticket(db, user, ticket_id)
    return get_support_ticket(db, ticket_id)


@router.get("/tickets/{ticket_id}/timeline", response_model=SupportTicketTimeline | TicketTimeline)
def get_timeline(
    ticket_id: UUID, db: Database, user: CurrentUser
) -> SupportTicketTimeline | TicketTimeline:
    if user.role == "customer":
        return get_customer_timeline(db, user, ticket_id)
    return get_support_timeline(db, ticket_id)


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=SupportTimelineItem | PublicTimelineItem,
    status_code=201,
)
def add_message(
    ticket_id: UUID,
    payload: MessageCreateRequest,
    db: Database,
    user: CurrentUser,
    response: Response,
) -> SupportTimelineItem | PublicTimelineItem:
    response.headers["Cache-Control"] = "no-store"
    if user.role == "customer":
        return create_customer_reply(db, user, ticket_id, payload)
    return add_support_message(db, user, ticket_id, payload)


@router.post("/tickets/{ticket_id}/claim", response_model=SupportTicketDetail)
def claim(ticket_id: UUID, db: Database, user: Support) -> SupportTicketDetail:
    return claim_ticket(db, user, ticket_id)


@router.put("/tickets/{ticket_id}/assignee", response_model=SupportTicketDetail)
def update_assignee(
    ticket_id: UUID,
    payload: TicketAssigneeUpdateRequest,
    db: Database,
    user: Admin,
) -> SupportTicketDetail:
    return assign_ticket(db, user, ticket_id, payload)


@router.patch("/tickets/{ticket_id}/priority", response_model=SupportTicketDetail)
def update_priority(
    ticket_id: UUID,
    payload: TicketPriorityUpdateRequest,
    db: Database,
    user: Support,
) -> SupportTicketDetail:
    return update_ticket_priority(db, user, ticket_id, payload)


@router.patch("/tickets/{ticket_id}/status", response_model=SupportTicketDetail)
def update_status(
    ticket_id: UUID,
    payload: TicketStatusUpdateRequest,
    db: Database,
    user: Support,
) -> SupportTicketDetail:
    return update_ticket_status(db, user, ticket_id, payload)


@router.post("/tickets/{ticket_id}/reopen", response_model=SupportTicketDetail | TicketDetail)
def reopen(
    ticket_id: UUID,
    payload: TicketReopenRequest,
    db: Database,
    user: CurrentUser,
) -> SupportTicketDetail | TicketDetail:
    return reopen_ticket(db, user, ticket_id, payload)
