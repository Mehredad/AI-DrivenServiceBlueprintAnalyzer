"""add has_seen_onboarding to users

Revision ID: 004
Revises: 003
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('has_seen_onboarding', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    op.drop_column('users', 'has_seen_onboarding')
