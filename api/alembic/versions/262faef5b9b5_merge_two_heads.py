"""merge_two_heads

Revision ID: 262faef5b9b5
Revises: 012, 23530278c355
Create Date: 2026-05-12 23:18:06.479375
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '262faef5b9b5'
down_revision: Union[str, None] = ('012', '23530278c355')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
