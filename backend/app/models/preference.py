from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class OrganizationPreference(SQLModel, table=True):
    __tablename__ = "organization_preferences"

    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(index=True)
    preferred_position: str
    evidence_count: int = 0
    accepted_count: int = 0
    modified_count: int = 0
    rejected_count: int = 0
    confidence: str = "low"
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    exceptions: str = ""
    supporting_memories: str = ""
