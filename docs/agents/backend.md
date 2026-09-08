# Backend guide

Applies when changing files under `backend/` or backend contracts consumed elsewhere.

## Structure

- `backend/app/routes/`: HTTP endpoints and HTTP error translation.
- `backend/app/models/`: Pydantic request and response contracts.
- `backend/app/services/`: domain logic, data access, embeddings, and provider clients.
- `backend/tests/`: unit and integration tests using fake clients.
- `backend/exel/`: historical name for offline import, embedding, and clustering jobs; do not rename it incidentally.

Keep routes thin: validate and translate HTTP at the route boundary, and place reusable logic in services. Define bounded inputs and outputs with Pydantic models. Return stable public errors rather than provider messages, local paths, stack traces, or secrets.

Do not replace test fakes with real Supabase or Gemini calls. Avoid introducing blocking, compute-heavy work into asynchronous request paths without explicit isolation or justification.

## Commands

Run backend commands from `backend/` because environment loading depends on the working directory:

```powershell
python -m pytest
python -m ruff check app exel tests
```

For a localized change, run directly affected tests first and the full suite before delivery when viable. Report any command that could not be run; do not imply it passed.

Read `backend/CPC_CLASSIFICATION.md` before changing CPC indexing, retrieval, manifest validation, or recommendation behavior.
