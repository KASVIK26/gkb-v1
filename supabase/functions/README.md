# Edge Functions

Empty for now. Kept as a placeholder so the folder exists and Git tracks it.

Per TECH_STACK.md ADR-2, Edge Functions are intentionally **not** the default place for
this project's logic — the public API is FastAPI on Cloud Run (`api/`), so there is one
Python codebase and one set of pydantic models shared with the curator pipeline.

Add a function here only for something that must run inside Supabase itself and doesn't fit
FastAPI, for example:
- a **database webhook** reacting to a table change (e.g. a new `ops.sensor_reading` row
  triggering a lightweight check before the hourly rollup job runs),
- a **Storage** upload hook (e.g. validating a farmer-uploaded photo before it's kept).

To add one later: `supabase functions new <name>`, then `supabase functions deploy <name>`
(needs `supabase login` and `supabase link` to the target project — not done from this
session).
