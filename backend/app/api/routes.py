from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session, select

from app.agents.contract_agent import ContractAgent
from app.config import get_settings
from app.database import get_session
from app.database_mongo import get_mongo_db
from app.models import Clause, Contract, DemoState, HumanDecision, LearningEvent
from app.services.document_extraction import (
    DocumentExtractionError,
    extract_clauses,
    extract_document_text,
)

logger = logging.getLogger("contractmind.routes")

router = APIRouter(prefix="/api")
agent = ContractAgent()
mongo = get_mongo_db()
settings = get_settings()

DEMO_CONTRACTS: list[dict[str, Any]] = [
    {
        "contract_id": "C001",
        "name": "NovaCloud Systems",
        "vendor": "NovaCloud",
        "summary": "Vendor agreement with unlimited liability language.",
        "risk_score": 88,
        "clauses": [{
            "category": "Limitation of Liability",
            "title": "Vendor liability cap",
            "original_text": "Vendor's total liability under this Agreement shall be unlimited in all circumstances.",
            "risk_level": "High",
            "entities": "Vendor, Customer",
            "key_terms": "liability, unlimited",
        }],
    },
    {
        "contract_id": "C005",
        "name": "Apex DataWorks",
        "vendor": "Apex",
        "summary": "Data-processing agreement with liability cap reset language.",
        "risk_score": 82,
        "clauses": [{
            "category": "Limitation of Liability",
            "title": "Liability cap",
            "original_text": "Vendor's aggregate liability under this Agreement shall be unlimited for any claim.",
            "risk_level": "High",
            "entities": "Vendor, Customer",
            "key_terms": "liability, aggregate, unlimited",
        }],
    },
    {
        "contract_id": "C015",
        "name": "BluePeak Enterprise",
        "vendor": "BluePeak",
        "summary": "Enterprise agreement with a 24-month liability cap and custom terms.",
        "risk_score": 76,
        "clauses": [{
            "category": "Limitation of Liability",
            "title": "Enterprise liability cap",
            "original_text": "Vendor's aggregate liability shall not exceed 24 months of fees paid by Customer.",
            "risk_level": "Medium",
            "entities": "Vendor, Customer",
            "key_terms": "liability, 24-month, enterprise",
        }],
    },
    {
        "contract_id": "C002",
        "name": "OrbitWorks",
        "vendor": "OrbitWorks",
        "summary": "Infrastructure subscription with termination and data retention clauses.",
        "risk_score": 70,
        "clauses": [
            {"category": "Termination", "title": "Termination for convenience", "original_text": "Either party may terminate this agreement for convenience with 10 days' prior written notice.", "risk_level": "Medium", "entities": "Vendor, Company", "key_terms": "termination, convenience"},
            {"category": "Data Protection", "title": "Data retention", "original_text": "Customer data may be retained for up to 90 days after contract termination without obligation to delete.", "risk_level": "Medium", "entities": "Customer, Vendor", "key_terms": "data, retention"},
        ],
    },
    {
        "contract_id": "C003",
        "name": "Vertex Data",
        "vendor": "Vertex",
        "summary": "Data and analytics services agreement with payment and confidentiality terms.",
        "risk_score": 64,
        "clauses": [
            {"category": "Payment Terms", "title": "Billing cadence", "original_text": "Invoices are due net 30 days from receipt. Late payments accrue interest at 2.5% monthly.", "risk_level": "Low", "entities": "Vendor, Company", "key_terms": "payment, invoice, net 30"},
            {"category": "Confidentiality", "title": "Confidential information", "original_text": "Confidential information shall remain protected for 3 years after initial disclosure.", "risk_level": "Medium", "entities": "Vendor, Company", "key_terms": "confidentiality, trade secrets"},
        ],
    },
    {
        "contract_id": "C004",
        "name": "QuantumStack",
        "vendor": "QuantumStack",
        "summary": "Cloud hosting agreement with indemnity and auto-renewal.",
        "risk_score": 78,
        "clauses": [
            {"category": "Indemnification", "title": "Indemnification scope", "original_text": "Customer shall indemnify and hold harmless Vendor from any and all claims whatsoever arising from use of the platform.", "risk_level": "High", "entities": "Vendor, Customer", "key_terms": "indemnify, hold harmless"},
            {"category": "Termination", "title": "Auto-renewal term", "original_text": "The subscription renews automatically for successive 12-month periods unless cancelled 90 days prior.", "risk_level": "High", "entities": "Vendor, Customer", "key_terms": "renewal, auto-renew"},
        ],
    },
]


def _seed_demo_data() -> None:
    with get_session() as session:
        existing_ids = {
            contract.contract_id for contract in session.exec(select(Contract)).all()
        }
        for contract_data in DEMO_CONTRACTS:
            if contract_data["contract_id"] in existing_ids:
                continue
            contract = Contract(
                contract_id=contract_data["contract_id"],
                name=contract_data["name"],
                vendor=contract_data["vendor"],
                summary=contract_data["summary"],
                status="uploaded",
                risk_score=contract_data["risk_score"],
            )
            session.add(contract)
            session.commit()
            session.refresh(contract)

            # Mirror in MongoDB contracts collection
            try:
                mongo.contracts.update_one(
                    {"contract_id": contract.contract_id},
                    {
                        "$set": {
                            "contract_id": contract.contract_id,
                            "name": contract.name,
                            "vendor": contract.vendor,
                            "summary": contract.summary,
                            "status": "uploaded",
                            "risk_score": contract.risk_score,
                            "organization_id": settings.organization_id,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                    upsert=True,
                )
            except Exception as exc:
                logger.debug("Mongo seed notice: %s", exc)

            for idx, clause_data in enumerate(contract_data["clauses"], start=1):
                recommendation = agent.analyze_clause(clause_data)
                clause_record = Clause(
                    clause_id=f"{contract_data['contract_id']}-cl-{idx}",
                    contract_id=contract.id,
                    category=clause_data["category"],
                    title=clause_data["title"],
                    original_text=clause_data["original_text"],
                    risk_level=clause_data["risk_level"],
                    entities=clause_data["entities"],
                    key_terms=clause_data["key_terms"],
                    recommended_action=recommendation.get("recommended_action", "review"),
                    suggested_text=recommendation.get("suggested_text", ""),
                    reason=recommendation.get("reason", ""),
                    risk_reason=recommendation.get("risk_reason", ""),
                    risk_factors=json.dumps(recommendation.get("risk_factors", [])),
                    analysis_source=recommendation.get("analysis_source", "RULE_BASED"),
                    memory_status=recommendation.get("memory_status", "unavailable"),
                    exception_detected=recommendation.get("exception_detected", False),
                    exception_evidence=recommendation.get("exception_evidence", False),
                    memory_evidence=recommendation.get("memory_evidence", ""),
                    confidence=recommendation.get("confidence", "Low"),
                )
                session.add(clause_record)

                try:
                    mongo.clauses.update_one(
                        {"clause_id": clause_record.clause_id},
                        {
                            "$set": {
                                "clause_id": clause_record.clause_id,
                                "contract_id": contract.contract_id,
                                "category": clause_data["category"],
                                "title": clause_data["title"],
                                "original_text": clause_data["original_text"],
                                "risk_level": clause_data["risk_level"],
                                "suggested_text": recommendation.get("suggested_text", ""),
                                "reason": recommendation.get("reason", ""),
                                "organization_id": settings.organization_id,
                            }
                        },
                        upsert=True,
                    )
                except Exception as exc:
                    logger.debug("Mongo clause seed notice: %s", exc)

        session.commit()
        mongo.persist_mock_data()


def _learned_preferences_from_decisions():
    # Read decisions from MongoDB (with SQLite fallback)
    preferences: dict[str, dict[str, Any]] = {}
    mongo_decisions = []
    try:
        mongo_decisions = list(mongo.decisions.find({"decision": {"$in": ["ACCEPT", "EDITED", "ACCEPTED", "modify", "accept"]}}))
    except Exception as exc:
        logger.debug("MongoDB read decisions notice: %s", exc)

    if mongo_decisions:
        for d in mongo_decisions:
            cat = d.get("clause_type") or "General"
            final_text = d.get("final_text") or d.get("ai_proposal") or ""
            if not final_text.strip():
                continue
            entry = preferences.setdefault(cat, {
                "category": cat,
                "preferred_position": final_text,
                "evidence_count": 0,
                "accepted_count": 0,
                "modified_count": 0,
                "rejected_count": 0,
                "confidence": "Low",
                "first_seen": d.get("created_at", datetime.now(timezone.utc).isoformat()),
                "last_updated": d.get("created_at", datetime.now(timezone.utc).isoformat()),
                "exceptions": "",
                "supporting_memories": [],
            })
            entry["evidence_count"] += 1
            dec_type = str(d.get("decision", "")).upper()
            if "ACCEPT" in dec_type:
                entry["accepted_count"] += 1
            elif "EDIT" in dec_type or "MODIFY" in dec_type:
                entry["modified_count"] += 1
                entry["preferred_position"] = final_text
                if any(t in final_text.lower() for t in ("enterprise", "24-month", "exception")):
                    entry["exceptions"] = final_text

            entry["last_updated"] = max(entry["last_updated"], str(d.get("created_at", "")))
            entry["supporting_memories"].append({
                "contract_id": d.get("contract_id", ""),
                "clause_id": d.get("clause_id", ""),
                "decision": d.get("decision", ""),
                "text": final_text[:120],
            })
    else:
        with get_session() as session:
            decisions = session.exec(select(HumanDecision)).all()
            for decision in decisions:
                if decision.decision == "reject":
                    continue
                clause = session.exec(select(Clause).where(Clause.clause_id == decision.clause_id)).first()
                if not clause:
                    continue
                final_text = decision.final_text or decision.reason or ""
                if not final_text.strip():
                    continue
                entry = preferences.setdefault(clause.category, {
                    "category": clause.category,
                    "preferred_position": final_text,
                    "evidence_count": 0,
                    "accepted_count": 0,
                    "modified_count": 0,
                    "rejected_count": 0,
                    "confidence": "Low",
                    "first_seen": decision.created_at.isoformat(),
                    "last_updated": decision.created_at.isoformat(),
                    "exceptions": "",
                    "supporting_memories": [],
                })
                entry["evidence_count"] += 1
                if decision.decision == "accept":
                    entry["accepted_count"] += 1
                elif decision.decision == "modify":
                    entry["modified_count"] += 1
                    entry["preferred_position"] = final_text

                entry["last_updated"] = max(entry["last_updated"], decision.created_at.isoformat())
                entry["supporting_memories"].append({
                    "contract_id": decision.contract_id,
                    "clause_id": decision.clause_id,
                    "decision": decision.decision,
                    "text": final_text[:120],
                })

    for entry in preferences.values():
        cnt = entry["evidence_count"]
        entry["confidence"] = "High" if cnt >= 4 else "Medium" if cnt >= 2 else "Low"

    return list(preferences.values())


def _record_learning_event(
    event_type: str,
    contract_id: str,
    clause_id: str = "",
    detail: str = "",
    succeeded: bool = True,
    session: Session | None = None,
) -> None:
    event = LearningEvent(
        event_type=event_type,
        contract_id=contract_id,
        clause_id=clause_id,
        detail=detail,
        succeeded=succeeded,
    )
    if session is not None:
        session.add(event)
    else:
        with get_session() as s:
            s.add(event)
            s.commit()

    # Mirror in MongoDB audit_events
    mongo.log_audit(
        event_type=event_type,
        contract_id=contract_id,
        clause_id=clause_id,
        details={"detail": detail, "succeeded": succeeded},
    )


# =========================================================================
# ROUTES
# =========================================================================

@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "gemini": "configured" if agent.gemini.is_available() else "unconfigured (using deterministic fallback)",
        "mongodb": mongo.status()["message"],
        "hindsight": agent.memory.memory_status()["state"],
    }


@router.get("/system/status")
def system_status():
    return {
        "gemini": {
            "available": agent.gemini.is_available(),
            "model": agent.gemini.model_name,
            "configured": bool(agent.gemini.api_key),
        },
        "mongodb": mongo.status(),
        "hindsight": agent.memory.memory_status(),
        "organization_id": settings.organization_id,
    }


@router.get("/hindsight/status")
async def hindsight_status():
    return await agent.memory.async_memory_status()


@router.post("/contracts/upload")
async def upload_contract(
    name: str = Form(...),
    vendor: str = Form(...),
    summary: str = Form(""),
    pasted_text: str = Form(""),
    file: UploadFile | None = File(None),
):
    if not name.strip() or not vendor.strip():
        raise HTTPException(status_code=400, detail="Contract name and vendor are required.")

    extracted_text = ""
    extension = ""
    paragraphs_info: list[dict[str, Any]] = []
    contract_id = f"C-{uuid4().hex[:8].upper()}"
    source_path = None

    if file is not None and file.filename:
        extension = Path(file.filename).suffix.lower()
        if extension not in {".docx", ".pdf", ".txt"}:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{extension}'. Please upload a valid DOCX, PDF, or TXT file.",
            )
        content = await file.read(settings.pdf_max_size_mb * 1024 * 1024 + 1)
        try:
            extracted_text, paragraphs_info = extract_document_text(
                file.filename,
                content,
                max_size_mb=settings.pdf_max_size_mb,
            )
        except DocumentExtractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Save uploaded file
        upload_root = settings.project_root / "backend" / "uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        destination = upload_root / f"{contract_id}{extension}"
        try:
            destination.write_bytes(content)
            source_path = str(destination)
        except OSError:
            pass
    elif pasted_text and pasted_text.strip():
        extracted_text = pasted_text.strip()
        paragraphs_info = [
            {"index": i, "text": p.strip(), "location": f"Paragraph {i+1}", "is_heading": False}
            for i, p in enumerate(extracted_text.split("\n\n"))
            if p.strip()
        ]
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide a document file (DOCX, PDF, TXT) or paste contract text.",
        )

    # Save to SQLite
    with get_session() as session:
        contract = Contract(
            contract_id=contract_id,
            name=name.strip(),
            vendor=vendor.strip(),
            summary=summary.strip(),
            status="uploaded",
            source_path=source_path,
            extracted_text=extracted_text,
        )
        session.add(contract)
        session.commit()
        session.refresh(contract)

    # Save to MongoDB contracts collection
    try:
        mongo.contracts.insert_one({
            "contract_id": contract_id,
            "name": name.strip(),
            "vendor": vendor.strip(),
            "summary": summary.strip(),
            "status": "uploaded",
            "risk_score": 0,
            "source_path": source_path,
            "extracted_text": extracted_text[:10000],
            "total_paragraphs": len(paragraphs_info),
            "organization_id": settings.organization_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        mongo.log_audit(
            event_type="CONTRACT_UPLOADED",
            contract_id=contract_id,
            details={"name": name, "vendor": vendor, "has_file": bool(file)},
        )
        mongo.persist_mock_data()
    except Exception as exc:
        logger.warning("MongoDB contract insert notice: %s", exc)

    return {
        "id": contract_id,
        "name": name,
        "vendor": vendor,
        "status": "uploaded",
        "document_extracted": True,
        "total_paragraphs": len(paragraphs_info),
    }


@router.get("/contracts")
def list_contracts():
    with get_session() as session:
        _seed_demo_data()
        results = session.exec(select(Contract)).all()
        return [{
            "id": c.contract_id,
            "name": c.name,
            "vendor": c.vendor,
            "status": c.status,
            "risk_score": c.risk_score,
            "summary": c.summary,
            "upload_date": c.upload_date,
        } for c in results]


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: str):
    with get_session() as session:
        contract = session.exec(select(Contract).where(Contract.contract_id == contract_id)).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        return {
            "id": contract.contract_id,
            "name": contract.name,
            "vendor": contract.vendor,
            "status": contract.status,
            "risk_score": contract.risk_score,
            "summary": contract.summary,
            "upload_date": contract.upload_date,
        }


@router.post("/contracts/{contract_id}/analyze")
def analyze_contract(contract_id: str):
    with get_session() as session:
        contract = session.exec(select(Contract).where(Contract.contract_id == contract_id)).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        demo_seed = next((entry for entry in DEMO_CONTRACTS if entry["contract_id"] == contract_id), None)
        extracted_text = contract.extracted_text
        if not extracted_text and contract.source_path:
            try:
                p = Path(contract.source_path)
                extracted_text, _ = extract_document_text(p.name, p.read_bytes())
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Could not read contract document: {exc}") from exc

        if extracted_text:
            clauses_data = extract_clauses(extracted_text, agent, contract_id=contract_id)
        elif demo_seed is not None:
            clauses_data = demo_seed["clauses"]
        else:
            raise HTTPException(status_code=422, detail="This contract has no text or document to analyze.")

        if not clauses_data:
            raise HTTPException(status_code=422, detail="No extractable legal clauses were detected in this document.")

        analyzed_results = []
        for idx, clause_item in enumerate(clauses_data, start=1):
            clause_id = clause_item.get("clause_id") or f"{contract_id}-cl-{idx}"
            recommendation = agent.analyze_clause({
                **clause_item,
                "current_text": clause_item["original_text"],
                "contract_name": contract.name,
                "vendor": contract.vendor,
            })

            # Check existing clause in SQLite
            existing = session.exec(select(Clause).where(Clause.clause_id == clause_id)).first()
            if existing:
                existing.category = clause_item["category"]
                existing.title = clause_item["title"]
                existing.original_text = clause_item["original_text"]
                existing.risk_level = recommendation["risk_level"]
                existing.risk_reason = recommendation["risk_reason"]
                existing.risk_factors = json.dumps(recommendation["risk_factors"])
                existing.analysis_source = recommendation["analysis_source"]
                existing.memory_status = recommendation["memory_status"]
                existing.exception_detected = recommendation["exception_detected"]
                existing.exception_evidence = recommendation["exception_evidence"]
                existing.suggested_text = recommendation["suggested_text"]
                existing.reason = recommendation["reason"]
                existing.memory_evidence = recommendation["memory_evidence"]
                existing.confidence = recommendation["confidence"]
                session.add(existing)
            else:
                clause_record = Clause(
                    clause_id=clause_id,
                    contract_id=contract.id,
                    category=clause_item["category"],
                    title=clause_item["title"],
                    original_text=clause_item["original_text"],
                    risk_level=recommendation["risk_level"],
                    entities=clause_item.get("entities", ""),
                    key_terms=clause_item.get("key_terms", ""),
                    recommended_action=recommendation.get("recommended_action", "review"),
                    suggested_text=recommendation.get("suggested_text", ""),
                    reason=recommendation.get("reason", ""),
                    risk_reason=recommendation["risk_reason"],
                    risk_factors=json.dumps(recommendation["risk_factors"]),
                    analysis_source=recommendation["analysis_source"],
                    memory_status=recommendation["memory_status"],
                    exception_detected=recommendation["exception_detected"],
                    exception_evidence=recommendation["exception_evidence"],
                    memory_evidence=recommendation["memory_evidence"],
                    confidence=recommendation["confidence"],
                )
                session.add(clause_record)

            # Mirror in MongoDB clauses collection
            try:
                mongo.clauses.update_one(
                    {"clause_id": clause_id},
                    {
                        "$set": {
                            "clause_id": clause_id,
                            "contract_id": contract_id,
                            "category": clause_item["category"],
                            "title": clause_item["title"],
                            "original_text": clause_item["original_text"],
                            "location": clause_item.get("location", f"Section {idx}"),
                            "risk_level": recommendation["risk_level"],
                            "risk_reason": recommendation["risk_reason"],
                            "key_concerns": recommendation["risk_factors"],
                            "contract_facts": recommendation.get("contract_facts", []),
                            "ai_inference": recommendation.get("ai_inference", []),
                            "suggested_redline": recommendation["suggested_text"],
                            "reasoning": recommendation["reason"],
                            "why_suggestion": recommendation.get("why_suggestion", ""),
                            "memory_status": recommendation["memory_status"],
                            "confidence": recommendation["confidence"],
                            "organization_id": settings.organization_id,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                    upsert=True,
                )
            except Exception as exc:
                logger.debug("Mongo clause update notice: %s", exc)

            analyzed_results.append({"clause_id": clause_id, "recommendation": recommendation})

            _record_learning_event(
                "RECALL",
                contract_id,
                clause_id,
                f"Memory recall: {len(recommendation['historical_evidence'])} match(es).",
                recommendation["memory_status"] not in {"error", "unavailable"},
                session=session,
            )
            _record_learning_event(
                "REASONING",
                contract_id,
                clause_id,
                f"Gemini: {recommendation['analysis_source']}; Risk: {recommendation['risk_level']}.",
                True,
                session=session,
            )

        session.commit()

        # Update contract risk score
        risk_map = {"Critical": 95, "High": 85, "Medium": 55, "Low": 25}
        avg_score = round(
            sum(risk_map.get(item["recommendation"]["risk_level"], 50) for item in analyzed_results)
            / len(analyzed_results)
        )
        contract.risk_score = avg_score
        contract.status = "analyzed"
        session.add(contract)
        session.commit()

        try:
            mongo.contracts.update_one(
                {"contract_id": contract_id},
                {"$set": {"status": "analyzed", "risk_score": avg_score}},
            )
            mongo.log_audit(
                event_type="CONTRACT_ANALYZED",
                contract_id=contract_id,
                details={"clauses_count": len(analyzed_results), "risk_score": avg_score},
            )
            mongo.persist_mock_data()
        except Exception as exc:
            logger.debug("Mongo update contract notice: %s", exc)

        return {"contract_id": contract_id, "recommendations": analyzed_results}


@router.get("/contracts/{contract_id}/clauses")
def list_clauses(contract_id: str):
    with get_session() as session:
        contract = session.exec(select(Contract).where(Contract.contract_id == contract_id)).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        clauses = session.exec(select(Clause).where(Clause.contract_id == contract.id)).all()
        return [{
            "clause_id": c.clause_id,
            "category": c.category,
            "title": c.title,
            "original_text": c.original_text,
            "risk_level": c.risk_level,
            "risk_reason": c.risk_reason,
            "risk_factors": json.loads(c.risk_factors or "[]"),
            "analysis_source": c.analysis_source,
            "memory_status": c.memory_status,
            "exception_detected": c.exception_detected,
            "exception_evidence": c.exception_evidence,
            "recommended_action": c.recommended_action,
            "suggested_text": c.suggested_text,
            "reason": c.reason,
            "memory_evidence": json.loads(c.memory_evidence) if c.memory_evidence.startswith("[") else [],
            "confidence": c.confidence,
            "human_decision": c.human_decision,
        } for c in clauses]


@router.post("/clauses/{clause_id}/decision")
def record_decision(clause_id: str, payload: dict[str, Any]):
    """
    Lawyer reviews and records decision:
    - accept -> ACCEPT & TEACH
    - modify -> EDIT & TEACH
    - reject -> REJECT & TEACH
    Stores in MongoDB persistence layer and retains to Hindsight long-term memory.
    """
    decision_type = str(payload.get("decision", "accept")).lower()
    if decision_type not in {"accept", "modify", "reject"}:
        raise HTTPException(status_code=400, detail="Decision must be 'accept', 'modify', or 'reject'.")

    edited_text = str(payload.get("edited_text") or "").strip()
    reason = str(payload.get("reason") or "").strip()

    if decision_type == "modify" and not edited_text:
        raise HTTPException(status_code=400, detail="Please provide your modified wording before saving.")

    with get_session() as session:
        clause = session.exec(select(Clause).where(Clause.clause_id == clause_id)).first()
        if not clause:
            raise HTTPException(status_code=404, detail="Clause not found")

        contract = session.get(Contract, clause.contract_id) if clause.contract_id else None
        contract_id = contract.contract_id if contract else ""
        contract_name = contract.name if contract else ""
        contract_vendor = contract.vendor if contract else ""

        original_recommendation = clause.suggested_text
        clause_category = clause.category
        original_clause_text = clause.original_text

        clause.human_decision = decision_type
        session.add(clause)

        # Record in SQLite human_decisions
        sqlite_decision = HumanDecision(
            clause_id=clause_id,
            contract_id=contract_id,
            decision=decision_type,
            edited_text=edited_text or None,
            reason=reason or None,
            original_recommendation=original_recommendation,
            final_text=edited_text if decision_type == "modify" else original_recommendation if decision_type == "accept" else "",
            approved=decision_type in {"accept", "modify"},
        )
        session.add(sqlite_decision)
        session.commit()
        session.refresh(sqlite_decision)

    # Process via ContractAgent (MongoDB persistence + Hindsight Retain)
    decision_result = agent.record_human_decision(
        clause_id=clause_id,
        contract_id=contract_id,
        decision_data={
            "decision": decision_type,
            "edited_text": edited_text or None,
            "reason": reason or None,
            "original_recommendation": original_recommendation,
            "category": clause_category,
            "original_clause": original_clause_text,
            "contract_name": contract_name,
            "contract_vendor": contract_vendor,
        },
    )

    memory_action = decision_result.get("memory_action", "not_attempted")

    # Update SQLite record status
    with get_session() as session:
        stored = session.get(HumanDecision, sqlite_decision.id)
        if stored:
            stored.memory_action = memory_action
            stored.memory_status = decision_result.get("memory_error") or ""
            session.add(stored)
            session.commit()

    if contract_id:
        if memory_action == "retained":
            _record_learning_event("RETAIN", contract_id, clause_id, "Hindsight RETAIN: decision added to organizational memory.", True)
        elif memory_action == "failed":
            _record_learning_event("RETAIN", contract_id, clause_id, f"Hindsight RETAIN failed: {decision_result.get('memory_error')}", False)
        else:
            _record_learning_event("DECISION", contract_id, clause_id, f"Decision recorded ({decision_type.upper()}).", True)

    return {
        "status": "recorded",
        "decision": decision_result,
        "memory_action": memory_action,
        "message": decision_result.get("message"),
        "can_retry": memory_action == "failed",
    }


@router.post("/clauses/{clause_id}/retry-memory")
def retry_memory_save(clause_id: str):
    """Retries Hindsight RETAIN for a clause decision if it failed previously."""
    mongo_dec = mongo.decisions.find_one({"clause_id": clause_id}, sort=[("created_at", -1)])
    if not mongo_dec:
        raise HTTPException(status_code=404, detail="No prior decision found for this clause.")

    result = agent.record_human_decision(
        clause_id=clause_id,
        contract_id=mongo_dec.get("contract_id", ""),
        decision_data={
            "decision": mongo_dec.get("decision", "accept").lower(),
            "edited_text": mongo_dec.get("final_text") if mongo_dec.get("decision") == "EDITED" else None,
            "reason": mongo_dec.get("reason"),
            "original_recommendation": mongo_dec.get("ai_proposal"),
            "category": mongo_dec.get("clause_type"),
            "original_clause": mongo_dec.get("original_text"),
        },
    )
    return {
        "status": "retried",
        "memory_action": result.get("memory_action"),
        "message": result.get("message"),
    }


@router.get("/memory")
def get_memory():
    status = agent.memory.memory_status()
    with get_session() as session:
        decisions = session.exec(select(HumanDecision)).all()
        decision_context = []
        for d in decisions:
            clause = session.exec(select(Clause).where(Clause.clause_id == d.clause_id)).first()
            contract = session.exec(select(Contract).where(Contract.contract_id == d.contract_id)).first()
            decision_context.append({
                "contract_id": d.contract_id,
                "contract_name": contract.name if contract else "",
                "clause_id": d.clause_id,
                "clause_type": clause.category if clause else "General",
                "decision": d.decision.upper(),
                "text": d.final_text or d.reason or d.original_recommendation,
                "timestamp": d.created_at.isoformat(),
                "memory_action": d.memory_action,
            })

    actual_memories = []
    if status["available"]:
        for ctx in decision_context:
            for item in agent.memory.recall_memory(f"decision_{ctx['clause_id']}"):
                actual_memories.append({
                    "topic": item.get("topic", "Hindsight Precedent"),
                    "content": item.get("content", ""),
                    "decision_context": ctx,
                })

    reflection_data = agent.reflect_on_history()
    return {
        "status": status,
        "actual_memories": actual_memories,
        "application_decisions": decision_context,
        "reflection": reflection_data.get("summary"),
        "reflection_state": "available" if reflection_data.get("summary") else (
            "empty" if status["available"] else "unavailable"
        ),
        "reflection_error": reflection_data.get("message") if not reflection_data.get("summary") else None,
    }


@router.get("/memory/decisions")
def get_memory_decisions(
    clause_type: str | None = Query(None),
    decision: str | None = Query(None),
    contract_id: str | None = Query(None),
):
    """Memory Explorer endpoint: browse historical lawyer decisions with filters."""
    query: dict[str, Any] = {}
    if clause_type:
        query["clause_type"] = clause_type
    if decision:
        query["decision"] = decision.upper()
    if contract_id:
        query["contract_id"] = contract_id

    results = []
    try:
        cursor = mongo.decisions.find(query).sort("created_at", -1)
        for doc in cursor:
            doc["_id"] = str(doc.get("_id", ""))
            results.append(doc)
    except Exception as exc:
        logger.warning("MongoDB read decisions notice: %s", exc)

    if not results:
        # Fallback to SQLite
        with get_session() as session:
            db_decisions = session.exec(select(HumanDecision).order_by(HumanDecision.created_at.desc())).all()
            for d in db_decisions:
                clause = session.exec(select(Clause).where(Clause.clause_id == d.clause_id)).first()
                cat = clause.category if clause else "General"
                if clause_type and cat.lower() != clause_type.lower():
                    continue
                if decision and d.decision.lower() != decision.lower():
                    continue
                if contract_id and d.contract_id != contract_id:
                    continue
                results.append({
                    "contract_id": d.contract_id,
                    "clause_id": d.clause_id,
                    "clause_type": cat,
                    "decision": d.decision.upper(),
                    "final_text": d.final_text,
                    "reason": d.reason,
                    "created_at": d.created_at.isoformat(),
                    "memory_action": d.memory_action,
                })

    return {"count": len(results), "decisions": results}


@router.get("/memory/preferences")
def get_preferences():
    return _learned_preferences_from_decisions()


@router.get("/playbook")
def get_negotiation_playbook():
    """Detailed Negotiation Playbook showing organizational positions, evidence, and exceptions."""
    prefs = _learned_preferences_from_decisions()
    clause_types = [
        "Limitation of Liability",
        "Payment Terms",
        "Termination",
        "Confidentiality",
        "Indemnification",
        "Intellectual Property",
        "Data Protection",
        "Warranty",
        "Governing Law",
    ]

    playbook_items = []
    for c_type in clause_types:
        found = next((p for p in prefs if p["category"].lower() == c_type.lower()), None)
        if found:
            playbook_items.append({
                "clause_type": c_type,
                "organizational_position": found["preferred_position"],
                "historical_evidence": f"{found['evidence_count']} relevant decisions",
                "accepted_count": found["accepted_count"],
                "modified_count": found["modified_count"],
                "rejected_count": found["rejected_count"],
                "exceptions": found["exceptions"] or "No negotiated exceptions on record.",
                "support_level": found["confidence"],
                "last_updated": found["last_updated"],
                "supporting_memories": found["supporting_memories"],
            })
        else:
            playbook_items.append({
                "clause_type": c_type,
                "organizational_position": f"Standard commercial protective position for {c_type}.",
                "historical_evidence": "0 relevant decisions (no memory yet)",
                "accepted_count": 0,
                "modified_count": 0,
                "rejected_count": 0,
                "exceptions": "None",
                "support_level": "None",
                "last_updated": "—",
                "supporting_memories": [],
            })

    return {"playbook": playbook_items, "organization_id": settings.organization_id}


@router.get("/memory/timeline")
def get_timeline():
    with get_session() as session:
        events = session.exec(select(LearningEvent).order_by(LearningEvent.created_at)).all()
        return [{
            "step": f"{e.contract_id or 'Application'} {e.event_type}",
            "date": e.created_at.isoformat(),
            "label": e.detail,
            "contract_id": e.contract_id,
            "clause_id": e.clause_id,
            "event_type": e.event_type,
            "succeeded": e.succeeded,
        } for e in events]


@router.post("/memory/reflect")
def reflect_memory():
    result = agent.reflect_on_history()
    succeeded = bool(result.get("summary"))
    _record_learning_event(
        "REFLECT",
        "",
        detail=result.get("summary") or result.get("message") or "Reflection empty.",
        succeeded=succeeded,
    )
    return {
        "status": "reflected" if succeeded else "empty" if result.get("available") else "unavailable",
        "summary": result.get("summary"),
        "message": result.get("message"),
        "items": result.get("items", []),
    }


@router.get("/dashboard")
async def dashboard():
    with get_session() as session:
        contracts = session.exec(select(Contract)).all()
        clauses = session.exec(select(Clause)).all()
        decisions = session.exec(select(HumanDecision)).all()
        events = session.exec(select(LearningEvent).order_by(LearningEvent.created_at.desc()).limit(6)).all()

        high_risk_count = sum(1 for c in clauses if c.risk_level.lower() in {"high", "critical"})
        memory_backed_count = sum(1 for c in clauses if c.analysis_source == "MEMORY_INFORMED")

        kpis = {
            "contracts_reviewed": len(contracts),
            "clauses_analyzed": len(clauses),
            "recommendations": len(clauses),
            "high_risk_clauses": high_risk_count,
            "memory_backed_recommendations": memory_backed_count,
            "accepted": sum(1 for d in decisions if d.decision == "accept"),
            "modified": sum(1 for d in decisions if d.decision == "modify"),
            "rejected": sum(1 for d in decisions if d.decision == "reject"),
            "memories_retained": sum(1 for d in decisions if d.memory_action == "retained"),
            "preferences_learned": len(_learned_preferences_from_decisions()),
            "exceptions_detected": sum(1 for c in clauses if c.exception_evidence or c.exception_detected),
            "hindsight_status": await agent.memory.async_memory_status(),
            "mongodb_status": mongo.status(),
            "gemini_status": {
                "available": agent.gemini.is_available(),
                "model": agent.gemini.model_name,
            },
        }

        return {
            "kpis": kpis,
            "learning_progress": [{
                "interaction": f"{e.contract_id or 'System'} {e.event_type}",
                "status": e.detail,
                "timestamp": e.created_at.isoformat(),
            } for e in reversed(events)],
            "recent_contracts": [{
                "id": c.contract_id,
                "name": c.name,
                "vendor": c.vendor,
                "status": c.status,
                "risk_score": c.risk_score,
                "summary": c.summary,
            } for c in contracts[:6]],
        }


@router.get("/history")
def get_history():
    with get_session() as session:
        decisions = session.exec(select(HumanDecision).order_by(HumanDecision.created_at.desc())).all()
        decision_history = []
        for d in decisions:
            clause = session.exec(select(Clause).where(Clause.clause_id == d.clause_id)).first()
            contract = session.exec(select(Contract).where(Contract.contract_id == d.contract_id)).first()
            decision_history.append({
                "contract_id": d.contract_id,
                "contract_name": contract.name if contract else "",
                "clause_id": d.clause_id,
                "clause_type": clause.category if clause else "General",
                "decision": d.decision,
                "original_recommendation": d.original_recommendation,
                "final_text": d.final_text,
                "rejection_reason": d.reason if d.decision == "reject" else None,
                "timestamp": d.created_at.isoformat(),
                "memory_action": d.memory_action,
                "memory_status": d.memory_status,
            })
        events = session.exec(select(LearningEvent).order_by(LearningEvent.created_at)).all()
        timeline = [{
            "step": f"{e.contract_id or 'Application'} {e.event_type}",
            "date": e.created_at.isoformat(),
            "label": e.detail,
            "contract_id": e.contract_id,
            "clause_id": e.clause_id,
            "event_type": e.event_type,
            "succeeded": e.succeeded,
        } for e in events]

    return {
        "timeline": timeline,
        "decisions": decision_history,
        "preferences": _learned_preferences_from_decisions(),
    }


# =========================================================================
# CHAT ASSISTANT (STORED IN MONGODB)
# =========================================================================

@router.get("/conversations/{contract_id}/messages")
def get_conversation_messages(contract_id: str):
    """Retrieve chat history for a contract from MongoDB."""
    messages = []
    try:
        cursor = mongo.messages.find({"contract_id": contract_id}).sort("timestamp", 1)
        for msg in cursor:
            messages.append({
                "id": str(msg.get("_id", "")),
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp", ""),
            })
    except Exception as exc:
        logger.warning("MongoDB chat fetch notice: %s", exc)

    return {"contract_id": contract_id, "messages": messages}


@router.post("/conversations/{contract_id}/messages")
def post_conversation_message(contract_id: str, payload: dict[str, Any]):
    """
    Save user message in MongoDB, reason with Gemini, and save AI assistant reply in MongoDB.
    Chat history belongs in MongoDB, NOT in Hindsight.
    """
    user_prompt = str(payload.get("message", "")).strip()
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    now_iso = datetime.now(timezone.utc).isoformat()
    # 1. Save user message in MongoDB
    try:
        mongo.messages.insert_one({
            "conversation_id": f"conv-{contract_id}",
            "contract_id": contract_id,
            "role": "user",
            "content": user_prompt,
            "timestamp": now_iso,
        })
    except Exception as exc:
        logger.warning("Mongo message save notice: %s", exc)

    # 2. Generate response via Gemini
    ai_reply = "I am reviewing this contract based on standard legal risk considerations."
    if agent.gemini.is_available() and agent.gemini.client is not None:
        try:
            # Gather contract context
            contract_context = ""
            with get_session() as session:
                c = session.exec(select(Contract).where(Contract.contract_id == contract_id)).first()
                if c:
                    contract_context = f"Contract: {c.name} (Vendor: {c.vendor})\nSummary: {c.summary}"

            prompt = f"""You are ContractMind AI assistant. The lawyer is reviewing contract {contract_id}.
{contract_context}

Lawyer question:
{user_prompt}

Provide a helpful, legally sound, and concise answer. Do not give formal legal advice; provide review assistance."""
            resp = agent.gemini.client.models.generate_content(
                model=agent.gemini.model_name,
                contents=prompt,
            )
            if resp.text:
                ai_reply = resp.text.strip()
        except Exception as exc:
            ai_reply = f"AI reasoning response error: {exc}"
    else:
        ai_reply = (
            f"Regarding your query about contract {contract_id}: "
            f"Review the identified clauses and risks. "
            f"Standard organizational positions favor capped mutual liability (12 months) and net 30 payment terms."
        )

    # 3. Save assistant reply in MongoDB
    reply_iso = datetime.now(timezone.utc).isoformat()
    try:
        mongo.messages.insert_one({
            "conversation_id": f"conv-{contract_id}",
            "contract_id": contract_id,
            "role": "assistant",
            "content": ai_reply,
            "timestamp": reply_iso,
        })
        mongo.persist_mock_data()
    except Exception as exc:
        logger.warning("Mongo assistant reply save notice: %s", exc)

    return {
        "contract_id": contract_id,
        "reply": ai_reply,
        "timestamp": reply_iso,
    }


# =========================================================================
# DEMO CONTROLS
# =========================================================================

@router.post("/demo/reset")
def reset_demo():
    with get_session() as session:
        session.query(HumanDecision).delete()
        session.query(Clause).delete()
        session.query(Contract).delete()
        session.query(DemoState).delete()
        session.commit()
    try:
        mongo.decisions.delete_many({})
        mongo.clauses.delete_many({})
        mongo.contracts.delete_many({})
        mongo.messages.delete_many({})
        mongo.audit_events.delete_many({})
    except Exception:
        pass
    _seed_demo_data()
    return {"status": "reset", "message": "Demo data and MongoDB state reset."}


@router.post("/demo/run")
def run_demo():
    _seed_demo_data()
    with get_session() as session:
        state = session.exec(select(DemoState)).first()
        if state is None:
            state = DemoState(current_step=0, active_contract_id="C001", last_action="Demo started; awaiting lawyer decision.")
        else:
            state.current_step = 0
            state.active_contract_id = "C001"
            state.last_action = "Demo started; awaiting lawyer decision."
        session.add(state)
        session.commit()

    return {
        "status": "ready",
        "message": "Demo ready. Review C001, then C005 and C015; decisions are saved to MongoDB and retained to Hindsight.",
    }


@router.get("/demo/status")
def demo_status():
    with get_session() as session:
        state = session.exec(select(DemoState)).first()
        if state is None:
            return {"step": 0, "active_contract_id": None, "last_action": "No demo started"}
        return {"step": state.current_step, "active_contract_id": state.active_contract_id, "last_action": state.last_action}
