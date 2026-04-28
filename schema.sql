-- Blueprint AI — Complete Database Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query → Paste → Run
-- Safe to re-run: all statements use CREATE IF NOT EXISTS / IF NOT EXISTS guards.

-- ── Shared auto-update trigger function ──────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            VARCHAR(255) NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    full_name        VARCHAR(255),
    role             VARCHAR(50)  NOT NULL DEFAULT 'designer',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login       TIMESTAMPTZ,
    is_active        BOOLEAN      NOT NULL DEFAULT true,
    has_seen_onboarding BOOLEAN   NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- ── refresh_tokens ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX        IF NOT EXISTS ix_refresh_tokens_user_id    ON refresh_tokens (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens (token_hash);

-- ── boards ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS boards (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID        NOT NULL REFERENCES users(id),
    title       VARCHAR(500) NOT NULL,
    domain      VARCHAR(100),
    phase       VARCHAR(50)  NOT NULL DEFAULT 'understand',
    state       JSONB        NOT NULL DEFAULT '{}',
    version     INTEGER      NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_archived BOOLEAN      NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS ix_boards_owner_id   ON boards (owner_id);
CREATE INDEX IF NOT EXISTS ix_boards_updated_at ON boards (updated_at);

DROP TRIGGER IF EXISTS boards_updated_at ON boards;
CREATE TRIGGER boards_updated_at
    BEFORE UPDATE ON boards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── board_collaborators ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS board_collaborators (
    board_id  UUID        NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    user_id   UUID        NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    role      VARCHAR(50) NOT NULL DEFAULT 'editor',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (board_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_board_collaborators_user_id ON board_collaborators (user_id);

-- ── capabilities ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS capabilities (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id     UUID        NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    cap_id       VARCHAR(20) NOT NULL,
    name         VARCHAR(255) NOT NULL,
    type         VARCHAR(100),
    risk_level   VARCHAR(20),
    frontstage   BOOLEAN      NOT NULL DEFAULT true,
    xai_strategy VARCHAR(255),
    autonomy     VARCHAR(100),
    input_spec   TEXT,
    output_spec  TEXT,
    owner        VARCHAR(255),
    status       VARCHAR(50)  NOT NULL DEFAULT 'draft',
    notes        TEXT,
    meta         JSONB        NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_capabilities_board_id ON capabilities (board_id);

DROP TRIGGER IF EXISTS capabilities_updated_at ON capabilities;
CREATE TRIGGER capabilities_updated_at
    BEFORE UPDATE ON capabilities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── elements ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS elements (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID        NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    swimlane_id UUID,
    step_id     UUID,
    type        VARCHAR(50)  NOT NULL,
    name        VARCHAR(200) NOT NULL,
    notes       TEXT,
    owner       VARCHAR(255),
    status      VARCHAR(30)  NOT NULL DEFAULT 'draft',
    meta        JSONB        NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_elements_board_id   ON elements (board_id);
CREATE INDEX IF NOT EXISTS ix_elements_board_type ON elements (board_id, type);

DROP TRIGGER IF EXISTS elements_updated_at ON elements;
CREATE TRIGGER elements_updated_at
    BEFORE UPDATE ON elements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── chat_messages ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_messages (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID        NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    user_id     UUID        REFERENCES users(id),
    role        VARCHAR(20) NOT NULL,
    content     TEXT        NOT NULL,
    attachments JSONB       NOT NULL DEFAULT '[]',
    token_count INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_chat_messages_board_id   ON chat_messages (board_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_created_at ON chat_messages (created_at);

-- ── insights ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS insights (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id     UUID        NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    severity     VARCHAR(20),
    title        VARCHAR(500) NOT NULL,
    description  TEXT,
    source_ref   VARCHAR(500),
    is_dismissed BOOLEAN      NOT NULL DEFAULT false,
    dismissed_by UUID        REFERENCES users(id),
    dismissed_at TIMESTAMPTZ,
    actions      JSONB        NOT NULL DEFAULT '[]',
    generated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_insights_board_id     ON insights (board_id);
CREATE INDEX IF NOT EXISTS ix_insights_is_dismissed ON insights (is_dismissed);

-- ── governance_decisions ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS governance_decisions (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id      UUID        NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    capability_id UUID        REFERENCES capabilities(id),
    decision_type VARCHAR(100),
    title         VARCHAR(500),
    rationale     TEXT,
    decided_by    UUID        REFERENCES users(id),
    decided_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_review   TIMESTAMPTZ,
    meta          JSONB        NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_governance_board_id   ON governance_decisions (board_id);
CREATE INDEX IF NOT EXISTS ix_governance_decided_at ON governance_decisions (decided_at);

-- ── audit_logs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID        REFERENCES boards(id),
    user_id     UUID        REFERENCES users(id),
    action      VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id   UUID,
    diff        JSONB,
    ip_address  INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_board_id   ON audit_logs (board_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);

-- ── exports ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exports (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id   UUID        NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    user_id    UUID        REFERENCES users(id),
    format     VARCHAR(10) NOT NULL,
    file_size  INTEGER,
    file_data  BYTEA,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_exports_board_id ON exports (board_id);

-- ── uploads ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS uploads (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id     UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(id),
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_uploads_board ON uploads (board_id);

-- ── import_jobs ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS import_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id     UUID NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    upload_id    UUID NOT NULL REFERENCES uploads(id),
    user_id      UUID NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'queued',
    result       JSONB,
    error        TEXT,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    token_count  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_import_jobs_board ON import_jobs (board_id);

-- ── alembic version marker (tells alembic all migrations are applied) ─────────
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('006');
