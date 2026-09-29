from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pymongo
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import get_settings

logger = logging.getLogger("contractmind.mongo")


class MongoManager:
    _instance: MongoManager | None = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.is_connected: bool = False
        self.is_mock: bool = False
        self.client: Any = None
        self.db: Database | Any = None
        self.storage_file: Path = self.settings.project_root / "backend" / "data" / "mongodb_data.json"
        self._init_connection()

    def _init_connection(self) -> None:
        uri = self.settings.mongodb_uri or "mongodb://localhost:27017"
        db_name = self.settings.mongodb_database or "contractmind"

        try:
            # Try connecting to real MongoDB with short timeout
            real_client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=1500)
            real_client.admin.command("ping")
            self.client = real_client
            self.db = real_client[db_name]
            self.is_connected = True
            self.is_mock = False
            logger.info("Connected to real MongoDB at %s (database: %s)", uri, db_name)
        except Exception as exc:
            logger.warning(
                "MongoDB server connection at %s failed (%s). Using disk-persisted mongomock fallback.",
                uri,
                exc,
            )
            try:
                import mongomock
                self.client = mongomock.MongoClient()
                self.db = self.client[db_name]
                self.is_connected = True
                self.is_mock = True
                self._load_persisted_mock_data()
                logger.info("Initialized disk-persisted mongomock fallback database '%s'", db_name)
            except Exception as mock_exc:
                logger.error("Failed to initialize mongomock: %s", mock_exc)
                self.is_connected = False
                self.is_mock = False
                self.client = None
                self.db = None

        if self.db is not None:
            self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            self.contracts.create_index("contract_id", unique=True)
            self.contracts.create_index("organization_id")
            self.clauses.create_index("clause_id", unique=True)
            self.clauses.create_index([("contract_id", pymongo.ASCENDING), ("organization_id", pymongo.ASCENDING)])
            self.decisions.create_index([("clause_id", pymongo.ASCENDING), ("contract_id", pymongo.ASCENDING)])
            self.decisions.create_index("created_at")
            self.conversations.create_index("conversation_id", unique=True)
            self.conversations.create_index("contract_id")
            self.messages.create_index([("conversation_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)])
            self.audit_events.create_index([("contract_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])
            self.users.create_index("user_id", unique=True)
            self.sessions.create_index("session_id", unique=True)
        except Exception as exc:
            logger.debug("Index creation notice: %s", exc)

    def _load_persisted_mock_data(self) -> None:
        """Loads previously saved documents from disk into in-memory mongomock collections."""
        if not self.storage_file.is_file():
            return
        try:
            raw = self.storage_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return
            for coll_name, docs in data.items():
                if isinstance(docs, list) and docs:
                    coll = self.db[coll_name]
                    for doc in docs:
                        # Clean ObjectId if stored
                        doc_clean = dict(doc)
                        doc_clean.pop("_id", None)
                        coll.insert_one(doc_clean)
            logger.info("Successfully loaded persisted MongoDB collections from %s", self.storage_file)
        except Exception as exc:
            logger.warning("Could not restore persisted MongoDB data: %s", exc)

    def persist_mock_data(self) -> None:
        """Dumps in-memory mock collections to disk JSON storage so data is permanently preserved."""
        if not self.is_mock or self.db is None:
            return
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            collections_to_save = [
                "contracts",
                "clauses",
                "decisions",
                "audit_events",
                "conversations",
                "messages",
                "users",
                "sessions",
            ]
            dump: dict[str, list[dict[str, Any]]] = {}
            for name in collections_to_save:
                coll = self.db[name]
                docs = []
                for doc in coll.find():
                    d = dict(doc)
                    d.pop("_id", None)
                    docs.append(d)
                dump[name] = docs
            self.storage_file.write_text(json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not persist mock MongoDB data: %s", exc)

    @property
    def users(self) -> Collection:
        return self.db["users"]

    @property
    def sessions(self) -> Collection:
        return self.db["sessions"]

    @property
    def conversations(self) -> Collection:
        return self.db["conversations"]

    @property
    def messages(self) -> Collection:
        return self.db["messages"]

    @property
    def contracts(self) -> Collection:
        return self.db["contracts"]

    @property
    def clauses(self) -> Collection:
        return self.db["clauses"]

    @property
    def reviews(self) -> Collection:
        return self.db["reviews"]

    @property
    def decisions(self) -> Collection:
        return self.db["decisions"]

    @property
    def audit_events(self) -> Collection:
        return self.db["audit_events"]

    def log_audit(
        self,
        event_type: str,
        contract_id: str,
        clause_id: str = "",
        details: dict[str, Any] | None = None,
        organization_id: str = "",
    ) -> None:
        if self.db is None:
            return
        org_id = organization_id or self.settings.organization_id
        record = {
            "event_type": event_type,
            "contract_id": contract_id,
            "clause_id": clause_id,
            "details": details or {},
            "organization_id": org_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.audit_events.insert_one(record)
            self.persist_mock_data()
        except Exception as exc:
            logger.warning("Could not record audit event: %s", exc)

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.is_connected,
            "is_mock": self.is_mock,
            "database": self.settings.mongodb_database,
            "uri": self.settings.mongodb_uri if not self.is_mock else "mongomock://disk-persisted",
            "message": "Connected to real MongoDB" if (self.is_connected and not self.is_mock)
            else "Persistent disk-backed MongoDB store active" if self.is_mock
            else "MongoDB unavailable",
        }


_mongo_manager: MongoManager | None = None


def get_mongo_db() -> MongoManager:
    global _mongo_manager
    if _mongo_manager is None:
        _mongo_manager = MongoManager()
    return _mongo_manager
