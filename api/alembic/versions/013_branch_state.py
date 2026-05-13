"""013 — branch state snapshot + element branch_id

Revision ID: 013
Revises: 262faef5b9b5
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "262faef5b9b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Branches get a state_snapshot column (stores swimlanes+steps for this branch)
    op.add_column("branches", sa.Column("state_snapshot", sa.JSON(), nullable=True))

    # Elements get a branch_id FK (NULL = main/default branch)
    op.add_column(
        "elements",
        sa.Column(
            "branch_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_elements_branch_id", "elements", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_elements_branch_id", "elements")
    op.drop_column("elements", "branch_id")
    op.drop_column("branches", "state_snapshot")
