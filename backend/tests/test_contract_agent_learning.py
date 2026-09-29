import json

from app.agents.contract_agent import ContractAgent


class MemoryStub:
    def __init__(self, recall_items=None, retain_result=None):
        self.recall_items = recall_items or []
        self.retain_result = retain_result or {"status": "retained", "topic": "decision"}
        self.last_error = None
        self.calls = []

    def available(self):
        return True

    def recall_memory(self, query):
        self.calls.append(("recall", query))
        return self.recall_items

    def reflect_memory(self, query=None):
        self.calls.append(("reflect", query))
        return []

    def retain_memory(self, topic, content, *, memory_type="project"):
        self.calls.append(("retain", topic, content, memory_type))
        return self.retain_result


def test_recalled_memory_is_used_as_recommendation_evidence():
    memory = MemoryStub([{
        "topic": "prior-liability-decision",
        "content": "Liability: Vendor liability was edited to a 12-month cap.",
        "raw": {"score": 0.9},
    }])
    agent = ContractAgent()
    agent.memory = memory

    result = agent.analyze_clause({
        "category": "Liability",
        "original_text": "Vendor liability shall be unlimited.",
    })

    assert memory.calls[0][0] == "recall"
    assert result["analysis_source"] == "MEMORY_INFORMED"
    assert result["suggested_text"] == "Cap vendor liability at 12 months of fees."
    assert json.loads(result["memory_evidence"])[0]["content"].startswith("Liability:")
    assert result["risk_factors"] == ["Uncapped or unlimited exposure"]


def test_rejection_without_reason_does_not_retain_but_meaningful_reason_does():
    memory = MemoryStub()
    agent = ContractAgent()
    agent.memory = memory

    no_reason = agent.record_human_decision("C001-cl-1", "C001", {"decision": "reject"})
    with_reason = agent.record_human_decision(
        "C001-cl-1",
        "C001",
        {"decision": "reject", "reason": "Keep current wording for this vendor category."},
    )

    assert no_reason["memory_action"] == "not_retained"
    assert with_reason["memory_action"] == "retained"
    assert len([call for call in memory.calls if call[0] == "retain"]) == 1


def test_enterprise_exception_uses_recalled_human_position():
    memory = MemoryStub([{
        "topic": "C015 decision",
        "content": json.dumps({
            "preference": "Use a 24-month cap for this approved enterprise vendor.",
            "contract_name": "Enterprise account",
        }),
    }])
    agent = ContractAgent()
    agent.memory = memory

    result = agent.analyze_clause({
        "category": "Liability",
        "original_text": "Vendor's aggregate liability is capped at 24 months of fees.",
    })

    assert result["exception_detected"] is True
    assert result["exception_evidence"] is True
    assert result["suggested_text"] == "Use a 24-month cap for this approved enterprise vendor."
