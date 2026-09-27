# Deployment guide

Three independently-deployable pieces, on three different (all free-tier) platforms:

| Piece | What it is | Platform | Needs |
|---|---|---|---|
| GKB dashboard | `public/` + `functions/` (static site + edge functions) | Cloudflare Pages | Supabase URL + anon key |
| Paper-extraction API | `api/` (FastAPI) | Render | `DATABASE_URL_DIRECT`, an LLM key |
| Review app | `tools/review_app/app.py` (Streamlit) | Streamlit Community Cloud | The API's public URL |

The dashboard is fully independent (talks to Supabase directly). The review app talks to the API
over HTTP, so deploy the API first and feed its URL into the review app's secrets.

None of these steps can be run on your behalf — each platform needs your own account login (an
OAuth browser flow or a dashboard you click through). Everything below is copy-paste commands and
exact settings; if you want a specific command actually run from here (e.g. `wrangler login`, which
just opens your browser), ask and it'll be run in this session.

---

## 0. Push to GitHub first

Render and Streamlit Community Cloud both deploy *from* a GitHub repo — they can't take a local
folder. Cloudflare Pages can do a direct upload (Part 1 uses that path, no GitHub needed for it),
but push anyway so everything stays in one place.

```bash
git push origin master
```

(`.env`, `.dev.vars`, and anything else with real secrets are already gitignored — confirmed
before writing this guide. Nothing sensitive goes to GitHub.)

---

## 1. Cloudflare Pages — the GKB dashboard

Already built for this (`wrangler.toml` exists, `public/` is the whole deploy artifact). Direct
upload, no GitHub connection required.

```bash
npx wrangler login
```

This opens a browser tab — log in with your Cloudflare account (or create a free one) and approve
the CLI. Then:

```bash
npx wrangler pages project create gkb-v1 --production-branch master
npx wrangler pages deploy public --project-name gkb-v1
```

The second command prints the live URL (`https://gkb-v1.pages.dev` or similar) when it finishes.

**Add the Supabase credentials** — the site is up, but `/api/stats` etc. will 503 until it has
them:

1. Cloudflare dashboard → Workers & Pages → **gkb-v1** → Settings → Environment variables.
2. Add for the **Production** environment:
   - `SUPABASE_URL` — same value as in your local `.dev.vars`.
   - `SUPABASE_PUBLISHABLE_KEY` — the **publishable/anon** key, never the secret/service-role key
     (the bridge views this reads are read-only and granted to `anon` specifically so this is safe).
3. Redeploy so the Functions pick the new env vars up:
   ```bash
   npx wrangler pages deploy public --project-name gkb-v1
   ```

**Verify:**
```bash
curl https://gkb-v1.pages.dev/api/stats
```
should return real counts (`{"crops":3,"varieties":...}`), not a 503.

---

## 2. Render — the paper-extraction API

Render's free "Web Service" tier runs a Python app straight from GitHub, no Dockerfile needed. The
free tier spins down after ~15 minutes of inactivity and takes ~30-60s to wake on the next
request — fine for a showcase, mention it if a demo viewer hits a cold start.

1. [render.com](https://render.com) → sign up / log in (GitHub OAuth is the easiest) → **New +** →
   **Web Service**.
2. Connect the `KASVIK26/gkb-v1` repo, branch `master`.
3. Configure:
   | Field | Value |
   |---|---|
   | Name | `gkb-paper-extraction-api` (or anything) |
   | Runtime | Python 3 |
   | Build Command | `pip install -e ".[api]"` |
   | Start Command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
   | Instance Type | Free |
4. Under **Environment**, add:
   - `DATABASE_URL_DIRECT` — the same value from your local `.env` (the direct/session-pooler
     Postgres connection string this project already uses for staging reads/writes).
   - `GEMINI_API_KEY` — your Gemini key (the default provider as of this session).
   - `OPEN_ROUTER_API_KEY` / `GROQ_API_KEY` — optional, only needed if you want those providers
     selectable in the deployed review app too.
   - `API_CORS_ORIGINS` — leave as `http://localhost:8501,http://127.0.0.1:8501,http://localhost:8788`
     for now; you'll add the real Streamlit Cloud origin in Part 4 once it exists.
5. **Create Web Service.** Render builds and deploys; watch the log for
   `Uvicorn running on http://0.0.0.0:$PORT`. Note the public URL it assigns
   (`https://gkb-paper-extraction-api.onrender.com`).

**Verify:**
```bash
curl https://gkb-paper-extraction-api.onrender.com/health
```
should return `{"status":"ok"}` (allow the ~30-60s cold-start delay on the first hit).

**Supabase network access**: if your Supabase project has "Network Restrictions" enabled (Settings
→ Database → Network Restrictions), either disable it for this demo or add `0.0.0.0/0` — Render's
outbound IPs aren't static on the free tier, so there's no fixed IP to allowlist instead.

---

## 3. Streamlit Community Cloud — the review app

Already prepared: `tools/review_app/requirements.txt` installs this repo editable with the
`review` extra (pulls in `curator`'s own dependencies too, so the Export tab's
`python -m curator.cli lit export-staged` subprocess call works). `app.py` already bridges
Streamlit's secrets manager into `os.environ` on startup.

1. [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → **Create app**.
2. Point it at `KASVIK26/gkb-v1`, branch `master`, main file path `tools/review_app/app.py`.
3. Before or right after deploying, open **Settings → Secrets** and paste:
   ```toml
   API_BASE_URL = "https://gkb-paper-extraction-api.onrender.com"
   DATABASE_URL_DIRECT = "postgresql://...."
   ```
   (`API_BASE_URL` is Part 2's Render URL. `DATABASE_URL_DIRECT` is the same value as Part 2's —
   only needed for the Export tab, which shells out to the CLI directly rather than going through
   the API.)
4. Deploy. Streamlit Cloud installs `requirements.txt` and starts the app; it prints a URL like
   `https://gkb-v1-review.streamlit.app`.

---

## 4. Connect them: fix CORS

The review app's browser-side JS (well, Streamlit's own frontend) calls the Render API directly
from the Streamlit Cloud origin — the API's CORS allowlist needs to include it, or the browser
blocks the request even though the API itself would happily respond.

1. Copy the Streamlit app's exact URL from Part 3 (`https://gkb-v1-review.streamlit.app`).
2. Render dashboard → your API service → Environment → edit `API_CORS_ORIGINS`:
   ```
   http://localhost:8501,http://127.0.0.1:8501,http://localhost:8788,https://gkb-v1-review.streamlit.app
   ```
3. Save — Render auto-redeploys on an environment variable change.

**Final end-to-end check**: open the Streamlit app URL, type a real PMID (e.g. `34897256`), pick a
crop and provider, click **Extract**. If it fetches, extracts, and shows accepted/rejected
candidates, all three pieces are correctly wired together.

---

## Known limitations of this setup (showcase-grade, not production)

- **No auth** on either the API or the review app — anyone with the URL can use them. Fine for a
  demo; put both behind Cloudflare Access (or equivalent) before sharing more broadly.
- **Render free tier cold-starts** (~30-60s) after ~15 min idle.
- **`DATABASE_URL_DIRECT` is a real production database credential** sitting in two different
  platforms' secret stores now (Render + Streamlit Cloud) — fine for your own demo, but rotate it
  if either account is ever shared or compromised.
