from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TicketCategory = Literal["account", "billing", "technical", "general"]
TicketStatus = Literal["open", "in_progress", "waiting_customer", "resolved", "closed"]
TicketPriority = Literal["low", "medium", "high"]


class TicketCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=8, max_length=150)
    description: str = Field(min_length=30, max_length=5000)
    category: TicketCategory

    @field_validator("subject")
    @classmethod
    def clean_subject(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not 8 <= len(normalized) <= 150:
            raise ValueError("Subject must contain 8–150 characters after trimming.")
        return normalized

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        normalized = value.strip()
        if not 30 <= len(normalized) <= 5000:
            raise ValueError("Description must contain 30–5000 characters after trimming.")
        return normalized


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=3000)
    visibility: Literal["public", "internal"] = "public"

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reply text cannot be blank.")
        return normalized


class TicketStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TicketStatus
    resolution_message: str | None = Field(default=None, min_length=10, max_length=1000)

    @field_validator("resolution_message")
    @classmethod
    def clean_resolution_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not 10 <= len(normalized) <= 1000:
            raise ValueError("Resolution summary must contain 10–1000 characters.")
        return normalized


class TicketPriorityUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: TicketPriority


class TicketAssigneeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The field is required; explicit null means "unassign".
    assignee_id: UUID | None


class TicketReopenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=3000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not 10 <= len(normalized) <= 3000:
            raise ValueError("Reopening reason must contain 10–3000 characters.")
        return normalized


class TicketSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference: str
    subject: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketSummary):
    description: str
    resolved_at: datetime | None
    closed_at: datetime | None


class Pagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class TicketPage(BaseModel):
    items: list[TicketSummary]
    pagination: Pagination


class SupportTicketSummary(TicketSummary):
    customer_id: UUID
    customer_name: str
    assignee_id: UUID | None
    assignee_name: str | None


class SupportTicketDetail(SupportTicketSummary):
    description: str
    resolved_at: datetime | None
    closed_at: datetime | None
    version: int


class SupportTicketPage(BaseModel):
    items: list[SupportTicketSummary]
    pagination: Pagination


class SupportUserSummary(BaseModel):
    id: UUID
    full_name: str
    role: Literal["agent", "admin"]


class TicketCounts(BaseModel):
    open: int = 0
    in_progress: int = 0
    waiting_customer: int = 0
    resolved: int = 0
    closed: int = 0


class DashboardSummary(BaseModel):
    ticket_counts: TicketCounts
    recent_tickets: list[TicketSummary]
    total_tickets: int


class PublicTimelineItem(BaseModel):
    kind: Literal["message", "event"]
    id: UUID
    created_at: datetime
    actor_name: str
    visibility: Literal["public"] = "public"
    body: str | None = None
    summary: str | None = None


class TicketTimeline(BaseModel):
    ticket_id: UUID
    items: list[PublicTimelineItem]


class SupportTimelineItem(BaseModel):
    kind: Literal["message", "event"]
    id: UUID
    created_at: datetime
    actor_name: str
    visibility: Literal["public", "internal"]
    body: str | None = None
    summary: str | None = None
    event_type: str | None = None
    old_value: dict[str, object] | None = None
    new_value: dict[str, object] | None = None


class SupportTicketTimeline(BaseModel):
    ticket_id: UUID
    items: list[SupportTimelineItem]
