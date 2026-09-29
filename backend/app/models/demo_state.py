from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel


class DemoState(SQLModel, table=True):
    __tablename__ = "demo_state"

    id: Optional[int] = Field(default=None, primary_key=True)
    current_step: int = 0
    active_contract_id: str | None = None
    last_action: str = ""
