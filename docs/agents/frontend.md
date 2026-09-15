# Frontend guide

Applies when changing files under `frontend/` or frontend-facing API contracts.

The frontend uses Next.js 16, React 19, TypeScript, Tailwind CSS 4, and npm.

- Preserve the Server Component and Client Component boundary. Add `"use client"` only when browser APIs, state, effects, or client event handlers require it.
- Avoid `any` unless the boundary cannot be typed more precisely and the reason is documented.
- Keep shared API contracts and backend access in `frontend/src/lib/` when appropriate.
- For UI changes, handle loading, empty, error, keyboard, focus, contrast, and responsive states relevant to the affected flow.
- Do not render external HTML without explicit sanitization.
- Never expose secrets through `NEXT_PUBLIC_*` variables.

## Commands

Run from `frontend/`:

```powershell
npm run lint
npm run build
```

There is currently no frontend test script. Do not claim frontend test coverage unless an appropriate test tool was added and executed.

Read `frontend/README.md` before changing runtime configuration, API URLs, or documented routes.
