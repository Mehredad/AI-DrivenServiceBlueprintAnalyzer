"""Add elements table

Revision ID: 002
Revises: 001
Create Date: 2026-04-25 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "elements",
        sa.Column("id",          UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",    UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("swimlane_id", UUID(as_uuid=False)),
        sa.Column("step_id",     UUID(as_uuid=False)),
        sa.Column("type",        sa.String(50),  nullable=False),
        sa.Column("name",        sa.String(200), nullable=False),
        sa.Column("notes",       sa.Text()),
        sa.Column("owner",       sa.String(255)),
        sa.Column("status",      sa.String(30),  server_default="draft"),
        sa.Column("meta",        JSONB, server_default="{}"),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_elements_board_id",   "elements", ["board_id"])
    op.create_index("ix_elements_board_type", "elements", ["board_id", "type"])

    op.execute("""
        CREATE TRIGGER elements_updated_at
        BEFORE UPDATE ON elements
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS elements_updated_at ON elements;")
    op.drop_index("ix_elements_board_type", "elements")
    op.drop_index("ix_elements_board_id",   "elements")
    op.drop_table("elements")
