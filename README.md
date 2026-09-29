# ContractMind AI

> Learn once. Negotiate consistently.

ContractMind AI is a legal-tech workspace for reviewing contract clauses with organizational memory. Instead of asking only, "what does this clause mean?" it asks, "what has our organization historically chosen for clauses like this?"

## Why Hindsight

The application is built around the official Hindsight pattern: persistent, durable lessons written as memory, retrieved when relevant, and used to form organizational preference over time. The project intentionally does not fake memory with in-code dictionaries or JSON-based mock state. When an actual persistent Hindsight memory system is present, the app uses it. If it is not present in the current environment, the backend surfaces a clear developer-facing warning instead of silently replacing it.

## Architecture

- Frontend: React + Vite + TypeScript + Tailwind-like CSS
- Backend: FastAPI + SQLAlchemy + Pydantic
- Database: SQLite for the hackathon MVP
- Document extraction: PDF, DOCX, and TXT text extraction
- Analysis: deterministic clause classification and risk analysis, with recommendations informed by real recalled organizational decisions when available
- Memory: the existing Hindsight Cloud client is the only organizational memory store

## Demo story

The product is designed around a single learning loop:

1. Teach the agent with a liability clause decision.
2. Reinforce the same preference across multiple vendor contracts.
3. Test on a new contract that mirrors the earlier pattern.
4. Recall the memory, recommend a consistent position, and log the human decision.
5. Retain the new decision and reflect on the updated pattern.

## Installation

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Running

### Backend

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## Environment variables

```bash
cp .env.example .env
```

Example values:

```env
DATABASE_URL=sqlite:///./contractmind.db
```

Hindsight Cloud configuration remains backend-only in the existing local environment. Do not expose its credentials to the frontend or commit `.env`.

## Project structure

```text
contractmind-ai/
├── backend/
│   ├── app/
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
├── docs/
├── content/
├── data/
├── README.md
├── .gitignore
├── .env.example
└── LICENSE
```

## Security and product quality

- API keys live in environment files only.
- No secrets are exposed to the frontend.
- Uploaded PDF, DOCX, and TXT documents are size-validated and text-extracted server-side.
- The human must approve recommendations before they become contract final terms.
- The app warns clearly when memory is not available instead of pretending it has learned.

## Limitations

This is a hackathon-grade MVP with sample demo contracts and a working contract-review loop. Uploaded PDF, DOCX, and TXT documents are text-extracted and reviewed with deterministic clause/risk rules and Hindsight evidence when available. Gemini generation is not currently configured. ContractMind AI provides AI-assisted contract analysis and drafting suggestions for review purposes only. It is not legal advice and does not replace review by a qualified legal professional.

## Future improvements

- Better clause boundary detection and clause comparison for complex contract layouts.
- Optional backend-only Gemini-assisted review (not required; current recommendations remain deterministic and memory-informed).
- Multi-user workspaces and multi-tenant preference memory.
- Postgres migration path from the current SQLite schema.

## Hindsight documentation

See [docs/hindsight.md](docs/hindsight.md) for details on how the memory lifecycle is modeled and how the app distinguishes general legal knowledge from organizational preference.
