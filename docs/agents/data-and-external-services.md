# Data and external services guide

Applies to Supabase, PostgreSQL migrations, Gemini, CPC artifacts, imports, embeddings, clustering, production environments, and sensitive data.

Treat invention descriptions, conversations, claims, patent exports, credentials, and private datasets as potentially sensitive.

- Never commit `.env` files, provider keys, database dumps, or private datasets.
- Never expose a Supabase `service_role` key in the frontend or a public environment variable.
- Do not send real user or patent data to Gemini, Supabase, or another provider for testing without explicit authorization.
- Tests must not consume network, quota, or real services unless the user explicitly requests and authorizes that integration test.
- Do not run migrations, seeds, uploads, bulk embedding generation, or clustering against a remote environment without explicit authorization and a confirmed target.
- Before a destructive migration, require prechecks, backup, rehearsal, compatibility planning, and a concrete rollback procedure.
- Do not assume existing migrations are idempotent or reconstruct the complete database schema. The current migration set extends a pre-existing `patentes` table.
- Do not version `backend/data/cpc_index/` or working exports under `backend/exel/`.

Read `ARQUITECTURA_Y_DESPLIEGUE_MVP.md` before changing deployment topology or environment boundaries. Treat `AUDITORIA_CODIGO.md` as dated evidence and validate each relevant claim against the current code and environment.
