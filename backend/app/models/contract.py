from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Contract(SQLModel, table=True):
    __tablename__ = "contracts"

    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: str = Field(index=True, unique=True)
    name: str
    vendor: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    status: str = "uploaded"
    risk_score: int = 0
    summary: str = ""
    source_path: str | None = None
    extracted_text: str = ""
