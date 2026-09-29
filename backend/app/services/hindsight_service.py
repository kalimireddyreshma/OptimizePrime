from __future__ import annotations

import json
import os
from typing import Any

from hindsight_client import Hindsight

from app.config import get_settings


class HindsightMemoryService:
    """Official Hindsight cloud memory client; no local or file-backed memory layer is used."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = (self.settings.hindsight_base_url or os.getenv("HINDSIGHT_BASE_URL") or "").strip()
        self.api_key = (self.settings.hindsight_api_key or os.getenv("HINDSIGHT_API_KEY") or "").strip()
        self.bank_id = (self.settings.hindsight_bank_id or os.getenv("HINDSIGHT_BANK_ID") or "").strip() or "contractmind-org"
        self.client: Hindsight | None = None
        self.last_error: str | None = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        if not self.base_url or not self.api_key:
            self.last_error = "Hindsight memory is unavailable: missing HINDSIGHT_BASE_URL or HINDSIGHT_API_KEY."
            self.client = None
            return

        try:
            self.client = Hindsight(base_url=self.base_url, api_key=self.api_key, timeout=300.0)
            self.last_error = None
        except Exception:
            self.last_error = "Hindsight memory initialization failed."
            self.client = None

    @staticmethod
    def _is_auth_error(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None) or getattr(
            getattr(exc, "response", None), "status_code", None
        )
        return status in {401, 403}

    @staticmethod
    def _has_recall_results(response: Any) -> bool:
        raw = HindsightMemoryService._normalized_model_dump(response)
        results = raw.get("results") if isinstance(raw, dict) else getattr(response, "results", None)
        return bool(results)

    def _connection_error_status(self, exc: Exception) -> str:
        if self._is_auth_error(exc):
            self.last_error = "Hindsight Cloud authentication failed."
            return "AUTH_ERROR"
        self.last_error = "Hindsight Cloud request failed."
        return "REQUEST_FAILED"

    def available(self) -> bool:
        return self.client is not None

    @staticmethod
    def _coerce_payload(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    @staticmethod
    def _normalized_model_dump(value: Any) -> Any:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        if hasattr(value, "__dict__"):
            return vars(value)
        return value

    @staticmethod
    def _extract_text(value: Any) -> str:
        raw = HindsightMemoryService._normalized_model_dump(value)
        if isinstance(raw, dict):
            for key in ("content", "text", "summary", "memory", "excerpt", "message", "value"):
                candidate = raw.get(key)
                if candidate is not None and candidate != "":
                    return HindsightMemoryService._coerce_payload(candidate)
            for nested in raw.values():
                text = HindsightMemoryService._extract_text(nested)
                if text:
                    return text
            return json.dumps(raw, ensure_ascii=False, sort_keys=True)
        if isinstance(raw, (list, tuple)):
            for item in raw:
                text = HindsightMemoryService._extract_text(item)
                if text:
                    return text
            return ""
        return HindsightMemoryService._coerce_payload(raw)

    def retain_memory(self, topic: str, content: Any, *, memory_type: str = "project") -> dict[str, Any] | None:
        if self.client is None:
            self.last_error = "Hindsight memory is unavailable: client not initialized."
            return None

        payload = self._coerce_payload(content)
        try:
            response = self.client.retain(
                self.bank_id,
                payload,
                context=f"{memory_type}:{topic}",
                metadata={"topic": topic, "memory_type": memory_type},
                tags=[topic, memory_type],
            )
            if getattr(response, "success", True) is False:
                self.last_error = "Hindsight Cloud RETAIN returned an unsuccessful result."
                return None
            self.last_error = None
            return {
                "status": "retained",
                "topic": topic,
                "bank_id": self.bank_id,
                "content": payload,
                "raw": self._normalized_model_dump(response),
            }
        except Exception as exc:
            self.last_error = "Hindsight Cloud RETAIN failed."
            return None

    def recall_memory(self, topic: str) -> list[dict[str, Any]]:
        if self.client is None:
            return []

        query = f"Find prior negotiation memory for {topic}."
        try:
            response = self.client.recall(
                self.bank_id,
                query=query,
                max_tokens=4096,
            )
            raw = self._normalized_model_dump(response)
            results = raw.get("results") if isinstance(raw, dict) else None
            if not isinstance(results, list):
                results = getattr(response, "results", None) or []
            memories: list[dict[str, Any]] = []
            for item in results:
                text = self._extract_text(item)
                if text:
                    memories.append({"topic": topic, "content": text, "raw": self._normalized_model_dump(item)})
            if memories:
                self.last_error = None
                return memories
            summary = next((
                self._coerce_payload(candidate)
                for key in ("summary", "text", "memory", "content")
                for candidate in (
                    raw.get(key) if isinstance(raw, dict) else None,
                    getattr(response, key, None),
                )
                if candidate
            ), "")
            if summary:
                self.last_error = None
                return [{"topic": topic, "content": summary, "raw": raw}]
            self.last_error = None
            return []
        except Exception as exc:
            self.last_error = "Hindsight Cloud RECALL failed."
            return []

    def reflect_memory(self, query: str | None = None) -> list[dict[str, Any]]:
        if self.client is None:
            return []

        prompt = query or "Summarize the organization’s contract negotiation preferences, exceptions, and repeated patterns."
        try:
            response = self.client.reflect(self.bank_id, prompt, budget="low", include_facts=True)
            raw = self._normalized_model_dump(response)
            text = next((
                self._coerce_payload(candidate)
                for key in ("text", "summary", "reflection", "content")
                for candidate in (
                    raw.get(key) if isinstance(raw, dict) else None,
                    getattr(response, key, None),
                )
                if candidate
            ), "")
            if not text:
                self.last_error = None
                return []
            self.last_error = None
            return [{"topic": "hindsight_reflection", "content": text, "raw": self._normalized_model_dump(response)}]
        except Exception as exc:
            self.last_error = "Hindsight Cloud REFLECT failed."
            return []

    def write_memory(self, key: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self.retain_memory(key, payload)

    def read_memory(self, key: str) -> dict[str, Any] | None:
        items = self.recall_memory(key)
        if not items:
            return None
        return {"topic": key, "content": items[0].get("content", "")}

    def list_memory(self) -> list[dict[str, Any]]:
        memories = self.reflect_memory()
        return [{"topic": item.get("topic", "hindsight"), "content": item.get("content", "")} for item in memories]

    def memory_status(self) -> dict[str, Any]:
        if self.client is None:
            return {
                "available": False,
                "state": "UNAVAILABLE",
                "bank_id": self.bank_id,
                "message": "Hindsight Cloud is not configured.",
            }

        try:
            response = self.client.recall(
                self.bank_id,
                query="ContractMind Hindsight Cloud connection check.",
                max_tokens=256,
            )
        except Exception as exc:
            state = self._connection_error_status(exc)
            return {
                "available": False,
                "state": state,
                "bank_id": self.bank_id,
                "message": self.last_error,
            }

        self.last_error = None
        has_memories = self._has_recall_results(response)
        return {
            "available": True,
            "state": "CONNECTED" if has_memories else "NO_MEMORIES",
            "bank_id": self.bank_id,
            "message": "Hindsight Cloud is connected." if has_memories else "Hindsight Cloud is connected; no memories were returned.",
        }

    async def async_memory_status(self) -> dict[str, Any]:
        if self.client is None:
            return {
                "available": False,
                "state": "UNAVAILABLE",
                "bank_id": self.bank_id,
                "message": "Hindsight Cloud is not configured.",
            }

        try:
            response = await self.client.arecall(
                self.bank_id,
                query="ContractMind Hindsight Cloud connection check.",
                max_tokens=256,
            )
        except Exception as exc:
            state = self._connection_error_status(exc)
            return {
                "available": False,
                "state": state,
                "bank_id": self.bank_id,
                "message": self.last_error,
            }

        self.last_error = None
        has_memories = self._has_recall_results(response)
        return {
            "available": True,
            "state": "CONNECTED" if has_memories else "NO_MEMORIES",
            "bank_id": self.bank_id,
            "message": "Hindsight Cloud is connected." if has_memories else "Hindsight Cloud is connected; no memories were returned.",
        }


__all__ = ["HindsightMemoryService"]
