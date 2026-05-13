"""Add waypoints column to connectors (PRD-19)."""
from alembic import op
import sqlalchemy as sa

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # waypoints was already added in migration 011; no-op here
    pass


def downgrade() -> None:
    pass
