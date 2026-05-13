"""Add connectors table (PRD-18)

Revision ID: 011
Revises: 010
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "board_id", UUID(as_uuid=False),
            sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("source_step_id",    UUID(as_uuid=False), nullable=True),
        sa.Column(
            "source_element_id", UUID(as_uuid=False),
            sa.ForeignKey("elements.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("target_step_id",    UUID(as_uuid=False), nullable=True),
        sa.Column(
            "target_element_id", UUID(as_uuid=False),
            sa.ForeignKey("elements.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("tier",           sa.Text(), nullable=False),
        sa.Column("connector_type", sa.Text(), nullable=False),
        sa.Column("label",     sa.Text(),  nullable=True),
        sa.Column("notes",     sa.Text(),  nullable=True),
        sa.Column("waypoints", sa.JSON(),  nullable=True, server_default="[]"),
        sa.Column(
            "created_by_user_id", UUID(as_uuid=False),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column("created_by_actor",   sa.Text(), nullable=False, server_default="user"),
        sa.Column(
            "updated_by_user_id", UUID(as_uuid=False),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column("updated_by_actor",   sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        # Integrity: exactly one source kind, exactly one target kind.
        sa.CheckConstraint(
            "(source_step_id IS NOT NULL)::int + (source_element_id IS NOT NULL)::int = 1",
            name="chk_one_source",
        ),
        sa.CheckConstraint(
            "(target_step_id IS NOT NULL)::int + (target_element_id IS NOT NULL)::int = 1",
            name="chk_one_target",
        ),
        # No self-loops at the same endpoint.
        sa.CheckConstraint(
            "(source_step_id IS DISTINCT FROM target_step_id) OR "
            "(source_element_id IS DISTINCT FROM target_element_id) OR "
            "(source_step_id IS NULL AND target_step_id IS NULL) OR "
            "(source_element_id IS NULL AND target_element_id IS NULL)",
            name="chk_not_self_loop",
        ),
    )
    op.create_index("ix_connectors_board",       "connectors", ["board_id"])
    op.create_index(
        "ix_connectors_source_step", "connectors", ["source_step_id"],
        postgresql_where=sa.text("source_step_id IS NOT NULL"),
    )
    op.create_index(
        "ix_connectors_source_el", "connectors", ["source_element_id"],
        postgresql_where=sa.text("source_element_id IS NOT NULL"),
    )
    op.create_index(
        "ix_connectors_target_step", "connectors", ["target_step_id"],
        postgresql_where=sa.text("target_step_id IS NOT NULL"),
    )
    op.create_index(
        "ix_connectors_target_el", "connectors", ["target_element_id"],
        postgresql_where=sa.text("target_element_id IS NOT NULL"),
    )
    op.create_index("ix_connectors_type", "connectors", ["board_id", "connector_type"])


def downgrade() -> None:
    op.drop_index("ix_connectors_type",       table_name="connectors")
    op.drop_index("ix_connectors_target_el",  table_name="connectors")
    op.drop_index("ix_connectors_target_step",table_name="connectors")
    op.drop_index("ix_connectors_source_el",  table_name="connectors")
    op.drop_index("ix_connectors_source_step",table_name="connectors")
    op.drop_index("ix_connectors_board",      table_name="connectors")
    op.drop_table("connectors")
