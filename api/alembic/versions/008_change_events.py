"""Add change_events table for PRD-17a history tracking

Revision ID: 008
Revises: 007
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "change_events",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "board_id", UUID(as_uuid=False),
            sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "actor_user_id", UUID(as_uuid=False),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column("actor_type", sa.String(30), nullable=False, server_default="user"),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("before_snapshot", JSONB(), nullable=True),
        sa.Column("after_snapshot", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_change_events_board_id_created_at",
        "change_events",
        ["board_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_change_events_board_id_created_at", table_name="change_events")
    op.drop_table("change_events")
