"""Add commits table and commit_id to change_events (PRD-17e)

Revision ID: 009
Revises: 008
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commits",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "board_id", UUID(as_uuid=False),
            sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "author_user_id", UUID(as_uuid=False),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column("actor_type", sa.String(30), nullable=False, server_default="user"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_commits_board_id_created_at", "commits", ["board_id", "created_at"])

    op.add_column(
        "change_events",
        sa.Column(
            "commit_id", UUID(as_uuid=False),
            sa.ForeignKey("commits.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.create_index("ix_change_events_commit_id", "change_events", ["commit_id"])


def downgrade() -> None:
    op.drop_index("ix_change_events_commit_id", table_name="change_events")
    op.drop_column("change_events", "commit_id")
    op.drop_index("ix_commits_board_id_created_at", table_name="commits")
    op.drop_table("commits")
