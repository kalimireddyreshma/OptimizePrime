from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Any
from pydantic import BaseModel
from docx import Document


class ParsedParagraph(BaseModel):
    index: int
    text: str
    is_heading: bool = False
    heading_level: int = 0
    location: str


class ParsedDocument(BaseModel):
    filename: str
    paragraphs: list[ParsedParagraph]
    full_text: str
    headings: list[str]
    metadata: dict[str, Any] = {}


class ContractParserError(Exception):
    """User-friendly contract parsing error (never exposes raw stack traces)."""
    pass


def validate_contract_file(
    filename: str,
    content: bytes,
    max_size_mb: int = 10,
    allowed_extensions: set[str] | None = None,
) -> str:
    """Validates file extension, size, and non-empty content."""
    if allowed_extensions is None:
        allowed_extensions = {".docx", ".pdf", ".txt"}

    if not filename or not filename.strip():
        raise ContractParserError("Filename cannot be empty.")

    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        allowed_list = ", ".join(ext.upper().replace(".", "") for ext in sorted(allowed_extensions))
        raise ContractParserError(
            f"Unsupported file type '{ext}'. Please upload a valid document in {allowed_list} format."
        )

    if not content or len(content) == 0:
        raise ContractParserError("The uploaded file is empty (0 bytes). Please upload a valid document.")

    max_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ContractParserError(
            f"The document exceeds the maximum allowable size of {max_size_mb} MB. "
            f"Current file size: {len(content) / (1024 * 1024):.1f} MB."
        )

    return ext


def normalize_text(text: str) -> str:
    """Normalizes whitespace and common typographical quotes/dashes."""
    if not text:
        return ""
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "--")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def parse_docx(content: bytes, filename: str = "contract.docx") -> ParsedDocument:
    """
    Dedicated DOCX contract parser.
    Extracts paragraphs in order, detects headings, normalizes text,
    and retains references to exact document locations.
    Independent of Gemini.
    """
    try:
        doc = Document(BytesIO(content))
    except Exception as exc:
        raise ContractParserError(
            f"Failed to read '{filename}'. The file appears corrupted or is not a valid Microsoft Word (.docx) document."
        ) from exc

    parsed_paragraphs: list[ParsedParagraph] = []
    headings: list[str] = []
    current_section = "Preamble"

    para_index = 0
    for p in doc.paragraphs:
        raw_text = normalize_text(p.text)
        if not raw_text:
            continue

        style_name = (p.style.name if p.style else "").lower()
        is_heading = False
        heading_level = 0

        # Check style
        if "heading" in style_name:
            is_heading = True
            m = re.search(r"\d+", style_name)
            heading_level = int(m.group(0)) if m else 1
        elif "title" in style_name:
            is_heading = True
            heading_level = 1
        elif len(raw_text) < 90 and (
            p.runs and any(r.bold for r in p.runs) or raw_text.isupper() or re.match(r"^(section|article|clause|\d+[\.\)])\s+", raw_text, re.IGNORECASE)
        ):
            # Heuristic for bold or numbered headings
            is_heading = True
            heading_level = 2

        if is_heading:
            current_section = raw_text
            headings.append(raw_text)

        location = f"{current_section} (Para {para_index + 1})"

        parsed_paragraphs.append(
            ParsedParagraph(
                index=para_index,
                text=raw_text,
                is_heading=is_heading,
                heading_level=heading_level,
                location=location,
            )
        )
        para_index += 1

    # Extract tables
    for table_idx, table in enumerate(doc.tables):
        for row_idx, row in enumerate(table.rows):
            cells_text = [normalize_text(cell.text) for cell in row.cells if normalize_text(cell.text)]
            if cells_text:
                row_str = " | ".join(cells_text)
                parsed_paragraphs.append(
                    ParsedParagraph(
                        index=para_index,
                        text=row_str,
                        is_heading=False,
                        heading_level=0,
                        location=f"Table {table_idx + 1}, Row {row_idx + 1}",
                    )
                )
                para_index += 1

    if not parsed_paragraphs:
        raise ContractParserError("The uploaded DOCX document contains no readable text or paragraphs.")

    full_text = "\n\n".join(p.text for p in parsed_paragraphs)
    return ParsedDocument(
        filename=filename,
        paragraphs=parsed_paragraphs,
        full_text=full_text,
        headings=headings,
        metadata={"total_paragraphs": len(parsed_paragraphs), "total_headings": len(headings)},
    )
