"""
Blueprint AI — All Pydantic Schemas

Covers auth, boards, capabilities, chat, insights, governance, audit, exports.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any, Literal, Optional
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
        allowed = {"pm", "designer", "researcher", "developer", "delivery", "governance"}
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


class GoogleAuth(BaseModel):
    credential: str  # Google ID token from Identity Services


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int   # seconds


class UserOut(BaseModel):
    id:                  str
    email:               str
    full_name:           Optional[str] = None
    role:                str
    has_seen_onboarding: bool = False
    created_at:          datetime

    model_config = {"from_attributes": True}


class UserPatch(BaseModel):
    has_seen_onboarding: Optional[bool] = None


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
        allowed = {"healthcare", "public", "banking", "education", "finance", "operations", "other"}
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
        if v not in {"understand", "design", "operate"}:
            raise ValueError("phase must be understand|design|operate")
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


class CollaboratorOut(BaseModel):
    user_id:   str
    email:     str
    full_name: Optional[str] = None
    role:      str
    joined_at: datetime


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


class ProposedAction(BaseModel):
    type:    str
    payload: dict[str, Any]


class ChatRequest(BaseModel):
    board_id:    str
    message:     str = Field(min_length=1, max_length=4000)
    history:     list[ChatHistoryItem] = Field(default_factory=list, max_length=40)
    role:        Optional[str] = None
    attachments: list[str] = Field(default_factory=list, max_length=3)  # list of upload UUIDs


class AgentError(BaseModel):
    code:         str
    user_message: str
    retry_advice: str
    request_id:   str


class AgentCallError(Exception):
    def __init__(self, error: AgentError) -> None:
        self.error = error
        super().__init__(error.code)


class ChatResponse(BaseModel):
    response:    Optional[str] = None
    token_count: Optional[int] = None
    message_id:  Optional[str] = None
    error:       Optional[AgentError] = None
    actions:     list[ProposedAction] = []


class ChatMessageOut(BaseModel):
    id:          str
    role:        str
    content:     str
    attachments: list[Any] = []
    created_at:  datetime
    author_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# UPLOADS
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS (PRD-11)
# ─────────────────────────────────────────────────────────────────────────────

class ImportStartRequest(BaseModel):
    upload_id: str = Field(min_length=1)


class ImportJobOut(BaseModel):
    job_id: str
    status: str   # queued | processing | done | partial | failed
    result: Optional[dict[str, Any]] = None
    error:  Optional[str] = None


class ImportAcceptRequest(BaseModel):
    edits: Optional[dict[str, Any]] = None   # full modified extraction result, or null to use stored result


class ImportAcceptResponse(BaseModel):
    success:  bool
    board_id: str


# ─────────────────────────────────────────────────────────────────────────────
# UPLOADS
# ─────────────────────────────────────────────────────────────────────────────

class UploadSignRequest(BaseModel):
    filename:     str = Field(min_length=1, max_length=255)
    content_type: str
    size:         int = Field(gt=0, le=10 * 1024 * 1024)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        allowed = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
        if v not in allowed:
            raise ValueError("Unsupported file type. PDF or images only.")
        return v


class UploadSignResponse(BaseModel):
    upload_id:  str
    upload_url: str


class UploadUrlResponse(BaseModel):
    url:        str
    expires_at: str


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


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE EVENTS (PRD-17a)
# ─────────────────────────────────────────────────────────────────────────────

class ChangeEventOut(BaseModel):
    id:              str
    board_id:        str
    actor_user_id:   Optional[str] = None
    actor_type:      str
    entity_type:     str
    entity_id:       str
    operation:       str
    before_snapshot: Optional[dict[str, Any]] = None
    after_snapshot:  Optional[dict[str, Any]] = None
    commit_id:       Optional[str] = None
    created_at:      datetime
    # Populated by the API layer, not stored in the DB:
    actor_name:      Optional[str] = None
    commit_message:  Optional[str] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# COMMITS (PRD-17e)
# ─────────────────────────────────────────────────────────────────────────────

class CommitOut(BaseModel):
    id:             str
    board_id:       str
    author_user_id: Optional[str] = None
    actor_type:     str
    message:        str
    created_at:     datetime
    author_name:    Optional[str] = None   # populated by API layer
    event_count:    int = 0                # populated by API layer

    model_config = {"from_attributes": True}


class GroupCommitRequest(BaseModel):
    event_ids: list[str] = Field(min_length=1)
    message:   str       = Field(min_length=1, max_length=500)


# ─────────────────────────────────────────────────────────────────────────────
# BRANCHES (PRD-17d)
# ─────────────────────────────────────────────────────────────────────────────

class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class BranchOut(BaseModel):
    id:                 str
    board_id:           str
    name:               str
    is_default:         bool
    state_snapshot:     Optional[dict[str, Any]] = None
    created_by_user_id: Optional[str] = None
    created_at:         datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# ELEMENTS
# ─────────────────────────────────────────────────────────────────────────────

_ELEMENT_TYPES = {
    "customer_action", "physical_evidence", "frontstage_action", "backstage_action",
    "support_process", "moment_of_truth",
    "touchpoint", "system", "data_flow", "handoff", "risk",
    "opportunity", "pain_point", "research_evidence", "ai_capability", "governance_checkpoint",
}
_ELEMENT_STATUSES = {"draft", "in-progress", "live", "deprecated"}


class ElementCreate(BaseModel):
    type:        str = Field(min_length=1, max_length=50)
    name:        str = Field(min_length=1, max_length=200)
    notes:       Optional[str] = Field(None, max_length=2000)
    owner:       Optional[str] = Field(None, max_length=255)
    status:      str = "draft"
    swimlane_id: Optional[str] = None
    step_id:     Optional[str] = None
    branch_id:   Optional[str] = None
    meta:        Optional[dict[str, Any]] = None
    actor:       str = Field("user", max_length=30)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in _ELEMENT_TYPES:
            raise ValueError(f"type must be one of {_ELEMENT_TYPES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _ELEMENT_STATUSES:
            raise ValueError("status must be draft|in-progress|live|deprecated")
        return v

    @field_validator("actor")
    @classmethod
    def validate_actor(cls, v: str) -> str:
        if v not in {"user", "agent", "agent_undo", "system"}:
            raise ValueError("actor must be user|agent|agent_undo|system")
        return v


class ElementUpdate(BaseModel):
    type:        Optional[str] = Field(None, max_length=50)
    name:        Optional[str] = Field(None, min_length=1, max_length=200)
    notes:       Optional[str] = Field(None, max_length=2000)
    owner:       Optional[str] = Field(None, max_length=255)
    status:      Optional[str] = None
    swimlane_id: Optional[str] = None
    step_id:     Optional[str] = None
    meta:        Optional[dict[str, Any]] = None
    actor:       str = Field("user", max_length=30)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _ELEMENT_TYPES:
            raise ValueError(f"type must be one of {_ELEMENT_TYPES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _ELEMENT_STATUSES:
            raise ValueError("status must be draft|in-progress|live|deprecated")
        return v

    @field_validator("actor")
    @classmethod
    def validate_actor(cls, v: str) -> str:
        if v not in {"user", "agent", "agent_undo", "system"}:
            raise ValueError("actor must be user|agent|agent_undo|system")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTORS (PRD-18)
# ─────────────────────────────────────────────────────────────────────────────

ConnectorType = Literal["sequence", "data_flow", "trigger", "dependency", "feedback", "failure"]
ConnectorTier = Literal["step", "element", "mixed"]

_CONNECTOR_TYPES = {"sequence", "data_flow", "trigger", "dependency", "feedback", "failure"}


class ConnectorCreate(BaseModel):
    source_step_id:    Optional[str] = None
    source_element_id: Optional[str] = None
    target_step_id:    Optional[str] = None
    target_element_id: Optional[str] = None
    connector_type:    ConnectorType
    label:             Optional[str] = Field(None, max_length=100)
    notes:             Optional[str] = Field(None, max_length=2000)
    waypoints:         list = Field(default_factory=list)
    actor:             Literal["user", "agent"] = "user"


class ConnectorUpdate(BaseModel):
    connector_type: Optional[ConnectorType] = None
    label:          Optional[str] = Field(None, max_length=100)
    notes:          Optional[str] = Field(None, max_length=2000)
    waypoints:      Optional[list] = None


class ConnectorOut(BaseModel):
    id:                 str
    board_id:           str
    source_step_id:     Optional[str] = None
    source_element_id:  Optional[str] = None
    target_step_id:     Optional[str] = None
    target_element_id:  Optional[str] = None
    tier:               str
    connector_type:     str
    label:              Optional[str] = None
    notes:              Optional[str] = None
    waypoints:          list = Field(default_factory=list)
    created_by_actor:   str
    created_by_user_id: Optional[str] = None
    updated_by_actor:   Optional[str] = None
    created_at:         datetime
    updated_at:         datetime

    model_config = {"from_attributes": True}


class ElementOut(BaseModel):
    id:          str
    board_id:    str
    branch_id:   Optional[str] = None
    swimlane_id: Optional[str] = None
    step_id:     Optional[str] = None
    type:        str
    name:        str
    notes:       Optional[str] = None
    owner:       Optional[str] = None
    status:      str
    meta:        dict[str, Any] = {}
    created_at:  datetime
    updated_at:  datetime
    created_by_actor: Optional[str] = None
    updated_by_actor: Optional[str] = None

    model_config = {"from_attributes": True}
