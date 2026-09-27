# AgriHub KB demo dashboard

A small Cloudflare Pages site (`public/` + `functions/api/*.js`) for interactively exercising the
live Supabase knowledge graph. Rebuilt 2026-09-26 against Postgres/Supabase; the original version
(same file names) queried Neo4j and stopped working when that database was deleted.

**This is a demo query layer, not the real risk-engine API.** RESEARCH_ROADMAP.md Phase 11 (the
actual "variety + IoT feed → risk + confidence + treatment" API) hasn't been built yet — see the
scope note in `functions/api/triggers.js` for exactly what's simplified here and why.

## What it does

Two tabs:

- **Browse the graph** — pick a crop and variety, see its documented `VARIETY_REACTION` claims,
  and browse all `GENE_CONFERS_RESISTANCE` claims for that crop. (Gene claims are shown crop-wide,
  not filtered to the selected variety — the KG has no `VARIETY_CARRIES_GENE` claims loaded yet,
  so there's nothing real to filter on.)
- **Check sensor readings** — pick a crop, optionally a variety, type in some sensor values (air
  temp, RH, soil temp, soil moisture, dew point, RH-hours), and see which `DISEASE_ENV_TRIGGER`
  claims' conditions are met, not met, or can't be evaluated (missing reading) — with the matching
  disease's `DISEASE_MANAGED_BY` advisory and the selected variety's own documented reaction, if
  known.

Everything shown is read live from Supabase via `public.kg_*` bridge views
(`supabase/migrations/20260926120000_dashboard_views.sql`), which sit on top of `kg_current` — the
schema `curator/graph/promote.py` atomically repoints at whichever release is live. No caching, no
mock data.

## Running it locally

```bash
# one-time: put the Supabase URL + publishable (anon) key in .dev.vars (gitignored)
printf 'SUPABASE_URL=...\nSUPABASE_PUBLISHABLE_KEY=...\n' > .dev.vars

npx wrangler pages dev public --port 8788
```

Then open http://localhost:8788. `wrangler pages dev` auto-detects `functions/` next to the
`public/` output directory — no separate server process needed.

Only the **publishable/anon** key belongs here — never the secret/service-role key. The bridge
views are read-only and granted to Supabase's `anon` role specifically so this is safe to expose
client-side.

## Deploying (Cloudflare Pages)

```bash
npx wrangler login                     # one-time, opens a browser OAuth flow
npx wrangler pages project create gkb-v1 --production-branch master
npx wrangler pages deploy public --project-name gkb-v1
```

Then, in the Cloudflare dashboard (Workers & Pages → gkb-v1 → Settings → Environment variables),
add `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` for the **Production** environment (same
publishable/anon values as `.dev.vars`, never the secret/service-role key) and redeploy
(`npx wrangler pages deploy public --project-name gkb-v1` again) so the Functions pick them up.

See the repo root's deployment guide for the full picture, including the two Python services this
dashboard doesn't depend on.

## Known simplifications (deliberate, not bugs)

- **Single-snapshot trigger checks, not windowed aggregation.** Each `EnvTrigger` condition
  describes a value aggregated over a time window (e.g. "mean over 24h"); this form compares the
  raw number you type directly against the same bounds. Good enough to see real trigger/advisory
  data fire; not a substitute for actually aggregating a sensor feed.
- **Gene resistance isn't variety-filtered.** See above — there's no data yet to filter on.
- **Only 6 of 17 diseases have a trigger, and 6 of 17 have an advisory** (PHASES.md tracks the
  rest) — most of the remaining diseases are blocked on paywalled papers or genuinely-thin
  literature, not something this dashboard can work around.
