"""Validated inputs and evidence records for bounded Invaris runs."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResultStatus(str, Enum):
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"


class AgentVersion(str, Enum):
    V1 = "V1"
    V2 = "V2"


class Identity(StrictModel):
    instance_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    candidate_id: str = Field(min_length=1, max_length=128)


class ClientProfile(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    required: bool = True
    expected_group: str = "X25519MLKEM768"


class ApprovedScope(StrictModel):
    endpoint: str = Field(min_length=1, max_length=512)
    writable_paths: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    allow_restart: bool = False
    allow_rollback: bool = False

    @field_validator("writable_paths")
    @classmethod
    def validate_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        for path in paths:
            if not path or path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/"):
                raise ValueError("writable paths must be safe relative paths")
        return paths


class Budgets(StrictModel):
    max_steps: int = Field(default=12, ge=1, le=100)
    max_errors: int = Field(default=3, ge=0, le=20)
    max_tool_calls: int = Field(default=20, ge=1, le=200)
    max_tokens: int = Field(default=12000, ge=1, le=1_000_000)
    max_duration_seconds: float = Field(default=300.0, gt=0, le=86400)
    max_cost_usd: float = Field(default=1.0, ge=0, le=10000)


class MigrationContract(StrictModel):
    identity: Identity
    target_group: str = "X25519MLKEM768"
    clients: tuple[ClientProfile, ...] = Field(min_length=1)
    scope: ApprovedScope
    budgets: Budgets = Field(default_factory=Budgets)
    approval_candidate_id: str = Field(min_length=1, max_length=128)

    @field_validator("target_group")
    @classmethod
    def supported_group(cls, value: str) -> str:
        if value != "X25519MLKEM768":
            raise ValueError("target_group must be X25519MLKEM768")
        return value

    @field_validator("approval_candidate_id")
    @classmethod
    def candidate_matches_approval(cls, value: str, info: Any) -> str:
        identity = info.data.get("identity")
        if identity is not None and identity.candidate_id != value:
            raise ValueError("approval_candidate_id must match the stable run candidate_id")
        return value


class ToolCall(StrictModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any]


class ModelReply(StrictModel):
    tool_calls: tuple[ToolCall, ...] = ()
    content: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


class ToolReceipt(StrictModel):
    tool_call_id: str
    name: str
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    instance_id: str | None = None
    run_id: str | None = None
    candidate_id: str | None = None
    probe_kind: str | None = None
    fresh: bool = False
    app_valid: bool | None = None
    observed_group: str | None = None
    policy_feasible: bool | None = None


class AgentResult(StrictModel):
    status: ResultStatus
    identity: Identity
    version: AgentVersion
    reason: str
    steps: int = Field(ge=0)
    receipts: tuple[ToolReceipt, ...] = ()
    model_usage: dict[str, Any] = Field(default_factory=dict)
    claimed_status: ResultStatus | None = None
    model_claim: str | None = None
    verification_status: ResultStatus = ResultStatus.UNVERIFIED
    duration_seconds: float = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)
