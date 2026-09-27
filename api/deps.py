"""FastAPI dependencies: a Postgres connection per request.

Reuses exactly the credential the Python pipeline already uses locally (DATABASE_URL_DIRECT from
.env) -- no new secret to configure for local development. In the target Cloud Run deployment
(TECH_STACK.md Sec 4/6) this comes from Secret Manager instead, but the dependency contract here
doesn't change either way.

The LLM client is NOT a fixed dependency here -- api/routers/lit.py builds one per-request from
the caller's own `provider` choice (openrouter | gemini | groq), since that choice is a request
body field, not something fixed at app startup.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg


def get_db() -> Iterator[psycopg.Connection]:
    dsn = os.environ.get("DATABASE_URL_DIRECT")
    if not dsn:
        raise RuntimeError("DATABASE_URL_DIRECT is not set -- see .env.example")
    with psycopg.connect(dsn, autocommit=True) as conn:
        yield conn
