"""
Blueprint AI — All ORM Models

Single file for the MVP. Every table the application uses is defined here.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, LargeBinary, func, JSON, Uuid,
)
from sqlalchemy.orm import relationship
from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# USERS & AUTH
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name     = Column(String(255))
    role          = Column(String(50), default="designer")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    last_login    = Column(DateTime(timezone=True))
    is_active     = Column(Boolean, default=True)

    has_seen_onboarding  = Column(Boolean, server_default='false', default=False)

    refresh_tokens       = relationship("RefreshToken",       back_populates="user", cascade="all, delete-orphan")
    owned_boards         = relationship("Board",              back_populates="owner", foreign_keys="Board.owner_id")
    board_collaborations = relationship("BoardCollaborator",  back_populates="user",  cascade="all, delete-orphan")
    chat_messages        = relationship("ChatMessage",        back_populates="user")
    governance_decisions = relationship("GovernanceDecision", back_populates="decided_by_user", foreign_keys="GovernanceDecision.decided_by")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id    = Column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")


# ─────────────────────────────────────────────────────────────────────────────
# BOARDS
# ─────────────────────────────────────────────────────────────────────────────

class Board(Base):
    __tablename__ = "boards"

    id          = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    owner_id    = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    title       = Column(String(500), nullable=False)
    domain      = Column(String(100))
    phase       = Column(String(50), default="understand")
    state       = Column(JSON, nullable=False, default=dict)
    version     = Column(Integer, default=1)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_archived = Column(Boolean, default=False)

    owner         = relationship("User",              back_populates="owned_boards", foreign_keys=[owner_id])
    collaborators = relationship("BoardCollaborator", back_populates="board", cascade="all, delete-orphan")
    capabilities  = relationship("Capability",        back_populates="board", cascade="all, delete-orphan")
    elements      = relationship("Element",           back_populates="board", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage",       back_populates="board", cascade="all, delete-orphan")
    insights      = relationship("Insight",           back_populates="board", cascade="all, delete-orphan")
    governance    = relationship("GovernanceDecision",back_populates="board", cascade="all, delete-orphan")
    audit_logs    = relationship("AuditLog",          back_populates="board")
    exports       = relationship("Export",            back_populates="board", cascade="all, delete-orphan")
    uploads       = relationship("Upload",            back_populates="board", cascade="all, delete-orphan")
    import_jobs   = relationship("ImportJob",         back_populates="board", cascade="all, delete-orphan")
    change_events = relationship("ChangeEvent",       back_populates="board", cascade="all, delete-orphan")
    commits       = relationship("Commit",            back_populates="board", cascade="all, delete-orphan")


class BoardCollaborator(Base):
    __tablename__ = "board_collaborators"

    board_id  = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True)
    user_id   = Column(Uuid(as_uuid=False), ForeignKey("users.id",  ondelete="CASCADE"), primary_key=True)
    role      = Column(String(50), default="editor")   # viewer | editor | admin
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    board = relationship("Board", back_populates="collaborators")
    user  = relationship("User",  back_populates="board_collaborations")


# ─────────────────────────────────────────────────────────────────────────────
# CAPABILITIES
# ─────────────────────────────────────────────────────────────────────────────

class Capability(Base):
    __tablename__ = "capabilities"

    id           = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id     = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    cap_id       = Column(String(20),  nullable=False)   # "CAP-001"
    name         = Column(String(255), nullable=False)
    type         = Column(String(100))
    risk_level   = Column(String(20))
    frontstage   = Column(Boolean, default=True)
    xai_strategy = Column(String(255))
    autonomy     = Column(String(100))
    input_spec   = Column(Text)
    output_spec  = Column(Text)
    owner        = Column(String(255))
    status       = Column(String(50), default="draft")
    notes        = Column(Text)
    meta         = Column(JSON, default=dict)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    board                = relationship("Board",              back_populates="capabilities")
    governance_decisions = relationship("GovernanceDecision", back_populates="capability")


# ─────────────────────────────────────────────────────────────────────────────
# ELEMENTS (unified element model — PRD-03)
# ─────────────────────────────────────────────────────────────────────────────

class Element(Base):
    __tablename__ = "elements"

    id          = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id    = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    swimlane_id = Column(Uuid(as_uuid=False))     # soft ref to boards.state swimlane UUID
    step_id     = Column(Uuid(as_uuid=False))     # soft ref to boards.state step UUID
    type        = Column(String(50), nullable=False)
    name        = Column(String(200), nullable=False)
    notes       = Column(Text)
    owner       = Column(String(255))
    status      = Column(String(30), default="draft")
    meta        = Column(JSON, default=dict)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by_user_id = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_by_actor   = Column(String(30), nullable=False, server_default="user", default="user")
    updated_by_user_id = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by_actor   = Column(String(30), nullable=False, server_default="user", default="user")

    board = relationship("Board", back_populates="elements")


# ─────────────────────────────────────────────────────────────────────────────
# AI CHAT HISTORY
# ─────────────────────────────────────────────────────────────────────────────

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id          = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id    = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id     = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    role        = Column(String(20),  nullable=False)   # user | assistant
    content     = Column(Text,        nullable=False)
    attachments = Column(JSON, default=list)            # [{"upload_id","filename","content_type"}]
    token_count = Column(Integer)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    board = relationship("Board", back_populates="chat_messages")
    user  = relationship("User",  back_populates="chat_messages")


# ─────────────────────────────────────────────────────────────────────────────
# INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

class Insight(Base):
    __tablename__ = "insights"

    id           = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id     = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    severity     = Column(String(20))    # high | medium | low | info | positive
    title        = Column(String(500), nullable=False)
    description  = Column(Text)
    source_ref   = Column(String(500))
    is_dismissed = Column(Boolean, default=False, index=True)
    dismissed_by = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    dismissed_at = Column(DateTime(timezone=True))
    actions      = Column(JSON, default=list)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    board = relationship("Board", back_populates="insights")


# ─────────────────────────────────────────────────────────────────────────────
# GOVERNANCE
# ─────────────────────────────────────────────────────────────────────────────

class GovernanceDecision(Base):
    __tablename__ = "governance_decisions"

    id            = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id      = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_id = Column(Uuid(as_uuid=False), ForeignKey("capabilities.id"), nullable=True)
    decision_type = Column(String(100))   # approve | modify | pause | escalate
    title         = Column(String(500))
    rationale     = Column(Text)
    decided_by    = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    decided_at    = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    next_review   = Column(DateTime(timezone=True))
    meta          = Column(JSON, default=dict)

    board           = relationship("Board",      back_populates="governance")
    capability      = relationship("Capability", back_populates="governance_decisions")
    decided_by_user = relationship("User",       back_populates="governance_decisions", foreign_keys=[decided_by])


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG  (application enforces INSERT-only — no UPDATE/DELETE)
# ─────────────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id    = Column(Uuid(as_uuid=False), ForeignKey("boards.id"), nullable=True, index=True)
    user_id     = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    action      = Column(String(100), nullable=False)   # board.update | capability.create | …
    entity_type = Column(String(100))
    entity_id   = Column(Uuid(as_uuid=False))
    diff        = Column(JSON)
    ip_address  = Column(String(45))
    user_agent  = Column(Text)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    board = relationship("Board", back_populates="audit_logs")


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

class Export(Base):
    __tablename__ = "exports"

    id         = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id   = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    format     = Column(String(10), nullable=False)   # pdf | json
    file_size  = Column(Integer)
    file_data  = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    board = relationship("Board", back_populates="exports")


# ─────────────────────────────────────────────────────────────────────────────
# FILE UPLOADS (PRD-10)
# ─────────────────────────────────────────────────────────────────────────────

class Upload(Base):
    __tablename__ = "uploads"

    id           = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id     = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id      = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=False)
    filename     = Column(Text, nullable=False)
    content_type = Column(Text, nullable=False)
    size_bytes   = Column(Integer, nullable=False)
    storage_path = Column(Text, nullable=False)    # boards/{board_id}/uploads/{uuid}-{name}
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    board = relationship("Board", back_populates="uploads")


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT JOBS (PRD-11)
# ─────────────────────────────────────────────────────────────────────────────

class ImportJob(Base):
    __tablename__ = "import_jobs"

    id           = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id     = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_id    = Column(Uuid(as_uuid=False), ForeignKey("uploads.id"), nullable=False)
    user_id      = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=False)
    status       = Column(Text, nullable=False, default="queued")   # queued|processing|done|partial|failed
    result       = Column(JSON)
    error        = Column(Text)
    started_at   = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    token_count  = Column(Integer)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    board = relationship("Board", back_populates="import_jobs")


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE EVENTS (PRD-17a — snapshot-based history)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# COMMITS (PRD-17e — semantic grouping of change events)
# ─────────────────────────────────────────────────────────────────────────────

class Commit(Base):
    __tablename__ = "commits"

    id             = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id       = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    actor_type     = Column(String(30), nullable=False, server_default="user", default="user")
    message        = Column(Text, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    board  = relationship("Board", back_populates="commits")
    events = relationship("ChangeEvent", back_populates="commit")


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id            = Column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    board_id      = Column(Uuid(as_uuid=False), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=True)
    actor_type    = Column(String(30), nullable=False, server_default="user", default="user")
    entity_type   = Column(String(50), nullable=False)
    entity_id     = Column(String(50), nullable=False)
    operation     = Column(String(20), nullable=False)  # create | update | delete | restore
    before_snapshot = Column(JSON, nullable=True)
    after_snapshot  = Column(JSON, nullable=True)
    commit_id     = Column(Uuid(as_uuid=False), ForeignKey("commits.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    board  = relationship("Board",  back_populates="change_events")
    commit = relationship("Commit", back_populates="events")
