from io import BytesIO

import pytest
from docx import Document

from app.agents.contract_agent import ContractAgent
from app.services.document_extraction import (
    DocumentExtractionError,
    extract_clauses,
    extract_document_text,
)


def make_text_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(output)


def make_docx(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def test_extracts_text_from_pdf_and_docx():
    pdf = extract_document_text("agreement.pdf", make_text_pdf("Vendor liability shall be unlimited."))
    docx = extract_document_text("agreement.docx", make_docx("Payment is due within thirty days."))
    assert "liability" in pdf.lower()
    assert "thirty days" in docx


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("agreement.exe", b"data", "Supported document types"),
        ("empty.txt", b"  ", "empty"),
        ("broken.pdf", b"not a pdf", "Could not extract text"),
    ],
)
def test_rejects_invalid_empty_and_unreadable_documents(filename, content, message):
    with pytest.raises(DocumentExtractionError, match=message):
        extract_document_text(filename, content)


def test_extracts_contract_clauses_from_actual_text():
    text = (
        "LIMITATION OF LIABILITY: Vendor liability shall be unlimited.\n"
        "CONFIDENTIALITY: Each party will protect confidential information for five years."
    )
    clauses = extract_clauses(text, ContractAgent())
    assert [clause["category"] for clause in clauses] == ["Liability", "Confidentiality"]
    assert "unlimited" in clauses[0]["original_text"]
    assert clauses[0]["risk_level"] == "High"
