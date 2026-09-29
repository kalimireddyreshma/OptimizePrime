from __future__ import annotations

import asyncio

from app.services.hindsight_service import HindsightMemoryService


class FakeHindsightClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 300.0, user_agent: str | None = None, max_attempts: int = 3):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_attempts = max_attempts
        self.calls = []

    def retain(self, bank_id: str, content: str | list[dict], timestamp=None, context=None, document_id=None, metadata=None, entities=None, resolve_entities=None, tags=None, update_mode=None, retain_async=False, operation_id=None):
        self.calls.append({"method": "retain", "bank_id": bank_id, "content": content})
        response = type("Retention", (), {})()
        response.success = True
        response.bank_id = bank_id
        response.items_count = 1
        response.operation_id = "op-123"
        return response

    def recall(self, bank_id: str, query: str, types=None, max_tokens=4096, budget="mid", trace=False, query_timestamp=None, include_entities=False, max_entity_tokens=500, include_chunks=False, max_chunk_tokens=8192, include_source_facts=False, max_source_facts_tokens=4096, tags=None, tags_match="any", tag_groups=None, prefer_observations=False, min_scores=None, temporal_window=None):
        self.calls.append({"method": "recall", "bank_id": bank_id, "query": query})
        response = type("Recall", (), {})()
        response.results = [{"content": "Cap supplier liability at 12 months of fees.", "score": 0.99}]
        return response

    async def arecall(self, bank_id: str, query: str, **kwargs):
        return self.recall(bank_id, query, **kwargs)

    def reflect(self, bank_id: str, query: str, budget="low", context=None, max_tokens=None, response_schema=None, tags=None, tags_match="any", include_facts=False, include_tool_calls=False, include_tool_call_output=True, tag_groups=None, apply_all_directives=False, fact_types=None, exclude_mental_models=False, exclude_mental_model_ids=None, reflect_search_observations_max_tokens=None, reflect_search_observations_include_entities=None):
        self.calls.append({"method": "reflect", "bank_id": bank_id, "query": query})
        response = type("Reflect", (), {})()
        response.text = "The organization prefers 12-month fee caps."
        response.based_on = {"memories": []}
        return response

    def close(self):
        return None


def test_hindsight_service_uses_official_client(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "test-key")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "contractmind-org")

    import app.services.hindsight_service as service_module

    monkeypatch.setattr(service_module, "Hindsight", FakeHindsightClient)

    service = HindsightMemoryService()
    assert service.available() is True
    assert asyncio.run(service.async_memory_status())["available"] is True

    retained = service.retain_memory("liability_cap", {"preferred_position": "Cap supplier liability at 12 months of fees."})
    assert retained is not None
    assert retained["status"] == "retained"

    recalled = service.recall_memory("liability_cap")
    assert recalled
    assert "12 months of fees" in recalled[0]["content"]

    reflected = service.reflect_memory("liability_cap")
    assert reflected
    assert "12-month" in reflected[0]["content"] or "organization prefers" in reflected[0]["content"].lower()


def test_hindsight_status_fails_when_cloud_recall_fails(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "test-key")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "contractmind-org")

    import app.services.hindsight_service as service_module

    class UnreachableHindsightClient(FakeHindsightClient):
        async def arecall(self, *args, **kwargs):
            raise RuntimeError("unreachable")

    monkeypatch.setattr(service_module, "Hindsight", UnreachableHindsightClient)

    service = HindsightMemoryService()
    status = asyncio.run(service.async_memory_status())
    assert status["available"] is False
    assert status["state"] == "REQUEST_FAILED"


def test_hindsight_service_is_unavailable_without_cloud_config(monkeypatch):
    import app.services.hindsight_service as service_module

    monkeypatch.setattr(service_module, "get_settings", lambda: type("Settings", (), {
        "hindsight_base_url": None,
        "hindsight_api_key": None,
        "hindsight_bank_id": None,
        "hindsight_path": None,
        "project_root": __import__("pathlib").Path("C:/temp"),
    })())
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "")
    monkeypatch.setenv("HINDSIGHT_PATH", "")
    monkeypatch.setenv("CLAUDE_CODE_PROJECT_DIR_NAME", "")

    service = HindsightMemoryService()
    assert service.available() is False
    assert service.memory_status()["state"] == "UNAVAILABLE"
    assert service.retain_memory("liability_cap", {"preferred_position": "test"}) is None
    assert service.recall_memory("liability_cap") == []
    assert service.reflect_memory("liability_cap") == []


def test_hindsight_status_distinguishes_empty_and_auth_error(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "test-key")

    import app.services.hindsight_service as service_module

    class EmptyClient(FakeHindsightClient):
        def recall(self, bank_id: str, query: str, **kwargs):
            return type("Recall", (), {"results": []})()

    monkeypatch.setattr(service_module, "Hindsight", EmptyClient)
    assert HindsightMemoryService().memory_status()["state"] == "NO_MEMORIES"

    class Unauthorized(Exception):
        status_code = 401

    class AuthErrorClient(FakeHindsightClient):
        def recall(self, bank_id: str, query: str, **kwargs):
            raise Unauthorized()

    monkeypatch.setattr(service_module, "Hindsight", AuthErrorClient)
    assert HindsightMemoryService().memory_status()["state"] == "AUTH_ERROR"
