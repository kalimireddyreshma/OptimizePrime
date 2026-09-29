from app.agents.hindsight_memory import HindsightMemoryService


class FakeHindsightClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 300.0):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def retain(self, bank_id: str, content: str, **kwargs):
        return type("Retention", (), {"success": True, "bank_id": bank_id, "content": content})()

    def recall(self, bank_id: str, query: str, **kwargs):
        return type("Recall", (), {"results": [{"content": "Cap supplier liability at 12 months of fees.", "score": 0.99}]})()

    def reflect(self, bank_id: str, query: str, **kwargs):
        return type("Reflect", (), {"text": "The organization prefers a 12-month liability cap with enterprise exceptions.", "based_on": {"memories": []}})()

    def close(self):
        return None


def test_real_hindsight_memory_roundtrip(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "hsk_test_key")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "contractmind-org")
    monkeypatch.setattr("app.services.hindsight_service.Hindsight", FakeHindsightClient)

    service = HindsightMemoryService()

    result = service.retain_memory(
        topic="liability_cap",
        content={
            "preferred_position": "Cap supplier liability at 12 months of fees.",
            "accepted_count": 5,
            "evidence_count": 6,
            "confidence": "high",
        },
    )

    assert result is not None
    assert result["status"] == "retained"
    assert "12 months" in result["content"]

    recalled = service.recall_memory("liability_cap")
    assert recalled
    assert any("12 months of fees" in item.get("content", "") for item in recalled)

    reflected = service.reflect_memory("liability_cap")
    assert reflected
    assert "12-month" in reflected[0].get("content", "") or "organization prefers" in reflected[0].get("content", "").lower()

    fresh = HindsightMemoryService()
    fresh_recall = fresh.recall_memory("liability_cap")
    assert fresh_recall
    assert any("12 months of fees" in item.get("content", "") for item in fresh_recall)
