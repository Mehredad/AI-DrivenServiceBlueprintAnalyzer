"""Add uploads table and chat_messages.attachments

Revision ID: 005
Revises: 004
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id",           UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",     UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",      UUID(as_uuid=False), sa.ForeignKey("users.id"),  nullable=False),
        sa.Column("filename",     sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes",   sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_uploads_board", "uploads", ["board_id"])

    op.add_column(
        "chat_messages",
        sa.Column("attachments", JSONB, server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "attachments")
    op.drop_index("ix_uploads_board", "uploads")
    op.drop_table("uploads")
