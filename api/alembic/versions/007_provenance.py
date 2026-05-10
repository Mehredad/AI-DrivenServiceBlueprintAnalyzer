"""Add provenance columns to elements

Revision ID: 007
Revises: 006
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("elements", sa.Column(
        "created_by_user_id", UUID(as_uuid=False),
        sa.ForeignKey("users.id"), nullable=True,
    ))
    op.add_column("elements", sa.Column(
        "created_by_actor", sa.String(30), nullable=False,
        server_default=sa.text("'user'"),
    ))
    op.add_column("elements", sa.Column(
        "updated_by_user_id", UUID(as_uuid=False),
        sa.ForeignKey("users.id"), nullable=True,
    ))
    op.add_column("elements", sa.Column(
        "updated_by_actor", sa.String(30), nullable=False,
        server_default=sa.text("'user'"),
    ))


def downgrade() -> None:
    op.drop_column("elements", "updated_by_actor")
    op.drop_column("elements", "updated_by_user_id")
    op.drop_column("elements", "created_by_actor")
    op.drop_column("elements", "created_by_user_id")
