"""Add import_jobs table

Revision ID: 006
Revises: 005
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id",           UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",     UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("upload_id",    UUID(as_uuid=False), sa.ForeignKey("uploads.id"), nullable=False),
        sa.Column("user_id",      UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status",       sa.Text(), nullable=False, server_default="queued"),
        sa.Column("result",       JSONB),
        sa.Column("error",        sa.Text()),
        sa.Column("started_at",   sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("token_count",  sa.Integer()),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_import_jobs_board", "import_jobs", ["board_id"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_board", "import_jobs")
    op.drop_table("import_jobs")
