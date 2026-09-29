from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel


class Clause(SQLModel, table=True):
    __tablename__ = "clauses"

    id: Optional[int] = Field(default=None, primary_key=True)
    clause_id: str = Field(index=True, unique=True)
    contract_id: int | None = Field(default=None, foreign_key="contracts.id")
    category: str
    title: str
    original_text: str
    risk_level: str = "medium"
    entities: str = ""
    key_terms: str = ""
    recommended_action: str = "review"
    suggested_text: str = ""
    reason: str = ""
    risk_reason: str = ""
    risk_factors: str = "[]"
    analysis_source: str = "RULE_BASED"
    memory_status: str = "unavailable"
    exception_detected: bool = False
    exception_evidence: bool = False
    memory_evidence: str = ""
    confidence: str = "low"
    human_decision: str | None = None
