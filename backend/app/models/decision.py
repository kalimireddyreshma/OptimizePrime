from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class HumanDecision(SQLModel, table=True):
    __tablename__ = "human_decisions"

    id: Optional[int] = Field(default=None, primary_key=True)
    clause_id: str = Field(index=True)
    contract_id: str = Field(index=True)
    decision: str
    edited_text: str | None = None
    reason: str | None = None
    original_recommendation: str = ""
    final_text: str = ""
    memory_action: str = "not_attempted"
    memory_status: str = ""
    approved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
