from app.agents.hindsight_memory import HindsightMemoryService


class FakeHindsightClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 300.0):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def retain(self, bank_id: str, content: str, **kwargs):
        response = type("Retention", (), {"success": True, "bank_id": bank_id, "content": content, "metadata": kwargs.get("metadata")})()
        return response

    def recall(self, bank_id: str, query: str, **kwargs):
        response = type("Recall", (), {"results": [{"content": "Cap supplier liability at 12 months of fees.", "score": 0.99}]})()
        return response

    def reflect(self, bank_id: str, query: str, **kwargs):
        response = type("Reflect", (), {"text": "The organization prefers a 12-month liability cap with enterprise exceptions.", "based_on": {"memories": []}})()
        return response

    def close(self):
        return None


def test_real_hindsight_memory_roundtrip(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "hsk_test_key")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "contractmind-org")
    monkeypatch.setattr("app.services.hindsight_service.Hindsight", FakeHindsightClient)

    service = HindsightMemoryService()
    retained = service.retain_memory(
        "liability_cap",
        {
            "preferred_position": "Cap supplier liability at 12 months of fees.",
            "accepted_count": 5,
            "evidence_count": 6,
            "confidence": "high",
        },
    )

    assert retained is not None
    assert retained["status"] == "retained"
    assert "12 months" in retained["content"]

    recalled = service.recall_memory("liability_cap")
    assert recalled
    assert any("12 months of fees" in item["content"] for item in recalled)

    reflected = service.reflect_memory("liability_cap")
    assert reflected
    assert "12-month" in reflected[0]["content"] or "organization prefers" in reflected[0]["content"].lower()

    fresh_service = HindsightMemoryService()
    fresh_recall = fresh_service.recall_memory("liability_cap")
    assert fresh_recall
    assert any("12 months of fees" in item["content"] for item in fresh_recall)
