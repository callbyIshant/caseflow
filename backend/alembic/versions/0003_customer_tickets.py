"""Add customer tickets, public messages and append-only events.

Revision ID: 0003_customer_tickets
Revises: 0002_users_sessions
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_customer_tickets"
down_revision: str | None = "0002_users_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_number", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.String(length=8), server_default="medium", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("category IN ('account', 'billing', 'technical', 'general')", name="ck_tickets_category"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_tickets_priority"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'waiting_customer', 'resolved', 'closed')", name="ck_tickets_status"),
        sa.CheckConstraint("length(subject) BETWEEN 8 AND 150", name="ck_tickets_subject_length"),
        sa.CheckConstraint("length(description) BETWEEN 30 AND 5000", name="ck_tickets_description_length"),
        sa.CheckConstraint("status != 'resolved' OR resolved_at IS NOT NULL", name="ck_tickets_resolved_at"),
        sa.CheckConstraint("status != 'closed' OR closed_at IS NOT NULL", name="ck_tickets_closed_at"),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_number", name="uq_tickets_ticket_number"),
    )
    op.create_index("ix_tickets_customer_created", "tickets", ["customer_id", "created_at", "id"], unique=False)
    op.create_index("ix_tickets_status_created", "tickets", ["status", "created_at", "id"], unique=False)
    op.create_index("ix_tickets_assignee_status_updated", "tickets", ["assignee_id", "status", "updated_at"], unique=False)

    op.create_table(
        "ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=8), server_default="public", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("visibility IN ('public', 'internal')", name="ck_ticket_messages_visibility"),
        sa.CheckConstraint("length(body) BETWEEN 1 AND 3000", name="ck_ticket_messages_body_length"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_messages_ticket_created", "ticket_messages", ["ticket_id", "created_at", "id"], unique=False)

    op.create_table(
        "ticket_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=8), server_default="internal", nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('ticket_created', 'ticket_claimed', 'ticket_assigned', 'priority_changed', "
            "'status_changed', 'ticket_reopened', 'public_message_added', 'internal_note_added')",
            name="ck_ticket_events_event_type",
        ),
        sa.CheckConstraint("visibility IN ('public', 'internal')", name="ck_ticket_events_visibility"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_events_ticket_created", "ticket_events", ["ticket_id", "created_at", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ticket_events_ticket_created", table_name="ticket_events")
    op.drop_table("ticket_events")
    op.drop_index("ix_ticket_messages_ticket_created", table_name="ticket_messages")
    op.drop_table("ticket_messages")
    op.drop_index("ix_tickets_assignee_status_updated", table_name="tickets")
    op.drop_index("ix_tickets_status_created", table_name="tickets")
    op.drop_index("ix_tickets_customer_created", table_name="tickets")
    op.drop_table("tickets")
