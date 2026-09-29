from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from app.agents.hindsight_memory import HindsightMemoryService
from app.config import get_settings
from app.database_mongo import get_mongo_db
from app.services.gemini_service import get_gemini_service, RiskLevelEnum

logger = logging.getLogger("contractmind.agent")


class ContractAgent:
    CLAUSE_KEYWORDS = {
        "Limitation of Liability": ["liability", "cap", "liability cap", "fees paid", "consequential damages"],
        "Indemnification": ["indemnify", "indemnity", "hold harmless", "defend"],
        "Termination": ["termination", "terminate", "termination for convenience", "material breach"],
        "Payment Terms": ["payment", "invoice", "net 30", "net 60", "fees", "billing"],
        "Confidentiality": ["confidential", "non-disclosure", "trade secret"],
        "Data Protection": ["data protection", "privacy", "personal data", "gdpr", "hipaa"],
        "Intellectual Property": ["intellectual property", "ip rights", "copyright", "patent", "trademarks"],
        "Warranty": ["warranty", "warranties", "as-is", "merchantability"],
        "Governing Law": ["governing law", "jurisdiction", "choice of law"],
        "Dispute Resolution": ["arbitration", "dispute resolution", "mediation"],
        "Insurance": ["insurance", "commercial general liability", "policy limit"],
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self.memory = HindsightMemoryService()
        self.gemini = get_gemini_service()
        self.mongo = get_mongo_db()
        self._last_memory_status = "unavailable"

    def classify_clause(self, clause_text: str) -> str:
        text = (clause_text or "").lower()
        for clause_type, keywords in self.CLAUSE_KEYWORDS.items():
            if any(keyword.lower() in text for keyword in keywords):
                return clause_type
        return "Other"

    def determine_risk(self, clause_text: str, clause_type: str) -> str:
        text = (clause_text or "").lower()
        if any(token in text for token in ["unlimited", "without limit", "exclusive remedy", "100%", "lifetime"]):
            return "High"
        if any(token in text for token in ["renew automatically", "net 60", "confidential for 5 years", "usage rights"]):
            return "Medium"
        if clause_type in {"Payment Terms", "Governing Law"}:
            return "Medium"
        return "Low"

    def recall_relevant_memories(self, clause_type: str, text: str) -> list[dict[str, Any]]:
        """
        Queries Hindsight for similar historical decisions.
        Returns empty list if Hindsight is unavailable or has no memories.
        """
        if not self.memory.available():
            self._last_memory_status = "unavailable"
            return []

        query = f"Recall historical legal decisions and preferred positions for {clause_type} clauses: {text[:160]}"
        recalled = self.memory.recall_memory(query)
        if self.memory.last_error:
            self._last_memory_status = "error"
            return []

        self._last_memory_status = "connected" if recalled else "no_memories"
        memories: list[dict[str, Any]] = []

        keywords = self.CLAUSE_KEYWORDS.get(clause_type, [clause_type])
        for item in recalled:
            content = str(item.get("content", "")).lower()
            if clause_type.lower() in content or any(kw.lower() in content for kw in keywords):
                memories.append({
                    "category": clause_type,
                    "content": item.get("content", ""),
                    "topic": item.get("topic", f"Hindsight:{clause_type}"),
                    "raw": item.get("raw"),
                })

        return memories

    def analyze_clause(self, clause: dict[str, Any]) -> dict[str, Any]:
        """
        Core reasoning flow:
        1. Parse clause text and classify.
        2. Gemini Risk Analysis.
        3. Hindsight Recall: search for similar historical decisions.
        4. Gemini Redline Generation: combines clause + risk analysis + memory evidence.
        """
        clause_text = clause.get("original_text", "") or clause.get("current_text", "")
        clause_type = clause.get("category") or clause.get("clause_type") or self.classify_clause(clause_text)
        contract_name = clause.get("contract_name", "")
        vendor = clause.get("vendor", "")

        # 1. Gemini Risk Analysis
        risk_result = self.gemini.analyze_clause_risk(
            clause_text=clause_text,
            clause_type=clause_type,
            contract_name=contract_name,
            vendor=vendor,
        )

        # 2. Hindsight Recall
        historical_evidence = self.recall_relevant_memories(clause_type, clause_text)[:4]

        # 3. Gemini Redline Suggestion
        redline_result = self.gemini.generate_redline_suggestion(
            clause_text=clause_text,
            clause_type=clause_type,
            risk_analysis=risk_result,
            hindsight_memories=historical_evidence,
        )

        # Detect potential exceptions
        context_text = f"{clause_text.lower()} {str(clause.get('title', '')).lower()}"
        exception_detected = any(term in context_text for term in ("24-month", "24 month", "enterprise", "strategic exception", "custom tier"))
        exception_evidence = any("exception" in str(m.get("content", "")).lower() for m in historical_evidence)

        # Structure memory evidence for UI
        evidence_summary: list[dict[str, Any]] = []
        for item in historical_evidence:
            content = str(item.get("content", ""))
            stored_decision = {}
            try:
                stored_decision = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                stored_decision = {}

            if not isinstance(stored_decision, dict):
                stored_decision = {}

            evidence_summary.append({
                "content": content,
                "topic": item.get("topic", "Hindsight Precedent"),
                "contract_id": stored_decision.get("contract_id", ""),
                "clause_id": stored_decision.get("clause_id", ""),
                "historical_decision": stored_decision.get("decision", "ACCEPTED"),
                "confidence": stored_decision.get("confidence", "High" if len(historical_evidence) >= 2 else "Medium"),
                "final_wording": stored_decision.get("final_wording") or stored_decision.get("preference", ""),
                "date": stored_decision.get("created_at", ""),
            })

        confidence = "High" if len(historical_evidence) >= 2 else "Medium" if historical_evidence else "Low"

        # Format why this suggestion
        if historical_evidence:
            why_suggestion = f"Informed by {len(historical_evidence)} historical organizational decision(s) retrieved from Hindsight."
        elif not self.memory.available():
            why_suggestion = "Organizational memory is temporarily unavailable. Using standard commercial risk position."
        else:
            why_suggestion = "NO RELEVANT ORGANIZATIONAL MEMORY FOUND. Using standard protective commercial position."

        recommendation = {
            "clause_type": clause_type,
            "category": clause_type,
            "current_text": clause_text,
            "risk_level": risk_result.risk_level.value.capitalize(),
            "risk_reason": risk_result.risk_reason,
            "risk_factors": risk_result.key_concerns,
            "contract_facts": risk_result.contract_facts,
            "ai_inference": risk_result.ai_inference,
            "recommended_action": risk_result.recommended_action,
            "recommended_change": redline_result.suggested_redline,
            "suggested_text": redline_result.suggested_redline,
            "reason": redline_result.reasoning,
            "why_suggestion": why_suggestion,
            "historical_evidence": historical_evidence,
            "confidence": confidence,
            "exception_detected": exception_detected,
            "exception_evidence": exception_evidence,
            "analysis_source": "MEMORY_INFORMED" if historical_evidence else "GEMINI_REASONING",
            "memory_evidence": json.dumps(evidence_summary, ensure_ascii=False),
            "memory_status": self._last_memory_status,
            "needs_human_review": redline_result.needs_human_review,
        }
        return recommendation

    def record_human_decision(
        self,
        clause_id: str,
        contract_id: str,
        decision_data: dict[str, Any],
        organization_id: str = "",
    ) -> dict[str, Any]:
        """
        Lawyer reviews and decides:
        ACCEPT & TEACH: saves decision, retains to Hindsight.
        EDIT & TEACH: saves lawyer-edited wording, retains difference.
        REJECT & TEACH: saves rejection with reason, retains exception.
        """
        org_id = organization_id or self.settings.organization_id
        decision_type = str(decision_data.get("decision", "accept")).lower()
        original_clause = decision_data.get("original_clause", "")
        ai_proposal = decision_data.get("original_recommendation", "") or decision_data.get("suggested_text", "")
        edited_text = (decision_data.get("edited_text") or "").strip()
        reason = (decision_data.get("reason") or "").strip()
        clause_type = decision_data.get("clause_type") or decision_data.get("category", "General")
        contract_name = decision_data.get("contract_name", "")
        reviewer_id = decision_data.get("reviewer_id", "counsel-1")

        final_text = ""
        if decision_type == "accept":
            final_text = ai_proposal or original_clause
        elif decision_type == "modify":
            final_text = edited_text
        elif decision_type == "reject":
            final_text = original_clause

        now_iso = datetime.now(timezone.utc).isoformat()

        # Build MongoDB decision document
        mongo_record = {
            "contract_id": contract_id,
            "clause_id": clause_id,
            "clause_type": clause_type,
            "original_text": original_clause,
            "ai_proposal": ai_proposal,
            "final_text": final_text,
            "decision": decision_type.upper(),
            "reason": reason,
            "reviewer_id": reviewer_id,
            "organization_id": org_id,
            "created_at": now_iso,
            "hindsight_memory_id": None,
        }

        # Determine learning value for Hindsight Retain
        # Retain meaningful decisions:
        # - ACCEPT: confirmed standard position
        # - EDIT: teacher signal ("AI proposed X, lawyer changed to Y")
        # - REJECT: if reason is provided, learned exception
        meaningful_learning = False
        memory_content_payload: dict[str, Any] = {}

        if decision_type == "accept":
            meaningful_learning = bool(final_text.strip())
            memory_content_payload = {
                "organization_id": org_id,
                "contract_id": contract_id,
                "clause_id": clause_id,
                "clause_type": clause_type,
                "decision": "ACCEPTED",
                "final_wording": final_text,
                "preference": final_text,
                "lesson": f"Approved {clause_type} standard position: {final_text[:200]}",
                "created_at": now_iso,
            }
        elif decision_type == "modify":
            meaningful_learning = bool(edited_text)
            memory_content_payload = {
                "organization_id": org_id,
                "contract_id": contract_id,
                "clause_id": clause_id,
                "clause_type": clause_type,
                "decision": "EDITED",
                "ai_proposal": ai_proposal,
                "final_wording": edited_text,
                "preference": edited_text,
                "reason": reason,
                "lesson": f"Lawyer modified {clause_type}. AI proposed: '{ai_proposal[:100]}', Lawyer preferred: '{edited_text[:100]}'.",
                "created_at": now_iso,
            }
        elif decision_type == "reject":
            meaningful_learning = bool(reason)
            memory_content_payload = {
                "organization_id": org_id,
                "contract_id": contract_id,
                "clause_id": clause_id,
                "clause_type": clause_type,
                "decision": "REJECTED",
                "ai_proposal": ai_proposal,
                "reason": reason,
                "lesson": f"Proposal for {clause_type} rejected. Reason/Exception: {reason}",
                "created_at": now_iso,
            }

        memory_action = "not_attempted"
        memory_error: str | None = None
        memory_result: dict[str, Any] | None = None

        if meaningful_learning and self.memory.available():
            topic_key = f"{org_id}:{clause_type.lower().replace(' ', '_')}:{clause_id}"
            retained = self.memory.retain_memory(
                topic_key,
                memory_content_payload,
                memory_type="lawyer_decision",
            )
            if retained:
                memory_action = "retained"
                memory_result = retained
                mongo_record["hindsight_memory_id"] = retained.get("topic")
            else:
                memory_action = "failed"
                memory_error = self.memory.last_error or "Hindsight Cloud RETAIN failed."
        elif meaningful_learning and not self.memory.available():
            memory_action = "failed"
            memory_error = "Organizational memory is temporarily unavailable."
        else:
            memory_action = "not_retained"

        # 1. Save in MongoDB persistence layer
        try:
            self.mongo.decisions.insert_one(mongo_record)
            mongo_record.pop("_id", None)
            self.mongo.log_audit(
                event_type=f"DECISION_{decision_type.upper()}",
                contract_id=contract_id,
                clause_id=clause_id,
                details={
                    "decision": decision_type,
                    "memory_action": memory_action,
                    "reason": reason,
                    "final_text_sample": final_text[:120],
                },
                organization_id=org_id,
            )
            self.mongo.persist_mock_data()
        except Exception as exc:
            logger.error("Failed to store decision in MongoDB: %s", exc)
            mongo_record.pop("_id", None)

        return {
            **mongo_record,
            "memory_action": memory_action,
            "memory_result": memory_result,
            "memory_error": memory_error,
            "message": (
                "Decision saved and added to organizational memory."
                if memory_action == "retained"
                else "Decision saved, but organizational memory could not be updated."
                if memory_action == "failed"
                else "Decision saved. No organizational preference retained (no reason provided for rejection)."
                if decision_type == "reject"
                else "Decision saved."
            ),
        }

    def reflect_on_history(self, organization_id: str = "") -> dict[str, Any]:
        """
        Uses genuine Hindsight Reflect to identify broader organizational negotiation patterns.
        Never fakes reflections!
        """
        if not self.memory.available():
            return {
                "available": False,
                "summary": None,
                "message": "Organizational memory is temporarily unavailable.",
            }

        prompt = (
            "Summarize the organization's recurring negotiation positions, "
            "identifying clause categories with strong historical patterns, "
            "positions that are inconsistent, and any negotiated exceptions."
        )
        reflection_items = self.memory.reflect_memory(prompt)
        if reflection_items:
            content = reflection_items[0].get("content", "")
            return {
                "available": True,
                "summary": content,
                "items": reflection_items,
            }
        return {
            "available": True,
            "summary": None,
            "message": "No organizational reflection is available yet.",
        }
