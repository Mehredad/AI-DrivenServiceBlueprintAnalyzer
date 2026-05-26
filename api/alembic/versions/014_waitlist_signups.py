"""014 — waitlist_signups table

Revision ID: 014
Revises: 013
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Table may already exist in production (created before this migration was tracked)
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "waitlist_signups"):
        op.create_table(
            "waitlist_signups",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("email", sa.String(320), nullable=False),
            sa.Column("full_name", sa.String(200)),
            sa.Column("job_title", sa.String(200)),
            sa.Column("industry", sa.String(200)),
            sa.Column("company", sa.String(200)),
            sa.Column("use_case", sa.String(2000)),
            sa.Column("source", sa.String(100), server_default="landing_hero_cta"),
            sa.Column("referrer", sa.String(500)),
            sa.Column("utm_source", sa.String(200)),
            sa.Column("utm_medium", sa.String(200)),
            sa.Column("utm_campaign", sa.String(200)),
            sa.Column("marketing_consent", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("status", sa.String(20), nullable=False, server_default="new"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    # Unique on lowercased email — expression index, not inline constraint
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_waitlist_email_lower ON waitlist_signups (lower(email))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_waitlist_created ON waitlist_signups (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_waitlist_status ON waitlist_signups (status)")


def downgrade() -> None:
    op.drop_index("ix_waitlist_status", table_name="waitlist_signups")
    op.drop_index("ix_waitlist_created", table_name="waitlist_signups")
    op.execute("DROP INDEX IF EXISTS ix_waitlist_email_lower")
    op.drop_table("waitlist_signups")
