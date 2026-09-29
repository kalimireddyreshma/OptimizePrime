from __future__ import annotations

from app.services.hindsight_service import HindsightMemoryService as _OfficialHindsightMemoryService


class HindsightMemoryService(_OfficialHindsightMemoryService):
    """Backward-compatible alias to the official Hindsight client-backed service."""

    pass
