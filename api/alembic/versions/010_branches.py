"""Add branches table (PRD-17d data model)

Revision ID: 010
Revises: 009
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "board_id", UUID(as_uuid=False),
            sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_by_user_id", UUID(as_uuid=False),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_branches_board_id", "branches", ["board_id"])
    op.create_unique_constraint(
        "uq_branches_board_id_name", "branches", ["board_id", "name"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_branches_board_id_name", "branches", type_="unique")
    op.drop_index("ix_branches_board_id", table_name="branches")
    op.drop_table("branches")
