from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Any

from docx import Document
from pypdf import PdfReader

from app.services.docx_parser import (
    ContractParserError,
    normalize_text,
    parse_docx,
    validate_contract_file,
)


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class DocumentExtractionError(ValueError):
    """User-facing document extraction error (never shows raw stack traces)."""
    pass


def extract_document_text(filename: str, content: bytes, max_size_mb: int = 10) -> tuple[str, list[dict[str, Any]]]:
    """
    Extracts text and paragraph location metadata from uploaded files.
    Returns (full_text, list_of_paragraph_metadata).
    """
    try:
        ext = validate_contract_file(filename, content, max_size_mb=max_size_mb, allowed_extensions=SUPPORTED_EXTENSIONS)
    except ContractParserError as exc:
        raise DocumentExtractionError(str(exc)) from exc

    paragraphs_info: list[dict[str, Any]] = []

    try:
        if ext == ".docx":
            parsed_doc = parse_docx(content, filename=filename)
            paragraphs_info = [
                {
                    "index": p.index,
                    "text": p.text,
                    "is_heading": p.is_heading,
                    "location": p.location,
                }
                for p in parsed_doc.paragraphs
            ]
            full_text = parsed_doc.full_text
        elif ext == ".pdf":
            reader = PdfReader(BytesIO(content))
            pages_text: list[str] = []
            para_idx = 0
            for page_num, page in enumerate(reader.pages, 1):
                raw = page.extract_text() or ""
                normalized = normalize_text(raw)
                if normalized:
                    pages_text.append(normalized)
                    for chunk in re.split(r"(?:\r?\n\s*){2,}", normalized):
                        clean_chunk = chunk.strip()
                        if clean_chunk:
                            paragraphs_info.append({
                                "index": para_idx,
                                "text": clean_chunk,
                                "is_heading": False,
                                "location": f"Page {page_num}, Section {para_idx + 1}",
                            })
                            para_idx += 1
            full_text = "\n\n".join(pages_text).strip()
        else:
            try:
                full_text = normalize_text(content.decode("utf-8"))
            except UnicodeDecodeError:
                full_text = normalize_text(content.decode("latin-1", errors="replace"))

            for idx, chunk in enumerate(re.split(r"(?:\r?\n\s*){2,}", full_text), 1):
                clean_chunk = chunk.strip()
                if clean_chunk:
                    paragraphs_info.append({
                        "index": idx - 1,
                        "text": clean_chunk,
                        "is_heading": False,
                        "location": f"Paragraph {idx}",
                    })
    except Exception as exc:
        if isinstance(exc, DocumentExtractionError):
            raise
        raise DocumentExtractionError(
            f"The uploaded {ext.upper().replace('.', '')} document could not be read or appears corrupted."
        ) from exc

    if not full_text.strip():
        raise DocumentExtractionError("The uploaded document contains no readable text.")

    return full_text, paragraphs_info


CLAUSE_PATTERNS: dict[str, tuple[str, ...]] = {
    "Limitation of Liability": (r"\bliabilit(?:y|ies)\b", r"\blimit(?:ation)? of liability\b", r"\bconsequential damages\b"),
    "Indemnification": (r"\bindemnif(?:y|ication)\b", r"\bhold harmless\b", r"\bdefend\b"),
    "Termination": (r"\bterminat(?:e|ion)\b", r"\bconvenience\b"),
    "Payment Terms": (r"\bpayment\b", r"\binvoic(?:e|es|ing)\b", r"\bfees?\b", r"\bnet \d+\b"),
    "Confidentiality": (r"\bconfidential(?:ity)?\b", r"\bnon-disclosure\b"),
    "Intellectual Property": (r"\bintellectual property\b", r"\bcopyright\b", r"\bpatent\b"),
    "Data Protection": (r"\bpersonal data\b", r"\bdata protection\b", r"\bprivacy\b", r"\bgdpr\b"),
    "Governing Law": (r"\bgoverning law\b", r"\bchoice of law\b", r"\bjurisdiction\b"),
    "Dispute Resolution": (r"\barbitrat(?:e|ion)\b", r"\bdispute resolution\b", r"\bmediation\b"),
    "Warranty": (r"\bwarrant(?:y|ies)\b", r"\bas-is\b"),
    "Insurance": (r"\binsurance\b", r"\bpolicy\b"),
}


def extract_clauses(
    contract_text: str,
    agent: Any,
    contract_id: str = "C-DOC",
    paragraphs_info: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Extracts clauses using Gemini reasoning engine if available,
    falling back to deterministic paragraph / pattern extraction.
    """
    if hasattr(agent, "gemini"):
        gemini_clauses = agent.gemini.extract_clauses_from_text(
            contract_text=contract_text,
            contract_id=contract_id,
            paragraphs_info=paragraphs_info,
        )
        if gemini_clauses:
            return [
                {
                    "clause_id": c.clause_id,
                    "category": c.clause_type,
                    "title": c.title,
                    "original_text": c.original_text,
                    "location": c.location,
                    "risk_level": c.risk_level.value.capitalize(),
                    "risk_reason": c.risk_reason,
                    "entities": "",
                    "key_terms": c.clause_type.lower(),
                }
                for c in gemini_clauses
            ]

    # Deterministic pattern-based clause extraction fallback
    paragraphs = [
        re.sub(r"\s+", " ", p).strip()
        for p in re.split(r"(?:\r?\n\s*){1,}", contract_text)
        if p.strip()
    ]
    if len(paragraphs) == 1:
        paragraphs = [
            part.strip()
            for part in re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9(\"'])", paragraphs[0])
            if part.strip()
        ]

    clauses: list[dict[str, Any]] = []
    idx = 1
    for paragraph in paragraphs:
        matched_category = "Other"
        for category, patterns in CLAUSE_PATTERNS.items():
            if any(re.search(pattern, paragraph, flags=re.IGNORECASE) for pattern in patterns):
                matched_category = category
                break

        if matched_category == "Other" and len(paragraph) < 45:
            continue

        clauses.append({
            "clause_id": f"{contract_id}-cl-{idx}",
            "category": matched_category,
            "title": f"{matched_category} Clause",
            "original_text": paragraph,
            "location": f"Paragraph {idx}",
            "risk_level": agent.determine_risk(paragraph, matched_category),
            "risk_reason": f"Standard review for {matched_category.lower()} language.",
            "entities": "",
            "key_terms": matched_category.lower(),
        })
        idx += 1

    return clauses
