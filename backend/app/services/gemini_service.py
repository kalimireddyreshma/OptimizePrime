from __future__ import annotations

import json
import logging
import os
import re
from enum import Enum
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger("contractmind.gemini")


class ClauseTypeEnum(str, Enum):
    LIMITATION_OF_LIABILITY = "Limitation of Liability"
    PAYMENT_TERMS = "Payment Terms"
    TERMINATION = "Termination"
    CONFIDENTIALITY = "Confidentiality"
    INDEMNIFICATION = "Indemnification"
    INTELLECTUAL_PROPERTY = "Intellectual Property"
    DATA_PROTECTION = "Data Protection"
    WARRANTY = "Warranty"
    GOVERNING_LAW = "Governing Law"
    DISPUTE_RESOLUTION = "Dispute Resolution"
    INSURANCE = "Insurance"
    OTHER = "Other"


class RiskLevelEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExtractedClauseItem(BaseModel):
    clause_id: str
    clause_type: str
    title: str
    original_text: str
    location: str
    risk_level: RiskLevelEnum
    risk_reason: str
    analysis_status: str = "extracted"


class ExtractionResult(BaseModel):
    clauses: list[ExtractedClauseItem]


class ClauseRiskAnalysis(BaseModel):
    risk_level: RiskLevelEnum
    risk_reason: str
    key_concerns: list[str] = Field(default_factory=list)
    recommended_action: str
    memory_relevance: str
    contract_facts: list[str] = Field(default_factory=list)
    ai_inference: list[str] = Field(default_factory=list)


class RedlineGenerationResult(BaseModel):
    recommendation: str
    reasoning: str
    suggested_redline: str
    memory_support: str
    historical_matches: list[str] = Field(default_factory=list)
    needs_human_review: bool = True


class GeminiService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = (
            self.settings.gemini_api_key
            or os.getenv("GEMINI_API_KEY")
            or ""
        ).strip()
        self.model_name = (
            self.settings.gemini_model
            or os.getenv("GEMINI_MODEL")
            or "gemini-2.5-flash"
        ).strip()
        self.client: genai.Client | None = None
        self._init_client()

    def _init_client(self) -> None:
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized with model: %s", self.model_name)
            except Exception as exc:
                logger.error("Failed to initialize Gemini client: %s", exc)
                self.client = None
        else:
            logger.info("GEMINI_API_KEY is not set; running in resilient deterministic fallback mode.")

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    def extract_clauses_from_text(
        self,
        contract_text: str,
        contract_id: str = "C-DOC",
        paragraphs_info: list[dict[str, Any]] | None = None,
    ) -> list[ExtractedClauseItem]:
        """
        Uses Gemini to extract and classify clauses from raw contract text.
        Falls back to rule-based parser if Gemini is unavailable or errors.
        """
        if self.is_available() and self.client is not None:
            try:
                prompt = f"""You are an expert contract lawyer. Analyze the following contract text and extract all substantive legal clauses.

For each clause:
1. Assign a unique clause_id (e.g., "{contract_id}-cl-1", "{contract_id}-cl-2").
2. Classify into one of these exact clause types:
   - Limitation of Liability
   - Payment Terms
   - Termination
   - Confidentiality
   - Indemnification
   - Intellectual Property
   - Data Protection
   - Warranty
   - Governing Law
   - Dispute Resolution
   - Insurance
   - Other
3. Provide a concise, descriptive title (e.g., "Vendor Liability Cap", "Termination for Convenience").
4. Extract the exact original_text of the clause.
5. Identify its approximate location (e.g., "Section 4.1", "Paragraph 12", or "General Provisions").
6. Assess initial risk_level (LOW, MEDIUM, HIGH, CRITICAL).
7. Explain the risk_reason clearly.

CONTRACT TEXT:
\"\"\"
{contract_text[:30000]}
\"\"\"
"""
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ExtractionResult,
                        temperature=0.1,
                    ),
                )
                if response.text:
                    parsed = ExtractionResult.model_validate_json(response.text)
                    if parsed.clauses:
                        return parsed.clauses
            except Exception as exc:
                logger.warning("Gemini clause extraction failed (%s). Using fallback parser.", exc)

        return self._fallback_extract_clauses(contract_text, contract_id, paragraphs_info)

    def analyze_clause_risk(
        self,
        clause_text: str,
        clause_type: str,
        contract_name: str = "",
        vendor: str = "",
    ) -> ClauseRiskAnalysis:
        """
        Performs thorough risk analysis using Gemini.
        Clearly separates: CURRENT CONTRACT FACTS, HISTORICAL MEMORY, AI INFERENCE.
        """
        if self.is_available() and self.client is not None:
            try:
                prompt = f"""You are a senior commercial counsel reviewing a contract clause.
Clause Type: {clause_type}
Contract: {contract_name} (Vendor: {vendor})

CURRENT CLAUSE:
\"\"\"
{clause_text}
\"\"\"

Analyze the risks.
1. Determine risk_level: LOW, MEDIUM, HIGH, or CRITICAL.
2. Provide a concise risk_reason.
3. List 2-4 key_concerns.
4. Provide recommended_action for negotiation.
5. Explain memory_relevance (what historical precedent would be useful to look for).
6. List contract_facts (verbatim facts explicitly stated in the clause).
7. List ai_inference (reasoning or risks derived from interpretation, clearly separated from facts).
"""
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ClauseRiskAnalysis,
                        temperature=0.2,
                    ),
                )
                if response.text:
                    return ClauseRiskAnalysis.model_validate_json(response.text)
            except Exception as exc:
                logger.warning("Gemini risk analysis failed (%s). Using fallback.", exc)

        return self._fallback_risk_analysis(clause_text, clause_type)

    def generate_redline_suggestion(
        self,
        clause_text: str,
        clause_type: str,
        risk_analysis: ClauseRiskAnalysis,
        hindsight_memories: list[dict[str, Any]],
        instructions: str = "",
    ) -> RedlineGenerationResult:
        """
        Gemini receives:
        CURRENT CLAUSE + RISK ANALYSIS + HINDSIGHT MEMORIES + INSTRUCTIONS
        Produces: recommendation, reasoning, suggested_redline, memory_support, historical_matches, needs_human_review.
        Gemini must never invent historical evidence!
        """
        memory_evidence_text = "NO RELEVANT ORGANIZATIONAL MEMORY FOUND."
        if hindsight_memories:
            memory_evidence_text = "\n".join([
                f"- Decision from {m.get('topic', 'Organizational Precedent')}: {m.get('content', '')}"
                for m in hindsight_memories
            ])

        if self.is_available() and self.client is not None:
            try:
                prompt = f"""You are an AI Contract Redline Agent assisting an organization's legal team.
The organization's negotiation behavior is guided by historical decisions stored in Hindsight memory.

CURRENT CLAUSE ({clause_type}):
\"\"\"
{clause_text}
\"\"\"

RISK ANALYSIS:
- Risk Level: {risk_analysis.risk_level.value}
- Risk Reason: {risk_analysis.risk_reason}
- Key Concerns: {', '.join(risk_analysis.key_concerns)}

HISTORICAL HINDSIGHT MEMORIES:
\"\"\"
{memory_evidence_text}
\"\"\"

ADDITIONAL INSTRUCTIONS:
{instructions or "Propose a balanced, protective redline aligned with organizational precedent if available."}

RULES:
1. NEVER invent or hallucinate historical evidence. Only cite memories provided above.
2. If Hindsight memory provides a clear preferred position (e.g. 12-month cap, net 30 payment), align your suggested redline with that precedent.
3. If no relevant memory was found, state clearly that standard commercial practice is applied.
4. Generate the exact suggested_redline text ready for the lawyer to review.
5. Set needs_human_review = True because all legal decisions require human approval.
"""
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=RedlineGenerationResult,
                        temperature=0.2,
                    ),
                )
                if response.text:
                    return RedlineGenerationResult.model_validate_json(response.text)
            except Exception as exc:
                logger.warning("Gemini redline generation failed (%s). Using fallback.", exc)

        return self._fallback_redline(clause_text, clause_type, risk_analysis, hindsight_memories)

    # ================= Fallbacks when Gemini is unconfigured or unavailable =================

    def _fallback_extract_clauses(
        self,
        contract_text: str,
        contract_id: str,
        paragraphs_info: list[dict[str, Any]] | None = None,
    ) -> list[ExtractedClauseItem]:
        patterns: dict[str, list[str]] = {
            "Limitation of Liability": [r"\bliabilit(?:y|ies)\b", r"\blimit(?:ation)? of liability\b", r"\bconsequential damages\b"],
            "Payment Terms": [r"\bpayment\b", r"\binvoic(?:e|es|ing)\b", r"\bnet \d+\b", r"\bfees\b"],
            "Termination": [r"\bterminat(?:e|ion)\b", r"\bnotice of termination\b", r"\bconvenience\b"],
            "Confidentiality": [r"\bconfidential(?:ity)?\b", r"\bnon-disclosure\b", r"\btrade secrets?\b"],
            "Indemnification": [r"\bindemnif(?:y|ication)\b", r"\bhold harmless\b", r"\bdefend\b"],
            "Intellectual Property": [r"\bintellectual property\b", r"\bip rights\b", r"\bcopyright\b", r"\bpatents?\b"],
            "Data Protection": [r"\bpersonal data\b", r"\bdata protection\b", r"\bprivacy\b", r"\bgdpr\b"],
            "Warranty": [r"\bwarrant(?:y|ies)\b", r"\bas-is\b", r"\bmerchantability\b"],
            "Governing Law": [r"\bgoverning law\b", r"\bchoice of law\b", r"\bjurisdiction\b"],
            "Dispute Resolution": [r"\barbitrat(?:e|ion)\b", r"\bdispute resolution\b", r"\bmediation\b"],
            "Insurance": [r"\binsurance\b", r"\bcommercial general liability\b", r"\bpolicy limits\b"],
        }

        paragraphs: list[tuple[str, str]] = []
        if paragraphs_info:
            for p in paragraphs_info:
                text = p.get("text", "").strip()
                if len(text) > 20:
                    paragraphs.append((text, p.get("location", "Contract Body")))
        else:
            chunks = re.split(r"(?:\r?\n\s*){2,}", contract_text)
            for idx, c in enumerate(chunks, 1):
                clean = re.sub(r"\s+", " ", c).strip()
                if len(clean) > 20:
                    paragraphs.append((clean, f"Section / Para {idx}"))

        extracted: list[ExtractedClauseItem] = []
        idx = 1
        for text, location in paragraphs:
            matched_type = "Other"
            for c_type, rgxs in patterns.items():
                if any(re.search(rgx, text, re.IGNORECASE) for rgx in rgxs):
                    matched_type = c_type
                    break

            if matched_type == "Other" and len(text) < 40:
                continue

            risk = RiskLevelEnum.LOW
            lower = text.lower()
            if any(term in lower for term in ["unlimited", "without limit", "sole discretion", "indemnify"]):
                risk = RiskLevelEnum.HIGH
            elif any(term in lower for term in ["net 60", "renew automatically", "30 days", "material breach"]):
                risk = RiskLevelEnum.MEDIUM

            reason = "Standard contractual clause."
            if risk == RiskLevelEnum.HIGH:
                reason = "Contains uncapped risk or one-sided indemnity language."
            elif risk == RiskLevelEnum.MEDIUM:
                reason = "Requires operational alignment and verification of timeline."

            extracted.append(
                ExtractedClauseItem(
                    clause_id=f"{contract_id}-cl-{idx}",
                    clause_type=matched_type,
                    title=f"{matched_type} Clause",
                    original_text=text,
                    location=location,
                    risk_level=risk,
                    risk_reason=reason,
                    analysis_status="extracted",
                )
            )
            idx += 1

        return extracted or [
            ExtractedClauseItem(
                clause_id=f"{contract_id}-cl-1",
                clause_type="Other",
                title="General Contract Terms",
                original_text=contract_text[:500],
                location="Document Beginning",
                risk_level=RiskLevelEnum.LOW,
                risk_reason="Standard contract provisions.",
                analysis_status="extracted",
            )
        ]

    def _fallback_risk_analysis(self, clause_text: str, clause_type: str) -> ClauseRiskAnalysis:
        text_lower = clause_text.lower()
        concerns = []
        facts = []
        inferences = []

        if "unlimited" in text_lower or "without limit" in text_lower:
            concerns.append("Uncapped financial exposure.")
            facts.append("Clause specifies liability is unlimited or without limit.")
            inferences.append("High likelihood of disproportionate catastrophic exposure.")
            risk = RiskLevelEnum.HIGH
            risk_reason = "Uncapped liability exposes organization to catastrophic commercial loss."
        elif "indemnif" in text_lower:
            concerns.append("Broad indemnification obligation.")
            facts.append("Indemnification commitment is present in the text.")
            inferences.append("Scope may not be limited strictly to third-party direct claims.")
            risk = RiskLevelEnum.HIGH
            risk_reason = "Indemnification scope must be restricted to defended third-party claims."
        elif any(k in text_lower for k in ["auto-renew", "renew automatically", "successive"]):
            concerns.append("Automatic contract extension without review window.")
            facts.append("Automatic renewal mechanism is specified.")
            inferences.append("Risk of unbudgeted multi-year renewals if cancel deadline is missed.")
            risk = RiskLevelEnum.MEDIUM
            risk_reason = "Requires advance cancellation notice calendar tracking."
        else:
            concerns.append("Standard commercial terms.")
            facts.append(f"Standard {clause_type} terminology used.")
            inferences.append("Low direct legal risk under normal commercial conditions.")
            risk = RiskLevelEnum.LOW
            risk_reason = f"Standard {clause_type.lower()} language."

        return ClauseRiskAnalysis(
            risk_level=risk,
            risk_reason=risk_reason,
            key_concerns=concerns,
            recommended_action=f"Negotiate standard organizational position for {clause_type}.",
            memory_relevance=f"Recall prior negotiated positions for {clause_type} clauses.",
            contract_facts=facts,
            ai_inference=inferences,
        )

    def _fallback_redline(
        self,
        clause_text: str,
        clause_type: str,
        risk_analysis: ClauseRiskAnalysis,
        hindsight_memories: list[dict[str, Any]],
    ) -> RedlineGenerationResult:
        if hindsight_memories:
            first_mem = hindsight_memories[0]
            content = str(first_mem.get("content", ""))
            return RedlineGenerationResult(
                recommendation=f"Update {clause_type} based on organizational precedent.",
                reasoning="Retrieved prior organizational decision from Hindsight memory.",
                suggested_redline=content if len(content) > 20 else f"Cap aggregate liability at fees paid in prior 12 months for {clause_type}.",
                memory_support=f"Precedent recalled from: {first_mem.get('topic', 'Hindsight memory')}",
                historical_matches=[m.get("content", "") for m in hindsight_memories[:3]],
                needs_human_review=True,
            )

        # Generic safe redlines
        redlines = {
            "Limitation of Liability": "Except for breaches of confidentiality or gross negligence, each party's aggregate liability under this Agreement shall be limited to the total fees paid or payable by Customer in the twelve (12) months preceding the incident.",
            "Payment Terms": "Customer shall pay undisputed invoice amounts within thirty (30) days of receipt of a valid and detailed invoice. Any contested charges may be withheld pending good-faith resolution.",
            "Termination": "Either party may terminate this Agreement without cause upon sixty (60) days' prior written notice, or immediately for material breach if such breach remains uncured thirty (30) days after written notice.",
            "Confidentiality": "Each party agrees to protect the other's Confidential Information with the same degree of care it uses for its own confidential data, for a period of three (3) years from disclosure.",
            "Indemnification": "Vendor shall defend, indemnify, and hold harmless Customer against direct third-party claims arising solely out of Vendor's gross negligence, willful misconduct, or infringement of intellectual property.",
        }

        fallback_redline = redlines.get(
            clause_type,
            f"Subject to mutual written consent and standard commercial reasonableness, the terms of this {clause_type} clause shall be adjusted."
        )

        return RedlineGenerationResult(
            recommendation=f"Standard commercial redline for {clause_type}.",
            reasoning=risk_analysis.risk_reason,
            suggested_redline=fallback_redline,
            memory_support="NO RELEVANT ORGANIZATIONAL MEMORY FOUND",
            historical_matches=[],
            needs_human_review=True,
        )


_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
