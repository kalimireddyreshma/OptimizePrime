from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LearningEvent(SQLModel, table=True):
    __tablename__ = "learning_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True)
    contract_id: str = Field(index=True)
    clause_id: str = ""
    detail: str = ""
    succeeded: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
