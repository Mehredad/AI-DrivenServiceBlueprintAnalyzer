"""
Blueprint AI — All Pydantic Schemas

Covers auth, boards, capabilities, chat, insights, governance, audit, exports.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email:     EmailStr
    password:  str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role:      str = "designer"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"designer", "clinician", "data", "governance", "pm"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password needs at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password needs at least one digit")
        return v


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int   # seconds


class UserOut(BaseModel):
    id:         str
    email:      str
    full_name:  Optional[str] = None
    role:       str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# BOARDS
# ─────────────────────────────────────────────────────────────────────────────

class BoardCreate(BaseModel):
    title:  str = Field(min_length=1, max_length=500)
    domain: Optional[str] = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"healthcare", "public", "banking", "education"}
        if v not in allowed:
            raise ValueError(f"domain must be one of {allowed}")
        return v


class BoardPatch(BaseModel):
    title:  Optional[str] = Field(None, max_length=500)
    domain: Optional[str] = None
    phase:  Optional[str] = None
    state:  Optional[dict[str, Any]] = None

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in {"understand", "harvest", "improve"}:
            raise ValueError("phase must be understand|harvest|improve")
        return v


class BoardOut(BaseModel):
    id:         str
    title:      str
    domain:     Optional[str] = None
    phase:      str
    state:      dict[str, Any]
    version:    int
    owner_id:   str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BoardSummary(BaseModel):
    """Lightweight board for list views."""
    id:         str
    title:      str
    domain:     Optional[str] = None
    phase:      str
    version:    int
    owner_id:   str
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollaboratorAdd(BaseModel):
    email: EmailStr
    role:  str = "editor"

    @field_validator("role")
    @classmethod
    def validate_collab_role(cls, v: str) -> str:
        if v not in {"viewer", "editor", "admin"}:
            raise ValueError("role must be viewer|editor|admin")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# CAPABILITIES
# ─────────────────────────────────────────────────────────────────────────────

class CapabilityCreate(BaseModel):
    cap_id:       str  = Field(min_length=1, max_length=20)
    name:         str  = Field(min_length=1, max_length=255)
    type:         Optional[str] = None
    risk_level:   Optional[str] = None
    frontstage:   bool = True
    xai_strategy: Optional[str] = Field(None, max_length=255)
    autonomy:     Optional[str] = None
    input_spec:   Optional[str] = None
    output_spec:  Optional[str] = None
    owner:        Optional[str] = Field(None, max_length=255)
    status:       str  = "draft"
    notes:        Optional[str] = None
    meta:         Optional[dict[str, Any]] = None

    @field_validator("risk_level")
    @classmethod
    def validate_risk(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in {"low", "medium", "high"}:
            raise ValueError("risk_level must be low|medium|high")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in {"draft", "pilot", "live", "deprecated"}:
            raise ValueError("status must be draft|pilot|live|deprecated")
        return v


class CapabilityOut(BaseModel):
    id:           str
    board_id:     str
    cap_id:       str
    name:         str
    type:         Optional[str] = None
    risk_level:   Optional[str] = None
    frontstage:   bool
    xai_strategy: Optional[str] = None
    autonomy:     Optional[str] = None
    input_spec:   Optional[str] = None
    output_spec:  Optional[str] = None
    owner:        Optional[str] = None
    status:       str
    notes:        Optional[str] = None
    meta:         dict[str, Any] = {}
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# AI AGENT CHAT
# ─────────────────────────────────────────────────────────────────────────────

class ChatHistoryItem(BaseModel):
    role:    str   # user | assistant
    content: str


class ChatRequest(BaseModel):
    board_id: str
    message:  str = Field(min_length=1, max_length=4000)
    history:  list[ChatHistoryItem] = Field(default_factory=list, max_length=40)


class ChatResponse(BaseModel):
    response:    str
    token_count: int
    message_id:  str


class ChatMessageOut(BaseModel):
    id:         str
    role:       str
    content:    str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

class InsightOut(BaseModel):
    id:           str
    board_id:     str
    severity:     Optional[str] = None
    title:        str
    description:  Optional[str] = None
    source_ref:   Optional[str] = None
    is_dismissed: bool
    actions:      list[dict[str, Any]] = []
    generated_at: datetime

    model_config = {"from_attributes": True}


class InsightDismiss(BaseModel):
    is_dismissed: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# GOVERNANCE
# ─────────────────────────────────────────────────────────────────────────────

class GovernanceCreate(BaseModel):
    capability_id: Optional[str]  = None
    decision_type: str
    title:         str = Field(min_length=1, max_length=500)
    rationale:     Optional[str]  = None
    next_review:   Optional[datetime] = None
    meta:          Optional[dict[str, Any]] = None

    @field_validator("decision_type")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v not in {"approve", "modify", "pause", "escalate"}:
            raise ValueError("decision_type must be approve|modify|pause|escalate")
        return v


class GovernanceOut(BaseModel):
    id:            str
    board_id:      str
    capability_id: Optional[str] = None
    decision_type: str
    title:         str
    rationale:     Optional[str] = None
    decided_at:    datetime
    next_review:   Optional[datetime] = None
    meta:          dict[str, Any] = {}

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id:          str
    action:      str
    entity_type: Optional[str] = None
    entity_id:   Optional[str] = None
    diff:        Optional[dict[str, Any]] = None
    created_at:  datetime

    model_config = {"from_attributes": True}
