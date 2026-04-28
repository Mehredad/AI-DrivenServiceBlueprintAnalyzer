"""rename phases harvest→design and improve→operate

Revision ID: 003
Revises: 002
Create Date: 2026-04-26
"""
from alembic import op

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE boards SET phase = 'design' WHERE phase = 'harvest'")
    op.execute("UPDATE boards SET phase = 'operate' WHERE phase = 'improve'")


def downgrade():
    op.execute("UPDATE boards SET phase = 'harvest' WHERE phase = 'design'")
    op.execute("UPDATE boards SET phase = 'improve' WHERE phase = 'operate'")
