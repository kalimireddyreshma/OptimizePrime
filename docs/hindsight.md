# Hindsight Cloud integration

## Memory system

The backend uses the existing `hindsight-client` SDK to connect directly to Hindsight Cloud. Hindsight is the only organizational memory system; the application does not replace it with in-memory, file, JSON, SQLite, or another vector-store implementation.

Credentials remain backend-only. The API does not return the Hindsight API key to the React application. Configure the existing Cloud endpoint, API key, and bank ID in the backend environment; never commit the private `.env` file.

## Memory lifecycle

- **RECALL:** clause review queries the configured Hindsight bank before producing a recommendation. Actual returned memory text is exposed as evidence; absent or failed recall is not represented as precedent.
- **RETAIN:** an accepted or modified recommendation, or a rejection with a meaningful reason, is submitted to Hindsight after the human decision is saved. A rejection with no meaningful reason is recorded in the application audit history but is not retained as a preference.
- **REFLECT:** the Memory surface and explicit reflect endpoint display only actual Hindsight Cloud responses. An empty response is shown as unavailable/empty, never as a canned summary.

Application decision and event history are stored in the existing SQL database to support auditability. Those records are presented separately from actual Hindsight memories and reflections; application history is not a substitute memory service.

## Health states

The backend checks the same Cloud client used for memory operations and reports `CONNECTED`, `NO_MEMORIES`, `UNAVAILABLE`, `AUTH_ERROR`, or `REQUEST_FAILED`. The API reports only a status, message, and bank identifier; it never includes credentials.

## Limits

Clause extraction and risk classification are deterministic. Gemini is not configured, and the application does not claim that a recommendation came from an LLM. Recommendations require human review and approval.
