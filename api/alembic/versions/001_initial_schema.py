"""Initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",            UUID(as_uuid=False), primary_key=True),
        sa.Column("email",         sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name",     sa.String(255)),
        sa.Column("role",          sa.String(50),  server_default="designer"),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("last_login",    sa.DateTime(timezone=True)),
        sa.Column("is_active",     sa.Boolean(), server_default="true"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── refresh_tokens ─────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id",         UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id",    UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_refresh_tokens_user_id",    "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # ── boards ─────────────────────────────────────────────────────────────────
    op.create_table(
        "boards",
        sa.Column("id",          UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id",    UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title",       sa.String(500), nullable=False),
        sa.Column("domain",      sa.String(100)),
        sa.Column("phase",       sa.String(50),  server_default="understand"),
        sa.Column("state",       JSONB,          nullable=False, server_default="{}"),
        sa.Column("version",     sa.Integer(),   server_default="1"),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("is_archived", sa.Boolean(), server_default="false"),
    )
    op.create_index("ix_boards_owner_id",   "boards", ["owner_id"])
    op.create_index("ix_boards_updated_at", "boards", ["updated_at"])

    # ── board_collaborators ────────────────────────────────────────────────────
    op.create_table(
        "board_collaborators",
        sa.Column("board_id",  UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id",   UUID(as_uuid=False), sa.ForeignKey("users.id",  ondelete="CASCADE"), primary_key=True),
        sa.Column("role",      sa.String(50), server_default="editor"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_board_collaborators_user_id", "board_collaborators", ["user_id"])

    # ── capabilities ───────────────────────────────────────────────────────────
    op.create_table(
        "capabilities",
        sa.Column("id",           UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",     UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cap_id",       sa.String(20),  nullable=False),
        sa.Column("name",         sa.String(255), nullable=False),
        sa.Column("type",         sa.String(100)),
        sa.Column("risk_level",   sa.String(20)),
        sa.Column("frontstage",   sa.Boolean(), server_default="true"),
        sa.Column("xai_strategy", sa.String(255)),
        sa.Column("autonomy",     sa.String(100)),
        sa.Column("input_spec",   sa.Text()),
        sa.Column("output_spec",  sa.Text()),
        sa.Column("owner",        sa.String(255)),
        sa.Column("status",       sa.String(50), server_default="draft"),
        sa.Column("notes",        sa.Text()),
        sa.Column("meta",         JSONB, server_default="{}"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at",   sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_capabilities_board_id", "capabilities", ["board_id"])

    # ── chat_messages ──────────────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id",          UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",    UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",     UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("role",        sa.String(20),  nullable=False),
        sa.Column("content",     sa.Text(),      nullable=False),
        sa.Column("token_count", sa.Integer()),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_chat_messages_board_id",   "chat_messages", ["board_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    # ── insights ───────────────────────────────────────────────────────────────
    op.create_table(
        "insights",
        sa.Column("id",           UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",     UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("severity",     sa.String(20)),
        sa.Column("title",        sa.String(500), nullable=False),
        sa.Column("description",  sa.Text()),
        sa.Column("source_ref",   sa.String(500)),
        sa.Column("is_dismissed", sa.Boolean(), server_default="false"),
        sa.Column("dismissed_by", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        sa.Column("actions",      JSONB, server_default="[]"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_insights_board_id",     "insights", ["board_id"])
    op.create_index("ix_insights_is_dismissed", "insights", ["is_dismissed"])

    # ── governance_decisions ───────────────────────────────────────────────────
    op.create_table(
        "governance_decisions",
        sa.Column("id",            UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",      UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability_id", UUID(as_uuid=False), sa.ForeignKey("capabilities.id"), nullable=True),
        sa.Column("decision_type", sa.String(100)),
        sa.Column("title",         sa.String(500)),
        sa.Column("rationale",     sa.Text()),
        sa.Column("decided_by",    UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at",    sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("next_review",   sa.DateTime(timezone=True)),
        sa.Column("meta",          JSONB, server_default="{}"),
    )
    op.create_index("ix_governance_board_id",   "governance_decisions", ["board_id"])
    op.create_index("ix_governance_decided_at", "governance_decisions", ["decided_at"])

    # ── audit_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id",          UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",    UUID(as_uuid=False), sa.ForeignKey("boards.id"), nullable=True),
        sa.Column("user_id",     UUID(as_uuid=False), sa.ForeignKey("users.id"),  nullable=True),
        sa.Column("action",      sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id",   UUID(as_uuid=False)),
        sa.Column("diff",        JSONB),
        sa.Column("ip_address",  INET()),
        sa.Column("user_agent",  sa.Text()),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_audit_logs_board_id",   "audit_logs", ["board_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── exports ────────────────────────────────────────────────────────────────
    op.create_table(
        "exports",
        sa.Column("id",         UUID(as_uuid=False), primary_key=True),
        sa.Column("board_id",   UUID(as_uuid=False), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",    UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("format",     sa.String(10), nullable=False),
        sa.Column("file_size",  sa.Integer()),
        sa.Column("file_data",  sa.LargeBinary()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_exports_board_id", "exports", ["board_id"])

    # ── updated_at trigger (auto-update boards.updated_at) ────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER boards_updated_at
        BEFORE UPDATE ON boards
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
        CREATE TRIGGER capabilities_updated_at
        BEFORE UPDATE ON capabilities
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    """)


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_table("audit_logs")
    op.drop_table("governance_decisions")
    op.drop_table("insights")
    op.drop_table("chat_messages")
    op.drop_table("capabilities")
    op.drop_table("board_collaborators")
    op.drop_table("boards")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at CASCADE;")
