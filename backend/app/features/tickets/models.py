from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('account', 'billing', 'technical', 'general')",
            name="ck_tickets_category",
        ),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_tickets_priority"),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'waiting_customer', 'resolved', 'closed')",
            name="ck_tickets_status",
        ),
        CheckConstraint("length(subject) BETWEEN 8 AND 150", name="ck_tickets_subject_length"),
        CheckConstraint(
            "length(description) BETWEEN 30 AND 5000", name="ck_tickets_description_length"
        ),
        CheckConstraint("status != 'resolved' OR resolved_at IS NOT NULL", name="ck_tickets_resolved_at"),
        CheckConstraint("status != 'closed' OR closed_at IS NOT NULL", name="ck_tickets_closed_at"),
        UniqueConstraint("ticket_number", name="uq_tickets_ticket_number"),
        Index("ix_tickets_customer_created", "customer_id", "created_at", "id"),
        Index("ix_tickets_status_created", "status", "created_at", "id"),
        Index("ix_tickets_assignee_status_updated", "assignee_id", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_number: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="medium", server_default="medium")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open", server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    @property
    def reference(self) -> str:
        return f"CF-{self.ticket_number:06d}"


class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    __table_args__ = (
        CheckConstraint("visibility IN ('public', 'internal')", name="ck_ticket_messages_visibility"),
        CheckConstraint("length(body) BETWEEN 1 AND 3000", name="ck_ticket_messages_body_length"),
        Index("ix_ticket_messages_ticket_created", "ticket_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(8), nullable=False, default="public", server_default="public")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('ticket_created', 'ticket_claimed', 'ticket_assigned', "
            "'priority_changed', 'status_changed', 'ticket_reopened', "
            "'public_message_added', 'internal_note_added')",
            name="ck_ticket_events_event_type",
        ),
        CheckConstraint("visibility IN ('public', 'internal')", name="ck_ticket_events_visibility"),
        Index("ix_ticket_events_ticket_created", "ticket_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    visibility: Mapped[str] = mapped_column(String(8), nullable=False, default="internal", server_default="internal")
    old_value: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
