from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DecisionType = Literal["accept", "modify", "reject", "ignore"]
ConfidenceType = Literal["High", "Medium", "Low"]


class UploadContractRequest(BaseModel):
    name: str
    vendor: str
    summary: str = ""


class ClauseSchema(BaseModel):
    clause_id: str
    category: str
    title: str
    original_text: str
    risk_level: str = "medium"
    entities: str = ""
    key_terms: str = ""
    recommended_action: str = "review"
    suggested_text: str = ""
    reason: str = ""
    memory_evidence: str = ""
    confidence: str = "low"
    human_decision: str | None = None


class ContractResponse(BaseModel):
    id: str
    name: str
    vendor: str
    status: str
    risk_score: int
    summary: str
    upload_date: datetime
    clauses: list[ClauseSchema] = []


class DecisionPayload(BaseModel):
    decision: DecisionType
    edited_text: str | None = None
    reason: str | None = None


class PreferenceSchema(BaseModel):
    category: str
    preferred_position: str
    evidence_count: int
    accepted_count: int
    modified_count: int
    rejected_count: int
    confidence: ConfidenceType
    first_seen: datetime
    last_updated: datetime
    exceptions: str = ""
    supporting_memories: str = ""


class MemoryEntry(BaseModel):
    id: str
    category: str
    historical_decision: str
    contract: str
    human_decision: str
    date: datetime
    related_clause: str
    supported_preference: bool
    exception: bool
    evidence: str = ""


class DemoStateResponse(BaseModel):
    step: int
    active_contract_id: str | None = None
    last_action: str = ""
