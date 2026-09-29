from io import BytesIO
import json
from types import SimpleNamespace

from docx import Document
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app import database
from app.main import app
from app.api import routes


class MemoryStub:
    last_error = None

    def available(self):
        return True

    def recall_memory(self, query):
        return [{
            "topic": "decision_C001",
            "content": '{"clause_type":"Liability","preference":"Cap vendor liability at 12 months of fees."}',
            "raw": {"score": 0.95},
        }]

    def reflect_memory(self, query=None):
        return [{"topic": "hindsight_reflection", "content": "Actual test reflection."}]

    def retain_memory(self, topic, content, *, memory_type="project"):
        return {"status": "retained", "topic": topic, "content": content}

    def memory_status(self):
        return {"available": True, "state": "CONNECTED", "message": "Connected"}

    async def async_memory_status(self):
        return self.memory_status()


class DemoMemoryStub(MemoryStub):
    def __init__(self):
        self.last_error = None
        self.items = []

    def recall_memory(self, query):
        return list(self.items)

    def retain_memory(self, topic, content, *, memory_type="project"):
        serialized = json.dumps(content)
        self.items.append({
            "topic": topic,
            "content": serialized,
            "raw": {"topic": topic},
        })
        return {"status": "retained", "topic": topic, "content": serialized}


def test_upload_analyze_decision_and_history_use_real_contract_text(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'workflow.db'}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(project_root=tmp_path))
    monkeypatch.setattr(routes.agent, "memory", MemoryStub())
    from app.services.document_extraction import extract_document_text
    document = Document()
    document.add_paragraph("LIMITATION OF LIABILITY: Vendor liability shall be unlimited.")
    document.add_paragraph("CONFIDENTIALITY: The parties will protect confidential information.")
    output = BytesIO()
    document.save(output)
    content = output.getvalue()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        upload = client.post(
            "/api/contracts/upload",
            data={"name": "Uploaded contract", "vendor": "Test vendor"},
            files={"file": ("terms.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert upload.status_code == 200
        contract_id = upload.json()["id"]

        analysis = client.post(f"/api/contracts/{contract_id}/analyze")
        assert analysis.status_code == 200
        recommendations = analysis.json()["recommendations"]
        assert len(recommendations) == 2
        assert recommendations[0]["recommendation"]["analysis_source"] == "MEMORY_INFORMED"
        assert "12 months" in recommendations[0]["recommendation"]["suggested_text"]

        clause_id = recommendations[0]["clause_id"]
        decision = client.post(
            f"/api/clauses/{clause_id}/decision",
            json={"decision": "modify", "edited_text": "Cap vendor liability at 18 months of fees."},
        )
        assert decision.status_code == 200
        assert decision.json()["memory_action"] == "retained"

        history = client.get("/api/history")
        assert history.status_code == 200
        entry = history.json()["decisions"][0]
        assert entry["contract_id"] == contract_id
        assert entry["decision"] == "modify"
        assert entry["original_recommendation"]
        assert entry["final_text"] == "Cap vendor liability at 18 months of fees."
        assert entry["memory_action"] == "retained"
        assert any(event["event_type"] == "RETAIN" for event in history.json()["timeline"])

        memory = client.get("/api/memory")
        assert memory.status_code == 200
        assert memory.json()["status"]["state"] == "CONNECTED"
        assert memory.json()["actual_memories"]
        assert client.post("/api/memory/reflect").json()["status"] == "reflected"
        assert client.get("/api/hindsight/status").json()["state"] == "CONNECTED"
        assert client.get("/api/dashboard").json()["kpis"]["memories_retained"] == 1

        rejection = client.post(f"/api/clauses/{clause_id}/decision", json={"decision": "reject"})
        assert rejection.status_code == 200
        assert rejection.json()["memory_action"] == "not_retained"
        assert client.get("/api/memory/preferences").json()[0]["modified_count"] == 1

        demo = client.post("/api/demo/run")
        assert demo.status_code == 200
        assert demo.json()["status"] == "ready"
        contracts = {contract["id"] for contract in client.get("/api/contracts").json()}
        assert {"C001", "C005", "C015"}.issubset(contracts)
        decisions = client.get("/api/history").json()["decisions"]
        assert decisions[0]["decision"] == "reject"
        assert decisions[1]["clause_id"] == clause_id

        assert client.post("/api/contracts/upload", data={"name": "Bad", "vendor": "Test"}, files={"file": ("bad.exe", b"data", "application/octet-stream")}).status_code == 400
        assert client.post("/api/contracts/upload", data={"name": "Empty", "vendor": "Test"}, files={"file": ("empty.txt", b" ", "text/plain")}).status_code == 400

    assert extract_document_text("terms.docx", content).startswith("LIMITATION OF LIABILITY")
    engine.dispose()


def test_demo_contracts_follow_recall_human_decision_retain_sequence(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(project_root=tmp_path))
    memory = DemoMemoryStub()
    monkeypatch.setattr(routes.agent, "memory", memory)

    with TestClient(app) as client:
        assert client.post("/api/demo/run").json()["status"] == "ready"

        first = client.post("/api/contracts/C001/analyze").json()["recommendations"][0]["recommendation"]
        assert first["analysis_source"] == "RULE_BASED"
        c001 = client.post(
            "/api/clauses/C001-cl-1/decision",
            json={"decision": "modify", "edited_text": "Cap vendor liability at 12 months of fees."},
        )
        assert c001.json()["memory_action"] == "retained"

        second = client.post("/api/contracts/C005/analyze").json()["recommendations"][0]["recommendation"]
        assert second["analysis_source"] == "MEMORY_INFORMED"
        assert "12 months" in second["suggested_text"]
        c005 = client.post(
            "/api/clauses/C005-cl-1/decision",
            json={"decision": "modify", "edited_text": "Use a 24-month cap for approved enterprise vendors."},
        )
        assert c005.json()["memory_action"] == "retained"

        third = client.post("/api/contracts/C015/analyze").json()["recommendations"][0]["recommendation"]
        assert third["exception_detected"] is True
        assert third["exception_evidence"] is True
        assert "24-month cap" in third["suggested_text"]

        assert client.post("/api/memory/reflect").json()["status"] == "reflected"

    engine.dispose()
